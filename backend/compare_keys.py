import sys, json, os
sys.path.insert(0, '/app')
from pathlib import Path
from app.crypto import decrypt, encrypt
from cryptography.fernet import Fernet

enc_key = os.environ.get("ENCRYPTION_KEY", "")
f = Fernet(enc_key.encode())

# Key from run 144 .task_input.json
ws = Path("/sandbox_host/144-task2")
inp = json.loads((ws / ".task_input.json").read_text())
key_in_file = inp.get("llm_api_key_enc", "")
print("Key in file (first 20):", key_in_file[:20])

# Decrypt it
try:
    decrypted_from_file = f.decrypt(key_in_file.encode()).decode()
    print("Decrypted from file (first 20):", decrypted_from_file[:20])
except Exception as e:
    print("Decrypt error:", e)

# Current key from DB
from app.database import SessionLocal
from app import models
db = SessionLocal()
cfg = db.query(models.LLMConfig).filter_by(is_active=True).first()
db.close()
current_key = decrypt(cfg.api_key) if cfg.api_key else ""
print("Current DB key (first 20):", current_key[:20])
print("Keys match:", decrypted_from_file == current_key if 'decrypted_from_file' in dir() else "N/A")

# Test the key from the file directly
import httpx
headers = {"Authorization": f"Bearer {decrypted_from_file}", "Content-Type": "application/json"}
body = {"model": cfg.model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
r = httpx.post(f"{cfg.base_url.rstrip('/')}/chat/completions", headers=headers, json=body, timeout=15)
print(f"\nDirect test with file key: {r.status_code}")
if r.status_code != 200:
    print("Response:", r.text[:200])
