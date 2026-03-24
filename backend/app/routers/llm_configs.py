from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db
from app.crypto import encrypt, decrypt

router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])


def _decrypt_config(config: models.LLMConfig) -> models.LLMConfig:
    """Decrypt api_key in-place before serialising to response."""
    if config.api_key:
        config.api_key = decrypt(config.api_key)
    return config


@router.get("/", response_model=list[schemas.LLMConfigOut])
def list_configs(db: Session = Depends(get_db)):
    configs = db.query(models.LLMConfig).order_by(models.LLMConfig.id).all()
    return [_decrypt_config(c) for c in configs]


@router.post("/", response_model=schemas.LLMConfigOut, status_code=201)
def create_config(payload: schemas.LLMConfigCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    if data.get("api_key"):
        data["api_key"] = encrypt(data["api_key"])
    config = models.LLMConfig(**data)
    db.add(config)
    db.commit()
    db.refresh(config)
    return _decrypt_config(config)


@router.patch("/{config_id}", response_model=schemas.LLMConfigOut)
def update_config(config_id: int, payload: schemas.LLMConfigCreate, db: Session = Depends(get_db)):
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    data = payload.model_dump(exclude_unset=True)
    if "api_key" in data and data["api_key"]:
        data["api_key"] = encrypt(data["api_key"])
    for k, v in data.items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return _decrypt_config(config)


@router.post("/{config_id}/activate", response_model=schemas.LLMConfigOut)
def activate_config(config_id: int, db: Session = Depends(get_db)):
    db.query(models.LLMConfig).update({"is_active": False})
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    config.is_active = True
    db.commit()
    db.refresh(config)
    return _decrypt_config(config)


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
