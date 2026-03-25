# Agent Studio — New Machine Setup Guide

This guide walks you through setting up the Agent Studio project on a new machine from the GitHub repository.

---

## Prerequisites

Before starting, ensure you have these installed on your new machine:

- **Git** — for cloning the repository
- **Python 3.12+** — for the backend
- **Node.js 18+** — for the frontend (includes npm)
- **PostgreSQL client** (optional, for direct DB access)

### Verify Installations

```bash
git --version
python --version
node --version
npm --version
```

---

## Step 1: Clone the Repository

```bash
git clone <your-github-repo-url>
cd AI_Agent_Workflow_Management
```

---

## Step 2: Backend Setup

### 2.1 Create Python Virtual Environment

```bash
cd backend
python -m venv venv
```

### 2.2 Activate Virtual Environment

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 2.3 Install Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- FastAPI & Uvicorn (web framework)
- SQLAlchemy & Alembic (database ORM + migrations)
- psycopg2 (PostgreSQL driver)
- Pydantic (data validation)
- httpx (HTTP client)
- cryptography (API key encryption)
- github-copilot-sdk (agent framework)
- python-docx, pypdf (document parsing)
- duckduckgo-search, beautifulsoup4 (web tools)

### 2.4 Configure Environment Variables

Create/update `backend/.env` with your credentials:

```env
DATABASE_URL=postgresql://user:password@host:port/dbname?sslmode=require&channel_binding=require
ENCRYPTION_KEY=<your-32-byte-base64-key>
```

**For DATABASE_URL:**
- Use NeonDB (PostgreSQL cloud) or local PostgreSQL
- Format: `postgresql://username:password@host:port/database?sslmode=require&channel_binding=require`

**For ENCRYPTION_KEY:**
- Generate a new key (if needed):
  ```python
  from cryptography.fernet import Fernet
  key = Fernet.generate_key().decode()
  print(key)
  ```
- Paste the generated key into `.env`

### 2.5 Run Database Migrations

```bash
alembic upgrade head
```

This creates all tables (domains, agents, llm_configs, tools, etc.)

### 2.6 Verify Backend Setup

```bash
python -c "from app.main import app; print('✓ Backend imports OK')"
```

---

## Step 3: Frontend Setup

### 3.1 Install Node Dependencies

```bash
cd ../frontend
npm install
```

This installs:
- React & React-DOM
- Axios (HTTP client)
- Vite (build tool)

### 3.2 Verify Frontend Setup

```bash
npm run build
```

Should complete without errors.

---

## Step 4: Start the Application

### Terminal 1 — Backend Server

```bash
cd backend
venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2 — Frontend Dev Server

```bash
cd frontend
npm run dev
```

Expected output:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

---

## Step 5: Access the Application

Open your browser and navigate to:

```
http://localhost:5173
```

You should see the Agent Studio interface with:
- Agent Creation page
- LLM Config page
- Tools Management page
- Task Playground page

---

## Checklist for New Machine Setup

Use this checklist to track your progress:

### Prerequisites
- [ ] Git installed and configured
- [ ] Python 3.12+ installed
- [ ] Node.js 18+ installed
- [ ] npm installed

### Backend Setup
- [ ] Repository cloned
- [ ] `cd backend` completed
- [ ] Virtual environment created (`venv/`)
- [ ] Virtual environment activated
- [ ] `pip install -r requirements.txt` completed
- [ ] `.env` file created with DATABASE_URL and ENCRYPTION_KEY
- [ ] `alembic upgrade head` completed successfully
- [ ] Backend imports verified

### Frontend Setup
- [ ] `cd frontend` completed
- [ ] `npm install` completed
- [ ] `npm run build` completed without errors

### Running the Application
- [ ] Backend server started on port 8000
- [ ] Frontend dev server started on port 5173
- [ ] Application accessible at http://localhost:5173
- [ ] Can create agents, configure LLM, manage tools, run tasks

---

## Troubleshooting

### Backend Issues

**"ModuleNotFoundError: No module named 'app'"**
- Ensure you're in the `backend/` directory
- Verify virtual environment is activated

**"psycopg2 error" or database connection fails**
- Check DATABASE_URL in `.env`
- Verify PostgreSQL/NeonDB is accessible
- Test connection: `psql <DATABASE_URL>`

**"ENCRYPTION_KEY not set"**
- Generate a new key (see Step 2.4)
- Add it to `.env`

**Port 8000 already in use**
- Use a different port: `uvicorn app.main:app --reload --port 8001`

### Frontend Issues

**"npm ERR! code ERESOLVE"**
- Clear npm cache: `npm cache clean --force`
- Delete `node_modules/` and `package-lock.json`
- Run `npm install` again

**Port 5173 already in use**
- Vite will auto-increment to 5174, 5175, etc.
- Or specify: `npm run dev -- --port 3000`

**Blank page or API errors**
- Ensure backend is running on port 8000
- Check browser console for errors (F12)
- Verify Vite proxy in `frontend/vite.config.js`

---

## Project Structure

```
AI_Agent_Workflow_Management/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── schemas.py              # Pydantic schemas
│   │   ├── database.py             # DB connection
│   │   ├── crypto.py               # API key encryption
│   │   ├── copilot_runner.py       # GitHub Copilot SDK wrapper
│   │   ├── shell_tools.py          # Shell command tools
│   │   ├── web_tools.py            # Web search tools
│   │   └── routers/
│   │       ├── domains.py          # Domain CRUD
│   │       ├── agents.py           # Agent CRUD + playground
│   │       ├── llm_configs.py      # LLM config management
│   │       ├── tools.py            # Tool permissions
│   │       └── task_playground.py  # Task execution engine
│   ├── alembic/
│   │   ├── env.py
│   │   ├── versions/               # DB migrations
│   │   └── alembic.ini
│   ├── requirements.txt            # Python dependencies
│   ├── .env                        # Environment variables
│   └── venv/                       # Virtual environment
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Main app component
│   │   ├── api.js                  # API client
│   │   ├── main.jsx                # React entry
│   │   ├── index.css               # Global styles
│   │   └── components/
│   │       ├── AgentCreationPage.jsx
│   │       ├── LLMConfigPage.jsx
│   │       ├── ToolsManagementPage.jsx
│   │       ├── TaskPlaygroundPage.jsx
│   │       └── SidePanel.jsx
│   ├── package.json                # Node dependencies
│   ├── vite.config.js              # Vite config + API proxy
│   └── index.html
├── .gitignore
└── SETUP_GUIDE.md                  # This file
```

---

## Key Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend Framework | FastAPI | ≥0.115.0 |
| Database | PostgreSQL (NeonDB) | Latest |
| ORM | SQLAlchemy | 2.0.29 |
| Migrations | Alembic | 1.13.1 |
| Agent Framework | GitHub Copilot SDK | ≥1.0.0b260319 |
| Frontend Framework | React | 18.2.0 |
| Build Tool | Vite | 5.2.0 |
| HTTP Client | Axios | 1.6.8 |
| Python | 3.12+ | - |
| Node.js | 18+ | - |

---

## Environment Variables Reference

### `backend/.env`

```env
# PostgreSQL connection string (NeonDB or local)
DATABASE_URL=postgresql://user:password@host:port/db?sslmode=require&channel_binding=require

# 32-byte base64 key for Fernet encryption (API keys at rest)
ENCRYPTION_KEY=<base64-encoded-32-byte-key>
```

### `frontend/vite.config.js`

Proxy configuration (already set up):
```javascript
proxy: {
  "/domains": "http://localhost:8000",
  "/agents": "http://localhost:8000",
  "/llm-configs": "http://localhost:8000",
  "/tools": "http://localhost:8000",
  "/task-playground": "http://localhost:8000",
  "/health": "http://localhost:8000",
}
```

---

## Common Commands

### Backend

```bash
# Activate virtual environment
venv\Scripts\Activate.ps1  # Windows PowerShell
source venv/bin/activate   # macOS/Linux

# Start dev server
uvicorn app.main:app --reload --port 8000

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Deactivate virtual environment
deactivate
```

### Frontend

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## Next Steps After Setup

1. **Create an LLM Config** — Go to LLM Config page, add your API key (OpenAI, Groq, Claude, etc.)
2. **Create a Domain** — Add a domain (e.g., "Finance", "Engineering")
3. **Create an Agent** — Add an agent under the domain with a system prompt
4. **Assign Tool Permissions** — Go to Tools Management, grant filesystem/shell/web access
5. **Run a Task** — Go to Task Playground, select agent, enter a task, and run it

---

## Support & Debugging

- **Backend logs** — Check terminal running uvicorn for errors
- **Frontend logs** — Open browser DevTools (F12) → Console tab
- **Database issues** — Verify DATABASE_URL and network connectivity
- **API key errors** — Ensure ENCRYPTION_KEY is set and valid

---

## Notes

- The `.env` file is **NOT** committed to Git (see `.gitignore`)
- Each developer needs their own `.env` with their own credentials
- The `venv/` and `node_modules/` directories are also ignored
- Database migrations are version-controlled in `backend/alembic/versions/`

---

**Last Updated:** March 2026
**Project:** Agent Studio with GitHub Copilot SDK Integration
