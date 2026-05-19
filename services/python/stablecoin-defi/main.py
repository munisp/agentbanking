from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import init_db
from router import router
from service import ServiceException

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Application Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url="/api/v1/openapi.json"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handler ---
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    logger.warning(f"Service Exception: {exc.name} - {exc.detail} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "name": exc.name},
    )

# --- Startup Event Handler ---
@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Application startup...")
    # Initialize database tables
    init_db()
    logger.info("Database initialized.")

# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def root() -> Dict[str, Any]:
    return {"message": "Welcome to the Stablecoin DeFi API", "version": settings.VERSION}

# --- Include Router ---
app.include_router(router)

# Example of how to run the application (for local development):
# uvicorn main:app --reload --host 0.0.0.0 --port 8000
