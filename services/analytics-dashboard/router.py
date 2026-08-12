"""
Router for analytics-dashboard service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs
returning fabricated {"status": "ok"} responses that SHADOW the real,
database-backed (and JWT-protected) endpoints in
services/analytics-dashboard/main.py. The /token stub was especially
dangerous: it impersonated the real JWT login endpoint (an auth bypass).
Until this stub is removed from every registration site, all endpoints fail
loudly with 501 Not Implemented. Do NOT re-add ok-fabricating handlers here.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/analytics-dashboard", tags=["analytics-dashboard"])

_STUB_DETAIL = (
    "analytics-dashboard stub endpoint disabled: use the real implementation "
    "in services/analytics-dashboard/main.py"
)


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; real API is in main.py"}


@router.post("/token")
async def login_for_access_token():
    # AUTH-BYPASS FIX: this stub previously returned {"status": "ok"} while
    # shadowing the real JWT-issuing /token endpoint in main.py. It now fails
    # loudly; tokens are only issued by the real implementation.
    _not_implemented()


@router.post("/user-activities/")
def create_user_activity():
    _not_implemented()


@router.get("/user-activities/")
def read_user_activities():
    _not_implemented()


@router.get("/user-activities/{activity_id}")
def read_user_activity(activity_id: int):
    _not_implemented()


@router.post("/transactions/")
def create_transaction():
    _not_implemented()


@router.get("/transactions/")
def read_transactions():
    _not_implemented()


@router.get("/transactions/{transaction_id}")
def read_transaction(transaction_id: int):
    _not_implemented()


@router.post("/metrics/")
def create_metric():
    _not_implemented()


@router.get("/metrics/")
def read_metrics():
    _not_implemented()


@router.get("/metrics/{metric_id}")
def read_metric(metric_id: int):
    _not_implemented()


@router.post("/alerts/")
def create_alert():
    _not_implemented()


@router.get("/alerts/")
def read_alerts():
    _not_implemented()


@router.get("/alerts/{alert_id}")
def read_alert(alert_id: int):
    _not_implemented()
