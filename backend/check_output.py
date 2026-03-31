import json, os
from pathlib import Path

base = Path("/sandbox_host")
# Find most recent run
runs = sorted([d for d in base.iterdir() if d.is_dir() and (d/".task_output.json").exists()],
              key=lambda d: d.stat().st_mtime, reverse=True)

for ws in runs[:2]:
    print(f"\n=== {ws.name} ===")
    out = json.loads((ws/".task_output.json").read_text())
    print("success:", out.get("success"))
    print("tool_usage:", out.get("tool_usage", []))
    print("output:", out.get("final_text","")[:300])
    print("files:", [f.name for f in ws.iterdir() if not f.name.startswith(".")])
