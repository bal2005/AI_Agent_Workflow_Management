import sys
sys.path.insert(0, '/app')

# Simulate what Celery worker does when it imports manager
from app.sandbox.manager import _read_key_from_env_file, SANDBOX_BASE, AGENT_IMAGE
import os

enc_key = _read_key_from_env_file("ENCRYPTION_KEY")
tavily  = _read_key_from_env_file("TAVILY_API_KEY")
print("ENCRYPTION_KEY via _read_key_from_env_file:", bool(enc_key), enc_key[:10] if enc_key else "EMPTY")
print("TAVILY_API_KEY via _read_key_from_env_file:", bool(tavily), tavily[:10] if tavily else "EMPTY")
print("os.environ ENCRYPTION_KEY:", bool(os.environ.get("ENCRYPTION_KEY")))
