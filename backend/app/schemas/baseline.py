
from typing import Any

from pydantic import BaseModel


class BaselineResponse(BaseModel):
    user_id: str
    baseline: dict[str, Any]
    status: str
