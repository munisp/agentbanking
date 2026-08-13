"""
Ballerina KYB Integration - Production Implementation
Business verification, UBO checks, corporate document verification, ongoing monitoring
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import httpx
import os

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ballerina KYB Integration", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class BusinessType(str, Enum):
    SOLE_PROPRIETOR = "sole_proprietor"
    PARTNERSHIP = "partnership"
    PRIVATE_LIMITED = "private_limited"
    PUBLIC_LIMITED = "public_limited"
    NGO = "ngo"

class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class BusinessVerificationRequest(BaseModel):
    business_name: str
    business_type: BusinessType
    registration_number: str
    country: str
    registration_date: str
    business_address: Dict
    directors: List[Dict]
    beneficial_owners: List[Dict]
    documents: List[Dict]

class VerificationResult(BaseModel):
    verification_id: str
    business_name: str
    status: VerificationStatus
    risk_level: RiskLevel
    checks_performed: List[Dict]
    issues_found: List[str]
    verified_at: Optional[str]
    expires_at: Optional[str]

class UBOCheck(BaseModel):
    ubo_id: str
    name: str
    ownership_percentage: float
    verification_status: VerificationStatus
    pep_check: Optional[bool]
    sanctions_check: Optional[bool]
    adverse_media: Optional[bool]
    risk_score: float

class BusinessCreditCheck(BaseModel):
    business_id: str
    credit_score: int
    credit_rating: str
    payment_history: Dict
    outstanding_debt: float
    credit_limit_recommendation: float
    timestamp: str

# Provider configuration: without these, the corresponding checks report
# not_available / requires_review instead of fabricated results.
REGISTRY_API_URL = os.getenv("KYB_REGISTRY_API_URL", "")
CREDIT_BUREAU_API_URL = os.getenv("KYB_CREDIT_BUREAU_API_URL", "")

class BallerinaKYBClient:
    """Ballerina KYB Integration Client"""
    
    def __init__(self, api_key: str, api_url: str = "https://api.ballerina.io/v1"):
        self.api_key = api_key
        self.api_url = api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.verification_fee = 50.0  # $50 per verification
        logger.info("Ballerina KYB client initialized")
    
    def _get_headers(self) -> Dict:
        """Get API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def verify_business_registry(self, business_name: str, registration_number: str, country: str) -> Dict:
        """Verify business with the corporate registry.

        Fails closed: when no registry provider is configured or reachable,
        the check reports not_available (never a fabricated registration).
        """
        
        logger.info(f"Verifying business registry: {business_name}, {registration_number}, {country}")
        
        if not REGISTRY_API_URL:
            logger.error("Business registry API not configured (KYB_REGISTRY_API_URL)")
            return {
                "check_type": "business_registry",
                "status": "not_available",
                "reason": "No business registry provider configured",
                "business_name": business_name,
                "registration_number": registration_number,
                "country": country,
                "registered": None,
                "verified_at": datetime.utcnow().isoformat()
            }
        
        try:
            resp = await self.client.get(
                f"{REGISTRY_API_URL.rstrip('/')}/search",
                params={
                    "name": business_name,
                    "registration_number": registration_number,
                    "country": country
                },
                headers=self._get_headers()
            )
            if resp.status_code != 200:
                logger.error(f"Registry API error: HTTP {resp.status_code}")
                return {
                    "check_type": "business_registry",
                    "status": "not_available",
                    "reason": f"Registry provider returned HTTP {resp.status_code}",
                    "business_name": business_name,
                    "registration_number": registration_number,
                    "country": country,
                    "registered": None,
                    "verified_at": datetime.utcnow().isoformat()
                }
            data = resp.json()
            registered = bool(data.get("registered"))
            return {
                "check_type": "business_registry",
                "status": "passed" if registered else "failed",
                "business_name": business_name,
                "registration_number": registration_number,
                "country": country,
                "registered": registered,
                "registration_date": data.get("registration_date"),
                "business_status": data.get("business_status"),
                "verified_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Registry verification failed: {e}")
            return {
                "check_type": "business_registry",
                "status": "not_available",
                "reason": f"Registry provider request failed: {e}",
                "business_name": business_name,
                "registration_number": registration_number,
                "country": country,
                "registered": None,
                "verified_at": datetime.utcnow().isoformat()
            }
    
    async def verify_directors(self, directors: List[Dict]) -> List[Dict]:
        """Verify company directors.

        No director screening provider is integrated, so every director is
        marked requires_review with screening not performed — never a
        fabricated verified/PEP-clean/sanctions-clean result.
        """
        
        logger.info(f"Verifying {len(directors)} directors")
        
        verified_directors = []
        for director in directors:
            verified_directors.append({
                "name": director["name"],
                "position": director.get("position", "Director"),
                "id_number": director.get("id_number"),
                "verification_status": "requires_review",
                "screening_status": "not_available",
                "screening_note": "No director screening provider configured; "
                                  "identity, PEP and sanctions status NOT checked",
                "pep_check": None,
                "sanctions_check": None,
                "adverse_media": None,
                "verified_at": datetime.utcnow().isoformat()
            })
        
        return verified_directors
    
    async def verify_beneficial_owners(self, beneficial_owners: List[Dict]) -> List[UBOCheck]:
        """Verify Ultimate Beneficial Owners (UBO).

        Without a UBO screening provider, every UBO requires manual review;
        PEP/sanctions/adverse-media flags are None (unknown), never
        fabricated as clean.
        """
        
        logger.info(f"Verifying {len(beneficial_owners)} beneficial owners")
        
        ubo_checks = []
        for idx, ubo in enumerate(beneficial_owners):
            # Calculate risk score
            risk_score = 0.0
            
            # Check ownership percentage (>25% requires verification)
            ownership = ubo.get("ownership_percentage", 0)
            if ownership < 25:
                risk_score += 0.2
            
            # No UBO screening provider is integrated: PEP/sanctions/adverse
            # media status is unknown, which itself is a risk requiring review.
            pep_check = None
            sanctions_check = None
            adverse_media = None
            risk_score += 0.4
            
            verification_status = VerificationStatus.REQUIRES_REVIEW
            
            ubo_checks.append(UBOCheck(
                ubo_id=f"UBO-{idx+1}",
                name=ubo["name"],
                ownership_percentage=ownership,
                verification_status=verification_status,
                pep_check=pep_check,
                sanctions_check=sanctions_check,
                adverse_media=adverse_media,
                risk_score=round(risk_score, 2)
            ))
        
        return ubo_checks
    
    async def verify_documents(self, documents: List[Dict]) -> List[Dict]:
        """Verify corporate documents.

        No document authenticity provider is integrated, so documents are
        recorded as received with authenticity NOT checked.
        """
        
        logger.info(f"Verifying {len(documents)} documents")
        
        required_docs = ["certificate_of_incorporation", "memorandum_of_association", "proof_of_address"]
        
        verified_docs = []
        for doc in documents:
            verified_docs.append({
                "document_type": doc["type"],
                "document_id": doc.get("id"),
                "verification_status": "requires_review",
                "authenticity_check": "not_performed",
                "authenticity_note": "No document authenticity provider configured",
                "expiry_date": doc.get("expiry_date"),
                "verified_at": datetime.utcnow().isoformat()
            })
        
        # Check for missing documents
        provided_types = [doc["type"] for doc in documents]
        missing_docs = [doc for doc in required_docs if doc not in provided_types]
        
        return {
            "verified_documents": verified_docs,
            "missing_documents": missing_docs
        }
    
    async def perform_credit_check(self, business_id: str, registration_number: str) -> BusinessCreditCheck:
        """Perform business credit check via the configured credit bureau.

        Raises RuntimeError when no bureau is configured or the bureau call
        fails — never returns a random or fabricated credit score.
        """
        
        logger.info(f"Performing credit check for business {business_id}")
        
        if not CREDIT_BUREAU_API_URL:
            raise RuntimeError(
                "Credit bureau integration not configured "
                "(KYB_CREDIT_BUREAU_API_URL missing); credit check unavailable"
            )
        
        try:
            resp = await self.client.get(
                f"{CREDIT_BUREAU_API_URL.rstrip('/')}/business/{registration_number}",
                headers=self._get_headers()
            )
        except Exception as e:
            raise RuntimeError(f"Credit bureau request failed: {e}") from e
        
        if resp.status_code != 200:
            raise RuntimeError(f"Credit bureau returned HTTP {resp.status_code}")
        
        data = resp.json()
        try:
            credit_score = int(data["credit_score"])
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(f"Credit bureau response missing credit_score: {e}") from e
        
        credit_rating = data.get("credit_rating") or (
            "AAA" if credit_score >= 750 else
            "AA" if credit_score >= 650 else
            "A" if credit_score >= 550 else "B"
        )
        
        return BusinessCreditCheck(
            business_id=business_id,
            credit_score=credit_score,
            credit_rating=credit_rating,
            payment_history=data.get("payment_history") or {},
            outstanding_debt=float(data.get("outstanding_debt", 0.0)),
            credit_limit_recommendation=float(data.get("credit_limit_recommendation", 0.0)),
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def verify_business(self, request: BusinessVerificationRequest) -> VerificationResult:
        """Perform complete business verification.

        Fails closed: if any required check could not actually be performed,
        the business can at most be REQUIRES_REVIEW, never VERIFIED.
        """
        
        verification_id = f"KYB-{datetime.utcnow().timestamp()}"
        
        logger.info(f"Starting business verification {verification_id} for {request.business_name}")
        
        checks_performed = []
        issues_found = []
        overall_risk_score = 0.0
        any_unavailable = False
        
        # 1. Business registry check
        registry_check = await self.verify_business_registry(
            request.business_name,
            request.registration_number,
            request.country
        )
        checks_performed.append(registry_check)
        
        if registry_check["status"] == "not_available":
            any_unavailable = True
            issues_found.append("Business registry check unavailable — manual verification required")
            overall_risk_score += 0.4
        elif registry_check["status"] != "passed":
            issues_found.append("Business not found in registry")
            overall_risk_score += 0.5
        
        # 2. Director verification
        director_checks = await self.verify_directors(request.directors)
        checks_performed.append({
            "check_type": "director_verification",
            "directors_verified": len(director_checks),
            "results": director_checks
        })
        
        for director in director_checks:
            if director["pep_check"] or director["sanctions_check"]:
                issues_found.append(f"Director {director['name']} flagged in PEP/sanctions check")
                overall_risk_score += 0.3
            if director.get("screening_status") == "not_available":
                any_unavailable = True
        if director_checks and any(d.get("screening_status") == "not_available" for d in director_checks):
            issues_found.append("Director screening unavailable — manual review required")
            overall_risk_score += 0.3
        
        # 3. UBO verification
        ubo_checks = await self.verify_beneficial_owners(request.beneficial_owners)
        checks_performed.append({
            "check_type": "ubo_verification",
            "ubos_verified": len(ubo_checks),
            "results": [ubo.dict() for ubo in ubo_checks]
        })
        
        for ubo in ubo_checks:
            overall_risk_score += ubo.risk_score * 0.3
            if ubo.verification_status == VerificationStatus.REQUIRES_REVIEW:
                any_unavailable = True
                issues_found.append(f"UBO {ubo.name} requires manual review")
        
        # 4. Document verification
        doc_verification = await self.verify_documents(request.documents)
        checks_performed.append({
            "check_type": "document_verification",
            "verified_documents": doc_verification["verified_documents"],
            "missing_documents": doc_verification["missing_documents"]
        })
        
        if doc_verification["verified_documents"]:
            any_unavailable = True
            issues_found.append("Document authenticity not verified — manual review required")
            overall_risk_score += 0.2
        if doc_verification["missing_documents"]:
            issues_found.append(f"Missing documents: {', '.join(doc_verification['missing_documents'])}")
            overall_risk_score += 0.2
        
        # 5. Credit check (real bureau only)
        try:
            credit_check = await self.perform_credit_check(verification_id, request.registration_number)
            checks_performed.append({
                "check_type": "credit_check",
                "credit_score": credit_check.credit_score,
                "credit_rating": credit_check.credit_rating
            })
            
            if credit_check.credit_score < 550:
                issues_found.append(f"Low credit score: {credit_check.credit_score}")
                overall_risk_score += 0.2
        except RuntimeError as e:
            any_unavailable = True
            issues_found.append(f"Credit check unavailable — manual review required ({e})")
            overall_risk_score += 0.3
            checks_performed.append({
                "check_type": "credit_check",
                "status": "not_available"
            })
        
        # Determine overall status and risk level
        if overall_risk_score < 0.3:
            status = VerificationStatus.VERIFIED
            risk_level = RiskLevel.LOW
        elif overall_risk_score < 0.5:
            status = VerificationStatus.VERIFIED
            risk_level = RiskLevel.MEDIUM
        elif overall_risk_score < 0.7:
            status = VerificationStatus.REQUIRES_REVIEW
            risk_level = RiskLevel.HIGH
        else:
            status = VerificationStatus.REJECTED
            risk_level = RiskLevel.CRITICAL
        
        # Fail closed: incomplete checks can never yield VERIFIED.
        if any_unavailable:
            if status == VerificationStatus.VERIFIED:
                status = VerificationStatus.REQUIRES_REVIEW
            if risk_level == RiskLevel.LOW:
                risk_level = RiskLevel.MEDIUM
        
        # Set expiry (1 year for verified businesses)
        verified_at = datetime.utcnow().isoformat() if status == VerificationStatus.VERIFIED else None
        expires_at = (datetime.utcnow() + timedelta(days=365)).isoformat() if status == VerificationStatus.VERIFIED else None
        
        logger.info(f"Verification {verification_id} completed: {status}, risk: {risk_level}")
        
        return VerificationResult(
            verification_id=verification_id,
            business_name=request.business_name,
            status=status,
            risk_level=risk_level,
            checks_performed=checks_performed,
            issues_found=issues_found if issues_found else ["No issues found"],
            verified_at=verified_at,
            expires_at=expires_at
        )
    
    async def ongoing_monitoring(self, verification_id: str) -> Dict:
        """Ongoing monitoring status.

        No monitoring provider is integrated, so monitoring is reported as
        not_configured rather than fabricating an active clean status.
        """
        
        logger.info(f"Monitoring status requested for {verification_id}")
        
        return {
            "verification_id": verification_id,
            "monitoring_status": "not_configured",
            "detail": "No ongoing monitoring provider integrated; no monitoring performed",
            "last_check": None,
            "changes_detected": [],
            "alerts": [],
            "next_check": None
        }
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Initialize client (API key from environment; never hardcode credentials)
kyb_client = BallerinaKYBClient(api_key=os.getenv("KYB_API_KEY", ""))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "kyb-ballerina",
        "verification_fee": kyb_client.verification_fee
    }

@app.post("/api/v1/kyb/verify", response_model=VerificationResult)
async def verify_business(request: BusinessVerificationRequest):
    """Perform complete business verification"""
    try:
        result = await kyb_client.verify_business(request)
        return result
    except Exception as e:
        logger.error(f"Business verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Business verification failed: {str(e)}")

@app.post("/api/v1/kyb/ubo/verify")
async def verify_ubos(beneficial_owners: List[Dict]):
    """Verify beneficial owners"""
    try:
        result = await kyb_client.verify_beneficial_owners(beneficial_owners)
        return {"ubo_checks": [ubo.dict() for ubo in result]}
    except Exception as e:
        logger.error(f"UBO verification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"UBO verification failed: {str(e)}")

@app.post("/api/v1/kyb/credit/check", response_model=BusinessCreditCheck)
async def credit_check(business_id: str, registration_number: str):
    """Perform business credit check (fails closed when bureau unavailable)"""
    try:
        result = await kyb_client.perform_credit_check(business_id, registration_number)
        return result
    except RuntimeError as e:
        logger.error(f"Credit check unavailable: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Credit check unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"Credit check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Credit check failed: {str(e)}")

@app.get("/api/v1/kyb/monitoring/{verification_id}")
async def ongoing_monitoring(verification_id: str):
    """Get ongoing monitoring status"""
    try:
        result = await kyb_client.ongoing_monitoring(verification_id)
        return result
    except Exception as e:
        logger.error(f"Monitoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Monitoring failed: {str(e)}")

@app.get("/api/v1/kyb/fee")
async def get_verification_fee():
    """Get KYB verification fee"""
    return {
        "verification_fee": kyb_client.verification_fee,
        "currency": "USD",
        "description": "One-time business verification fee"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8037)
