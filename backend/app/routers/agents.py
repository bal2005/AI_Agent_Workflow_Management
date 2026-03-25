from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app import models, schemas
from app.database import get_db
from app.crypto import decrypt
from app.copilot_runner import run_via_copilot_sdk

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return (
        db.query(models.Agent)
        .options(joinedload(models.Agent.domain))
        .order_by(models.Agent.name)
        .all()
    )


@router.get("/check-name")
def check_agent_name(name: str, db: Session = Depends(get_db)):
    exists = db.query(models.Agent).filter(models.Agent.name == name).first()
    return {"exists": exists is not None}


@router.post("/", response_model=schemas.AgentOut, status_code=201)
async def create_agent(
    name: str = Form(...),
    domain_id: int = Form(...),
    system_prompt: Optional[str] = Form(None),
    skill: Optional[str] = Form(None),  # frontend sends "skill", alias for system_prompt
    md_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if db.query(models.Agent).filter(models.Agent.name == name.strip()).first():
        raise HTTPException(status_code=409, detail="Agent name already exists")
    if not db.query(models.Domain).filter(models.Domain.id == domain_id).first():
        raise HTTPException(status_code=404, detail="Domain not found")

    md_filename = None
    final_prompt = system_prompt or skill or ""

    if md_file:
        if not md_file.filename.endswith(".md"):
            raise HTTPException(status_code=400, detail="Only .md files are accepted")
        content = await md_file.read()
        try:
            final_prompt = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Could not decode .md file as UTF-8")
        md_filename = md_file.filename

    if not final_prompt.strip():
        raise HTTPException(status_code=422, detail="System prompt is required (text or .md file)")

    agent = models.Agent(
        name=name.strip(),
        system_prompt=final_prompt.strip(),
        md_filename=md_filename,
        domain_id=domain_id,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return (
        db.query(models.Agent)
        .options(joinedload(models.Agent.domain))
        .filter(models.Agent.id == agent.id)
        .first()
    )


@router.post("/playground")
async def run_playground(payload: schemas.PlaygroundRequest, db: Session = Depends(get_db)):
    config = None
    if payload.llm_config_id:
        config = db.query(models.LLMConfig).filter(models.LLMConfig.id == payload.llm_config_id).first()
    else:
        config = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()

    if not config:
        return {
            "result": (
                "[No LLM configured]\n\n"
                "→ Go to LLM Config, create a config, and click 'Set Active'."
            )
        }

    result = await run_via_copilot_sdk(config, payload.system_prompt, payload.user_prompt, allow_tools=False)
    return {"result": result}
