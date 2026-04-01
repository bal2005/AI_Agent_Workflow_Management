from app.database import SessionLocal
from app import models

db = SessionLocal()

tasks = db.query(models.Task).all()
for t in tasks:
    agent_name = t.agent.name if t.agent else "no agent"
    print(f"Task: {t.name!r} → agent: {agent_name} (id={t.agent_id})")

web_tool = db.query(models.Tool).filter(models.Tool.key == "web").first()
if web_tool:
    print(f"\nWeb tool: {web_tool.name}")
    print(f"Permissions: {[p.key for p in web_tool.permissions]}")
else:
    print("\nNo 'web' tool found in DB — need to seed it")

# Also check web_search key
ws_tool = db.query(models.Tool).filter(models.Tool.key == "web_search").first()
if ws_tool:
    print(f"\nweb_search tool: {ws_tool.name}")
    print(f"Permissions: {[p.key for p in ws_tool.permissions]}")

db.close()
