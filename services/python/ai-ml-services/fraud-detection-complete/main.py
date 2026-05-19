import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from .config import settings
from .database import init_db
from .router import router
from .service import ItemNotFound, DuplicateItem, ServiceException

# Configure logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO) # Corrected logging level setting

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events.
    """
    # Startup: Initialize the database
    log.info("Application startup: Initializing database...")
    await init_db()
    log.info("Database initialized.")
    
    yield
    
    # Shutdown: Clean up resources if necessary
    log.info("Application shutdown.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# --- Middleware ---

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Exception Handlers ---

@app.exception_handler(ItemNotFound)
async def item_not_found_exception_handler(request: Request, exc: ItemNotFound):
    log.warning(f"Item Not Found: {exc.model_name} with ID {exc.item_id} not found.")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )

@app.exception_handler(DuplicateItem)
async def duplicate_item_exception_handler(request: Request, exc: DuplicateItem):
    log.warning(f"Duplicate Item: {exc.model_name} - {exc.field}='{exc.value}' already exists.")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    log.error(f"Service Exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected service error occurred."},
    )

# --- Include Routers ---

app.include_router(router)

# --- Root Endpoint ---

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.VERSION}