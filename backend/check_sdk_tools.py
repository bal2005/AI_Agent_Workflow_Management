"""Check how SDK 0.2.x handles tools vs available_tools."""
import subprocess

r = subprocess.run(
    ['docker', 'run', '--rm', '--entrypoint', 'python3', 'agent-runner:latest', '-c', '''
import inspect
from copilot import CopilotClient
from copilot.types import Tool

# Check Tool constructor signature
print("Tool signature:", inspect.signature(Tool.__init__))

# Check if available_tools param description mentions custom tools
sig = inspect.signature(CopilotClient.create_session)
p = sig.parameters.get("available_tools")
print("available_tools annotation:", p.annotation if p else "NOT FOUND")

p2 = sig.parameters.get("excluded_tools")
print("excluded_tools annotation:", p2.annotation if p2 else "NOT FOUND")
'''],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
print(r.stderr[:300])
