from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.alert import Alert
from app.models.analyst_feedback import AnalystFeedback
from app.models.security_event import SecurityEvent
from app.models.user_profile import UserProfile


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(test_db) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def alert_id(test_db) -> str:
    alert_id = uuid4()

    with test_db() as db:
        db.add(
            Alert(
                id=alert_id,
                title="Test alert",
                severity="medium",
                risk_score=45,
                status="open",
                explanation="Test explanation",
                evidence={},
            )
        )
        db.commit()

    return str(alert_id)


def test_create_and_list_feedback(client: TestClient, alert_id: str) -> None:
    payload = {
        "analyst_id": "analyst-demo",
        "verdict": "true_positive",
        "comment": "Suspicious activity confirmed.",
    }

    create_response = client.post(
        f"/alerts/{alert_id}/feedback",
        json=payload,
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["analyst_id"] == "analyst-demo"
    assert created["verdict"] == "true_positive"
    assert created["comment"] == "Suspicious activity confirmed."

    list_response = client.get(f"/alerts/{alert_id}/feedback")

    assert list_response.status_code == 200, list_response.text
    body = list_response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == created["id"]


def test_invalid_verdict_is_rejected(
    client: TestClient,
    alert_id: str,
) -> None:
    response = client.post(
        f"/alerts/{alert_id}/feedback",
        json={
            "analyst_id": "analyst-demo",
            "verdict": "suspicious",
            "comment": "Invalid verdict",
        },
    )

    assert response.status_code == 422, response.text


def test_feedback_for_missing_alert_returns_404(
    client: TestClient,
) -> None:
    response = client.post(
        f"/alerts/{uuid4()}/feedback",
        json={
            "analyst_id": "analyst-demo",
            "verdict": "benign",
        },
    )

    assert response.status_code == 404


def test_listing_feedback_for_missing_alert_returns_404(
    client: TestClient,
) -> None:
    response = client.get(f"/alerts/{uuid4()}/feedback")

    assert response.status_code == 404
