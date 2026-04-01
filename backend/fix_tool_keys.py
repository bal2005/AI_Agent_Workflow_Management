"""Fix wrong tool key 'web' → 'web_search' and 'open_result_links' → 'open_links' in workflow_runner.py"""
path = "/app/app/workflow_runner.py"
with open(path) as f:
    content = f.read()

# Fix tool key
content = content.replace('checker.allowed("web", "perform_search")', 'checker.allowed("web_search", "perform_search")')
content = content.replace('checker.allowed("web", "open_result_links")', 'checker.allowed("web_search", "open_links")')

with open(path, "w") as f:
    f.write(content)

# Verify
import subprocess
r = subprocess.run(["python3", "-m", "py_compile", path], capture_output=True, text=True)
print("Syntax check:", "OK" if r.returncode == 0 else r.stderr)

# Show the fixed lines
for i, line in enumerate(content.split("\n"), 1):
    if "checker.allowed" in line:
        print(f"  {i}: {line.strip()}")
