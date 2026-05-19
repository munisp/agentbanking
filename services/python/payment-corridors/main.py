from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from . import router
from .config import settings
from .database import init_db
from .service import NotFoundError, ConflictError

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
    logger.info("Database initialized.")
    yield
    # Shutdown: No specific shutdown tasks for this simple service
    logger.info("Application shutdown.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# --- Middleware ---

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Custom Exception Handlers ---

@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> None:
    logger.warning(f"NotFoundError: {exc.detail} for request {request.url}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> None:
    logger.warning(f"ConflictError: {exc.detail} for request {request.url}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

# --- API Routes ---

app.include_router(router.router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    return {"message": f"{settings.PROJECT_NAME} is running!"}

# Example of how to run the app (for documentation purposes, not executed here)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
