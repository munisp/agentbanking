"""
POS Shell Configuration Service — Entry Point
"""

import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router import router
from service import POSShellConfigService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instance
pos_shell_service: POSShellConfigService = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pos_shell_service

    # Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=False)

    # Kafka (optional — graceful degradation if unavailable)
    kafka_producer = None
    kafka_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    if kafka_servers:
        try:
            kafka_producer = AIOKafkaProducer(bootstrap_servers=kafka_servers)
            await kafka_producer.start()
            logger.info("Kafka producer connected")
        except Exception as e:
            logger.warning(f"Kafka unavailable, running without event broadcasting: {e}")

    pos_shell_service = POSShellConfigService(redis_client, kafka_producer)
    logger.info("POS Shell Config Service started")

    yield

    # Cleanup
    await redis_client.close()
    if kafka_producer:
        await kafka_producer.stop()


app = FastAPI(
    title="POS Shell Configuration Service",
    description="Manages tile layout configurations for Android POS home screens",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pos-shell-config"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
