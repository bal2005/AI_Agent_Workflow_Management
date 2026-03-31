"""Check how Tool objects become tool_defs in the SDK payload."""
import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c', '''
import copilot, os

sdk_path = os.path.dirname(copilot.__file__)

with open(sdk_path + "/client.py") as f:
    content = f.read()

lines = content.split("\\n")
# Find tool_defs construction
for i, line in enumerate(lines):
    if "tool_defs" in line:
        start = max(0, i-3)
        end = min(len(lines), i+4)
        print(f"--- line {i} ---")
        for l in lines[start:end]:
            print(l)
        print()
'''],
    capture_output=True, text=True, timeout=15
)
print(r.stdout[:3000])
