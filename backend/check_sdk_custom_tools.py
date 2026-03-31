"""Check how custom tools are sent to the model in SDK 0.2.x."""
import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c', '''
import copilot, inspect

sdk_path = __import__("os").path.dirname(copilot.__file__)

# Read client.py and find how custom tools (Tool objects) are serialized
with open(sdk_path + "/client.py") as f:
    content = f.read()

# Find lines around "tools" parameter handling
lines = content.split("\\n")
for i, line in enumerate(lines):
    if ("tools" in line.lower() and 
        ("payload" in line or "custom" in line.lower() or "handler" in line.lower())):
        start = max(0, i-2)
        end = min(len(lines), i+5)
        print(f"--- line {i} ---")
        for l in lines[start:end]:
            print(l)
        print()
'''],
    capture_output=True, text=True, timeout=15
)
print(r.stdout[:4000])
print(r.stderr[:200])
