"""
government-integration - FastAPI microservice
Auto-generated main entry point
"""
import os
import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Government Integration Service",
    description="54agent Agency Banking Platform - government-integration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
try:
    from router import router
    app.include_router(router, prefix="/api/v1/government-integration")
    logger.info("Router loaded for government-integration")
except ImportError:
    logger.warning("No router found for government-integration, service running in base mode")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "government-integration", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"service": "government-integration", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8161))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
