import subprocess

# Check what CMD the image has
r = subprocess.run(
    ['docker', 'inspect', 'agent-runner:latest', '--format', '{{.Config.Cmd}} {{.Config.Entrypoint}} {{.Architecture}}'],
    capture_output=True, text=True, timeout=10
)
print("Image config:", r.stdout.strip())

# Try running with explicit entrypoint to bypass CMD
r2 = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', '/sandbox_host/debug-test-001:/workspace',
     '--entrypoint', 'python3',
     'agent-runner:latest', '/app/agent_runner.py'],
    capture_output=True, text=True, timeout=60
)
print("\nWith explicit entrypoint:")
print("Exit:", r2.returncode)
print("Stdout:", r2.stdout[:300])
print("Stderr:", r2.stderr[:300])

out = '/sandbox_host/debug-test-001/.task_output.json'
import os
print("\nOutput file exists:", os.path.exists(out))
if os.path.exists(out):
    print(open(out).read()[:300])
