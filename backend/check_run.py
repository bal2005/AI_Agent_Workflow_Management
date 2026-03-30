import subprocess, os
from pathlib import Path

# Find the most recent workspace with a task_input.json
base = Path("/sandbox_host")
workspaces = sorted(
    [d for d in base.iterdir() if d.is_dir() and (d / ".task_input.json").exists()],
    key=lambda d: d.stat().st_mtime, reverse=True
)
print("Workspaces with input:", [w.name for w in workspaces])

if not workspaces:
    print("No workspaces with input found")
    exit()

ws = workspaces[0]
print(f"\nTesting with: {ws.name}")
print("Files:", list(ws.iterdir()))

# Run the container against this workspace
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{ws}:/workspace',
     '--network', 'bridge',
     'agent-runner:latest'],
    capture_output=True, text=True, timeout=60
)
print("\nExit:", r.returncode)
print("Stdout:", r.stdout[:500])
print("Stderr:", r.stderr[:500])

out = ws / ".task_output.json"
log = ws / "run.log"
print("\nOutput file:", out.exists())
if out.exists():
    print(out.read_text()[:300])
print("Log file:", log.exists())
if log.exists():
    print(log.read_text()[:300])
