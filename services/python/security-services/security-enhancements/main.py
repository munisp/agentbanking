import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.config import LOGGING_CONFIG

from config import settings
from router import router
from database import init_db
from service import ServiceException

# --- Logging Configuration ---

# Customize Uvicorn logging to be more concise
LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(levelprefix)s %(message)s"
LOGGING_CONFIG["formatters"]["access"]["fmt"] = '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Application Initialization ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="API Key Management Service for Security Enhancements.",
)

# --- Event Handlers ---

@app.on_event("startup")
async def startup_event():
    """Initializes the database connection and creates tables on startup."""
    logger.info("Application startup: Initializing database...")
    # This call is safe even if tables already exist
    init_db()
    logger.info("Application startup complete.")

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Handles custom service layer exceptions."""
    logger.error(f"Service Exception: {exc.message} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handles all other unhandled exceptions."""
    logger.exception(f"Unhandled Exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred."},
    )

# --- Router Inclusion ---

app.include_router(router)

# --- Root Endpoint (Optional) ---

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.VERSION}

# Example of how to run the application (for local development)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)