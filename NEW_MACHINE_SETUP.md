# Setting Up Agent Studio on a New Machine

Welcome! This document explains how to clone and set up the Agent Studio project from GitHub on a new machine.

## Quick Start (5 minutes)

1. **Clone the repo:**
   ```bash
   git clone <your-github-repo-url>
   cd AI_Agent_Workflow_Management
   ```

2. **Follow the checklist:**
   - Open `QUICK_SETUP_CHECKLIST.txt` and work through it step-by-step
   - It's a simple checkbox list — takes ~10 minutes

3. **Start the servers:**
   - Terminal 1: `cd backend && venv\Scripts\Activate.ps1 && uvicorn app.main:app --reload --port 8000`
   - Terminal 2: `cd frontend && npm run dev`

4. **Open browser:**
   - Navigate to `http://localhost:5173`

## Detailed Setup

For a more detailed walkthrough with troubleshooting, see `SETUP_GUIDE.md`.

## Key Files

| File | Purpose |
|------|---------|
| `QUICK_SETUP_CHECKLIST.txt` | **START HERE** — Simple checkbox list |
| `SETUP_GUIDE.md` | Detailed step-by-step guide with explanations |
| `backend/.env.example` | Template for environment variables |
| `backend/requirements.txt` | Python dependencies |
| `frontend/package.json` | Node.js dependencies |

## Prerequisites

Before you start, make sure you have:

- **Git** — for cloning
- **Python 3.12+** — for backend
- **Node.js 18+** — for frontend
- **PostgreSQL** — NeonDB (cloud) or local instance

Verify with:
```bash
git --version
python --version
node --version
npm --version
```

## What You'll Need

### 1. Database Credentials

You need a PostgreSQL database. Two options:

**Option A: NeonDB (Recommended — Free tier available)**
- Sign up at https://neon.tech
- Create a project and database
- Copy the connection string
- Format: `postgresql://user:password@host:port/db?sslmode=require&channel_binding=require`

**Option B: Local PostgreSQL**
- Install PostgreSQL locally
- Create a database: `createdb agent_studio`
- Connection string: `postgresql://postgres:password@localhost:5432/agent_studio`

### 2. Encryption Key

Generate a new encryption key for API key storage:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output and save it — you'll need it in `.env`.

### 3. LLM API Key (Optional but Recommended)

To use the Task Playground, you'll need an LLM API key:
- **OpenAI** — https://platform.openai.com/api-keys
- **Groq** — https://console.groq.com/keys (free, fast)
- **Claude** — https://console.anthropic.com/
- **Ollama** — Local (free, no key needed)

You can add this later through the UI.

## The Setup Process

### Step 1: Clone the Repository

```bash
git clone <your-github-repo-url>
cd AI_Agent_Workflow_Management
```

### Step 2: Backend Setup (5 minutes)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\Activate.ps1  # Windows PowerShell
# OR
source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials
# Copy backend/.env.example to backend/.env
# Edit it with your DATABASE_URL and ENCRYPTION_KEY

# Run migrations
alembic upgrade head
```

### Step 3: Frontend Setup (2 minutes)

```bash
cd ../frontend

# Install dependencies
npm install

# Verify build works
npm run build
```

### Step 4: Start the Servers

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

### Step 5: Access the Application

Open your browser and go to:
```
http://localhost:5173
```

You should see the Agent Studio interface!

## Troubleshooting

### "ModuleNotFoundError: No module named 'app'"
- Make sure you're in the `backend/` directory
- Verify virtual environment is activated

### "psycopg2 error" or database connection fails
- Check your DATABASE_URL in `.env`
- Verify the database is accessible
- Test with: `psql <your-database-url>`

### "ENCRYPTION_KEY not set"
- Generate a new key (see Prerequisites section)
- Add it to `backend/.env`

### Frontend shows blank page
- Check that backend is running on port 8000
- Open browser DevTools (F12) and check Console for errors
- Verify Vite proxy is configured in `frontend/vite.config.js`

### Port already in use
- Backend: Use `--port 8001` instead of 8000
- Frontend: Vite will auto-increment to 5174, 5175, etc.

## Project Structure

```
AI_Agent_Workflow_Management/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── models.py          # Database models
│   │   ├── routers/           # API endpoints
│   │   ├── shell_tools.py     # Shell commands
│   │   ├── web_tools.py       # Web search
│   │   └── crypto.py          # Encryption
│   ├── alembic/               # Database migrations
│   ├── requirements.txt       # Python deps
│   ├── .env                   # Credentials (NOT in Git)
│   └── venv/                  # Virtual environment
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── App.jsx            # Main component
│   │   ├── api.js             # API client
│   │   └── components/        # Pages
│   ├── package.json           # Node deps
│   ├── vite.config.js         # Vite config
│   └── node_modules/
├── SETUP_GUIDE.md             # Detailed guide
├── QUICK_SETUP_CHECKLIST.txt  # Quick checklist
└── NEW_MACHINE_SETUP.md       # This file
```

## Important Notes

1. **`.env` is NOT in Git** — Each developer creates their own with their own credentials
2. **`venv/` and `node_modules/` are ignored** — Reinstall on each machine
3. **Database migrations are version-controlled** — In `backend/alembic/versions/`
4. **Each developer needs their own credentials** — DATABASE_URL and ENCRYPTION_KEY

## Next Steps After Setup

1. Go to **LLM Config** page and add your LLM provider (OpenAI, Groq, Claude, etc.)
2. Go to **Agent Creation** page and create a domain and agent
3. Go to **Tools Management** page and assign permissions
4. Go to **Task Playground** page and run a task

## Getting Help

- **Backend errors** — Check the terminal running uvicorn
- **Frontend errors** — Open browser DevTools (F12) → Console
- **Database issues** — Verify DATABASE_URL and connectivity
- **API key errors** — Ensure ENCRYPTION_KEY is set

## Technologies Used

- **Backend:** FastAPI, SQLAlchemy, PostgreSQL, GitHub Copilot SDK
- **Frontend:** React, Vite, Axios
- **Database:** PostgreSQL (NeonDB or local)
- **Python:** 3.12+
- **Node.js:** 18+

## Support

For detailed instructions, see:
- `SETUP_GUIDE.md` — Complete step-by-step guide
- `QUICK_SETUP_CHECKLIST.txt` — Quick reference checklist
- `backend/.env.example` — Environment variable template

---

**Happy coding! 🚀**
