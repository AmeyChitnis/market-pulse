"""
FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — ensures models are registered on Base
from app.database import Base, engine
from app.routers import collection, health, items
from app.services.scheduler import shutdown_scheduler, start_scheduler
from app.routers import categories
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist yet. Fine for early development;
    # a real migration tool (Alembic) replaces this once the schema
    # stabilizes and we need versioned migrations.
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Market Pulse API",
    description="Time-series market analytics for tradeable virtual assets.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the local React dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(collection.router)
app.include_router(items.router)
app.include_router(categories.router)

# Serve the built React app, if it has been copied here.
#
# MUST come after all include_router calls: mounting at "/" catches
# everything not already matched, so any route registered afterwards
# would be shadowed by the static handler and 404.
#
# html=True makes unknown paths fall back to index.html, so a page
# refresh on a client-side route still loads the app.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")