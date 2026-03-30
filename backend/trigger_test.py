"""Trigger schedule 7 and watch the sandbox output."""
import time, json
from pathlib import Path

from app.scheduler_tasks import run_schedule

print("Triggering schedule 7...")
result = run_schedule.apply(args=[7, 'manual'])
print("Celery result:", result.result)

# Find the latest workspace
base = Path("/sandbox_host")
workspaces = sorted(
    [d for d in base.iterdir() if d.is_dir() and (d / ".task_input.json").exists()],
    key=lambda d: d.stat().st_mtime, reverse=True
)

print(f"\nFound {len(workspaces)} sandbox workspace(s)")
for ws in workspaces[:3]:
    print(f"\n--- {ws.name} ---")
    out_file = ws / ".task_output.json"
    log_file = ws / "run.log"
    if out_file.exists():
        out = json.loads(out_file.read_text())
        print("success:", out.get("success"))
        print("final_text:", str(out.get("final_text", ""))[:200])
        print("tool_usage:", out.get("tool_usage", []))
        if out.get("error"):
            print("error:", out.get("error"))
    else:
        print("No output file")
    if log_file.exists():
        print("run.log:", log_file.read_text()[-500:])
