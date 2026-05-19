import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import router, service
from .config import settings

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Application Initialization ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# --- Middleware ---

# CORS Middleware
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    # Add other allowed origins in a production environment
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Exception Handlers ---

@app.exception_handler(service.NotFoundException)
async def not_found_exception_handler(request: Request, exc: service.NotFoundException):
    logger.warning(f"Not Found Error: {exc.detail} for path {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": exc.detail},
    )

@app.exception_handler(service.ConflictException)
async def conflict_exception_handler(request: Request, exc: service.ConflictException):
    logger.warning(f"Conflict Error: {exc.detail} for path {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"message": exc.detail},
    )

@app.exception_handler(service.AuthenticationException)
async def authentication_exception_handler(request: Request, exc: service.AuthenticationException):
    logger.warning(f"Authentication Error: {exc.detail} for path {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"message": exc.detail},
        headers={"WWW-Authenticate": "Bearer"},
    )

# --- Router Inclusion ---

for api_router in router.all_routers:
    app.include_router(api_router)

# --- Root Endpoint ---

@app.get("/", tags=["root"])
def read_root():
    return {"message": f"{settings.PROJECT_NAME} API is running", "version": settings.VERSION}

# --- Startup Event ---

@app.on_event("startup")
async def startup_event():
    # NOTE: In a production environment, database migration tools (like Alembic)
    # should be used instead of `init_db()`. This is for demonstration/testing.
    # from .database import init_db
    # init_db()
    logger.info(f"{settings.PROJECT_NAME} starting up...")

# --- Shutdown Event ---

@app.on_event("shutdown")
def shutdown_event():
    logger.info(f"{settings.PROJECT_NAME} shutting down...")