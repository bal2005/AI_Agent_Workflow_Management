import subprocess
r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c',
     'import inspect; from copilot import CopilotClient; sig=inspect.signature(CopilotClient.create_session); [print(k,":",v) for k,v in sig.parameters.items()]'],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
print(r.stderr[:200])
