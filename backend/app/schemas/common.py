from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """에러 응답"""

    error: str
    message: str
    details: dict[str, Any] | None = None
