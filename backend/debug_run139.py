import subprocess, os, json
from pathlib import Path

enc_key = os.environ.get("ENCRYPTION_KEY", "")
tavily  = os.environ.get("TAVILY_API_KEY", "")

ws_path = Path("/sandbox_host/139-task4")
print("Files:", list(ws_path.iterdir()))

# Read task input to understand what's being sent
inp = json.loads((ws_path / ".task_input.json").read_text())
print("model:", inp.get("llm_model"))
print("base_url:", inp.get("llm_base_url"))
print("tools:", inp.get("available_tools"))
print("permissions:", inp.get("granted_permissions"))
print("has_key:", bool(inp.get("llm_api_key_enc")))

# Run the container and capture full output
host_ws = "C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/139-task4"
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{host_ws}:/workspace',
     '--network', 'bridge',
     '--env', f'ENCRYPTION_KEY={enc_key}',
     '--env', f'TAVILY_API_KEY={tavily}',
     '--entrypoint', 'sh',
     'agent-runner:latest', '-c',
     'python3 /app/agent_runner.py 2>&1; echo "EXIT_CODE:$?"'],
    capture_output=True, text=True, timeout=60
)
print("\n=== Container output ===")
print(r.stdout[:3000])
print("stderr:", r.stderr[:500])
