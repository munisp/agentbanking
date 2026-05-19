from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from router import router
from config import settings, logger
from service import IntegrationServiceError

# --- Application Lifespan Events ---

@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    """
    Handles startup and shutdown events.
    """
    logger.info(f"Starting up {settings.APP_NAME}...")
    
    # 1. Initialize Database
    init_db()
    
    # 2. Add any other startup logic (e.g., connection pools, cache initialization)
    
    yield
    
    # 3. Shutdown logic (e.g., closing connections)
    logger.info(f"Shutting down {settings.APP_NAME}...")

# --- FastAPI Application Initialization ---

app = FastAPI(
    title=settings.APP_NAME,
    description="API service for managing third-party integrations and logging their activity.",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# --- Middleware ---

# 1. CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:8080",
    # Add other allowed origins in a production environment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For simplicity, allowing all origins. Should be restricted in production.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Custom Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Outgoing response: {response.status_code}")
    return response

# --- Global Exception Handlers ---

@app.exception_handler(IntegrationServiceError)
async def integration_service_exception_handler(request: Request, exc: IntegrationServiceError) -> None:
    """
    A catch-all handler for unhandled exceptions originating from the service layer.
    """
    logger.error(f"Unhandled IntegrationServiceError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected server error occurred.", "detail": str(exc)},
    )

# --- Include Routers ---

app.include_router(router)

# --- Root Endpoint ---

@app.get("/", tags=["Status"], summary="Service Health Check")
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.APP_NAME} is running successfully!"}

# --- Example of running the app (for local development) ---
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
