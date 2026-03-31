"""Find where available_tools is used in the SDK source."""
import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c', '''
import copilot, inspect, os

# Find the SDK source location
sdk_path = os.path.dirname(copilot.__file__)
print("SDK path:", sdk_path)

# Search for available_tools usage
for root, dirs, files in os.walk(sdk_path):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            content = open(path).read()
            if "available_tools" in content and "custom" in content.lower():
                print(f"\\nFound in {path}:")
                for i, line in enumerate(content.split("\\n")):
                    if "available_tools" in line:
                        print(f"  {i}: {line}")
'''],
    capture_output=True, text=True, timeout=15
)
print(r.stdout[:3000])
print(r.stderr[:200])
