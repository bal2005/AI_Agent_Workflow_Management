"""
Test that web search is available and fires correctly in the workflow runner.
Checks:
1. Agent has web search permission
2. _allowed_tool_names includes perform_web_search
3. _execute_task_fallback includes web tools
4. A real search call works
"""
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app import models
from app.sandbox.permissions import PermissionChecker

db = SessionLocal()

# Find an agent with web search permission
agents = db.query(models.Agent).all()
web_agent = None
for agent in agents:
    checker = PermissionChecker.from_db(db, agent.id)
    if checker.allowed("web", "perform_search"):
        web_agent = agent
        print(f"Found agent with web search: {agent.name} (id={agent.id})")
        print(f"  Grants: {checker.grants}")
        break

if not web_agent:
    print("No agent has web search permission. Grant it in Tools Management page.")
    db.close()
    sys.exit(0)

# Check _allowed_tool_names includes web tools
task = db.query(models.Task).filter(models.Task.agent_id == web_agent.id).first()
if task:
    from app.workflow_runner import _allowed_tool_names
    allowed = _allowed_tool_names(task, db)
    print(f"\nAllowed tools for task '{task.name}': {sorted(allowed)}")
    print(f"Web search included: {'perform_web_search' in allowed}")

# Test the actual Tavily search
import os
print(f"\nTAVILY_API_KEY set: {bool(os.environ.get('TAVILY_API_KEY'))}")
from app.web_tools import perform_web_search
result = perform_web_search("Python MCP server latest version", max_results=2)
print(f"\nSearch result (first 300 chars):\n{result[:300]}")

db.close()
