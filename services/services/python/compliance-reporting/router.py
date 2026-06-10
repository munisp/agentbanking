"""
Router for compliance-reporting service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/compliance-reporting", tags=["compliance-reporting"])

@router.post("/reports/generate")
async def generate_report(
    report_type: ReportType,
    period_start: datetime,
    period_end: datetime,
    background_tasks: BackgroundTasks
):
    return {"status": "ok"}

@router.get("/reports")
async def list_reports(
    report_type: Optional[ReportType] = None,
    status: Optional[ReportStatus] = None,
    limit: int = 50
):
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

