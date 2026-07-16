"""
Monthly VAT return scheduler.
Runs on the 1st of each month to auto-generate (and optionally auto-file)
VAT returns for the prior month for all registered agents.
"""

import logging
from datetime import datetime, date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SessionLocal
from service import NigeriaVATService

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def run_monthly_vat_generation():
    """
    Auto-generates VAT returns for the previous month.
    Runs at 02:00 on the 1st of every month.
    """
    today = date.today()
    # Previous month
    if today.month == 1:
        year, month = today.year - 1, 12
    else:
        year, month = today.year, today.month - 1

    logger.info(f"[VAT Scheduler] Auto-generating returns for {year}-{month:02d}")

    db = SessionLocal()
    try:
        svc = NigeriaVATService(db)
        results = svc.auto_generate_for_period(year, month)
        generated = sum(1 for r in results if r.get("status") == "generated")
        filed = sum(1 for r in results if r.get("filed"))
        logger.info(
            f"[VAT Scheduler] {year}-{month:02d} complete: "
            f"{generated} generated, {filed} auto-filed, {len(results)} total entities"
        )
    except Exception as exc:
        logger.error(f"[VAT Scheduler] Monthly generation failed: {exc}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        run_monthly_vat_generation,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="monthly_vat_generation",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[VAT Scheduler] Started — monthly returns will auto-generate on the 1st at 02:00")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
