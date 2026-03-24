from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Boolean, JSON
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
