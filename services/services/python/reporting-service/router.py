"""
Router for reporting-service service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/reporting-service", tags=["reporting-service"])

@router.post("/reports/generate")
async def generate_report(request: ReportRequest):
    return {"status": "ok"}

@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    return {"status": "ok"}

@router.get("/reports")
async def list_reports(
    report_type: Optional[ReportType] = None,
    start_date: Optional[str] = None,
    limit: int = Query(10, le=100)):
    return {"status": "ok"}

@router.delete("/reports/{report_id}")
async def delete_report(report_id: str):
    return {"status": "ok"}

@router.get("/health")
async def health():
    return {"status": "ok"}

