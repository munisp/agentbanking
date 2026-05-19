import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import init_db
from .router import router
from .service import ServiceException
from .schemas import APIExceptionSchema

# --- Logging Setup ---
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="A production-ready white-label API for identity verification (KYC/KYB).",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Event Handlers ---
@app.on_event("startup")
async def startup_event():
    """Initializes the database on application startup."""
    logger.info("Application startup: Initializing database.")
    # NOTE: In a production environment, this should be replaced with a proper migration tool (e.g., Alembic)
    # and only run if the database is empty or needs initial setup.
    init_db()
    logger.info("Database initialization complete.")

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---
@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Handles custom service exceptions and returns a standardized JSON response."""
    logger.error(f"Service Exception caught: {exc.code} - {exc.detail}", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content=APIExceptionSchema(detail=exc.detail, code=exc.code).model_dump(),
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handles all unhandled exceptions."""
    logger.critical(f"Unhandled Exception caught: {type(exc).__name__} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=APIExceptionSchema(
            detail="An unexpected error occurred on the server.",
            code="INTERNAL_SERVER_ERROR"
        ).model_dump(),
    )

# --- Include Router ---
app.include_router(router)

# --- Root Endpoint ---
@app.get("/", tags=["health"])
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.PROJECT_VERSION}