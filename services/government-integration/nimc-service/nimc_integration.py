"""
NIMC (National Identity Management Commission) Integration
NIN (National Identification Number) verification for Nigerian citizens
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime, date
from enum import Enum
import logging
import httpx
import hashlib
import hmac
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NIMC Integration Service", version="1.0.0")

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    MISMATCH = "mismatch"
    ERROR = "error"

class NINVerificationRequest(BaseModel):
    nin: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone_number: Optional[str] = None

class NINVerificationResponse(BaseModel):
    verification_id: str
    status: VerificationStatus
    nin: str
    nin_valid: bool
    data_match: bool
    verified_fields: Dict[str, bool]
    nimc_data: Optional[Dict]
    confidence_score: float
    timestamp: str

class NIMCIntegrationService:
    """NIMC database integration for NIN verification"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = "https://api.nimc.gov.ng/v1",
        use_sandbox: bool = False
    ):
        """
        Initialize NIMC integration
        
        Args:
            api_key: NIMC API key
            api_secret: NIMC API secret
            base_url: NIMC API base URL
            use_sandbox: Use sandbox environment for testing
        """
        self.api_key = api_key or os.environ.get("NIMC_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("NIMC_API_SECRET", "")
        self.base_url = base_url
        self.use_sandbox = use_sandbox
        
        if use_sandbox:
            self.base_url = "https://sandbox.nimc.gov.ng/v1"
        
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"NIMC Integration initialized (sandbox: {use_sandbox})")
    
    async def verify_nin(
        self,
        nin: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        date_of_birth: Optional[str] = None,
        phone_number: Optional[str] = None
    ) -> NINVerificationResponse:
        """
        Verify NIN with NIMC database
        
        Args:
            nin: 11-digit National Identification Number
            first_name: First name for verification
            last_name: Last name for verification
            date_of_birth: Date of birth (YYYY-MM-DD)
            phone_number: Phone number for verification
        
        Returns:
            NINVerificationResponse
        """
        verification_id = f"nin_{nin}_{datetime.utcnow().timestamp()}"
        
        try:
            # Step 1: Validate NIN format
            if not self._validate_nin_format(nin):
                return NINVerificationResponse(
                    verification_id=verification_id,
                    status=VerificationStatus.ERROR,
                    nin=nin,
                    nin_valid=False,
                    data_match=False,
                    verified_fields={},
                    nimc_data=None,
                    confidence_score=0.0,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Step 2: Query NIMC database
            logger.info(f"Querying NIMC database for NIN: {nin}")
            nimc_data = await self._query_nimc_database(nin)
            
            if not nimc_data:
                return NINVerificationResponse(
                    verification_id=verification_id,
                    status=VerificationStatus.NOT_FOUND,
                    nin=nin,
                    nin_valid=True,
                    data_match=False,
                    verified_fields={},
                    nimc_data=None,
                    confidence_score=0.0,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Step 3: Verify provided data against NIMC data
            verified_fields = self._verify_fields(
                nimc_data,
                first_name,
                last_name,
                date_of_birth,
                phone_number
            )
            
            # Step 4: Calculate confidence score
            confidence_score = self._calculate_confidence(verified_fields)
            
            # Step 5: Determine overall status
            data_match = all(verified_fields.values()) if verified_fields else True
            status = VerificationStatus.VERIFIED if data_match else VerificationStatus.MISMATCH
            
            # Step 6: Sanitize NIMC data (remove sensitive fields)
            sanitized_data = self._sanitize_nimc_data(nimc_data)
            
            result = NINVerificationResponse(
                verification_id=verification_id,
                status=status,
                nin=nin,
                nin_valid=True,
                data_match=data_match,
                verified_fields=verified_fields,
                nimc_data=sanitized_data,
                confidence_score=confidence_score,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(
                f"NIN verification complete: {verification_id}, "
                f"status: {status}, confidence: {confidence_score:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"NIN verification error: {e}")
            return NINVerificationResponse(
                verification_id=verification_id,
                status=VerificationStatus.ERROR,
                nin=nin,
                nin_valid=False,
                data_match=False,
                verified_fields={},
                nimc_data=None,
                confidence_score=0.0,
                timestamp=datetime.utcnow().isoformat()
            )
    
    async def _query_nimc_database(self, nin: str) -> Optional[Dict]:
        """
        Query NIMC database for NIN data
        
        Args:
            nin: National Identification Number
        
        Returns:
            NIMC data or None if not found
        """
        try:
            # Prepare request
            endpoint = f"{self.base_url}/nin/verify"
            
            payload = {
                "nin": nin,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Generate signature
            signature = self._generate_signature(payload)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Signature": signature,
                "Content-Type": "application/json"
            }
            
            # Make request
            response = await self.client.post(
                endpoint,
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data")
            elif response.status_code == 404:
                logger.warning(f"NIN not found: {nin}")
                return None
            else:
                logger.error(f"NIMC API error: {response.status_code} - {response.text}")
                return None
                
        except httpx.HTTPError as e:
            logger.error(f"NIMC API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"NIMC query error: {e}")
            # In sandbox mode, return mock data
            if self.use_sandbox:
                return self._get_mock_nimc_data(nin)
            return None
    
    def _validate_nin_format(self, nin: str) -> bool:
        """Validate NIN format (11 digits)"""
        
        if not nin:
            return False
        
        # Remove spaces and dashes
        nin_clean = nin.replace(" ", "").replace("-", "")
        
        # Check if 11 digits
        if len(nin_clean) != 11:
            return False
        
        # Check if all digits
        if not nin_clean.isdigit():
            return False
        
        return True
    
    def _verify_fields(
        self,
        nimc_data: Dict,
        first_name: Optional[str],
        last_name: Optional[str],
        date_of_birth: Optional[str],
        phone_number: Optional[str]
    ) -> Dict[str, bool]:
        """Verify provided fields against NIMC data"""
        
        verified = {}
        
        if first_name:
            nimc_first_name = nimc_data.get("firstname", "").lower()
            verified["first_name"] = self._names_match(first_name.lower(), nimc_first_name)
        
        if last_name:
            nimc_last_name = nimc_data.get("surname", "").lower()
            verified["last_name"] = self._names_match(last_name.lower(), nimc_last_name)
        
        if date_of_birth:
            nimc_dob = nimc_data.get("birthdate", "")
            verified["date_of_birth"] = self._dates_match(date_of_birth, nimc_dob)
        
        if phone_number:
            nimc_phone = nimc_data.get("telephoneno", "")
            verified["phone_number"] = self._phones_match(phone_number, nimc_phone)
        
        return verified
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if names match (fuzzy matching)"""
        
        if not name1 or not name2:
            return False
        
        # Exact match
        if name1 == name2:
            return True
        
        # Check if one contains the other (handles middle names)
        if name1 in name2 or name2 in name1:
            return True
        
        # Calculate similarity (simplified Levenshtein)
        similarity = self._calculate_similarity(name1, name2)
        return similarity >= 0.85
    
    def _dates_match(self, date1: str, date2: str) -> bool:
        """Check if dates match"""
        
        if not date1 or not date2:
            return False
        
        # Extract digits only
        digits1 = ''.join(c for c in date1 if c.isdigit())
        digits2 = ''.join(c for c in date2 if c.isdigit())
        
        return digits1 == digits2
    
    def _phones_match(self, phone1: str, phone2: str) -> bool:
        """Check if phone numbers match"""
        
        if not phone1 or not phone2:
            return False
        
        # Extract digits only
        digits1 = ''.join(c for c in phone1 if c.isdigit())
        digits2 = ''.join(c for c in phone2 if c.isdigit())
        
        # Remove country code if present
        if digits1.startswith("234"):
            digits1 = digits1[3:]
        if digits2.startswith("234"):
            digits2 = digits2[3:]
        
        # Remove leading zero
        digits1 = digits1.lstrip("0")
        digits2 = digits2.lstrip("0")
        
        return digits1 == digits2
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity (simplified)"""
        
        if str1 == str2:
            return 1.0
        
        # Token-based similarity
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union)
    
    def _calculate_confidence(self, verified_fields: Dict[str, bool]) -> float:
        """Calculate overall confidence score"""
        
        if not verified_fields:
            return 1.0  # No fields to verify
        
        verified_count = sum(1 for v in verified_fields.values() if v)
        total_count = len(verified_fields)
        
        return verified_count / total_count
    
    def _sanitize_nimc_data(self, nimc_data: Dict) -> Dict:
        """Remove sensitive fields from NIMC data"""
        
        # Fields to include in response
        safe_fields = [
            "firstname",
            "surname",
            "middlename",
            "birthdate",
            "gender",
            "state_of_origin",
            "lga_of_origin",
            "nin_status"
        ]
        
        sanitized = {}
        for field in safe_fields:
            if field in nimc_data:
                sanitized[field] = nimc_data[field]
        
        return sanitized
    
    def _generate_signature(self, payload: Dict) -> str:
        """Generate HMAC signature for request"""
        
        # Create canonical string
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.api_secret.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_mock_nimc_data(self, nin: str) -> Dict:
        """Get mock NIMC data for sandbox testing"""
        
        return {
            "nin": nin,
            "firstname": "JOHN",
            "surname": "DOE",
            "middlename": "SMITH",
            "birthdate": "1990-01-15",
            "gender": "M",
            "state_of_origin": "LAGOS",
            "lga_of_origin": "IKEJA",
            "telephoneno": "08012345678",
            "nin_status": "ACTIVE",
            "issued_date": "2015-06-20"
        }
    
    def get_service_info(self) -> Dict:
        """Get service information"""
        return {
            "service": "nimc-integration",
            "version": "1.0.0",
            "base_url": self.base_url,
            "sandbox_mode": self.use_sandbox,
            "local_processing": True
        }

# Production: set KYC_SANDBOX_MODE=false to call real NIMC API.
# Defaults to sandbox=True so the service is safe out-of-the-box.
import os as _os
nimc_service = NIMCIntegrationService(
    use_sandbox=_os.getenv("KYC_SANDBOX_MODE", "true").lower() != "false"
)

# API endpoints
@app.post("/api/v1/nimc/verify-nin", response_model=NINVerificationResponse)
async def verify_nin(request: NINVerificationRequest):
    """Verify NIN with NIMC database"""
    
    result = await nimc_service.verify_nin(
        nin=request.nin,
        first_name=request.first_name,
        last_name=request.last_name,
        date_of_birth=request.date_of_birth,
        phone_number=request.phone_number
    )
    
    return result

@app.get("/health")
async def health_check():
    """Health check"""
    info = nimc_service.get_service_info()
    info["status"] = "healthy"
    info["timestamp"] = datetime.utcnow().isoformat()
    return info

@app.get("/info")
async def service_info():
    """Get service information"""
    return nimc_service.get_service_info()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8047)
