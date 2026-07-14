"""
Router for loan-management service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/loan-management", tags=["loan-management"])

@router.post("/applications")
async def apply_for_loan(application: LoanApplication):
    return {"status": "ok"}

@router.get("/loans/{loan_id}")
async def get_loan(loan_id: str):
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

