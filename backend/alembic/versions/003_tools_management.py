"""add tools management tables: tools, tool_permissions, agent_tool_access

Revision ID: 003
Revises: 002
Create Date: 2026-03-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tools ──────────────────────────────────────────────────────────────
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True, server_default="low"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tools_id"), "tools", ["id"], unique=False)
    op.create_index(op.f("ix_tools_key"), "tools", ["key"], unique=True)

    # ── tool_permissions ───────────────────────────────────────────────────
    op.create_table(
        "tool_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_permissions_id"), "tool_permissions", ["id"], unique=False)

    # ── agent_tool_access ──────────────────────────────────────────────────
    op.create_table(
        "agent_tool_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("granted_permissions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("config", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tool_access_id"), "agent_tool_access", ["id"], unique=False)

    # ── seed tool definitions ──────────────────────────────────────────────
    tools_table = sa.table(
        "tools",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("risk_level", sa.String),
        sa.column("metadata", sa.JSON),
    )
    op.bulk_insert(tools_table, [
        {
            "key": "filesystem",
            "name": "File System",
            "description": "Grants agents access to read, write, and monitor files and folders on the host system.",
            "risk_level": "medium",
            "metadata": {"icon": "📁"},
        },
        {
            "key": "shell",
            "name": "Shell Access",
            "description": "Allows agents to execute shell commands on the host machine.",
            "risk_level": "high",
            "metadata": {"icon": "⚡", "supported_shells": ["PowerShell", "CMD"]},
        },
        {
            "key": "web_search",
            "name": "Web Search",
            "description": "Enables agents to search the web and optionally open result links.",
            "risk_level": "low",
            "metadata": {"icon": "🔍"},
        },
        {
            "key": "github",
            "name": "GitHub",
            "description": "Connects agents to GitHub repositories for reading code, issues, PRs, and optionally making changes.",
            "risk_level": "medium",
            "metadata": {"icon": "🐙"},
        },
        {
            "key": "email",
            "name": "Email",
            "description": "Integrates with email providers (Gmail API, Outlook API, SMTP+IMAP) to send, read, and monitor messages.",
            "risk_level": "medium",
            "metadata": {"icon": "✉️"},
        },
    ])

    # ── seed tool permissions ──────────────────────────────────────────────
    # We need the tool IDs — use a subquery approach via raw SQL
    conn = op.get_bind()

    def tool_id(key):
        return conn.execute(sa.text("SELECT id FROM tools WHERE key = :k"), {"k": key}).scalar()

    perms = []
    for key, label in [
        ("read_files", "Read files"),
        ("write_files", "Write files"),
        ("browse_folders", "Browse folders"),
        ("detect_file_changes", "Detect file changes"),
        ("detect_folder_changes", "Detect folder changes"),
    ]:
        perms.append({"tool_id": tool_id("filesystem"), "key": key, "label": label})

    for key, label in [
        ("execute_commands", "Execute commands"),
        ("allow_readonly", "Allow read-only commands"),
        ("allow_write_impact", "Allow write-impacting commands"),
    ]:
        perms.append({"tool_id": tool_id("shell"), "key": key, "label": label})

    for key, label in [
        ("perform_search", "Perform search"),
        ("open_links", "Open result links"),
    ]:
        perms.append({"tool_id": tool_id("web_search"), "key": key, "label": label})

    for key, label in [
        ("read_repo", "Read repo"),
        ("read_issues", "Read issues"),
        ("read_prs", "Read pull requests"),
        ("create_branch", "Create branch"),
        ("commit_changes", "Commit changes"),
        ("create_pr", "Create PR"),
    ]:
        perms.append({"tool_id": tool_id("github"), "key": key, "label": label})

    for key, label in [
        ("send_email", "Send email"),
        ("read_inbox", "Read inbox"),
        ("read_attachments", "Read attachments"),
        ("create_draft", "Create draft"),
        ("monitor_incoming", "Monitor incoming mail"),
    ]:
        perms.append({"tool_id": tool_id("email"), "key": key, "label": label})

    tp_table = sa.table(
        "tool_permissions",
        sa.column("tool_id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("label", sa.String),
    )
    op.bulk_insert(tp_table, perms)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tool_access_id"), table_name="agent_tool_access")
    op.drop_table("agent_tool_access")
    op.drop_index(op.f("ix_tool_permissions_id"), table_name="tool_permissions")
    op.drop_table("tool_permissions")
    op.drop_index(op.f("ix_tools_key"), table_name="tools")
    op.drop_index(op.f("ix_tools_id"), table_name="tools")
    op.drop_table("tools")
