from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings, logger
from database import init_db
from routers import kyc_router

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


# Custom Exception for the service
class KYCServiceException(Exception):
    def __init__(self, name: str, status_code: int = status.HTTP_400_BAD_REQUEST, detail: str = None):
        self.name = name
        self.status_code = status_code
        self.detail = detail or f"An error occurred in the {name} service."

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting up {settings.PROJECT_NAME}...")
    
    # Initialize database (create tables if they don't exist)
    # In a real-world scenario, this might be handled by migrations (e.g., Alembic)
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Depending on the requirement, you might want to raise the exception or continue
        # For a production-ready app, a failed DB connection on startup is critical.
        # We'll log and continue for the sandbox environment.
        pass

    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API service for Compliance and Know Your Customer (KYC) operations.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should be restricted in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handler
@app.exception_handler(KYCServiceException)
async def kyc_service_exception_handler(request: Request, exc: KYCServiceException):
    logger.error(f"KYCServiceException caught: {exc.name} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail, "name": exc.name},
    )

# Include Routapp.include_router(kyc_router, prefix=settings.API_V1_STR, tags=["KYC Operations"])Root endpoint for health check
@app.get("/", status_code=status.HTTP_200_OK, include_in_schema=False)
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running."}

# The application is ready to be run with uvicorn:
# uvicorn main:app --reload