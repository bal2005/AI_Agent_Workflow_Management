import subprocess, json, os, sys
sys.path.insert(0, '/app')
os.environ['SANDBOX_BASE'] = '/sandbox_host'
os.environ['HOST_SANDBOX_BASE'] = 'C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data'
os.environ['AGENT_IMAGE'] = 'agent-runner:latest'

# Reload module with new env
import importlib
import app.sandbox.manager as mgr_mod
importlib.reload(mgr_mod)

from app.sandbox.manager import SandboxManager, HOST_SANDBOX_BASE, SANDBOX_BASE
print("SANDBOX_BASE:", SANDBOX_BASE)
print("HOST_SANDBOX_BASE:", HOST_SANDBOX_BASE)

mgr = SandboxManager(run_id="hostpath-test-001")
mgr.prepare_workspace()

payload = {
    "system_prompt": "You are a helpful assistant.",
    "user_message": "Reply with exactly: SANDBOX_WORKS",
    "llm_base_url": "https://ollama.com/v1",
    "llm_api_key": os.environ.get("OLLAMA_API_KEY", ""),
    "llm_model": "gpt-oss:120b",
    "llm_temperature": 0.1,
    "llm_max_tokens": 20,
    "granted_permissions": {},
    "available_tools": [],
}
mgr.write_task_input(payload)

# Show the exact docker command
host_ws = HOST_SANDBOX_BASE.rstrip("/") + "/hostpath-test-001"
print(f"\nVolume mount: {host_ws}:/workspace")
print("Input file exists:", (mgr.workspace / ".task_input.json").exists())

result = mgr.run(payload, network_access=True)
print("\nResult:", json.dumps(result, indent=2)[:500])
