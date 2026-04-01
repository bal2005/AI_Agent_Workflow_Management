from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import domains, agents, llm_configs, tools, task_playground, tasks, schedules, filesystem, sandbox_monitor, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    # Start filesystem trigger listeners for all active filesystem-triggered schedules
    try:
        from app.triggers.trigger_registry import registry
        registry.start_all()
    except Exception as e:
        import logging
        logging.getLogger("main").warning(f"Trigger registry startup failed: {e}")

    yield  # app runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    try:
        from app.triggers.trigger_registry import registry
        registry.stop_all()
    except Exception:
        pass


app = FastAPI(title="Agent Studio API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domains.router)
app.include_router(agents.router)
app.include_router(llm_configs.router)
app.include_router(tools.router)
app.include_router(task_playground.router)
app.include_router(tasks.router)
app.include_router(schedules.router)
app.include_router(filesystem.router)
app.include_router(sandbox_monitor.router)
app.include_router(dashboard.router)

@app.get("/health")
def health():
    return {"status": "ok"}
