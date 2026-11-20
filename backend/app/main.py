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
from app.routes.admin_users import router as admin_users_router
from app.routes.participations import router as participations_router
from app.routes.payments import router as payments_router
from app.routes.rewards import router as rewards_router
from app.routes.questions import router as questions_router
from app.routes.question_bank import router as question_bank_router
from app.routes.surveys import router as surveys_router
from app.routes.subscriptions import router as subscriptions_router
from app.routes.wallet import router as wallet_router
from app.routes.withdrawals import router as withdrawals_router
from app.routes.notifications import router as notifications_router
from app.routes.categories import router as categories_router

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
app.include_router(admin_users_router)
app.include_router(participations_router)
app.include_router(questions_router)
app.include_router(question_bank_router)
app.include_router(surveys_router)
app.include_router(subscriptions_router)
app.include_router(payments_router)
app.include_router(wallet_router)
app.include_router(rewards_router)
app.include_router(withdrawals_router)
app.include_router(notifications_router)
app.include_router(categories_router)


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
