
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.routes.baselines import router as baselines_router
from app.config import settings
from app.database import engine
from app.api.routes.events import router as events_router
from app.api.routes.anomalies import router as anomalies_router
from app.api.routes.alerts import router as alerts_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
app.include_router(anomalies_router)
app.include_router(events_router)
app.include_router(baselines_router)
app.include_router(alerts_router)

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
