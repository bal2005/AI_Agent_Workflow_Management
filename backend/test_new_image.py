import subprocess, os

enc_key = os.environ.get("ENCRYPTION_KEY", "")
tavily  = os.environ.get("TAVILY_API_KEY", "")
host_ws = "C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/138-task2"

r = subprocess.run(
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
print("Exit:", r.returncode)
print("Stdout:", r.stdout[:2000])
print("Stderr:", r.stderr[:1000])
