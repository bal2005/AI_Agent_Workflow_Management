"""Test the sandbox container end-to-end with a minimal payload."""
import subprocess, json, os
from pathlib import Path

# Use an existing workspace that has a task_input.json
workspace = "/sandbox_host/122-task2"

# First check permissions on the workspace
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', 'python3',
     '-v', f'{workspace}:/workspace',
     'agent-runner:latest', '-c',
     'import os,stat; p="/workspace"; s=os.stat(p); print("mode:", oct(s.st_mode)); print("uid:", s.st_uid); print("gid:", s.st_gid); print("files:", os.listdir(p))'],
    capture_output=True, text=True, timeout=15
)
print("=== Workspace check ===")
print("stdout:", r.stdout)
print("stderr:", r.stderr[:200])
print("exit:", r.returncode)

# Now try a minimal write test
r2 = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', 'python3',
     '-v', f'{workspace}:/workspace',
     'agent-runner:latest', '-c',
     'open("/workspace/test_write.txt","w").write("ok"); print("write OK")'],
    capture_output=True, text=True, timeout=15
)
print("\n=== Write test ===")
print("stdout:", r2.stdout)
print("stderr:", r2.stderr[:200])
print("exit:", r2.returncode)
