from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from config import settings
from router import stablecoin_router, account_router, transaction_router
from service import ServiceException

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Application Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG
)

# --- CORS Middleware ---
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Global Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """Handles custom service exceptions."""
    logger.error(f"Service Exception: {exc.detail} at {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> None:
    """Handles Pydantic validation errors."""
    logger.error(f"Validation Error: {exc.errors()} at {request.url}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation Error", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> None:
    """Handles all other unhandled exceptions."""
    logger.exception(f"Unhandled Exception: {exc} at {request.url}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )

# --- API Routers ---
app.include_router(stablecoin_router, prefix=settings.API_V1_STR)
app.include_router(account_router, prefix=settings.API_V1_STR)
app.include_router(transaction_router, prefix=settings.API_V1_STR)

# --- Root Endpoint ---
@app.get("/", tags=["Status"])
def read_root() -> Dict[str, Any]:
    return {"message": f"{settings.PROJECT_NAME} is running", "version": "1.0.0"}

# --- Startup Event (Optional, but good practice for DB init) ---
@app.on_event("startup")
async def startup_event() -> None:
    # In a production environment, this should be handled by a migration tool (e.g., Alembic)
    # For this example, we'll ensure the database is initialized if in debug mode.
    if settings.DEBUG:
        from database import init_db
        init_db()
        logger.info("Database initialized (if in DEBUG mode).")

# To run the application:
# uvicorn main:app --reload --host 0.0.0.0 --port 8000