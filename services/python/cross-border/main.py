from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import init_db
from router import router

# --- Configuration and Logging ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Application Initialization ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="API for managing Cross-Border Payments, Parties, and FX Rates.",
)

# --- Event Handlers ---

@app.on_event("startup")
async def startup_event() -> None:
    """Initializes the database on application startup."""
    logger.info("Application startup: Initializing database...")
    init_db()
    logger.info("Application startup complete.")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Performs cleanup on application shutdown."""
    logger.info("Application shutdown: Cleanup complete.")

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    """Logs incoming requests and outgoing responses."""
    logger.info(f"Incoming Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Outgoing Response: {request.method} {request.url} - Status {response.status_code}")
    return response

# --- Exception Handlers ---

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> None:
    """Handles Pydantic validation errors."""
    logger.error(f"Validation Error: {exc.errors()} for request {request.url}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> None:
    """Handles standard FastAPI/Starlette HTTP exceptions."""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail} for request {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> None:
    """Handles all unhandled exceptions."""
    logger.critical(f"Unhandled Exception: {type(exc).__name__} - {exc} for request {request.url}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error. Please contact support."},
    )

# --- Include Routers ---

app.include_router(router)

# --- Root Endpoint ---

@app.get("/", tags=["health"])
async def root() -> Dict[str, Any]:
    """Health check endpoint."""
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.VERSION}