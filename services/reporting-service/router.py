"""
Router for reporting-service service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses and referenced undefined names
(ReportRequest/ReportType/Query/Optional), so they could not even be imported.
The REAL reporting API lives in services/reporting-service/main.py under
/api/v1/reports/*. This stub must never shadow it; until this router is
removed from every registration site, all endpoints fail loudly with
501 Not Implemented instead of fabricating success.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/reporting-service", tags=["reporting-service"])

_STUB_DETAIL = (
    "reporting-service stub endpoint disabled: use the real reporting API in "
    "services/reporting-service/main.py (/api/v1/reports/*)"
)


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.post("/reports/generate")
async def generate_report():
    _not_implemented()


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    _not_implemented()


@router.get("/reports")
async def list_reports():
    _not_implemented()


@router.delete("/reports/{report_id}")
async def delete_report(report_id: str):
    _not_implemented()


@router.get("/health")
async def health():
    return {"status": "ok", "note": "stub router only; real reporting API is in main.py at /api/v1/reports/*"}
