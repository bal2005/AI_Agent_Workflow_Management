import subprocess, json, os, sys
from pathlib import Path

sys.path.insert(0, '/app')
from app.database import SessionLocal
from app import models
from app.crypto import decrypt, encrypt

enc_key = os.environ.get("ENCRYPTION_KEY", "")
tavily  = os.environ.get("TAVILY_API_KEY", "")

db = SessionLocal()
cfg = db.query(models.LLMConfig).filter_by(is_active=True).first()
db.close()

decrypted_key = decrypt(cfg.api_key) if cfg.api_key else ""
re_encrypted  = encrypt(decrypted_key) if decrypted_key else ""
base_url      = cfg.base_url.rstrip("/")
model         = cfg.model_name

print(f"Base URL: {base_url}")
print(f"Model: {model}")
print(f"Decrypted key (first 12): {decrypted_key[:12]}")
print(f"Re-encrypted (first 20): {re_encrypted[:20]}")

# Write a minimal test payload
test_ws = Path("/sandbox_host/key-test-001")
test_ws.mkdir(exist_ok=True)
payload = {
    "system_prompt": "You are helpful.",
    "user_message": "Reply with just: OK",
    "llm_base_url": base_url,
    "llm_api_key_enc": re_encrypted,
    "llm_model": model,
    "llm_provider": "custom",
    "llm_temperature": 0.1,
    "llm_max_tokens": 10,
    "granted_permissions": {},
    "available_tools": [],
}
(test_ws / ".task_input.json").write_text(json.dumps(payload))
# Remove old output
(test_ws / ".task_output.json").unlink(missing_ok=True)

host_ws = "C:/Users/mbalasubramanian/Documents/AI_Agent_Workflow_Management/sandbox_data/key-test-001"

r = subprocess.run(
    ['docker', 'run', '--rm', '--user', 'root',
     '-v', f'{host_ws}:/workspace',
     '--network', 'bridge',
     '--env', f'ENCRYPTION_KEY={enc_key}',
     '--env', f'TAVILY_API_KEY={tavily}',
     '--entrypoint', 'sh',
     'agent-runner:latest', '-c',
     'python3 /app/agent_runner.py 2>&1; echo "EXIT:$?"'],
    capture_output=True, text=True, timeout=60
)
print("\n=== Container output ===")
print(r.stdout[:2000])

out_file = test_ws / ".task_output.json"
if out_file.exists():
    out = json.loads(out_file.read_text())
    print("\nsuccess:", out.get("success"))
    print("error:", out.get("error"))
    print("text:", out.get("final_text", "")[:200])
