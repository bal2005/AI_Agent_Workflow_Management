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
    system_prompt: str   # the agent's skill/instructions
    user_prompt: str
    llm_config_id: Optional[int] = None

class PlaygroundResponse(BaseModel):
    result: str
    engine: str = "direct"  # "copilot-sdk" | "direct" | "none"

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


# ── Tools Management schemas ──────────────────────────────────────────────────

class ToolPermissionOut(BaseModel):
    id: int
    key: str
    label: str
    model_config = {"from_attributes": True}


class ToolOut(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    risk_level: Optional[str] = "low"
    metadata_: Optional[dict] = None
    permissions: list[ToolPermissionOut] = []
    model_config = {"from_attributes": True}


class AgentToolAccessOut(BaseModel):
    id: int
    agent_id: int
    tool_id: int
    tool_key: str                        # convenience — avoids extra join on frontend
    granted_permissions: list[str] = []
    config: Optional[dict] = None
    model_config = {"from_attributes": True}


class AgentToolAccessUpsert(BaseModel):
    """Payload for saving/updating tool access for one agent."""
    # List of (tool_key, [permission_keys], config_dict) entries
    tool_key: str
    granted_permissions: list[str] = []
    config: Optional[dict] = None


class AgentToolAccessBulkSave(BaseModel):
    """Save all tool permissions for an agent in one call."""
    entries: list[AgentToolAccessUpsert]
