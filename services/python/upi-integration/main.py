from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from datetime import datetime

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from router import router
from schemas import HealthCheck
from service import NotFoundException, ConflictException, PaymentGatewayException

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- Application Initialization ---
app = FastAPI(
    title=f"{settings.SERVICE_NAME.upper()} API",
    description="API service for managing UPI transaction integration and webhooks.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Event Handlers ---

@app.on_event("startup")
async def startup_event() -> None:
    """Initializes the database on application startup."""
    logger.info(f"Starting up {settings.SERVICE_NAME} service...")
    init_db()
    logger.info("Database initialized.")

@app.on_event("shutdown")
def shutdown_event() -> None:
    """Logs shutdown event."""
    logger.info(f"Shutting down {settings.SERVICE_NAME} service...")

# --- Middleware ---

# CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:8000",
    # Add other allowed origins in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for simplicity, restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    """Logs incoming requests."""
    start_time = datetime.now()
    response = await call_next(request)
    process_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Request: {request.method} {request.url.path} | Status: {response.status_code} | Time: {process_time:.4f}s")
    return response

# --- Exception Handlers ---

@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException) -> None:
    """Handles custom NotFoundException."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(ConflictException)
async def conflict_exception_handler(request: Request, exc: ConflictException) -> None:
    """Handles custom ConflictException."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(PaymentGatewayException)
async def pg_exception_handler(request: Request, exc: PaymentGatewayException) -> None:
    """Handles custom PaymentGatewayException."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

# --- Root and Health Check Endpoints ---

@app.get("/", response_model=HealthCheck, summary="Health Check")
def health_check() -> None:
    """Returns the health status of the service."""
    return HealthCheck(timestamp=datetime.utcnow())

# --- Include Router ---
app.include_router(router)

# Example of how to run the application (for documentation purposes)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)