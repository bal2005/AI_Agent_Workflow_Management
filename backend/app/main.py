from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import domains, agents, llm_configs

app = FastAPI(title="Agent Studio API")

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

@app.get("/health")
def health():
    return {"status": "ok"}
