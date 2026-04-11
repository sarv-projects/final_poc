"""SuperOwl Voice AI POC — Main Application Entry Point."""

import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.database import engine
from app.models import Base
from app.routers import (
    businesses,
    onboarding,
    playground,
    prompts,
    slack_actions,
    slack_events,
    trigger,
    vapi_webhook,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Create tables if using SQLite (for production use Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="SuperOwl Voice AI",
    description="Multi‑tenant voice AI platform for inbound/outbound calls",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(businesses.router, prefix="/businesses", tags=["Businesses"])
app.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])
app.include_router(trigger.router, prefix="/trigger", tags=["Call Triggers"])
app.include_router(vapi_webhook.router, prefix="/vapi-webhook", tags=["VAPI Webhooks"])
app.include_router(slack_events.router, prefix="/slack/events", tags=["Slack Events"])
app.include_router(
    slack_actions.router, prefix="/slack/actions", tags=["Slack Actions"]
)
app.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
app.include_router(playground.router, prefix="/playground", tags=["Playground"])


# Frontend static files
FRONTEND_DIR = pathlib.Path(__file__).resolve().parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the Voice Configuration dashboard."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
