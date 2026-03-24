from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/llm-configs", tags=["llm-configs"])


@router.get("/", response_model=list[schemas.LLMConfigOut])
def list_configs(db: Session = Depends(get_db)):
    return db.query(models.LLMConfig).order_by(models.LLMConfig.id).all()


@router.post("/", response_model=schemas.LLMConfigOut, status_code=201)
def create_config(payload: schemas.LLMConfigCreate, db: Session = Depends(get_db)):
    config = models.LLMConfig(**payload.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.patch("/{config_id}", response_model=schemas.LLMConfigOut)
def update_config(config_id: int, payload: schemas.LLMConfigCreate, db: Session = Depends(get_db)):
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/activate", response_model=schemas.LLMConfigOut)
def activate_config(config_id: int, db: Session = Depends(get_db)):
    # Deactivate all, then activate the chosen one
    db.query(models.LLMConfig).update({"is_active": False})
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    config.is_active = True
    db.commit()
    db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    config = db.query(models.LLMConfig).filter(models.LLMConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()
