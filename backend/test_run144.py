import subprocess, os, json
from pathlib import Path

enc_key = os.environ.get("ENCRYPTION_KEY", "")
tavily  = os.environ.get("TAVILY_API_KEY", "")
host_ws = "C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/144-task2"

# Check what's in the input
ws = Path("/sandbox_host/144-task2")
inp = json.loads((ws / ".task_input.json").read_text())
print("tools:", inp.get("available_tools"))
print("base_url:", inp.get("llm_base_url"))
print("key_first20:", inp.get("llm_api_key_enc", "")[:20])

r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{host_ws}:/workspace',
     '--network', 'bridge',
     '--env', f'ENCRYPTION_KEY={enc_key}',
     '--env', f'TAVILY_API_KEY={tavily}',
     '--entrypoint', 'sh',
     'agent-runner:latest', '-c',
     'python3 /app/agent_runner.py 2>&1; echo "EXIT:$?"'],
    capture_output=True, text=True, timeout=60
)
print("\n=== Container output ===")
print(r.stdout[:3000])
print("stderr:", r.stderr[:500])
