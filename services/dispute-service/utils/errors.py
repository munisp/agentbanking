import logging
from typing import Optional, Any
from pydantic import ValidationError
from fastapi.responses import JSONResponse


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for an Api Error"""

    status_code: int
    message: str
    payload: Optional[Any]

    def __init__(self, message: str, status_code: int, payload: Optional[Any] = None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        error_data = dict(self.payload or {})
        error_data["message"] = self.message
        error_data["status"] = "error"
        return error_data


class BadRequestError(ApiError):
    """BadRequestError"""

    message: str
    payload: Optional[Any]

    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(message, 400, payload)


class InternalApiError(ApiError):
    """Internal Api Error"""

    message: str
    payload: Optional[Any]

    def __init__(self, message: str, payload: Optional[Any] = None, code: int = 500):
        super().__init__(message, code, payload)


class InvalidInputError(ApiError):
    """InvalidInputError"""

    message: str
    payload: Optional[Any]

    def __init__(self, messages: list[str] | list | dict):
        message = validation_messages_to_string(messages)
        super().__init__(message, 422)


def handle_api_error(error: ApiError):
    """Handle API Errors"""

    logger.error("handle_api_error")
    logger.error("error status: %s", error.to_dict())
    return JSONResponse(content=error.to_dict(), status_code=error.status_code)


def handle_generic_error(error: Exception):
    """Handle generic error"""

    logger.error("caught a generic error")
    response = {
        "message": "An unexpected error occurred",
        "status": "error",
        "error": type(error).__name__,
    }
    return JSONResponse(content=response, status_code=500)

def validation_messages_to_string(messages):
    """Convert Validation Messages to readable string"""

    if isinstance(messages, dict):
        # Flatten dictionary values
        return "; ".join(
            f"{field}: {', '.join(msgs)}" for field, msgs in messages.items()
        )

    if isinstance(messages, list):
        # Join list of messages
        return "; ".join(messages)

    # Handle unexpected cases
    return str(messages)