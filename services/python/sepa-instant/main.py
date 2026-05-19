from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db
from router import router
from service import ServiceException

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(settings.SERVICE_NAME)

# --- Application Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Handles startup and shutdown events.
    """
    # Startup: Initialize database
    logger.info("Application startup: Initializing database...")
    init_db()
    logger.info("Database initialization complete.")
    
    yield
    
    # Shutdown: Clean up resources (if any)
    logger.info("Application shutdown: Resources cleaned up.")

# --- FastAPI Application Instance ---
app = FastAPI(
    title=settings.SERVICE_NAME.replace('-', ' ').title(),
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
)

# --- Middleware ---

# 1. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# --- Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """
    Custom handler for business logic exceptions defined in service.py.
    """
    logger.error(f"Service Exception: {exc.message} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

# --- Routers ---

app.include_router(router)

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.VERSION,
        "status": "running",
        "database_url": settings.DATABASE_URL # For quick check, remove in production
    }

# To run the application:
# uvicorn main:app --reload
# or using the command line:
# python -m uvicorn main:app --reload