import logging
from typing import Optional, Any
from pydantic import ValidationError
from fastapi.responses import JSONResponse
from fastapi import HTTPException


logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base class for an Api Error"""

    status_code: int
    code: Optional[str]
    message: str
    payload: Optional[Any]

    def __init__(
        self,
        message: str,
        status_code: int,
        code: str,
        payload: Optional[Any] = None,
        service: str = "auth-service",
    ):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.code = code
        self.payload = payload
        self.service = service

    def to_dict(self):
        error_data = dict(self.payload or {})
        error_data["message"] = self.message
        error_data["status"] = "error"
        error_data["code"] = self.code
        error_data["service"] = self.service
        return error_data


class InvalidUpline(ApiError):
    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(
            message,
            status_code=400,
            code="AUTH-AUTH-INV-3003",  # pick your code
            payload=payload,
        )

    def to_dict(self):
        super_error_data = super().to_dict()
        super_error_data["type"] = "InvalidUpline"
        return super_error_data


class UserAlreadyExistException(ApiError):
    def __init__(self, message: Optional[str]):
        super().__init__(
            message or "User already exist",
            status_code=409,
            code="AUTH-AUTH-CONF-3002",
        )

    def to_dict(self):
        super_error_data = super().to_dict()
        super_error_data["type"] = "UserAlreadyExist"
        return super_error_data


class BadRequestError(ApiError):
    """BadRequestError"""

    message: str
    payload: Optional[Any]

    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(
            message,
            status_code=400,
            code="AUTH-AUTH-VAL-3001",
            payload=payload,
        )


class InternalApiError(ApiError):
    """Internal Api Error"""

    message: str
    payload: Optional[Any]

    def __init__(self, message: str, payload: Optional[Any] = None, code: int = 500):
        super().__init__(
            message,
            status_code=code,
            code="AUTH-AUTH-INT-5001",
            payload=payload,
        )


class InvalidInputError(ApiError):
    """InvalidInputError"""

    message: str
    payload: Optional[Any]

    def __init__(self, messages: list[str] | list | dict):
        message = validation_messages_to_string(messages)
        super().__init__(
            message,
            status_code=422,
            code="AUTH-AUTH-VAL-3004",
        )


def handle_input_validation_error(error: ValidationError):
    """Handle Input Validation Error"""
    return handle_api_error(InvalidInputError(error.messages))


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


def raise_http_exception_handler(status_code: int, message: str, code: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "status": "error",
            "code": code,
            "service": "auth-service",
        },
    )


def api_error_to_http(error: ApiError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail=error.to_dict(),
    )
