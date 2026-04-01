from app.database import SessionLocal
from app import models
from app.sandbox.permissions import PermissionChecker

db = SessionLocal()

# Check raw DB
rows = db.query(models.AgentToolAccess).filter(
    models.AgentToolAccess.agent_id.in_([7, 8])
).all()
for r in rows:
    tool_key = r.tool.key if r.tool else f"tool_id={r.tool_id}"
    print(f"agent={r.agent_id} tool={tool_key!r} perms={r.granted_permissions}")

# Check PermissionChecker
for agent_id in [7, 8]:
    checker = PermissionChecker.from_db(db, agent_id)
    print(f"\nAgent {agent_id} grants: {checker.grants}")
    print(f"  web_search.perform_search: {checker.allowed('web_search', 'perform_search')}")

db.close()
