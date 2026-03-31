"""See the full tool definition structure built from a Tool object."""
import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c', '''
import copilot, os

sdk_path = os.path.dirname(copilot.__file__)
with open(sdk_path + "/client.py") as f:
    content = f.read()

lines = content.split("\\n")
# Print lines 560-580 to see the full definition dict
for i, line in enumerate(lines[558:590], start=558):
    print(f"{i}: {line}")
'''],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
