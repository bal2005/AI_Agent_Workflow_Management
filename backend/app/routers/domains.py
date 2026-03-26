from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, schemas
from app.database import get_db

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("/", response_model=list[schemas.DomainOut])
def list_domains(db: Session = Depends(get_db)):
    return db.query(models.Domain).order_by(models.Domain.name).all()


@router.post("/", response_model=schemas.DomainOut, status_code=201)
def create_domain(payload: schemas.DomainCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Domain).filter(models.Domain.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Domain already exists")
    domain = models.Domain(
        name=payload.name,
        domain_prompt=payload.domain_prompt.strip() if payload.domain_prompt else None,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.patch("/{domain_id}", response_model=schemas.DomainOut)
def update_domain(domain_id: int, payload: schemas.DomainUpdate, db: Session = Depends(get_db)):
    domain = db.query(models.Domain).filter(models.Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    if payload.name is not None:
        payload.name = payload.name.strip()
        if not payload.name:
            raise HTTPException(status_code=422, detail="Domain name cannot be empty")
        domain.name = payload.name
    if payload.domain_prompt is not None:
        domain.domain_prompt = payload.domain_prompt.strip() or None
    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=204)
def delete_domain(domain_id: int, db: Session = Depends(get_db)):
    domain = db.query(models.Domain).filter(models.Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    db.delete(domain)
    db.commit()
