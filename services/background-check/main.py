import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Background Check Service
Automated background verification for agent onboarding

This service integrates with third-party background check providers
to verify agent credentials, criminal records, credit history, and references.

FAIL-CLOSED POLICY: this is an identity/compliance domain. A provider
failure, missing credentials, or an unimplemented check MUST NEVER produce
a fabricated PASS or clean record. Such checks are reported as FAILED /
INCONCLUSIVE / NOT_AVAILABLE and force manual review.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("background-check-service")
app.include_router(metrics_router)

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import httpx
import asyncio
import logging
from uuid import uuid4
import os
import sys

# Add shared libraries to path
sys.path.append("/home/ubuntu/remittance-platform-unified/backend/python-services/shared")

from keycloak_auth import KeycloakAuth, require_auth, get_user_id
from permify_client import PermifyClient
from dapr_client import DaprClient
from kafka_producer import KafkaProducerClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Background Check Service",
    description="Automated background verification for agent onboarding",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
keycloak_auth = KeycloakAuth()
permify_client = PermifyClient()
dapr_client = DaprClient(app_id="background-check-service", dapr_port=3500)
kafka_producer = KafkaProducerClient()

# Configuration
SMILE_IDENTITY_API_KEY = os.getenv("SMILE_IDENTITY_API_KEY", "")
SMILE_IDENTITY_PARTNER_ID = os.getenv("SMILE_IDENTITY_PARTNER_ID", "")
YOUVERIFY_API_KEY = os.getenv("YOUVERIFY_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/background_check")

# Enums
class CheckType(str, Enum):
    CRIMINAL_RECORD = "criminal_record"
    CREDIT_HISTORY = "credit_history"
    EMPLOYMENT = "employment"
    REFERENCE = "reference"
    IDENTITY = "identity"
    ADDRESS = "address"

class CheckStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"
    NOT_AVAILABLE = "not_available"

class CheckResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"

# Pydantic models
class BackgroundCheckRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID to perform background check on")
    check_types: List[CheckType] = Field(..., description="Types of checks to perform")
    first_name: str
    last_name: str
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    phone_number: str
    email: EmailStr
    address: str
    nin: Optional[str] = Field(None, description="National Identification Number")
    bvn: Optional[str] = Field(None, description="Bank Verification Number")
    employment_history: Optional[List[Dict[str, Any]]] = None
    references: Optional[List[Dict[str, str]]] = None

class BackgroundCheckResponse(BaseModel):
    check_id: str
    agent_id: str
    status: CheckStatus
    created_at: datetime
    estimated_completion: datetime
    message: str

class CheckStatusResponse(BaseModel):
    check_id: str
    agent_id: str
    status: CheckStatus
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    checks_completed: int
    checks_total: int
    created_at: datetime
    updated_at: datetime

class CheckResultDetail(BaseModel):
    check_type: CheckType
    status: CheckStatus
    result: Optional[CheckResult]
    details: Dict[str, Any]
    provider: str
    checked_at: datetime

class CheckResultsResponse(BaseModel):
    check_id: str
    agent_id: str
    overall_status: CheckStatus
    overall_result: Optional[CheckResult]
    checks: List[CheckResultDetail]
    created_at: datetime
    completed_at: Optional[datetime]
    reviewed_by: Optional[str]
    review_notes: Optional[str]

# In-memory storage (replace with PostgreSQL in production)
background_checks: Dict[str, Dict[str, Any]] = {}

# Helper functions
async def verify_permission(user: Dict[str, Any], action: str, resource_id: str = None):
    """Verify user has permission to perform action"""
    user_id = get_user_id(user)
    
    if resource_id:
        has_permission = await permify_client.check_permission(
            user_id=user_id,
            permission=action,
            resource_type="background_check",
            resource_id=resource_id
        )
    else:
        has_permission = await permify_client.check_permission(
            user_id=user_id,
            permission=action,
            resource_type="background_check"
        )
    
    if not has_permission:
        raise HTTPException(status_code=403, detail="Permission denied")

def _check_not_available(check_type: CheckType, provider: str, reason: str) -> CheckResultDetail:
    """Return an explicit NOT_AVAILABLE result for an unimplemented or
    unconfigured check. NEVER fabricates a PASS, clean record, or score."""
    logger.error(
        f"{check_type} check is not available ({provider}): {reason}. "
        "Manual review required."
    )
    return CheckResultDetail(
        check_type=check_type,
        status=CheckStatus.NOT_AVAILABLE,
        result=None,
        details={
            "error": reason,
            "provider_available": False,
            "manual_review_required": True
        },
        provider=provider,
        checked_at=datetime.utcnow()
    )

async def perform_identity_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform identity verification using Smile Identity.
    
    Fail-closed: any provider error, non-200 response, or missing
    credentials yields FAILED / INCONCLUSIVE - never a fabricated PASS
    attributed to Smile Identity.
    """
    logger.info(f"Performing identity check for agent {data.agent_id}")
    
    if not SMILE_IDENTITY_API_KEY or not SMILE_IDENTITY_PARTNER_ID:
        logger.error("Smile Identity credentials are not configured")
        return CheckResultDetail(
            check_type=CheckType.IDENTITY,
            status=CheckStatus.FAILED,
            result=CheckResult.INCONCLUSIVE,
            details={
                "error": "Smile Identity provider is not configured (missing API key/partner ID)",
                "provider_available": False,
                "manual_review_required": True
            },
            provider="Smile Identity",
            checked_at=datetime.utcnow()
        )
    
    try:
        async with httpx.AsyncClient() as client:
            # Call Smile Identity API
            response = await client.post(
                "https://api.smileidentity.com/v1/id_verification",
                headers={
                    "Authorization": f"Bearer {SMILE_IDENTITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "partner_id": SMILE_IDENTITY_PARTNER_ID,
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "id_number": data.nin or data.bvn,
                    "id_type": "NIN" if data.nin else "BVN",
                    "country": "NG"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result_data = response.json()
                return CheckResultDetail(
                    check_type=CheckType.IDENTITY,
                    status=CheckStatus.COMPLETED,
                    result=CheckResult.PASS if result_data.get("match") else CheckResult.FAIL,
                    details=result_data,
                    provider="Smile Identity",
                    checked_at=datetime.utcnow()
                )
            
            logger.error(
                f"Smile Identity API error: {response.status_code} - {response.text}"
            )
            return CheckResultDetail(
                check_type=CheckType.IDENTITY,
                status=CheckStatus.FAILED,
                result=CheckResult.INCONCLUSIVE,
                details={
                    "error": f"Smile Identity API returned status {response.status_code}",
                    "provider_available": False,
                    "manual_review_required": True
                },
                provider="Smile Identity",
                checked_at=datetime.utcnow()
            )
    except Exception as e:
        logger.error(f"Identity check failed: {str(e)}")
        return CheckResultDetail(
            check_type=CheckType.IDENTITY,
            status=CheckStatus.FAILED,
            result=CheckResult.INCONCLUSIVE,
            details={
                "error": f"Smile Identity provider error: {str(e)}",
                "provider_available": False,
                "manual_review_required": True
            },
            provider="Smile Identity",
            checked_at=datetime.utcnow()
        )

async def perform_criminal_record_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform criminal record check.
    
    No real provider integration exists yet. Fail closed: report
    NOT_AVAILABLE and require manual review instead of fabricating a
    clean criminal record.
    """
    logger.info(f"Criminal record check requested for agent {data.agent_id}")
    
    return _check_not_available(
        CheckType.CRIMINAL_RECORD,
        "Nigeria Police Force API",
        "Criminal record provider integration is not implemented; "
        "no databases were checked. Manual criminal record review required."
    )

async def perform_credit_history_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform credit history check.
    
    No real credit bureau integration exists yet. Fail closed: report
    NOT_AVAILABLE and require manual review instead of fabricating a
    credit score.
    """
    logger.info(f"Credit history check requested for agent {data.agent_id}")
    
    return _check_not_available(
        CheckType.CREDIT_HISTORY,
        "CRC Credit Bureau",
        "Credit bureau provider integration is not implemented; "
        "no credit report was obtained. Manual credit review required."
    )

async def perform_employment_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform employment verification.
    
    No real employment verification provider exists yet. Fail closed:
    report NOT_AVAILABLE and require manual review instead of fabricating
    employer verifications.
    """
    logger.info(f"Employment check requested for agent {data.agent_id}")
    
    if not data.employment_history:
        return CheckResultDetail(
            check_type=CheckType.EMPLOYMENT,
            status=CheckStatus.COMPLETED,
            result=CheckResult.INCONCLUSIVE,
            details={"message": "No employment history provided"},
            provider="Manual Verification",
            checked_at=datetime.utcnow()
        )
    
    return _check_not_available(
        CheckType.EMPLOYMENT,
        "Employment Verification Service",
        "Employment verification provider integration is not implemented; "
        "no employers were contacted. Manual employment verification required."
    )

async def perform_reference_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform reference check.
    
    No real reference check provider exists yet. Fail closed: report
    NOT_AVAILABLE and require manual review instead of fabricating
    positive reference responses.
    """
    logger.info(f"Reference check requested for agent {data.agent_id}")
    
    if not data.references:
        return CheckResultDetail(
            check_type=CheckType.REFERENCE,
            status=CheckStatus.COMPLETED,
            result=CheckResult.INCONCLUSIVE,
            details={"message": "No references provided"},
            provider="Manual Verification",
            checked_at=datetime.utcnow()
        )
    
    return _check_not_available(
        CheckType.REFERENCE,
        "Reference Check Service",
        "Reference check provider integration is not implemented; "
        "no references were contacted. Manual reference verification required."
    )

async def perform_address_check(data: BackgroundCheckRequest) -> CheckResultDetail:
    """Perform address verification.
    
    No real address verification provider exists yet. Fail closed: report
    NOT_AVAILABLE and require manual review instead of fabricating a
    verified address and GPS coordinates.
    """
    logger.info(f"Address check requested for agent {data.agent_id}")
    
    return _check_not_available(
        CheckType.ADDRESS,
        "Address Verification Service",
        "Address verification provider integration is not implemented; "
        "the address was not verified. Manual address verification required."
    )

async def run_background_checks(check_id: str, data: BackgroundCheckRequest):
    """Run all requested background checks asynchronously"""
    logger.info(f"Starting background checks for check_id: {check_id}")
    
    check_functions = {
        CheckType.IDENTITY: perform_identity_check,
        CheckType.CRIMINAL_RECORD: perform_criminal_record_check,
        CheckType.CREDIT_HISTORY: perform_credit_history_check,
        CheckType.EMPLOYMENT: perform_employment_check,
        CheckType.REFERENCE: perform_reference_check,
        CheckType.ADDRESS: perform_address_check
    }
    
    # Update status to in_progress
    background_checks[check_id]["status"] = CheckStatus.IN_PROGRESS
    background_checks[check_id]["updated_at"] = datetime.utcnow()
    
    # Run all checks
    results = []
    for check_type in data.check_types:
        if check_type in check_functions:
            try:
                result = await check_functions[check_type](data)
                results.append(result)
                
                # Update progress
                progress = int((len(results) / len(data.check_types)) * 100)
                background_checks[check_id]["progress"] = progress
                background_checks[check_id]["checks_completed"] = len(results)
                
            except Exception as e:
                logger.error(f"Check {check_type} failed: {str(e)}")
                results.append(CheckResultDetail(
                    check_type=check_type,
                    status=CheckStatus.FAILED,
                    result=None,
                    details={"error": str(e), "manual_review_required": True},
                    provider="Unknown",
                    checked_at=datetime.utcnow()
                ))
    
    # Determine overall result.
    # Fail-closed: overall PASS requires every check to be a real PASS.
    # Any FAIL, NOT_AVAILABLE, FAILED, or INCONCLUSIVE check forces
    # manual review (overall result is never a fabricated PASS).
    all_passed = bool(results) and all(
        r.result == CheckResult.PASS and r.status == CheckStatus.COMPLETED
        for r in results
    )
    any_failed = any(r.result == CheckResult.FAIL for r in results)
    
    if any_failed:
        overall_result = CheckResult.FAIL
    elif all_passed:
        overall_result = CheckResult.PASS
    else:
        overall_result = CheckResult.INCONCLUSIVE
    
    # Final status: COMPLETED only on a genuine all-PASS outcome; anything
    # else requires human review.
    final_status = (
        CheckStatus.COMPLETED if overall_result == CheckResult.PASS
        else CheckStatus.REQUIRES_REVIEW
    )
    
    # Update final status
    background_checks[check_id].update({
        "status": final_status,
        "overall_result": overall_result,
        "checks": [r.dict() for r in results],
        "completed_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "progress": 100,
        "checks_completed": len(results)
    })
    
    # Publish event to Kafka
    try:
        await kafka_producer.publish(
            topic="background_checks.completed",
            key=check_id,
            value={
                "check_id": check_id,
                "agent_id": data.agent_id,
                "status": final_status.value,
                "overall_result": overall_result.value,
                "completed_at": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to publish background check completion event for {check_id}: {e}"
        )
    
    logger.info(
        f"Background checks completed for check_id: {check_id}, "
        f"status: {final_status}, result: {overall_result}"
    )

# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "background-check-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/v1/background-check/initiate", response_model=BackgroundCheckResponse)
async def initiate_background_check(
    request: BackgroundCheckRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Initiate a background check for an agent"""
    
    # Verify permission
    await verify_permission(user, "background_check.create")
    
    # Generate check ID
    check_id = str(uuid4())
    
    # Create check record
    check_record = {
        "check_id": check_id,
        "agent_id": request.agent_id,
        "status": CheckStatus.PENDING,
        "check_types": request.check_types,
        "data": request.dict(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "progress": 0,
        "checks_completed": 0,
        "checks_total": len(request.check_types),
        "created_by": get_user_id(user)
    }
    
    background_checks[check_id] = check_record
    
    # Schedule background checks
    background_tasks.add_task(run_background_checks, check_id, request)
    
    # Calculate estimated completion (5 minutes per check type)
    estimated_completion = datetime.utcnow() + timedelta(minutes=5 * len(request.check_types))
    
    return BackgroundCheckResponse(
        check_id=check_id,
        agent_id=request.agent_id,
        status=CheckStatus.PENDING,
        created_at=check_record["created_at"],
        estimated_completion=estimated_completion,
        message=f"Background check initiated with {len(request.check_types)} checks"
    )

@app.get("/api/v1/background-check/{check_id}/status", response_model=CheckStatusResponse)
async def get_check_status(
    check_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Get the status of a background check"""
    
    # Verify permission
    await verify_permission(user, "background_check.read", check_id)
    
    if check_id not in background_checks:
        raise HTTPException(status_code=404, detail="Background check not found")
    
    check = background_checks[check_id]
    
    return CheckStatusResponse(
        check_id=check_id,
        agent_id=check["agent_id"],
        status=check["status"],
        progress=check.get("progress", 0),
        checks_completed=check.get("checks_completed", 0),
        checks_total=check["checks_total"],
        created_at=check["created_at"],
        updated_at=check["updated_at"]
    )

@app.get("/api/v1/background-check/{check_id}/results", response_model=CheckResultsResponse)
async def get_check_results(
    check_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Get the results of a completed background check"""
    
    # Verify permission
    await verify_permission(user, "background_check.read", check_id)
    
    if check_id not in background_checks:
        raise HTTPException(status_code=404, detail="Background check not found")
    
    check = background_checks[check_id]
    
    if check["status"] not in [CheckStatus.COMPLETED, CheckStatus.REQUIRES_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Background check is not completed yet. Current status: {check['status']}"
        )
    
    checks = [CheckResultDetail(**c) for c in check.get("checks", [])]
    
    return CheckResultsResponse(
        check_id=check_id,
        agent_id=check["agent_id"],
        overall_status=check["status"],
        overall_result=check.get("overall_result"),
        checks=checks,
        created_at=check["created_at"],
        completed_at=check.get("completed_at"),
        reviewed_by=check.get("reviewed_by"),
        review_notes=check.get("review_notes")
    )

@app.post("/api/v1/background-check/{check_id}/retry")
async def retry_background_check(
    check_id: str,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Retry a failed background check"""
    
    # Verify permission
    await verify_permission(user, "background_check.update", check_id)
    
    if check_id not in background_checks:
        raise HTTPException(status_code=404, detail="Background check not found")
    
    check = background_checks[check_id]
    
    if check["status"] != CheckStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed checks. Current status: {check['status']}"
        )
    
    # Reset check status
    check["status"] = CheckStatus.PENDING
    check["progress"] = 0
    check["checks_completed"] = 0
    check["updated_at"] = datetime.utcnow()
    
    # Recreate request object
    request_data = BackgroundCheckRequest(**check["data"])
    
    # Schedule background checks
    background_tasks.add_task(run_background_checks, check_id, request_data)
    
    return {"message": "Background check retry initiated", "check_id": check_id}

@app.delete("/api/v1/background-check/{check_id}")
async def delete_background_check(
    check_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Delete a background check record"""
    
    # Verify permission
    await verify_permission(user, "background_check.delete", check_id)
    
    if check_id not in background_checks:
        raise HTTPException(status_code=404, detail="Background check not found")
    
    del background_checks[check_id]
    
    return {"message": "Background check deleted successfully", "check_id": check_id}

@app.get("/api/v1/background-check/agent/{agent_id}")
async def get_agent_background_checks(
    agent_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """Get all background checks for a specific agent"""
    
    # Verify permission
    await verify_permission(user, "background_check.read")
    
    agent_checks = [
        {
            "check_id": check_id,
            "status": check["status"],
            "overall_result": check.get("overall_result"),
            "created_at": check["created_at"],
            "completed_at": check.get("completed_at")
        }
        for check_id, check in background_checks.items()
        if check["agent_id"] == agent_id
    ]
    
    return {
        "agent_id": agent_id,
        "total_checks": len(agent_checks),
        "checks": agent_checks
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
