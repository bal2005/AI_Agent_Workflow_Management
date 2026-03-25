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


# ── Task schemas ──────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    name: str
    description: str
    agent_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_system_behavior: Optional[str] = None
    tool_usage_mode: Optional[str] = "allowed"
    workflow: Optional[str] = None
    folder_path: Optional[str] = None
    status: Optional[str] = "draft"


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    agent_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_system_behavior: Optional[str] = None
    tool_usage_mode: Optional[str] = None
    workflow: Optional[str] = None
    folder_path: Optional[str] = None
    status: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    name: str
    description: str
    agent_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_system_behavior: Optional[str] = None
    tool_usage_mode: Optional[str] = None
    workflow: Optional[str] = None
    folder_path: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    agent: Optional[AgentOut] = None
    model_config = {"from_attributes": True}


class TaskDryRunRequest(BaseModel):
    task_id: Optional[int] = None   # if saved already
    # inline fields for unsaved dry run
    description: str
    agent_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_top_p: Optional[float] = None
    llm_system_behavior: Optional[str] = None
    tool_usage_mode: Optional[str] = "allowed"
    workflow: Optional[str] = None
    folder_path: Optional[str] = None


class TaskDryRunResponse(BaseModel):
    result: str
    steps: list[str] = []
    engine: str = "copilot-sdk"


# ── Scheduler schemas ─────────────────────────────────────────────────────────

class ScheduleTaskItem(BaseModel):
    task_id: int
    position: int = 0
    model_config = {"from_attributes": True}


class ScheduleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_type: str = "manual"          # manual | interval | cron
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None   # minutes | hours | days
    cron_expression: Optional[str] = None
    is_active: bool = True
    task_ids: list[ScheduleTaskItem] = []


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    task_ids: Optional[list[ScheduleTaskItem]] = None

    model_config = {"from_attributes": True}


class ScheduleTaskOut(BaseModel):
    id: int
    task_id: int
    position: int
    task: Optional["TaskOut"] = None
    model_config = {"from_attributes": True}


class ScheduleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    trigger_type: str
    interval_value: Optional[int] = None
    interval_unit: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: bool
    next_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    schedule_tasks: list[ScheduleTaskOut] = []
    model_config = {"from_attributes": True}


class ScheduleTaskRunOut(BaseModel):
    id: int
    task_id: int
    position: int
    status: str
    output: Optional[str] = None
    logs: list[str] = []
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    task: Optional["TaskOut"] = None
    model_config = {"from_attributes": True}


class ScheduleRunOut(BaseModel):
    id: int
    schedule_id: int
    status: str
    triggered_by: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime
    task_runs: list[ScheduleTaskRunOut] = []
    model_config = {"from_attributes": True}
