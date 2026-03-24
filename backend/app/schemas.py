from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

# Domain schemas
class DomainCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Domain name cannot be empty")
        return v.strip()

class DomainOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    model_config = {"from_attributes": True}

# Agent schemas
class AgentOut(BaseModel):
    id: int
    name: str
    system_prompt: str
    md_filename: Optional[str] = None
    domain_id: int
    domain: DomainOut
    created_at: datetime
    model_config = {"from_attributes": True}

# Playground schema
class PlaygroundRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    llm_config_id: Optional[int] = None

# LLM Config schemas
class LLMConfigCreate(BaseModel):
    provider: str
    label: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = 0.7
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

class LLMConfigOut(BaseModel):
    id: int
    provider: str
    label: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    top_k: Optional[int] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
