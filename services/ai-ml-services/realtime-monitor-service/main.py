"""
Main FastAPI Application
Nigerian Remittance Platform - Real-time Dashboard Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging

from api.endpoints import realtime_monitor, websocket_endpoint
from tasks.broadcast_tasks import broadcast_tasks
from db.session import engine
from db.base import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Nigerian Remittance Platform - Real-time Dashboard Backend")
    
    # Create database tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    # Start background tasks
    logger.info("Starting background broadcast tasks...")
    await broadcast_tasks.start()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop background tasks
    logger.info("Stopping background broadcast tasks...")
    await broadcast_tasks.stop()
    
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Nigerian Remittance Platform - Real-time Dashboard API",
    description="Real-time dashboard backend with WebSocket support for the Nigerian Remittance Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include routers
app.include_router(realtime_monitor.router)
app.include_router(websocket_endpoint.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Nigerian Remittance Platform - Real-time Dashboard API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/dashboard",
            "api": "/api/v1/realtime-monitor",
            "docs": "/docs",
            "health": "/api/v1/realtime-monitor/health"
        }
    }


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "service": "realtime-dashboard-backend"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
