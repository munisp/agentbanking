from typing import Any, Dict, List, Optional, Union, Tuple

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from config import settings
from database import init_db
from router import router
from exceptions import NotFoundException, AlreadyExistsException, ServiceException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Context manager for application startup and shutdown events.
    """
    # Startup: Initialize database
    logger.info("Application startup: Initializing database...")
    init_db()
    yield
    # Shutdown: Clean up resources if necessary
    logger.info("Application shutdown: Resources released.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    version="1.0.0",
    description="API for managing AI Models and Experiments in an AI Platform.",
    lifespan=lifespan
)

# --- Middleware ---

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Exception Handlers ---

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> None:
    logger.warning(f"NotFoundException: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(AlreadyExistsException)
async def already_exists_exception_handler(request: Request, exc: AlreadyExistsException) -> None:
    logger.warning(f"AlreadyExistsException: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    logger.error(f"ServiceException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> None:
    logger.error(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected error occurred."},
    )

# --- Routers ---

app.include_router(router, prefix=settings.API_V1_STR, tags=["ai-platform"])

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": "AI Platform Service is running."}

if __name__ == "__main__":
    # Note: In a production environment, you would typically use a process manager
    # like Gunicorn to run the application. This is for local development/testing.
    uvicorn.run(app, host="0.0.0.0", port=8000)
