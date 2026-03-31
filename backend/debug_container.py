import subprocess, json
from pathlib import Path

# Find the most recent workspace
base = Path("/sandbox_host")
workspaces = sorted(
    [d for d in base.iterdir() if d.is_dir() and (d / ".task_input.json").exists()],
    key=lambda d: d.stat().st_mtime, reverse=True
)
if not workspaces:
    print("No workspaces found")
    exit()

ws = workspaces[0]
print(f"Testing workspace: {ws.name}")

import os
enc_key = os.environ.get("ENCRYPTION_KEY", "")
tavily  = os.environ.get("TAVILY_API_KEY", "")
host_ws = f"C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/{ws.name}"

r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{host_ws}:/workspace',
     '--network', 'bridge',
     '--env', f'ENCRYPTION_KEY={enc_key}',
     '--env', f'TAVILY_API_KEY={tavily}',
     '--entrypoint', 'python3',
     'agent-runner:latest', '-c',
     'import sys; sys.path.insert(0,"/app"); import agent_runner; print("import OK")'],
    capture_output=True, text=True, timeout=20
)
print("Import test — exit:", r.returncode)
print("stdout:", r.stdout)
print("stderr:", r.stderr[:500])

# Now run the actual entrypoint
r2 = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{host_ws}:/workspace',
     '--network', 'bridge',
     '--env', f'ENCRYPTION_KEY={enc_key}',
     '--env', f'TAVILY_API_KEY={tavily}',
     '--entrypoint', 'sh',
     'agent-runner:latest', '-c',
     'python3 /app/agent_runner.py; echo "EXIT:$?"'],
    capture_output=True, text=True, timeout=60
)
print("\nFull run — exit:", r2.returncode)
print("stdout:", r2.stdout[:2000])
print("stderr:", r2.stderr[:1000])
