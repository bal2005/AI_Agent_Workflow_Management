import sys, os
sys.path.insert(0, '/app')

# Simulate what manager.py does
from dotenv import load_dotenv
load_dotenv()
enc_key = os.environ.get("ENCRYPTION_KEY", "")
print("After dotenv load, ENCRYPTION_KEY set:", bool(enc_key))
print("Key first 10:", enc_key[:10] if enc_key else "EMPTY")

# Check the .env file directly
env_path = "/app/.env"
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if "ENCRYPTION_KEY" in line:
                print("In .env file:", line.strip()[:40])
