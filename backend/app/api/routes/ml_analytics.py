from fastapi import APIRouter, HTTPException, Response

from app.schemas.ml_analytics import MLAnalyticsDemoResponse
from app.services.ml_analytics import run_ml_analytics_demo

router = APIRouter(prefix="/ml-analytics", tags=["Experimental ML Analytics"])


@router.get("/demo", response_model=MLAnalyticsDemoResponse)
def get_ml_analytics_demo(response: Response):
    """Compute a read-only demonstration using only the bundled synthetic fixture."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return run_ml_analytics_demo()
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="The bundled synthetic ML demonstration is temporarily unavailable.",
        ) from exc
