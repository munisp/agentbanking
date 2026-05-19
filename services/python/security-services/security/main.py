from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .config import settings
from .database import init_db
from .router import security_router
from .service import SecurityServiceException

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application startup and shutdown events.
    """
    logger.info("Application startup event triggered.")
    init_db()
    yield
    logger.info("Application shutdown event triggered.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception Handlers ---
@app.exception_handler(SecurityServiceException)
async def security_exception_handler(request: Request, exc: SecurityServiceException):
    """
    Custom exception handler for all business logic exceptions.
    """
    logger.warning(f"SecurityServiceException caught: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """
    Generic exception handler for unhandled exceptions.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "An unexpected error occurred."},
    )

# --- Routers ---
app.include_router(security_router, prefix=settings.API_V1_STR)

# --- Root Endpoint ---
@app.get("/", tags=["Status"])
async def root():
    """
    Root endpoint to check API status.
    """
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.VERSION}

logger.info(f"FastAPI application '{settings.PROJECT_NAME}' initialized.")
