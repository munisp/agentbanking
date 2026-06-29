import logging
from typing import Optional, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

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
        service: str = "support-comms-service",
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


class BadRequestError(ApiError):
    """BadRequestError"""

    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(
            message,
            status_code=400,
            code="SCS-VAL-3001",
            payload=payload,
        )


class NotFoundError(ApiError):
    """NotFoundError"""

    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(
            message,
            status_code=404,
            code="SCS-NOT-3004",
            payload=payload,
        )


class InternalApiError(ApiError):
    """Internal Api Error"""

    def __init__(self, message: str, payload: Optional[Any] = None):
        super().__init__(
            message,
            status_code=500,
            code="SCS-INT-5001",
            payload=payload,
        )


def handle_api_error(error: ApiError):
    """Handle API Errors"""
    logger.error("handle_api_error: %s", error.to_dict())
    return JSONResponse(content=error.to_dict(), status_code=error.status_code)


def handle_generic_error(error: Exception):
    """Handle generic error"""
    logger.error("caught a generic error: %s", str(error))
    response = {
        "message": "An unexpected error occurred",
        "status": "error",
        "error": type(error).__name__,
    }
    return JSONResponse(content=response, status_code=500)


def raise_http_exception_handler(status_code: int, message: str, code: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "status": "error",
            "code": code,
            "service": "support-comms-service",
        },
    )
