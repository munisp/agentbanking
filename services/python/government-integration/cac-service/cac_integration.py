"""
CAC (Corporate Affairs Commission) Integration
RC (Registration Certificate) verification for Nigerian businesses
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import httpx
import hashlib
import hmac
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CAC Integration Service", version="1.0.0")

class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    MISMATCH = "mismatch"
    INACTIVE = "inactive"
    ERROR = "error"

class BusinessType(str, Enum):
    LIMITED_COMPANY = "limited_company"
    BUSINESS_NAME = "business_name"
    INCORPORATED_TRUSTEES = "incorporated_trustees"

class RCVerificationRequest(BaseModel):
    rc_number: str
    business_name: Optional[str] = None
    business_type: Optional[BusinessType] = None

class RCVerificationResponse(BaseModel):
    verification_id: str
    status: VerificationStatus
    rc_number: str
    rc_valid: bool
    data_match: bool
    verified_fields: Dict[str, bool]
    cac_data: Optional[Dict]
    confidence_score: float
    timestamp: str

class CACIntegrationService:
    """CAC database integration for RC verification"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: str = "https://api.cac.gov.ng/v1",
        use_sandbox: bool = False
    ):
        """
        Initialize CAC integration
        
        Args:
            api_key: CAC API key
            api_secret: CAC API secret
            base_url: CAC API base URL
            use_sandbox: Use sandbox environment for testing
        """
        self.api_key = api_key or os.environ.get("CAC_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("CAC_API_SECRET", "")
        self.base_url = base_url
        self.use_sandbox = use_sandbox
        
        if use_sandbox:
            self.base_url = "https://sandbox.cac.gov.ng/v1"
        
        self.client = httpx.AsyncClient(timeout=30.0)
        
        logger.info(f"CAC Integration initialized (sandbox: {use_sandbox})")
    
    async def verify_rc(
        self,
        rc_number: str,
        business_name: Optional[str] = None,
        business_type: Optional[BusinessType] = None
    ) -> RCVerificationResponse:
        """
        Verify RC with CAC database
        
        Args:
            rc_number: Registration Certificate number
            business_name: Business name for verification
            business_type: Type of business entity
        
        Returns:
            RCVerificationResponse
        """
        verification_id = f"rc_{rc_number}_{datetime.utcnow().timestamp()}"
        
        try:
            # Step 1: Validate RC format
            if not self._validate_rc_format(rc_number):
                return RCVerificationResponse(
                    verification_id=verification_id,
                    status=VerificationStatus.ERROR,
                    rc_number=rc_number,
                    rc_valid=False,
                    data_match=False,
                    verified_fields={},
                    cac_data=None,
                    confidence_score=0.0,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Step 2: Query CAC database
            logger.info(f"Querying CAC database for RC: {rc_number}")
            cac_data = await self._query_cac_database(rc_number)
            
            if not cac_data:
                return RCVerificationResponse(
                    verification_id=verification_id,
                    status=VerificationStatus.NOT_FOUND,
                    rc_number=rc_number,
                    rc_valid=True,
                    data_match=False,
                    verified_fields={},
                    cac_data=None,
                    confidence_score=0.0,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Step 3: Check if business is active
            if cac_data.get("status") != "ACTIVE":
                return RCVerificationResponse(
                    verification_id=verification_id,
                    status=VerificationStatus.INACTIVE,
                    rc_number=rc_number,
                    rc_valid=True,
                    data_match=False,
                    verified_fields={},
                    cac_data=self._sanitize_cac_data(cac_data),
                    confidence_score=0.0,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Step 4: Verify provided data against CAC data
            verified_fields = self._verify_fields(
                cac_data,
                business_name,
                business_type
            )
            
            # Step 5: Calculate confidence score
            confidence_score = self._calculate_confidence(verified_fields)
            
            # Step 6: Determine overall status
            data_match = all(verified_fields.values()) if verified_fields else True
            status = VerificationStatus.VERIFIED if data_match else VerificationStatus.MISMATCH
            
            # Step 7: Sanitize CAC data
            sanitized_data = self._sanitize_cac_data(cac_data)
            
            result = RCVerificationResponse(
                verification_id=verification_id,
                status=status,
                rc_number=rc_number,
                rc_valid=True,
                data_match=data_match,
                verified_fields=verified_fields,
                cac_data=sanitized_data,
                confidence_score=confidence_score,
                timestamp=datetime.utcnow().isoformat()
            )
            
            logger.info(
                f"RC verification complete: {verification_id}, "
                f"status: {status}, confidence: {confidence_score:.2f}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"RC verification error: {e}")
            return RCVerificationResponse(
                verification_id=verification_id,
                status=VerificationStatus.ERROR,
                rc_number=rc_number,
                rc_valid=False,
                data_match=False,
                verified_fields={},
                cac_data=None,
                confidence_score=0.0,
                timestamp=datetime.utcnow().isoformat()
            )
    
    async def get_company_details(self, rc_number: str) -> Optional[Dict]:
        """
        Get detailed company information from CAC
        
        Args:
            rc_number: Registration Certificate number
        
        Returns:
            Company details or None
        """
        try:
            cac_data = await self._query_cac_database(rc_number)
            
            if not cac_data:
                return None
            
            # Get additional details
            directors = await self._get_directors(rc_number)
            shareholders = await self._get_shareholders(rc_number)
            
            return {
                "basic_info": self._sanitize_cac_data(cac_data),
                "directors": directors,
                "shareholders": shareholders
            }
            
        except Exception as e:
            logger.error(f"Error getting company details: {e}")
            return None
    
    async def _query_cac_database(self, rc_number: str) -> Optional[Dict]:
        """
        Query CAC database for RC data
        
        Args:
            rc_number: Registration Certificate number
        
        Returns:
            CAC data or None if not found
        """
        try:
            # Prepare request
            endpoint = f"{self.base_url}/company/search"
            
            payload = {
                "rc_number": rc_number,
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
                logger.warning(f"RC not found: {rc_number}")
                return None
            else:
                logger.error(f"CAC API error: {response.status_code} - {response.text}")
                return None
                
        except httpx.HTTPError as e:
            logger.error(f"CAC API request error: {e}")
            return None
        except Exception as e:
            logger.error(f"CAC query error: {e}")
            # In sandbox mode, return mock data
            if self.use_sandbox:
                return self._get_mock_cac_data(rc_number)
            return None
    
    async def _get_directors(self, rc_number: str) -> List[Dict]:
        """Get list of directors"""
        
        try:
            endpoint = f"{self.base_url}/company/{rc_number}/directors"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("directors", [])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting directors: {e}")
            if self.use_sandbox:
                return self._get_mock_directors()
            return []
    
    async def _get_shareholders(self, rc_number: str) -> List[Dict]:
        """Get list of shareholders"""
        
        try:
            endpoint = f"{self.base_url}/company/{rc_number}/shareholders"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = await self.client.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("shareholders", [])
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting shareholders: {e}")
            if self.use_sandbox:
                return self._get_mock_shareholders()
            return []
    
    def _validate_rc_format(self, rc_number: str) -> bool:
        """Validate RC format"""
        
        if not rc_number:
            return False
        
        # Remove spaces and dashes
        rc_clean = rc_number.replace(" ", "").replace("-", "").upper()
        
        # RC format: RC followed by 6-7 digits (e.g., RC123456)
        # or BN followed by digits for business names
        # or IT followed by digits for incorporated trustees
        
        if rc_clean.startswith("RC") and len(rc_clean) >= 8:
            return rc_clean[2:].isdigit()
        elif rc_clean.startswith("BN") and len(rc_clean) >= 8:
            return rc_clean[2:].isdigit()
        elif rc_clean.startswith("IT") and len(rc_clean) >= 8:
            return rc_clean[2:].isdigit()
        
        return False
    
    def _verify_fields(
        self,
        cac_data: Dict,
        business_name: Optional[str],
        business_type: Optional[BusinessType]
    ) -> Dict[str, bool]:
        """Verify provided fields against CAC data"""
        
        verified = {}
        
        if business_name:
            cac_name = cac_data.get("company_name", "").lower()
            verified["business_name"] = self._names_match(business_name.lower(), cac_name)
        
        if business_type:
            cac_type = cac_data.get("company_type", "").lower()
            verified["business_type"] = self._types_match(business_type, cac_type)
        
        return verified
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if business names match"""
        
        if not name1 or not name2:
            return False
        
        # Remove common suffixes
        suffixes = ["limited", "ltd", "plc", "inc", "llc"]
        for suffix in suffixes:
            name1 = name1.replace(suffix, "").strip()
            name2 = name2.replace(suffix, "").strip()
        
        # Exact match
        if name1 == name2:
            return True
        
        # Check if one contains the other
        if name1 in name2 or name2 in name1:
            return True
        
        # Calculate similarity
        similarity = self._calculate_similarity(name1, name2)
        return similarity >= 0.85
    
    def _types_match(self, type1: BusinessType, type2: str) -> bool:
        """Check if business types match"""
        
        type_mapping = {
            BusinessType.LIMITED_COMPANY: ["limited", "ltd", "plc", "company"],
            BusinessType.BUSINESS_NAME: ["business", "bn", "enterprise"],
            BusinessType.INCORPORATED_TRUSTEES: ["trustees", "it", "trust"]
        }
        
        keywords = type_mapping.get(type1, [])
        return any(keyword in type2.lower() for keyword in keywords)
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity"""
        
        if str1 == str2:
            return 1.0
        
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
            return 1.0
        
        verified_count = sum(1 for v in verified_fields.values() if v)
        total_count = len(verified_fields)
        
        return verified_count / total_count
    
    def _sanitize_cac_data(self, cac_data: Dict) -> Dict:
        """Remove sensitive fields from CAC data"""
        
        safe_fields = [
            "rc_number",
            "company_name",
            "company_type",
            "registration_date",
            "status",
            "state",
            "lga",
            "address",
            "email",
            "phone",
            "branch_address",
            "authorized_share_capital",
            "paid_up_capital"
        ]
        
        sanitized = {}
        for field in safe_fields:
            if field in cac_data:
                sanitized[field] = cac_data[field]
        
        return sanitized
    
    def _generate_signature(self, payload: Dict) -> str:
        """Generate HMAC signature for request"""
        
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        signature = hmac.new(
            self.api_secret.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _get_mock_cac_data(self, rc_number: str) -> Dict:
        """Get mock CAC data for sandbox testing"""
        
        return {
            "rc_number": rc_number,
            "company_name": "ACME TECHNOLOGIES LIMITED",
            "company_type": "LIMITED_COMPANY",
            "registration_date": "2018-03-15",
            "status": "ACTIVE",
            "state": "LAGOS",
            "lga": "IKEJA",
            "address": "123 ALLEN AVENUE, IKEJA, LAGOS",
            "email": "info@acmetech.ng",
            "phone": "08012345678",
            "authorized_share_capital": "10000000.00",
            "paid_up_capital": "5000000.00",
            "objectives": "TECHNOLOGY SERVICES"
        }
    
    def _get_mock_directors(self) -> List[Dict]:
        """Get mock directors data"""
        
        return [
            {
                "name": "JOHN DOE",
                "position": "MANAGING DIRECTOR",
                "appointment_date": "2018-03-15",
                "nationality": "NIGERIAN",
                "nin": "12345678901"
            },
            {
                "name": "JANE SMITH",
                "position": "DIRECTOR",
                "appointment_date": "2018-03-15",
                "nationality": "NIGERIAN",
                "nin": "23456789012"
            }
        ]
    
    def _get_mock_shareholders(self) -> List[Dict]:
        """Get mock shareholders data"""
        
        return [
            {
                "name": "JOHN DOE",
                "shares": 6000,
                "percentage": 60.0,
                "shareholder_type": "INDIVIDUAL"
            },
            {
                "name": "JANE SMITH",
                "shares": 4000,
                "percentage": 40.0,
                "shareholder_type": "INDIVIDUAL"
            }
        ]
    
    def get_service_info(self) -> Dict:
        """Get service information"""
        return {
            "service": "cac-integration",
            "version": "1.0.0",
            "base_url": self.base_url,
            "sandbox_mode": self.use_sandbox,
            "local_processing": True
        }

# Initialize service (use sandbox by default)
cac_service = CACIntegrationService(use_sandbox=True)

# API endpoints
@app.post("/api/v1/cac/verify-rc", response_model=RCVerificationResponse)
async def verify_rc(request: RCVerificationRequest):
    """Verify RC with CAC database"""
    
    result = await cac_service.verify_rc(
        rc_number=request.rc_number,
        business_name=request.business_name,
        business_type=request.business_type
    )
    
    return result

@app.get("/api/v1/cac/company/{rc_number}")
async def get_company_details(rc_number: str):
    """Get detailed company information"""
    
    details = await cac_service.get_company_details(rc_number)
    
    if not details:
        raise HTTPException(status_code=404, detail="Company not found")
    
    return details

@app.get("/health")
async def health_check():
    """Health check"""
    info = cac_service.get_service_info()
    info["status"] = "healthy"
    info["timestamp"] = datetime.utcnow().isoformat()
    return info

@app.get("/info")
async def service_info():
    """Get service information"""
    return cac_service.get_service_info()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8048)
