"""
FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401 — ensures models are registered on Base
from app.database import Base, engine
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist yet. Fine for early development;
    # a real migration tool (Alembic) replaces this once the schema
    # stabilizes and we need versioned migrations.
    Base.metadata.create_all(bind=engine)
    yield


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
