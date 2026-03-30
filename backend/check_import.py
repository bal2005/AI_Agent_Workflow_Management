import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root', '--entrypoint', 'python3',
     'agent-runner:latest', '-c',
     'import sys; sys.path.insert(0,"/app"); import agent_runner; print("import OK")'],
    capture_output=True, text=True, timeout=15
)
print("stdout:", r.stdout)
print("stderr:", r.stderr[:500])
print("exit:", r.returncode)
