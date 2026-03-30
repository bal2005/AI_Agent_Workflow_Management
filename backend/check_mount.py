import subprocess

# Check if /workspace is accessible inside the container with the mount
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', '/sandbox_host/debug-test-001:/workspace',
     '--entrypoint', 'python3',
     'agent-runner:latest', '-c',
     'import os; print("workspace exists:", os.path.exists("/workspace")); print("files:", os.listdir("/workspace") if os.path.exists("/workspace") else "N/A"); print("input:", os.path.exists("/workspace/.task_input.json"))'],
    capture_output=True, text=True, timeout=15
)
print("stdout:", r.stdout)
print("stderr:", r.stderr[:300])
print("exit:", r.returncode)
