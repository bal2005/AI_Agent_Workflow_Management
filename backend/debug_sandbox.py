import subprocess, json, os, sys
sys.path.insert(0, '/app')
os.environ.setdefault('SANDBOX_BASE', '/sandbox_host')
os.environ.setdefault('AGENT_IMAGE', 'agent-runner:latest')

from app.sandbox.manager import SandboxManager, SANDBOX_BASE, AGENT_IMAGE
print("SANDBOX_BASE:", SANDBOX_BASE)
print("AGENT_IMAGE:", AGENT_IMAGE)

# Create a test sandbox and run it
mgr = SandboxManager(run_id="debug-test-001")
mgr.prepare_workspace()

# Write a minimal payload
payload = {
    "system_prompt": "You are a helpful assistant.",
    "user_message": "Say hello in one sentence.",
    "llm_base_url": "https://ollama.com/v1",
    "llm_api_key": "test",
    "llm_model": "gpt-oss:120b",
    "llm_temperature": 0.7,
    "llm_max_tokens": 100,
    "granted_permissions": {},
    "available_tools": [],
}
mgr.write_task_input(payload)

# Build the exact docker command that will run
cmd = [
    "docker", "run", "--rm",
    "--name", f"agent-run-{mgr.run_id[:12]}",
    "-v", f"{mgr.workspace}:/workspace",
    "--network", "bridge",
    "--memory", "512m",
    "--cpus", "1.0",
    "--env", f"RUN_ID={mgr.run_id}",
    "--user", "root",
    AGENT_IMAGE,
]
print("\nDocker command:", " ".join(cmd))
print("Workspace:", mgr.workspace)
print("Input file exists:", (mgr.workspace / ".task_input.json").exists())

# Run it
r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
print("\nExit code:", r.returncode)
print("Stdout:", r.stdout[:500])
print("Stderr:", r.stderr[:500])

# Check output
out_file = mgr.workspace / ".task_output.json"
print("\nOutput file exists:", out_file.exists())
if out_file.exists():
    print("Output:", out_file.read_text()[:500])

log_file = mgr.workspace / "run.log"
if log_file.exists():
    print("Log:", log_file.read_text()[:500])
