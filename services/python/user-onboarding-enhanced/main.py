from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import settings
from database import init_db
from router import router as onboarding_router # Assuming router.py will define a router named 'router'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database tables
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="FastAPI service for Enhanced User Onboarding with KYC and Document Verification.",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handler (Example) ---
class UserOnboardingException(Exception):
    def __init__(self, name: str, status_code: int, detail: str) -> None:
        self.name = name
        self.status_code = status_code
        self.detail = detail

@app.exception_handler(UserOnboardingException)
async def custom_exception_handler(request: Request, exc: UserOnboardingException) -> None:
    logger.error(f"Custom Exception: {exc.name} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail, "name": exc.name},
    )

# --- Root Endpoint ---
@app.get("/", tags=["Health Check"])
def read_root() -> Dict[str, Any]:
    return {"message": "User Onboarding Enhanced Service is running."}

# --- Include Routers ---
app.include_router(onboarding_router, prefix="/api/v1/onboarding", tags=["Onboarding"])

# --- Startup/Shutdown Events ---
@app.on_event("startup")
async def startup_event() -> None:
    logger.info(f"{settings.PROJECT_NAME} starting up...")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info(f"{settings.PROJECT_NAME} shutting down...")

# Note: In a real application, we would also add authentication middleware here.
# For this task, we will handle authentication logic within the service/router layer.