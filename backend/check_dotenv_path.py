import os
from dotenv import load_dotenv

# Check where manager.py thinks .env is
manager_dir = "/app/app/sandbox"
env_path = os.path.abspath(os.path.join(manager_dir, "..", "..", ".env"))
print("Computed .env path:", env_path)
print("File exists:", os.path.exists(env_path))

# Try loading it
result = load_dotenv(dotenv_path=env_path, override=True)
print("load_dotenv returned:", result)
print("ENCRYPTION_KEY after load:", bool(os.environ.get("ENCRYPTION_KEY")))

# Also try /app/.env directly
result2 = load_dotenv(dotenv_path="/app/.env", override=True)
print("\nDirect /app/.env load:", result2)
print("ENCRYPTION_KEY after direct load:", bool(os.environ.get("ENCRYPTION_KEY")))
print("Key first 10:", os.environ.get("ENCRYPTION_KEY", "")[:10])
