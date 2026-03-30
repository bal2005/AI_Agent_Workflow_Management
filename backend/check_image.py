import subprocess

# Check what's in the image
r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', 'python3',
     'agent-runner:latest', '-c',
     'f=open("/app/agent_runner.py").read(); print("LINES:", f.count(chr(10))); print("TAIL:", f[-300:])'],
    capture_output=True, text=True, timeout=15
)
print("stdout:", r.stdout)
print("stderr:", r.stderr[:300])
print("exit:", r.returncode)
