from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ai_assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantStatusResponse,
)
from app.services.ai_soc_assistant import (
    AssistantUnavailable,
    assistant_status,
    run_assistant_chat,
)

router = APIRouter(prefix="/ai-assistant", tags=["AI SOC Assistant"])


@router.get("/status", response_model=AssistantStatusResponse)
def get_assistant_status(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return assistant_status()


@router.post("/chat", response_model=AssistantChatResponse)
def chat_with_assistant(
    payload: AssistantChatRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        return run_assistant_chat(db, payload)
    except AssistantUnavailable as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
