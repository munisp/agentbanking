"""
NIBSS Integration API Endpoints
"""
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from service import NIBSSService, get_nibss_service
from models import Bank
from schemas import NameEnquiryRequest

router = APIRouter(prefix="/api/nibss", tags=["nibss"])

class AccountVerificationRequest(BaseModel):
    account_number: str
    bank_code: str

class AccountVerificationResponse(BaseModel):
    success: bool
    account_name: str
    account_number: str
    bank_name: str
    verified: bool

@router.post("/verify-account", response_model=AccountVerificationResponse)
async def verify_account(data: AccountVerificationRequest):
    """Verify Nigerian bank account via NIBSS."""
    # Mock NIBSS Name Enquiry API call
    # In production, integrate with actual NIBSS API

    bank_names = {
        "058": "Guaranty Trust Bank",
        "044": "Access Bank",
        "033": "United Bank for Africa"
    }

    return {
        "success": True,
        "account_name": "JOHN DOE",
        "account_number": data.account_number,
        "bank_name": bank_names.get(data.bank_code, "Unknown Bank"),
        "verified": True
    }


@router.get("/health/validate")
async def validate_nibss_integration(
    service: NIBSSService = Depends(get_nibss_service)
):
    """
    Smoke-test endpoint that validates database connectivity, seed data,
    and NIBSS API reachability. Returns a structured validation report.
    """
    results = {}

    # Check 1: Database
    try:
        bank_count = service.db.query(Bank).count()
        results["database"] = {"status": "ok", "bank_records": bank_count}
    except Exception as e:
        results["database"] = {"status": "error", "detail": str(e)}

    # Check 2: NIBSS endpoint reachability
    nibss_base = os.getenv("NIBSS_BASE_URL", "")
    if nibss_base:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{nibss_base}/health", headers={
                    "APIKey": os.getenv("NIBSS_API_KEY", ""),
                })
            results["nibss_api"] = {
                "status": "reachable" if r.status_code < 500 else "error",
                "http_status": r.status_code,
                "url": nibss_base,
            }
        except Exception as e:
            results["nibss_api"] = {"status": "unreachable", "detail": str(e), "url": nibss_base}
    else:
        results["nibss_api"] = {"status": "not_configured", "detail": "NIBSS_BASE_URL not set"}

    # Check 3: Name enquiry capability (use a known test account if sandbox URL set)
    sandbox_account = os.getenv("NIBSS_SANDBOX_ACCOUNT", "")
    sandbox_bank_code = os.getenv("NIBSS_SANDBOX_BANK_CODE", "")
    if sandbox_account and sandbox_bank_code:
        try:
            result = service.perform_name_enquiry(
                NameEnquiryRequest(account_number=sandbox_account, bank_code=sandbox_bank_code)
            )
            results["name_enquiry"] = {"status": "ok", "response_code": result.response_code}
        except Exception as e:
            results["name_enquiry"] = {"status": "error", "detail": str(e)}
    else:
        results["name_enquiry"] = {"status": "skipped", "detail": "NIBSS_SANDBOX_ACCOUNT/NIBSS_SANDBOX_BANK_CODE not set"}

    overall = "healthy" if all(v.get("status") in ("ok", "skipped", "not_configured") for v in results.values()) else "degraded"

    return {
        "overall": overall,
        "checks": results,
        "timestamp": datetime.utcnow().isoformat(),
    }
