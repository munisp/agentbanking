"""
scheduler.py — APScheduler cron scheduler for CBN Automated Reporting Engine

Schedules all mandatory CBN report generation jobs:
  - Monthly Agent Banking Activity Report: 1st of each month at 06:00 UTC
  - Quarterly Fraud Incident Report: 1st day of Jan/Apr/Jul/Oct at 06:30 UTC
  - Annual KYC Compliance Report: 1st Jan at 07:00 UTC
  - SAR (Suspicious Activity Report): Every 4 hours (continuous monitoring)
  - Agent Network Expansion Report: 1st day of each quarter at 07:30 UTC
  - Daily reconciliation digest: Every day at 23:30 UTC

Usage:
  python scheduler.py               # Run scheduler standalone
  import scheduler; scheduler.start() # Embed in FastAPI lifespan
"""

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import requests

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
CBN_SERVICE_URL = os.getenv("CBN_SERVICE_URL", "http://localhost:8095")
INSTITUTION_CODE = os.getenv("CBN_INSTITUTION_CODE", "54agent001")
INSTITUTION_NAME = os.getenv("CBN_INSTITUTION_NAME", "54agent Agency Banking Platform")
CBN_SUBMISSION_URL = os.getenv("CBN_SUBMISSION_URL", "https://cbn-portal.gov.ng/api/v1/reports")
CBN_API_KEY = os.getenv("CBN_API_KEY", "")
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Africa/Lagos")  # WAT (UTC+1)
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")

# ── Job functions ─────────────────────────────────────────────────────────────

def _post_job(endpoint: str, payload: dict, job_name: str) -> bool:
    """POST a job trigger to the CBN service REST API."""
    try:
        resp = requests.post(
            f"{CBN_SERVICE_URL}{endpoint}",
            json=payload,
            timeout=300,  # 5-minute timeout for report generation
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        logger.info("[CBN Scheduler] %s completed: HTTP %d", job_name, resp.status_code)
        return True
    except requests.exceptions.RequestException as exc:
        logger.error("[CBN Scheduler] %s failed: %s", job_name, exc)
        _send_alert(f"CBN Scheduler: {job_name} failed", str(exc))
        return False


def _send_alert(title: str, detail: str) -> None:
    """Send a webhook alert on job failure."""
    if not ALERT_WEBHOOK_URL:
        return
    try:
        requests.post(
            ALERT_WEBHOOK_URL,
            json={"text": f":warning: *{title}*\n```{detail}```"},
            timeout=10,
        )
    except Exception:
        pass  # Alert failure must never crash the scheduler


def job_monthly_activity_report() -> None:
    """Generate CBN Monthly Agent Banking Activity Report.
    Runs on the 1st of each month at 06:00 WAT.
    Covers the previous calendar month.
    """
    now = datetime.now(tz=timezone.utc)
    # Report for the previous month
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month = first_of_this_month - timedelta(days=1)
    year, month = last_month.year, last_month.month

    logger.info("[CBN Scheduler] Generating monthly activity report for %d-%02d", year, month)
    _post_job(
        "/api/v1/reports/monthly-activity",
        {
            "year": year,
            "month": month,
            "institution_code": INSTITUTION_CODE,
            "institution_name": INSTITUTION_NAME,
            "auto_submit": True,
            "submission_url": CBN_SUBMISSION_URL,
            "api_key": CBN_API_KEY,
        },
        f"Monthly Activity Report {year}-{month:02d}",
    )


def job_quarterly_fraud_report() -> None:
    """Generate CBN Quarterly Fraud Incident Report.
    Runs on the 1st of Jan/Apr/Jul/Oct at 06:30 WAT.
    Covers the previous quarter.
    """
    now = datetime.now(tz=timezone.utc)
    current_month = now.month
    # Determine previous quarter
    if current_month in (1, 2, 3):
        # Q4 of previous year
        quarter, year = 4, now.year - 1
    elif current_month in (4, 5, 6):
        quarter, year = 1, now.year
    elif current_month in (7, 8, 9):
        quarter, year = 2, now.year
    else:
        quarter, year = 3, now.year

    logger.info("[CBN Scheduler] Generating quarterly fraud report for Q%d %d", quarter, year)
    _post_job(
        "/api/v1/reports/quarterly-fraud",
        {
            "year": year,
            "quarter": quarter,
            "institution_code": INSTITUTION_CODE,
            "institution_name": INSTITUTION_NAME,
            "auto_submit": True,
            "submission_url": CBN_SUBMISSION_URL,
            "api_key": CBN_API_KEY,
        },
        f"Quarterly Fraud Report Q{quarter} {year}",
    )


def job_annual_kyc_report() -> None:
    """Generate CBN Annual KYC Compliance Report.
    Runs on 1st January at 07:00 WAT.
    Covers the previous calendar year.
    """
    year = datetime.now(tz=timezone.utc).year - 1
    logger.info("[CBN Scheduler] Generating annual KYC report for %d", year)
    _post_job(
        "/api/v1/reports/annual-kyc",
        {
            "year": year,
            "institution_code": INSTITUTION_CODE,
            "institution_name": INSTITUTION_NAME,
            "auto_submit": True,
            "submission_url": CBN_SUBMISSION_URL,
            "api_key": CBN_API_KEY,
        },
        f"Annual KYC Report {year}",
    )


def job_sar_monitoring() -> None:
    """Continuous SAR (Suspicious Activity Report) monitoring.
    Runs every 4 hours. Detects transactions exceeding NGN 5M threshold.
    """
    logger.info("[CBN Scheduler] Running SAR monitoring sweep")
    _post_job(
        "/api/v1/reports/sar-sweep",
        {
            "lookback_hours": 4,
            "threshold_single_ngn": 5_000_000,
            "threshold_daily_ngn": 10_000_000,
            "institution_code": INSTITUTION_CODE,
            "auto_submit": True,
            "submission_url": CBN_SUBMISSION_URL,
            "api_key": CBN_API_KEY,
        },
        "SAR Monitoring Sweep",
    )


def job_network_expansion_report() -> None:
    """Generate CBN Agent Network Expansion Report.
    Runs on the 1st of each quarter at 07:30 WAT.
    """
    now = datetime.now(tz=timezone.utc)
    current_month = now.month
    if current_month in (1, 2, 3):
        quarter, year = 4, now.year - 1
    elif current_month in (4, 5, 6):
        quarter, year = 1, now.year
    elif current_month in (7, 8, 9):
        quarter, year = 2, now.year
    else:
        quarter, year = 3, now.year

    logger.info("[CBN Scheduler] Generating network expansion report for Q%d %d", quarter, year)
    _post_job(
        "/api/v1/reports/network-expansion",
        {
            "year": year,
            "quarter": quarter,
            "institution_code": INSTITUTION_CODE,
            "institution_name": INSTITUTION_NAME,
            "auto_submit": True,
            "submission_url": CBN_SUBMISSION_URL,
            "api_key": CBN_API_KEY,
        },
        f"Network Expansion Report Q{quarter} {year}",
    )


def job_daily_reconciliation() -> None:
    """Generate daily reconciliation digest.
    Runs every day at 23:30 WAT (22:30 UTC).
    """
    now = datetime.now(tz=timezone.utc)
    report_date = now.date().isoformat()
    logger.info("[CBN Scheduler] Generating daily reconciliation digest for %s", report_date)
    _post_job(
        "/api/v1/reports/daily-reconciliation",
        {
            "date": report_date,
            "institution_code": INSTITUTION_CODE,
        },
        f"Daily Reconciliation {report_date}",
    )


# ── Scheduler setup ───────────────────────────────────────────────────────────

def _on_job_error(event) -> None:
    """APScheduler error listener."""
    logger.error(
        "[CBN Scheduler] Job %s raised an exception: %s",
        event.job_id,
        event.exception,
    )
    _send_alert(f"CBN Scheduler job failed: {event.job_id}", str(event.exception))


def _on_job_executed(event) -> None:
    """APScheduler execution listener."""
    logger.info(
        "[CBN Scheduler] Job %s executed in %.2fs",
        event.job_id,
        event.retval if isinstance(event.retval, float) else 0,
    )


def create_scheduler(async_mode: bool = False) -> BackgroundScheduler:
    """Create and configure the APScheduler instance with all CBN jobs."""
    tz = SCHEDULER_TIMEZONE

    if async_mode:
        scheduler = AsyncIOScheduler(timezone=tz)
    else:
        scheduler = BackgroundScheduler(timezone=tz)

    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)

    # Monthly Activity Report — 1st of each month at 06:00 WAT
    scheduler.add_job(
        job_monthly_activity_report,
        CronTrigger(day=1, hour=6, minute=0, timezone=tz),
        id="cbn_monthly_activity",
        name="CBN Monthly Activity Report",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace
        coalesce=True,
    )

    # Quarterly Fraud Report — 1st of Jan/Apr/Jul/Oct at 06:30 WAT
    scheduler.add_job(
        job_quarterly_fraud_report,
        CronTrigger(month="1,4,7,10", day=1, hour=6, minute=30, timezone=tz),
        id="cbn_quarterly_fraud",
        name="CBN Quarterly Fraud Report",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    # Annual KYC Report — 1st January at 07:00 WAT
    scheduler.add_job(
        job_annual_kyc_report,
        CronTrigger(month=1, day=1, hour=7, minute=0, timezone=tz),
        id="cbn_annual_kyc",
        name="CBN Annual KYC Report",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    # SAR Monitoring — every 4 hours
    scheduler.add_job(
        job_sar_monitoring,
        IntervalTrigger(hours=4),
        id="cbn_sar_monitoring",
        name="CBN SAR Monitoring",
        replace_existing=True,
        misfire_grace_time=600,  # 10 min grace
        coalesce=True,
    )

    # Network Expansion Report — 1st of each quarter at 07:30 WAT
    scheduler.add_job(
        job_network_expansion_report,
        CronTrigger(month="1,4,7,10", day=1, hour=7, minute=30, timezone=tz),
        id="cbn_network_expansion",
        name="CBN Network Expansion Report",
        replace_existing=True,
        misfire_grace_time=3600,
        coalesce=True,
    )

    # Daily Reconciliation — every day at 23:30 WAT (22:30 UTC)
    scheduler.add_job(
        job_daily_reconciliation,
        CronTrigger(hour=22, minute=30, timezone="UTC"),
        id="cbn_daily_reconciliation",
        name="CBN Daily Reconciliation",
        replace_existing=True,
        misfire_grace_time=1800,
        coalesce=True,
    )

    logger.info("[CBN Scheduler] Scheduler configured with %d jobs", len(scheduler.get_jobs()))
    return scheduler


# ── Singleton scheduler ───────────────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None


def start(async_mode: bool = False) -> BackgroundScheduler:
    """Start the CBN reporting scheduler (idempotent)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.info("[CBN Scheduler] Already running")
        return _scheduler

    _scheduler = create_scheduler(async_mode=async_mode)
    _scheduler.start()
    logger.info("[CBN Scheduler] Started. Next runs:")
    for job in _scheduler.get_jobs():
        logger.info("  %-35s → %s", job.name, job.next_run_time)
    return _scheduler


def stop() -> None:
    """Gracefully stop the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("[CBN Scheduler] Stopped.")
    _scheduler = None


# ── Standalone entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import signal
    import time

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    logger.info("[CBN Scheduler] Starting standalone scheduler...")
    logger.info("[CBN Scheduler] Service URL: %s", CBN_SERVICE_URL)
    logger.info("[CBN Scheduler] Institution: %s (%s)", INSTITUTION_NAME, INSTITUTION_CODE)

    sched = start()

    def _handle_signal(signum, frame):
        logger.info("[CBN Scheduler] Received signal %d — shutting down", signum)
        stop()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("[CBN Scheduler] Running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        stop()
