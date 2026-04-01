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
    skill: Optional[str] = Form(None),
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


@router.patch("/{agent_id}", response_model=schemas.AgentOut)
def update_agent(agent_id: int, payload: schemas.AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Agent name cannot be empty")
        conflict = db.query(models.Agent).filter(
            models.Agent.name == name, models.Agent.id != agent_id
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Agent name already exists")
        agent.name = name
    if payload.system_prompt is not None:
        if not payload.system_prompt.strip():
            raise HTTPException(status_code=422, detail="System prompt cannot be empty")
        agent.system_prompt = payload.system_prompt.strip()
    if payload.domain_id is not None:
        if not db.query(models.Domain).filter(models.Domain.id == payload.domain_id).first():
            raise HTTPException(status_code=404, detail="Domain not found")
        agent.domain_id = payload.domain_id
    db.commit()
    db.refresh(agent)
    return (
        db.query(models.Agent)
        .options(joinedload(models.Agent.domain))
        .filter(models.Agent.id == agent_id)
        .first()
    )


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()


@router.post("/playground")
async def run_playground(payload: schemas.PlaygroundRequest, db: Session = Depends(get_db)):
    from app.prompt_utils import compose_agent_prompt
    from app.web_tools import build_web_tools
    from app.routers.task_playground import _run_agent_loop
    from pathlib import Path
    import tempfile

    print(f"[PLAYGROUND] domain_prompt received: {repr(payload.domain_prompt)}", flush=True)
    print(f"[PLAYGROUND] system_prompt received: {repr(payload.system_prompt[:80] if payload.system_prompt else None)}", flush=True)

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

    system, user_msg = compose_agent_prompt(
        payload.domain_prompt,
        payload.system_prompt,
        payload.user_prompt,
    )
    web_permissions = payload.web_permissions or {}
    print(f"[PLAYGROUND] web_permissions received: {web_permissions}", flush=True)
    web_tools = build_web_tools(web_permissions)
    if web_tools:
        result, _steps = await _run_agent_loop(
            config,
            system,
            user_msg,
            Path(tempfile.gettempdir()),
            web_tools,
        )
        return {"result": result}

    result = await run_via_copilot_sdk(config, system, user_msg, allow_tools=False)
    return {"result": result}
