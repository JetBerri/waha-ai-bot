import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.rag import hybrid, memory
from app.routers import webhook
from app.services.openai_client import close_openai
from app.services.waha import close_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the Qdrant collections on boot and close every client on shutdown."""

    hybrid.ensure_knowledge()
    memory.ensure_memory()

    yield

    await close_client()
    await close_openai()


app = FastAPI(title="waha-ai-bot", lifespan=lifespan)

app.include_router(webhook.router)


@app.get("/health")
async def health() -> dict:
    """Liveness probe."""

    return {"status": "ok"}
