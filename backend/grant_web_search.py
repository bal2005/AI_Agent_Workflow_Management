"""Grant web search permission to agents used in the 'Code gen and Code review' schedule."""
from app.database import SessionLocal
from app import models

db = SessionLocal()

# Find the web_search tool
web_tool = db.query(models.Tool).filter(models.Tool.key == "web_search").first()
if not web_tool:
    print("ERROR: web_search tool not found in DB")
    db.close()
    exit(1)

print(f"Web tool: {web_tool.name} (id={web_tool.id})")
print(f"Available permissions: {[p.key for p in web_tool.permissions]}")

# Grant to agents used in tasks
agent_ids = [7, 8]  # Python MCP Server Agent, Code Review Agent
for agent_id in agent_ids:
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        continue

    existing = db.query(models.AgentToolAccess).filter_by(
        agent_id=agent_id, tool_id=web_tool.id
    ).first()

    if existing:
        existing.granted_permissions = ["perform_search", "open_links"]
        print(f"Updated web search for agent: {agent.name}")
    else:
        access = models.AgentToolAccess(
            agent_id=agent_id,
            tool_id=web_tool.id,
            granted_permissions=["perform_search", "open_links"],
            config={},
        )
        db.add(access)
        print(f"Granted web search to agent: {agent.name}")

db.commit()
print("\nDone. Agents now have web search permission.")
db.close()
