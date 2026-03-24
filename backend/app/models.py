from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agents = relationship("Agent", back_populates="domain", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    md_filename = Column(String(255), nullable=True)   # original uploaded filename
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    domain = relationship("Domain", back_populates="agents")


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)          # openai | gemini | claude | ollama | custom
    label = Column(String(100), nullable=False)            # display name
    base_url = Column(String(500), nullable=True)
    api_key = Column(Text, nullable=True)                  # store encrypted in prod
    model_name = Column(String(100), nullable=True)
    temperature = Column(Float, nullable=True, default=0.7)
    top_k = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=False)             # only one active at a time
    created_at = Column(DateTime(timezone=True), server_default=func.now())
