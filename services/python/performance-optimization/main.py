from typing import Any, Dict, List, Optional, Union, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from config import settings, logger
from database import engine
from models import Base
from router import router
from service import NotFoundError, IntegrityConstraintError

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


# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(

@app.get("/health")
async def health():
    return {"status": "ok", "service": "performance-optimization"}

    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="API for tracking performance metrics and managing optimization tasks."
)

# --- CORS Middleware ---
# In a real-world scenario, origins should be restricted
origins = [
    "*", # Allow all for development/demo
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> None:
    logger.warning(f"NotFoundError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": str(exc)},
    )

@app.exception_handler(IntegrityConstraintError)
async def integrity_constraint_exception_handler(request: Request, exc: IntegrityConstraintError) -> None:
    logger.error(f"IntegrityConstraintError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": str(exc)},
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> None:
    logger.error(f"SQLAlchemyError: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "A database error occurred."},
    )

# --- Root Endpoint ---

@app.get("/", tags=["health"])
async def root() -> Dict[str, Any]:
    return {"message": f"{settings.APP_NAME} is running", "version": settings.VERSION}

# --- Include Router ---
app.include_router(router)

# --- Logging Middleware (Optional but good practice) ---
@app.middleware("http")
async def log_requests(request: Request, call_next) -> None:
    logger.info(f"Incoming request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Outgoing response: {response.status_code}")
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
