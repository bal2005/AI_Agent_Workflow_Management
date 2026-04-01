import os
from dotenv import load_dotenv
load_dotenv()
key = os.environ.get("ENCRYPTION_KEY", "")
print("ENCRYPTION_KEY set:", bool(key))
print("Key first 10:", key[:10] if key else "EMPTY")

# Check what the sandbox manager passes to docker run
from app.sandbox.manager import SANDBOX_BASE
enc_key_for_container = os.environ.get("ENCRYPTION_KEY", "")
print("Key passed to container:", bool(enc_key_for_container))
