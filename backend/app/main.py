
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.routes.baselines import router as baselines_router
from app.config import settings
from app.database import engine
from app.api.routes.events import router as events_router

app = FastAPI(title=settings.app_name)

app.include_router(events_router)
app.include_router(baselines_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ueba-backend",
        "environment": settings.environment,
    }


@app.get("/health/db")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"status": "ok", "database": "connected"}

    except SQLAlchemyError:
        return {"status": "error", "database": "disconnected"}
