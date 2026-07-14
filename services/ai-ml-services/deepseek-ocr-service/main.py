"""
DeepSeek-OCR Service
Main FastAPI application for document verification
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from router import router
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="DeepSeek-OCR Document Verification Service",
    description="AI-powered document verification using DeepSeek-OCR for KYC",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info("DeepSeek-OCR service starting up...")
    logger.info("Service ready to accept requests")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("DeepSeek-OCR service shutting down...")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "DeepSeek-OCR Document Verification",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "deepseek-ocr"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
