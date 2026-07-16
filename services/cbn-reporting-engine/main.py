"""
main.py — CBN Automated Reporting Engine FastAPI application
Wires together the FastAPI app, database, and APScheduler cron jobs.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from router import router
from models import Base
from config import engine
import scheduler as cbn_scheduler

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on startup, stop on shutdown."""
    logger.info("[CBN] Starting CBN Reporting Engine...")
    try:
        Base.metadata.create_all(bind=engine)
    except IntegrityError:
        logger.info("[CBN] Tables already exist, skipping schema creation")
    sched = cbn_scheduler.start(async_mode=False)
    logger.info("[CBN] APScheduler started with %d jobs", len(sched.get_jobs()))
    yield
    logger.info("[CBN] Shutting down CBN Reporting Engine...")
    cbn_scheduler.stop()
    logger.info("[CBN] APScheduler stopped.")


app = FastAPI(
    title="CBN Automated Reporting Engine",
    version="2.0.0",
    description=(
        "Generates and submits all mandatory CBN reports: "
        "Monthly Activity, Quarterly Fraud, Annual KYC, SAR, Network Expansion."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health_check():
    """Liveness probe."""
    sched = cbn_scheduler._scheduler
    return {
        "status": "ok",
        "service": "cbn-reporting-engine",
        "scheduler": {
            "running": sched.running if sched else False,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in (sched.get_jobs() if sched else [])
            ],
        },
    }
