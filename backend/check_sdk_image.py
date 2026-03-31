import subprocess
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', 'python3',
     'agent-runner:latest', '-c',
     'import copilot; import cryptography; import httpx; print("SDK OK:", copilot.__version__ if hasattr(copilot,"__version__") else "installed"); print("cryptography OK"); print("httpx OK:", httpx.__version__)'],
    capture_output=True, text=True, timeout=15
)
print("stdout:", r.stdout)
print("stderr:", r.stderr[:200])
print("exit:", r.returncode)
