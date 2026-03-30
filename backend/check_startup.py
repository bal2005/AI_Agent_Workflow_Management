import subprocess

# Run with a simple echo to verify the container starts at all
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', '/sandbox_host/debug-test-001:/workspace',
     '--entrypoint', 'sh',
     'agent-runner:latest', '-c', 'echo STARTED && python3 --version && ls /workspace && python3 /app/agent_runner.py; echo EXIT:$?'],
    capture_output=True, text=True, timeout=60
)
print("Exit:", r.returncode)
print("Stdout:", r.stdout[:1000])
print("Stderr:", r.stderr[:1000])
