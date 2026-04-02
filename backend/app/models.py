from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    domain_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agents = relationship("Agent", back_populates="domain", cascade="all, delete-orphan")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    system_prompt = Column(Text, nullable=False)
    md_filename = Column(String(255), nullable=True)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    domain = relationship("Domain", back_populates="agents")
    tool_access = relationship("AgentToolAccess", back_populates="agent", cascade="all, delete-orphan")


class LLMConfig(Base):
    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False)
    label = Column(String(100), nullable=False)
    base_url = Column(String(500), nullable=True)
    api_key = Column(Text, nullable=True)
    model_name = Column(String(100), nullable=True)
    temperature = Column(Float, nullable=True, default=0.7)
    top_k = Column(Integer, nullable=True)
    top_p = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Tools Management ──────────────────────────────────────────────────────────

class Tool(Base):
    """
    Defines an available tool and its specification.
    Seeded once; rarely changes at runtime.
    """
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    # Stable machine key, e.g. "filesystem", "shell", "web_search"
    key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    # "low" | "medium" | "high" — drives warning badges in the UI
    risk_level = Column(String(20), nullable=True, default="low")
    # Flexible JSON blob: supported_shells, config_schema, etc.
    metadata_ = Column("metadata", JSON, nullable=True, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    permissions = relationship("ToolPermission", back_populates="tool", cascade="all, delete-orphan")
    agent_access = relationship("AgentToolAccess", back_populates="tool", cascade="all, delete-orphan")


class ToolPermission(Base):
    """
    Enumerates the individual permission flags a tool exposes.
    e.g. filesystem → read_files, write_files, browse_folders …
    """
    __tablename__ = "tool_permissions"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    # Machine key used in granted_permissions list, e.g. "read_files"
    key = Column(String(100), nullable=False)
    label = Column(String(200), nullable=False)   # Human-readable label for the UI
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tool = relationship("Tool", back_populates="permissions")


class AgentToolAccess(Base):
    """
    Records which tool permissions are granted to a specific agent,
    plus any agent-specific config overrides for that tool.

    granted_permissions: list[str]  — e.g. ["read_files", "browse_folders"]
    config:              dict        — e.g. {"root_path": "/workspace", "readonly_mode": true}
    """
    __tablename__ = "agent_tool_access"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    # List of permission keys granted to this agent for this tool
    granted_permissions = Column(JSON, nullable=False, default=list)
    # Agent-specific config values for this tool
    config = Column(JSON, nullable=True, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent", back_populates="tool_access")
    tool = relationship("Tool", back_populates="agent_access")


class Task(Base):
    """
    A saved task definition: name, description (prompt), agent, LLM config,
    optional workflow steps, folder path, and tool usage mode.
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)           # acts as the task prompt
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    llm_config_id = Column(Integer, ForeignKey("llm_configs.id"), nullable=True)

    # LLM overrides stored per-task
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_temperature = Column(Float, nullable=True)
    llm_max_tokens = Column(Integer, nullable=True)
    llm_top_p = Column(Float, nullable=True)
    llm_system_behavior = Column(Text, nullable=True)    # optional system behavior override
    tool_usage_mode = Column(String(20), nullable=True, default="allowed")  # allowed|restricted|none

    # Optional step-by-step workflow (one step per line)
    workflow = Column(Text, nullable=True)

    # Folder path the task operates on
    folder_path = Column(String(500), nullable=True)

    status = Column(String(20), nullable=False, default="draft")  # draft|active
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    agent = relationship("Agent")
    llm_config = relationship("LLMConfig")


class TaskRun(Base):
    """Standalone execution record for a manually-run task."""
    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    triggered_by = Column(String(20), nullable=False, default="manual")  # manual | scheduler
    status = Column(String(20), nullable=False, default="pending")       # running | success | failed
    output = Column(Text, nullable=True)
    logs = Column(JSON, nullable=True, default=list)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    task = relationship("Task")


# ── Scheduler ─────────────────────────────────────────────────────────────────

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # manual | interval | cron
    trigger_type = Column(String(20), nullable=False, default="manual")
    # interval fields
    interval_value = Column(Integer, nullable=True)
    interval_unit = Column(String(20), nullable=True)   # minutes | hours | days
    # cron field
    cron_expression = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    # Visual workflow graph — { "nodes": [...] } — stored as JSON, managed by the frontend builder
    workflow_json = Column(JSON, nullable=True)
    # Trigger configuration for non-manual triggers
    # For trigger_type="filesystem": {"watch_path":..., "recursive":..., "events":[...], ...}
    trigger_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    schedule_tasks = relationship(
        "ScheduleTask", back_populates="schedule",
        cascade="all, delete-orphan", order_by="ScheduleTask.position"
    )
    runs = relationship("ScheduleRun", back_populates="schedule", cascade="all, delete-orphan")


class ScheduleTask(Base):
    """Ordered list of tasks attached to a schedule."""
    __tablename__ = "schedule_tasks"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    position = Column(Integer, nullable=False, default=0)

    schedule = relationship("Schedule", back_populates="schedule_tasks")
    task = relationship("Task")


class ScheduleRun(Base):
    """One execution of a schedule."""
    __tablename__ = "schedule_runs"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending|running|success|failed
    triggered_by = Column(String(20), nullable=False, default="manual")  # manual|scheduler
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    schedule = relationship("Schedule", back_populates="runs")
    task_runs = relationship("ScheduleTaskRun", back_populates="run", cascade="all, delete-orphan",
                             order_by="ScheduleTaskRun.position")

    @property
    def schedule_name(self) -> str | None:
        return self.schedule.name if self.schedule else None


class ScheduleTaskRun(Base):
    """Result of one task within a schedule run."""
    __tablename__ = "schedule_task_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("schedule_runs.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    position = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")  # pending|running|success|failed|skipped
    output = Column(Text, nullable=True)
    logs = Column(JSON, nullable=True, default=list)   # list of step strings
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)

    run = relationship("ScheduleRun", back_populates="task_runs")
    task = relationship("Task")


class EmailTriggerState(Base):
    """
    Tracks IMAP message UIDs that have already triggered a workflow run.
    One row per (schedule, message) — the unique constraint prevents double-firing.
    """
    __tablename__ = "email_trigger_state"

    id          = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    message_uid = Column(String(200), nullable=False)   # IMAP UID (string)
    sender      = Column(String(500), nullable=True)
    subject     = Column(String(1000), nullable=True)
    seen_at     = Column(DateTime(timezone=True), server_default=func.now())

    schedule = relationship("Schedule")


class TriggerLog(Base):
    """Records every filesystem event detected by the watchdog listener."""
    __tablename__ = "trigger_logs"

    id            = Column(Integer, primary_key=True, index=True)
    schedule_id   = Column(Integer, ForeignKey("schedules.id"), nullable=False)
    event_type    = Column(String(50), nullable=False)   # created|modified|deleted|moved
    file_path     = Column(String(1000), nullable=True)
    matched       = Column(Boolean, nullable=False, default=True)
    debounced     = Column(Boolean, nullable=False, default=False)
    workflow_fired = Column(Boolean, nullable=False, default=False)
    notes         = Column(Text, nullable=True)
    triggered_at  = Column(DateTime(timezone=True), server_default=func.now())

    schedule = relationship("Schedule")
