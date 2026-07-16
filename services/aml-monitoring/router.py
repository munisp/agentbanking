"""
Router for aml-monitoring service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/aml-monitoring", tags=["aml-monitoring"])

@router.post("/monitor")
async def monitor_transaction(
    transaction: TransactionMonitor,
    background_tasks: BackgroundTasks
):
    return {"status": "ok"}

@router.get("/alerts")
async def list_alerts(
    risk_level: Optional[RiskLevel] = None,
    reviewed: Optional[bool] = None,
    limit: int = 50
):
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

