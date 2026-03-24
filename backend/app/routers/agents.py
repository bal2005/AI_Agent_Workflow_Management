from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app import models, schemas
from app.database import get_db

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
    md_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if db.query(models.Agent).filter(models.Agent.name == name.strip()).first():
        raise HTTPException(status_code=409, detail="Agent name already exists")
    if not db.query(models.Domain).filter(models.Domain.id == domain_id).first():
        raise HTTPException(status_code=404, detail="Domain not found")

    md_filename = None
    final_prompt = system_prompt or ""

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
def run_playground(payload: schemas.PlaygroundRequest, db: Session = Depends(get_db)):
    # Resolve which config to use
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

    if config.provider == "ollama":
        return _run_ollama(config, payload.system_prompt, payload.user_prompt)

    if config.provider == "claude":
        return _run_claude(config, payload.system_prompt, payload.user_prompt)

    # openai / gemini (openai-compat) / custom — all use the OpenAI chat completions format
    return _run_openai_compat(config, payload.system_prompt, payload.user_prompt)


# ── OpenAI-compatible (OpenAI, Groq, Together, custom, Gemini OpenAI-compat) ──

def _run_openai_compat(config: models.LLMConfig, system_prompt: str, user_prompt: str) -> dict:
    import httpx

    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    model = config.model_name or "gpt-4o"
    api_key = config.api_key or ""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    if config.top_p is not None:
        body["top_p"] = config.top_p
    if config.max_tokens is not None:
        body["max_tokens"] = config.max_tokens

    try:
        resp = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"result": data["choices"][0]["message"]["content"]}
    except httpx.ConnectError:
        return {"result": f"[Connection error] Could not reach {base_url}"}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        return {"result": f"[API error {e.response.status_code}] {detail}"}
    except Exception as e:
        return {"result": f"[Error] {str(e)}"}


# ── Ollama (/api/chat) ──

def _run_ollama(config: models.LLMConfig, system_prompt: str, user_prompt: str) -> dict:
    import httpx

    base_url = (config.base_url or "http://localhost:11434").rstrip("/")
    model = config.model_name or "llama3"

    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {},
    }
    if config.temperature is not None:
        body["options"]["temperature"] = config.temperature
    if config.top_k is not None:
        body["options"]["top_k"] = config.top_k
    if config.top_p is not None:
        body["options"]["top_p"] = config.top_p
    if config.max_tokens is not None:
        body["options"]["num_predict"] = config.max_tokens

    try:
        resp = httpx.post(f"{base_url}/api/chat", json=body, timeout=60)
        resp.raise_for_status()
        return {"result": resp.json()["message"]["content"]}
    except httpx.ConnectError:
        return {"result": f"[Ollama] Could not connect to {base_url}. Is Ollama running?"}
    except httpx.HTTPStatusError as e:
        return {"result": f"[Ollama error {e.response.status_code}] {e.response.text}"}
    except Exception as e:
        return {"result": f"[Ollama error] {str(e)}"}


# ── Anthropic Claude ──

def _run_claude(config: models.LLMConfig, system_prompt: str, user_prompt: str) -> dict:
    import httpx

    base_url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/")
    model = config.model_name or "claude-3-opus-20240229"
    api_key = config.api_key or ""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    body: dict = {
        "model": model,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": config.max_tokens or 1024,
    }
    if config.temperature is not None:
        body["temperature"] = config.temperature
    if config.top_k is not None:
        body["top_k"] = config.top_k
    if config.top_p is not None:
        body["top_p"] = config.top_p

    try:
        resp = httpx.post(f"{base_url}/messages", headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return {"result": resp.json()["content"][0]["text"]}
    except httpx.ConnectError:
        return {"result": f"[Claude] Could not connect to {base_url}"}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = e.response.text
        return {"result": f"[Claude error {e.response.status_code}] {detail}"}
    except Exception as e:
        return {"result": f"[Claude error] {str(e)}"}
