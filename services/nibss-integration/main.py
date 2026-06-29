from typing import Any, Dict, List, Optional, Union, Tuple

import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings
from database import init_db, populate_banks, SessionLocal
from router import router
from service import ServiceException

# --- 1. Logging Setup ---

# Configure root logger
logging.basicConfig(level=settings.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. Application Initialization ---

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    description="FastAPI service for NIBSS Instant Payment (NIP) and Name Enquiry integration."
)

# --- 3. Middleware ---

# CORS Middleware
# In a production environment, you would restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- 4. Custom Exception Handler ---

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException) -> None:
    """
    Handles custom ServiceException errors and returns a clean JSON response.
    """
    logger.error(f"Service Exception: {exc.message} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )

# --- 5. Startup Event ---

@app.on_event("startup")
def on_startup() -> None:
    """
    Initializes the database and populates initial data on application startup.
    """
    logger.info("Application startup: Initializing database...")
    init_db()
    
    # Populate banks if running in a development environment
    if settings.DEBUG:
        db = SessionLocal()
        try:
            populate_banks(db)
        finally:
            db.close()
    
    logger.info("Database initialization complete.")

# --- 6. Include Router ---

app.include_router(router)

# --- 7. Root Endpoint (Optional Health Check) ---

@app.get("/", tags=["Health"])
def read_root() -> Dict[str, Any]:
    return {"message": f"{settings.PROJECT_NAME} is running", "version": settings.VERSION}

# --- 8. Run Application (for local development) ---

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
