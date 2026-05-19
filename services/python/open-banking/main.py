from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging

from config import settings
from router import router
from service import NotFoundException, ConflictException, UnauthorizedException, ForbiddenException

log = logging.getLogger(__name__)

# --- Application Setup ---
app = FastAPI(
    title=settings.SERVICE_NAME,
    version=settings.VERSION,
    description="A production-ready Open Banking API built with FastAPI and SQLAlchemy.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS Middleware ---
# Allows all origins for development. Restrict this in production.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> None:
    log.warning(f"NotFoundException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(ConflictException)
async def conflict_exception_handler(request: Request, exc: ConflictException) -> None:
    log.warning(f"ConflictException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException) -> None:
    log.warning(f"UnauthorizedException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.detail},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException) -> None:
    log.warning(f"ForbiddenException: {exc.detail} for URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"message": exc.detail},
    )

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.SERVICE_NAME} API is running", "version": settings.VERSION}

# --- Include Router ---
app.include_router(router)

# --- Database Initialization (Optional, for quick setup) ---
# In a real production environment, migrations (e.g., Alembic) would be used.
# This is included for a complete, runnable example.
@app.on_event("startup")
async def startup_event() -> None:
    log.info("Application startup...")
    try:
        from database import engine, Base
        async with engine.begin() as conn:
            # Create all tables if they don't exist
            # This is a development-only feature. Use Alembic for production migrations.
            await conn.run_sync(Base.metadata.create_all)
        log.info("Database tables checked/created successfully.")
    except Exception as e:
        log.error(f"Failed to connect to or initialize database: {e}")
        # In a real app, you might want to raise an exception to prevent startup

# --- Main Execution Block (for local development) ---
if __name__ == "__main__":
    import uvicorn
    log.info("Starting Uvicorn server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )