import subprocess, os, json, sys
sys.path.insert(0, '/app')
from pathlib import Path
from app.sandbox.manager import _read_key_from_env_file

enc_key = _read_key_from_env_file("ENCRYPTION_KEY")
tavily  = _read_key_from_env_file("TAVILY_API_KEY")
print("enc_key:", bool(enc_key), enc_key[:10])
print("tavily:", bool(tavily))

ws = Path("/sandbox_host/147-task2")
inp = json.loads((ws / ".task_input.json").read_text())
print("key_in_file:", inp.get("llm_api_key_enc", "")[:20])

host_ws = "C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/147-task2"
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
print(r.stdout[:2000])
