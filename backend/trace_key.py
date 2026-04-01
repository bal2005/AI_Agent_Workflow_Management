"""Trace the exact API key flow from DB → sandbox container."""
import sys, json
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app import models
from app.crypto import decrypt, encrypt

db = SessionLocal()
cfg = db.query(models.LLMConfig).filter_by(is_active=True).first()
db.close()

print("=== DB stored key ===")
raw_in_db = cfg.api_key
print(f"Raw in DB (first 30): {raw_in_db[:30] if raw_in_db else 'EMPTY'}")

print("\n=== After decrypt() ===")
decrypted = decrypt(raw_in_db) if raw_in_db else ""
print(f"Decrypted (first 20): {decrypted[:20] if decrypted else 'EMPTY'}")
print(f"Looks like Ollama key: {decrypted.startswith('b6') or decrypted.startswith('tvly') or decrypted.startswith('sk-')}")

print("\n=== After re-encrypt for sandbox ===")
re_encrypted = encrypt(decrypted) if decrypted else ""
print(f"Re-encrypted (first 30): {re_encrypted[:30] if re_encrypted else 'EMPTY'}")

print("\n=== Simulate container decrypt ===")
import os
enc_key = os.environ.get("ENCRYPTION_KEY", "")
print(f"ENCRYPTION_KEY set: {bool(enc_key)}")

from cryptography.fernet import Fernet
f = Fernet(enc_key.encode())
final_key = f.decrypt(re_encrypted.encode()).decode()
print(f"Final key in container (first 20): {final_key[:20]}")
print(f"Matches original: {final_key == decrypted}")

print("\n=== Test direct API call with this key ===")
import httpx
headers = {"Authorization": f"Bearer {final_key}", "Content-Type": "application/json"}
body = {"model": cfg.model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
try:
    r = httpx.post(f"{cfg.base_url.rstrip('/')}/chat/completions", headers=headers, json=body, timeout=15)
    print(f"Status: {r.status_code}")
    if r.status_code == 401:
        print("Response:", r.text[:200])
    else:
        print("SUCCESS - key works")
except Exception as e:
    print(f"Error: {e}")
