"""FastAPI application entry point.

Phase 1 exposes only a health endpoint. Auth, surveys, and admin routes are
added in later phases.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine
from app.routes.auth import router as auth_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if the database is unreachable.
    with engine.connect() as connection:
        connection.exec_driver_sql("SELECT 1")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Survey platform API. Phase 1 skeleton.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
