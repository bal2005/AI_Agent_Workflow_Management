"""
Test that:
1. API key is encrypted in .task_input.json (not plaintext)
2. Container decrypts it and gets a valid LLM response
"""
import sys, json, os
sys.path.insert(0, '/app')

from app.crypto import encrypt, decrypt
from app.sandbox.manager import SandboxManager, HOST_SANDBOX_BASE

# Get the real API key from the active LLM config
from app.database import SessionLocal
from app import models
db = SessionLocal()
cfg = db.query(models.LLMConfig).filter(models.LLMConfig.is_active == True).first()
if not cfg:
    print("ERROR: No active LLM config")
    sys.exit(1)

real_key = decrypt(cfg.api_key) if cfg.api_key else ""
base_url = cfg.base_url or "https://api.openai.com/v1"
model = cfg.model_name or "gpt-4o"
db.close()

print(f"LLM: {model} @ {base_url}")
print(f"Key present: {bool(real_key)}, length: {len(real_key)}")

# Encrypt the key as workflow_runner does
encrypted_key = encrypt(real_key)
print(f"\nEncrypted key (first 40 chars): {encrypted_key[:40]}...")
print(f"Plaintext key visible in file: {real_key[:8]}... → NOT in encrypted: {real_key[:8] not in encrypted_key}")

# Build payload with encrypted key
mgr = SandboxManager(run_id="enc-key-test-001")
mgr.prepare_workspace()

payload = {
    "system_prompt": "You are a helpful assistant. Be concise.",
    "user_message": "Reply with exactly 3 words: ENCRYPTION TEST PASSED",
    "llm_base_url": base_url.rstrip("/"),
    "llm_api_key_enc": encrypted_key,   # encrypted — not plaintext
    "llm_model": model,
    "llm_temperature": 0.1,
    "llm_max_tokens": 20,
    "granted_permissions": {},
    "available_tools": [],
}

# Verify the input file doesn't contain the plaintext key
mgr.write_task_input(payload)
raw_json = (mgr.workspace / ".task_input.json").read_text()
assert real_key not in raw_json, "FAIL: plaintext API key found in task_input.json!"
assert encrypted_key in raw_json, "FAIL: encrypted key not in task_input.json"
print("\n✓ Plaintext key NOT in .task_input.json")
print("✓ Encrypted key IS in .task_input.json")

# Run the sandbox
needs_network = "localhost" not in base_url and "127.0.0.1" not in base_url
print(f"\nRunning sandbox (network={'bridge' if needs_network else 'none'})...")
result = mgr.run(payload, network_access=needs_network)

print(f"\nResult success: {result.get('success')}")
print(f"Final text: {result.get('final_text', '')[:200]}")
if result.get('error'):
    print(f"Error: {result.get('error')}")
if result.get('logs'):
    print(f"Sandbox log:\n{result.get('sandbox_log', '')[-500:]}")
