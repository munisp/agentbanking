import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Production-Ready KYC/KYB Verification Service
Local implementation using Temporal for workflow orchestration
Integrates with: PostgreSQL, Kafka, Redis, Temporal, Lakehouse
"""

import os
import uuid
import logging
import json
import hashlib
import base64
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, AsyncGenerator
from decimal import Decimal
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
import re

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query, Path, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("kyc/kyb-verification-service-(production)")
app.include_router(metrics_router)

from pydantic import BaseModel, Field, EmailStr, validator
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VerificationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class VerificationType(str, Enum):
    KYC = "kyc"
    KYB = "kyb"
    AML = "aml"
    PEP = "pep"
    SANCTIONS = "sanctions"
    DOCUMENT = "document"
    LIVENESS = "liveness"
    ADDRESS = "address"


class DocumentType(str, Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    VOTER_ID = "voter_id"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    BUSINESS_REGISTRATION = "business_registration"
    TAX_CERTIFICATE = "tax_certificate"
    MEMORANDUM_OF_ASSOCIATION = "memorandum_of_association"
    ARTICLES_OF_INCORPORATION = "articles_of_incorporation"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ServiceConfig:
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/remittance"
    ))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"))
    kafka_bootstrap_servers: str = field(default_factory=lambda: os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    temporal_host: str = field(default_factory=lambda: os.getenv("TEMPORAL_HOST", "localhost:7233"))
    temporal_url: str = field(default_factory=lambda: os.getenv("TEMPORAL_URL", "http://localhost:7233"))
    lakehouse_url: str = field(default_factory=lambda: os.getenv("LAKEHOUSE_URL", "http://localhost:8181"))
    ocr_service_url: str = field(default_factory=lambda: os.getenv("OCR_SERVICE_URL", "http://localhost:8030"))
    document_storage_path: str = field(default_factory=lambda: os.getenv("DOCUMENT_STORAGE_PATH", "/tmp/documents"))


class DatabasePool:
    """Production-ready async database connection pool"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                max_inactive_connection_lifetime=300,
                command_timeout=60
            )
            logger.info("Database pool initialized")
    
    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        if self._pool is None:
            raise RuntimeError("Database pool not initialized")
        async with self._pool.acquire() as connection:
            yield connection
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        async with self.acquire() as connection:
            async with connection.transaction():
                yield connection


class RedisClient:
    """Production-ready Redis client"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
    
    async def initialize(self):
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            await self._client.ping()
            logger.info("Redis client initialized")
    
    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("Redis client not initialized")
        return self._client


class KafkaProducer:
    """Kafka producer for event streaming"""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self._producer = None
    
    async def initialize(self):
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all'
            )
            await self._producer.start()
            logger.info("Kafka producer initialized")
        except ImportError:
            logger.warning("aiokafka not installed")
        except Exception as e:
            logger.warning(f"Kafka connection failed: {e}")
    
    async def close(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
    
    async def send_event(self, topic: str, key: str, value: Dict[str, Any]):
        if self._producer:
            try:
                await self._producer.send_and_wait(topic, value=value, key=key)
            except Exception as e:
                logger.error(f"Failed to send Kafka event: {e}")


class TemporalWorkflowClient:
    """Temporal-based KYC/KYB workflow orchestration client (open-source replacement)"""
    
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self._client = httpx.AsyncClient(base_url=self.url, timeout=60.0)
        logger.info("Temporal workflow client initialized")
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def create_workflow(self, workflow_type: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new verification workflow via Temporal"""
        if not self._client:
            return self._local_workflow_creation(workflow_type, entity_data)
        
        try:
            response = await self._client.post(
                "/api/v1/namespaces/default/workflows",
                json={
                    "workflowId": f"remittance-{workflow_type}-{uuid.uuid4().hex[:8]}",
                    "workflowType": {"name": f"remittance-{workflow_type}"},
                    "taskQueue": {"name": "kyc-kyb-verification"},
                    "input": {
                        "payloads": [{
                            "data": entity_data
                        }]
                    }
                }
            )
            if response.status_code in (200, 201):
                result = response.json()
                return {
                    "id": result.get("workflowId", result.get("runId", str(uuid.uuid4()))),
                    "workflowDefinitionId": f"remittance-{workflow_type}",
                    "status": "active",
                    "context": {"entity": entity_data, "documents": [], "pluginsOutput": {}},
                    "createdAt": datetime.utcnow().isoformat()
                }
            return self._local_workflow_creation(workflow_type, entity_data)
        except Exception as e:
            logger.warning(f"Temporal API call failed: {e}, using local workflow")
            return self._local_workflow_creation(workflow_type, entity_data)
    
    def _local_workflow_creation(self, workflow_type: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Local workflow creation when Temporal is unavailable"""
        workflow_id = str(uuid.uuid4())
        return {
            "id": workflow_id,
            "workflowDefinitionId": f"remittance-{workflow_type}",
            "status": "active",
            "context": {
                "entity": entity_data,
                "documents": [],
                "pluginsOutput": {}
            },
            "createdAt": datetime.utcnow().isoformat()
        }
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow status from Temporal"""
        if not self._client:
            return {"id": workflow_id, "status": "active"}
        
        try:
            response = await self._client.get(
                f"/api/v1/namespaces/default/workflows/{workflow_id}"
            )
            if response.status_code == 200:
                result = response.json()
                status_map = {
                    "WORKFLOW_EXECUTION_STATUS_RUNNING": "active",
                    "WORKFLOW_EXECUTION_STATUS_COMPLETED": "completed",
                    "WORKFLOW_EXECUTION_STATUS_FAILED": "failed",
                    "WORKFLOW_EXECUTION_STATUS_TIMED_OUT": "timed_out",
                }
                raw_status = result.get("workflowExecutionInfo", {}).get("status", "")
                return {
                    "id": workflow_id,
                    "status": status_map.get(raw_status, "active")
                }
            return {"id": workflow_id, "status": "active"}
        except Exception as e:
            logger.warning(f"Failed to get workflow status: {e}")
            return {"id": workflow_id, "status": "active"}
    
    async def submit_document(self, workflow_id: str, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit document to workflow via Temporal signal"""
        if not self._client:
            return self._local_document_submission(workflow_id, document_data)
        
        try:
            response = await self._client.post(
                f"/api/v1/namespaces/default/workflows/{workflow_id}/signal",
                json={
                    "signalName": "document_submitted",
                    "input": {"payloads": [{"data": document_data}]}
                }
            )
            if response.status_code in (200, 201):
                return {
                    "id": str(uuid.uuid4()),
                    "workflowId": workflow_id,
                    "type": document_data.get("type"),
                    "status": "pending_verification",
                    "createdAt": datetime.utcnow().isoformat()
                }
            return self._local_document_submission(workflow_id, document_data)
        except Exception as e:
            logger.warning(f"Document submission failed: {e}")
            return self._local_document_submission(workflow_id, document_data)
    
    def _local_document_submission(self, workflow_id: str, document_data: Dict[str, Any]) -> Dict[str, Any]:
        """Local document submission when Temporal is unavailable"""
        return {
            "id": str(uuid.uuid4()),
            "workflowId": workflow_id,
            "type": document_data.get("type"),
            "status": "pending_verification",
            "createdAt": datetime.utcnow().isoformat()
        }


class LakehouseClient:
    """Lakehouse client for analytics"""
    
    def __init__(self, url: str):
        self.url = url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        self._client = httpx.AsyncClient(base_url=self.url, timeout=60.0)
        logger.info("Lakehouse client initialized")
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def write_event(self, table: str, data: Dict[str, Any]) -> bool:
        if not self._client:
            return True
        try:
            response = await self._client.post(f"/v1/tables/{table}/records", json=data)
            return response.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Lakehouse write failed: {e}")
            return False


class NigerianIDValidator:
    """Nigerian ID document validation rules"""
    
    NIN_PATTERN = re.compile(r'^\d{11}$')
    BVN_PATTERN = re.compile(r'^\d{11}$')
    PHONE_PATTERN = re.compile(r'^(\+234|0)[789]\d{9}$')
    CAC_PATTERN = re.compile(r'^(RC|BN|IT)\d{6,8}$', re.IGNORECASE)
    TIN_PATTERN = re.compile(r'^\d{8}-\d{4}$')
    
    @classmethod
    def validate_nin(cls, nin: str) -> tuple[bool, str]:
        """Validate Nigerian National Identification Number"""
        if not nin:
            return False, "NIN is required"
        if not cls.NIN_PATTERN.match(nin):
            return False, "NIN must be 11 digits"
        
        checksum = sum(int(d) * (11 - i) for i, d in enumerate(nin[:10])) % 11
        expected_check = 11 - checksum if checksum != 0 else 0
        if int(nin[10]) != expected_check:
            return False, "Invalid NIN checksum"
        
        return True, "Valid NIN"
    
    @classmethod
    def validate_bvn(cls, bvn: str) -> tuple[bool, str]:
        """Validate Bank Verification Number"""
        if not bvn:
            return False, "BVN is required"
        if not cls.BVN_PATTERN.match(bvn):
            return False, "BVN must be 11 digits"
        return True, "Valid BVN"
    
    @classmethod
    def validate_phone(cls, phone: str) -> tuple[bool, str]:
        """Validate Nigerian phone number"""
        if not phone:
            return False, "Phone number is required"
        normalized = phone.replace(" ", "").replace("-", "")
        if not cls.PHONE_PATTERN.match(normalized):
            return False, "Invalid Nigerian phone number format"
        return True, "Valid phone number"
    
    @classmethod
    def validate_cac(cls, cac_number: str) -> tuple[bool, str]:
        """Validate CAC registration number"""
        if not cac_number:
            return False, "CAC number is required"
        if not cls.CAC_PATTERN.match(cac_number):
            return False, "Invalid CAC number format (expected RC/BN/IT followed by 6-8 digits)"
        return True, "Valid CAC number"
    
    @classmethod
    def validate_tin(cls, tin: str) -> tuple[bool, str]:
        """Validate Tax Identification Number"""
        if not tin:
            return False, "TIN is required"
        if not cls.TIN_PATTERN.match(tin):
            return False, "Invalid TIN format (expected XXXXXXXX-XXXX)"
        return True, "Valid TIN"


class RiskScorer:
    """Risk scoring engine for KYC/KYB verification"""
    
    HIGH_RISK_COUNTRIES = ["AF", "IR", "KP", "SY", "YE", "VE", "MM", "BY", "RU"]
    HIGH_RISK_INDUSTRIES = ["gambling", "cryptocurrency", "weapons", "adult_entertainment", "precious_metals"]
    PEP_POSITIONS = ["president", "minister", "governor", "senator", "judge", "military_officer", "diplomat"]
    
    @classmethod
    def calculate_kyc_risk_score(
        cls,
        personal_info: Dict[str, Any],
        verification_results: Dict[str, Any],
        document_scores: List[float]
    ) -> tuple[float, RiskLevel, List[str]]:
        """Calculate KYC risk score"""
        
        base_score = 0.5
        risk_factors = []
        
        if document_scores:
            avg_doc_score = sum(document_scores) / len(document_scores)
            base_score = (base_score + avg_doc_score) / 2
        
        if verification_results.get("identity_verified"):
            base_score += 0.1
        else:
            base_score -= 0.15
            risk_factors.append("Identity not verified")
        
        if verification_results.get("address_verified"):
            base_score += 0.05
        else:
            risk_factors.append("Address not verified")
        
        if verification_results.get("liveness_passed"):
            base_score += 0.1
        else:
            base_score -= 0.1
            risk_factors.append("Liveness check failed")
        
        country = personal_info.get("country", "").upper()
        if country in cls.HIGH_RISK_COUNTRIES:
            base_score -= 0.2
            risk_factors.append(f"High-risk country: {country}")
        
        if verification_results.get("pep_match"):
            base_score -= 0.15
            risk_factors.append("PEP match found")
        
        if verification_results.get("sanctions_match"):
            base_score -= 0.3
            risk_factors.append("Sanctions match found")
        
        if verification_results.get("adverse_media"):
            base_score -= 0.1
            risk_factors.append("Adverse media found")
        
        age = personal_info.get("age", 30)
        if age < 21:
            base_score -= 0.05
            risk_factors.append("Young applicant")
        elif age > 70:
            base_score -= 0.05
            risk_factors.append("Senior applicant")
        
        risk_score = max(0.0, min(1.0, base_score))
        
        if risk_score >= 0.8:
            risk_level = RiskLevel.LOW
        elif risk_score >= 0.6:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 0.4:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.VERY_HIGH
        
        return risk_score, risk_level, risk_factors
    
    @classmethod
    def calculate_kyb_risk_score(
        cls,
        business_info: Dict[str, Any],
        verification_results: Dict[str, Any],
        document_scores: List[float]
    ) -> tuple[float, RiskLevel, List[str]]:
        """Calculate KYB risk score"""
        
        base_score = 0.5
        risk_factors = []
        
        if document_scores:
            avg_doc_score = sum(document_scores) / len(document_scores)
            base_score = (base_score + avg_doc_score) / 2
        
        if verification_results.get("business_registered"):
            base_score += 0.15
        else:
            base_score -= 0.2
            risk_factors.append("Business not registered")
        
        if verification_results.get("tax_compliant"):
            base_score += 0.1
        else:
            risk_factors.append("Tax compliance not verified")
        
        years_in_business = business_info.get("years_in_business", 0)
        if years_in_business >= 5:
            base_score += 0.1
        elif years_in_business >= 2:
            base_score += 0.05
        elif years_in_business < 1:
            base_score -= 0.1
            risk_factors.append("New business (less than 1 year)")
        
        industry = business_info.get("industry", "").lower()
        if industry in cls.HIGH_RISK_INDUSTRIES:
            base_score -= 0.2
            risk_factors.append(f"High-risk industry: {industry}")
        
        country = business_info.get("country", "").upper()
        if country in cls.HIGH_RISK_COUNTRIES:
            base_score -= 0.2
            risk_factors.append(f"High-risk country: {country}")
        
        if verification_results.get("ubo_verified"):
            base_score += 0.1
        else:
            base_score -= 0.1
            risk_factors.append("UBO not verified")
        
        if verification_results.get("sanctions_match"):
            base_score -= 0.3
            risk_factors.append("Business sanctions match")
        
        risk_score = max(0.0, min(1.0, base_score))
        
        if risk_score >= 0.8:
            risk_level = RiskLevel.LOW
        elif risk_score >= 0.6:
            risk_level = RiskLevel.MEDIUM
        elif risk_score >= 0.4:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.VERY_HIGH
        
        return risk_score, risk_level, risk_factors


SANCTIONS_API_URL = os.getenv("SANCTIONS_API_URL", "http://localhost:8050")


class AMLScreener:
    """Anti-Money Laundering screening via external sanctions/PEP API"""

    WATCHLIST_SOURCES = [
        "OFAC_SDN",
        "UN_SANCTIONS",
        "EU_SANCTIONS",
        "UK_SANCTIONS",
        "NIGERIA_EFCC",
        "INTERPOL",
    ]

    HIGH_RISK_COUNTRIES = {"KP", "IR", "SY", "RU", "BY", "CU", "VE", "MM", "SD", "SO"}

    @classmethod
    async def _call_screening_api(
        cls,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Call the external screening API with retry"""
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        f"{SANCTIONS_API_URL}{endpoint}",
                        json=payload,
                    )
                    if response.status_code == 200:
                        return response.json()
                    logger.warning(f"Screening API returned {response.status_code} on attempt {attempt + 1}")
            except httpx.ConnectError:
                logger.warning(f"Screening API unavailable on attempt {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        return None

    @classmethod
    async def screen_individual(
        cls,
        first_name: str,
        last_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Screen individual against watchlists via external API"""

        screening_results: Dict[str, Any] = {
            "screened_at": datetime.utcnow().isoformat(),
            "full_name": f"{first_name} {last_name}",
            "sanctions_match": False,
            "pep_match": False,
            "adverse_media": False,
            "matches": [],
            "sources_checked": cls.WATCHLIST_SOURCES,
            "risk_indicators": [],
        }

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": date_of_birth,
            "nationality": nationality,
        }

        api_result = await cls._call_screening_api("/api/v1/screen/individual", payload)

        if api_result:
            for match in api_result.get("matches", []):
                screening_results["matches"].append(match)
                match_type = match.get("type", "").upper()
                if match_type == "SANCTIONS":
                    screening_results["sanctions_match"] = True
                elif match_type == "PEP":
                    screening_results["pep_match"] = True
                elif match_type == "ADVERSE_MEDIA":
                    screening_results["adverse_media"] = True
            screening_results["risk_indicators"].extend(api_result.get("risk_indicators", []))
        else:
            screening_results["risk_indicators"].append("screening_api_unavailable")

        if nationality and nationality.upper() in cls.HIGH_RISK_COUNTRIES:
            screening_results["risk_indicators"].append(f"High-risk nationality: {nationality}")

        return screening_results

    @classmethod
    async def screen_business(
        cls,
        business_name: str,
        registration_number: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Screen business against watchlists via external API"""

        screening_results: Dict[str, Any] = {
            "screened_at": datetime.utcnow().isoformat(),
            "business_name": business_name,
            "sanctions_match": False,
            "adverse_media": False,
            "matches": [],
            "sources_checked": cls.WATCHLIST_SOURCES,
            "risk_indicators": [],
        }

        payload = {
            "business_name": business_name,
            "registration_number": registration_number,
            "country": country,
        }

        api_result = await cls._call_screening_api("/api/v1/screen/business", payload)

        if api_result:
            for match in api_result.get("matches", []):
                screening_results["matches"].append(match)
                match_type = match.get("type", "").upper()
                if match_type == "SANCTIONS":
                    screening_results["sanctions_match"] = True
                elif match_type == "ADVERSE_MEDIA":
                    screening_results["adverse_media"] = True
            screening_results["risk_indicators"].extend(api_result.get("risk_indicators", []))
        else:
            screening_results["risk_indicators"].append("screening_api_unavailable")

        if country and country.upper() in cls.HIGH_RISK_COUNTRIES:
            screening_results["risk_indicators"].append(f"High-risk jurisdiction: {country}")

        return screening_results


class KYCVerificationRequest(BaseModel):
    agent_id: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: str
    gender: str
    nationality: str
    phone: str
    email: EmailStr
    address: Dict[str, Any]
    nin: Optional[str] = None
    bvn: Optional[str] = None
    
    @validator('date_of_birth')
    def validate_dob(cls, v):
        try:
            dob = datetime.strptime(v, "%Y-%m-%d")
            age = (datetime.now() - dob).days // 365
            if age < 18:
                raise ValueError("Applicant must be at least 18 years old")
            if age > 120:
                raise ValueError("Invalid date of birth")
            return v
        except ValueError as e:
            raise ValueError(f"Invalid date format: {e}")


class KYBVerificationRequest(BaseModel):
    agent_id: str
    business_name: str
    business_type: str
    registration_number: str
    tax_id: Optional[str] = None
    incorporation_date: str
    industry: str
    business_address: Dict[str, Any]
    directors: List[Dict[str, Any]]
    shareholders: List[Dict[str, Any]]
    annual_revenue: Optional[float] = None
    employee_count: Optional[int] = None


class VerificationResponse(BaseModel):
    verification_id: str
    agent_id: str
    verification_type: str
    status: str
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_factors: List[str] = []
    workflow_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None


class ServiceContainer:
    """Container for all service dependencies"""
    
    def __init__(self, config: ServiceConfig):
        self.config = config
        self.db = DatabasePool(config.database_url)
        self.redis = RedisClient(config.redis_url)
        self.kafka = KafkaProducer(config.kafka_bootstrap_servers)
        self.workflow = TemporalWorkflowClient(config.temporal_url)
        self.lakehouse = LakehouseClient(config.lakehouse_url)
    
    async def initialize(self):
        await self.db.initialize()
        await self.redis.initialize()
        await self.kafka.initialize()
        await self.workflow.initialize()
        await self.lakehouse.initialize()
        await self._ensure_tables()
        logger.info("All services initialized")
    
    async def close(self):
        await self.lakehouse.close()
        await self.workflow.close()
        await self.kafka.close()
        await self.redis.close()
        await self.db.close()
        logger.info("All services closed")
    
    async def _ensure_tables(self):
        """Ensure all required tables exist"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kyc_verifications (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id VARCHAR(50) NOT NULL,
                    verification_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    workflow_id VARCHAR(100),
                    personal_info JSONB,
                    verification_results JSONB DEFAULT '{}',
                    risk_score DECIMAL(5,4),
                    risk_level VARCHAR(20),
                    risk_factors JSONB DEFAULT '[]',
                    documents JSONB DEFAULT '[]',
                    aml_screening JSONB,
                    reviewer_id VARCHAR(50),
                    reviewer_notes TEXT,
                    approved_at TIMESTAMP,
                    rejected_at TIMESTAMP,
                    rejection_reason TEXT,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kyb_verifications (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id VARCHAR(50) NOT NULL,
                    verification_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    workflow_id VARCHAR(100),
                    business_info JSONB,
                    verification_results JSONB DEFAULT '{}',
                    risk_score DECIMAL(5,4),
                    risk_level VARCHAR(20),
                    risk_factors JSONB DEFAULT '[]',
                    documents JSONB DEFAULT '[]',
                    directors_verification JSONB DEFAULT '[]',
                    shareholders_verification JSONB DEFAULT '[]',
                    aml_screening JSONB,
                    reviewer_id VARCHAR(50),
                    reviewer_notes TEXT,
                    approved_at TIMESTAMP,
                    rejected_at TIMESTAMP,
                    rejection_reason TEXT,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    verification_id UUID NOT NULL,
                    verification_type VARCHAR(10) NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    file_name VARCHAR(255),
                    file_path VARCHAR(500),
                    file_size INTEGER,
                    mime_type VARCHAR(100),
                    ocr_result JSONB,
                    validation_result JSONB,
                    verification_score DECIMAL(5,4),
                    status VARCHAR(50) DEFAULT 'pending',
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    verified_at TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_audit_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    verification_id UUID NOT NULL,
                    verification_type VARCHAR(10) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    actor_id VARCHAR(50),
                    actor_type VARCHAR(20),
                    details JSONB,
                    ip_address INET,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            logger.info("Database tables ensured")


services: Optional[ServiceContainer] = None


def get_services() -> ServiceContainer:
    if services is None:
        raise RuntimeError("Services not initialized")
    return services


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global services
    
    try:
        config = ServiceConfig()
        services = ServiceContainer(config)
        await services.initialize()
        yield
    finally:
        if services:
            await services.close()


app = FastAPI(
    title="KYC/KYB Verification Service (Production)",
    description="Production-ready KYC/KYB verification with Temporal workflow orchestration",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/kyc/verify", response_model=VerificationResponse)
async def initiate_kyc_verification(
    data: KYCVerificationRequest,
    background_tasks: BackgroundTasks,
    svc: ServiceContainer = Depends(get_services)
):
    """Initiate KYC verification for an agent"""
    
    if data.nin:
        valid, message = NigerianIDValidator.validate_nin(data.nin)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid NIN: {message}")
    
    if data.bvn:
        valid, message = NigerianIDValidator.validate_bvn(data.bvn)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid BVN: {message}")
    
    valid, message = NigerianIDValidator.validate_phone(data.phone)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid phone: {message}")
    
    personal_info = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "middle_name": data.middle_name,
        "date_of_birth": data.date_of_birth,
        "gender": data.gender,
        "nationality": data.nationality,
        "phone": data.phone,
        "email": data.email,
        "address": data.address,
        "nin": data.nin,
        "bvn": data.bvn
    }
    
    workflow = await svc.workflow.create_workflow("kyc", personal_info)
    
    aml_results = await AMLScreener.screen_individual(
        data.first_name,
        data.last_name,
        data.date_of_birth,
        data.nationality
    )
    
    verification_results = {
        "identity_verified": False,
        "address_verified": False,
        "liveness_passed": False,
        "pep_match": aml_results.get("pep_match", False),
        "sanctions_match": aml_results.get("sanctions_match", False),
        "adverse_media": aml_results.get("adverse_media", False)
    }
    
    risk_score, risk_level, risk_factors = RiskScorer.calculate_kyc_risk_score(
        personal_info,
        verification_results,
        []
    )
    
    status = VerificationStatus.PENDING
    if aml_results.get("sanctions_match"):
        status = VerificationStatus.REJECTED
    elif aml_results.get("pep_match"):
        status = VerificationStatus.MANUAL_REVIEW
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO kyc_verifications (
                agent_id, verification_type, status, workflow_id, personal_info,
                verification_results, risk_score, risk_level, risk_factors, aml_screening,
                expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            data.agent_id, VerificationType.KYC.value, status.value,
            workflow.get("id"), json.dumps(personal_info),
            json.dumps(verification_results), risk_score, risk_level.value,
            json.dumps(risk_factors), json.dumps(aml_results),
            datetime.utcnow() + timedelta(days=365)
        )
        
        await conn.execute(
            """
            INSERT INTO verification_audit_log (
                verification_id, verification_type, action, actor_id, actor_type, details
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            result['id'], "kyc", "verification_initiated", data.agent_id, "agent",
            json.dumps({"workflow_id": workflow.get("id")})
        )
    
    event_data = {
        "event_type": "kyc.verification_initiated",
        "verification_id": str(result['id']),
        "agent_id": data.agent_id,
        "status": status.value,
        "risk_level": risk_level.value,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("kyc-events", data.agent_id, event_data)
    await svc.lakehouse.write_event("kyc_events", event_data)
    
    return VerificationResponse(
        verification_id=str(result['id']),
        agent_id=result['agent_id'],
        verification_type=result['verification_type'],
        status=result['status'],
        risk_score=float(result['risk_score']) if result['risk_score'] else None,
        risk_level=result['risk_level'],
        risk_factors=json.loads(result['risk_factors']) if result['risk_factors'] else [],
        workflow_id=result['workflow_id'],
        created_at=result['created_at'],
        updated_at=result['updated_at'],
        expires_at=result['expires_at']
    )


@app.post("/kyb/verify", response_model=VerificationResponse)
async def initiate_kyb_verification(
    data: KYBVerificationRequest,
    background_tasks: BackgroundTasks,
    svc: ServiceContainer = Depends(get_services)
):
    """Initiate KYB verification for an agent's business"""
    
    valid, message = NigerianIDValidator.validate_cac(data.registration_number)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid CAC number: {message}")
    
    if data.tax_id:
        valid, message = NigerianIDValidator.validate_tin(data.tax_id)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid TIN: {message}")
    
    business_info = {
        "business_name": data.business_name,
        "business_type": data.business_type,
        "registration_number": data.registration_number,
        "tax_id": data.tax_id,
        "incorporation_date": data.incorporation_date,
        "industry": data.industry,
        "business_address": data.business_address,
        "directors": data.directors,
        "shareholders": data.shareholders,
        "annual_revenue": data.annual_revenue,
        "employee_count": data.employee_count
    }
    
    try:
        inc_date = datetime.strptime(data.incorporation_date, "%Y-%m-%d")
        years_in_business = (datetime.now() - inc_date).days // 365
        business_info["years_in_business"] = years_in_business
    except ValueError:
        business_info["years_in_business"] = 0
    
    workflow = await svc.workflow.create_workflow("kyb", business_info)
    
    aml_results = await AMLScreener.screen_business(
        data.business_name,
        data.registration_number,
        data.business_address.get("country", "NG")
    )
    
    verification_results = {
        "business_registered": False,
        "tax_compliant": False,
        "ubo_verified": False,
        "sanctions_match": aml_results.get("sanctions_match", False),
        "adverse_media": aml_results.get("adverse_media", False)
    }
    
    risk_score, risk_level, risk_factors = RiskScorer.calculate_kyb_risk_score(
        business_info,
        verification_results,
        []
    )
    
    status = VerificationStatus.PENDING
    if aml_results.get("sanctions_match"):
        status = VerificationStatus.REJECTED
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO kyb_verifications (
                agent_id, verification_type, status, workflow_id, business_info,
                verification_results, risk_score, risk_level, risk_factors, aml_screening,
                expires_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            data.agent_id, VerificationType.KYB.value, status.value,
            workflow.get("id"), json.dumps(business_info),
            json.dumps(verification_results), risk_score, risk_level.value,
            json.dumps(risk_factors), json.dumps(aml_results),
            datetime.utcnow() + timedelta(days=365)
        )
        
        await conn.execute(
            """
            INSERT INTO verification_audit_log (
                verification_id, verification_type, action, actor_id, actor_type, details
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            result['id'], "kyb", "verification_initiated", data.agent_id, "agent",
            json.dumps({"workflow_id": workflow.get("id"), "business_name": data.business_name})
        )
    
    event_data = {
        "event_type": "kyb.verification_initiated",
        "verification_id": str(result['id']),
        "agent_id": data.agent_id,
        "business_name": data.business_name,
        "status": status.value,
        "risk_level": risk_level.value,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("kyc-events", data.agent_id, event_data)
    await svc.lakehouse.write_event("kyb_events", event_data)
    
    return VerificationResponse(
        verification_id=str(result['id']),
        agent_id=result['agent_id'],
        verification_type=result['verification_type'],
        status=result['status'],
        risk_score=float(result['risk_score']) if result['risk_score'] else None,
        risk_level=result['risk_level'],
        risk_factors=json.loads(result['risk_factors']) if result['risk_factors'] else [],
        workflow_id=result['workflow_id'],
        created_at=result['created_at'],
        updated_at=result['updated_at'],
        expires_at=result['expires_at']
    )


@app.get("/kyc/{verification_id}", response_model=VerificationResponse)
async def get_kyc_verification(
    verification_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get KYC verification status"""
    
    async with svc.db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM kyc_verifications WHERE id = $1",
            uuid.UUID(verification_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Verification not found")
        
        return VerificationResponse(
            verification_id=str(result['id']),
            agent_id=result['agent_id'],
            verification_type=result['verification_type'],
            status=result['status'],
            risk_score=float(result['risk_score']) if result['risk_score'] else None,
            risk_level=result['risk_level'],
            risk_factors=json.loads(result['risk_factors']) if result['risk_factors'] else [],
            workflow_id=result['workflow_id'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            expires_at=result['expires_at']
        )


@app.get("/kyb/{verification_id}", response_model=VerificationResponse)
async def get_kyb_verification(
    verification_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get KYB verification status"""
    
    async with svc.db.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM kyb_verifications WHERE id = $1",
            uuid.UUID(verification_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Verification not found")
        
        return VerificationResponse(
            verification_id=str(result['id']),
            agent_id=result['agent_id'],
            verification_type=result['verification_type'],
            status=result['status'],
            risk_score=float(result['risk_score']) if result['risk_score'] else None,
            risk_level=result['risk_level'],
            risk_factors=json.loads(result['risk_factors']) if result['risk_factors'] else [],
            workflow_id=result['workflow_id'],
            created_at=result['created_at'],
            updated_at=result['updated_at'],
            expires_at=result['expires_at']
        )


@app.post("/kyc/{verification_id}/documents")
async def upload_kyc_document(
    verification_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...),
    svc: ServiceContainer = Depends(get_services)
):
    """Upload document for KYC verification"""
    
    async with svc.db.acquire() as conn:
        verification = await conn.fetchrow(
            "SELECT * FROM kyc_verifications WHERE id = $1",
            uuid.UUID(verification_id)
        )
        if not verification:
            raise HTTPException(status_code=404, detail="Verification not found")
    
    file_content = await file.read()
    file_hash = hashlib.sha256(file_content).hexdigest()
    file_path = f"{svc.config.document_storage_path}/{verification_id}/{file_hash}_{file.filename}"
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    ocr_result = None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{svc.config.ocr_service_url}/ocr/extract",
                files={"file": (file.filename, file_content, file.content_type)},
                data={"document_type": document_type.value}
            )
            if response.status_code == 200:
                ocr_result = response.json()
    except Exception as e:
        logger.warning(f"OCR service unavailable: {e}")
    
    validation_result = {
        "document_type": document_type.value,
        "file_hash": file_hash,
        "file_size": len(file_content),
        "validated_at": datetime.utcnow().isoformat()
    }
    
    verification_score = 0.7
    if ocr_result and ocr_result.get("confidence", 0) > 0.8:
        verification_score = 0.9
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            """
            INSERT INTO verification_documents (
                verification_id, verification_type, document_type, file_name,
                file_path, file_size, mime_type, ocr_result, validation_result,
                verification_score, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            RETURNING *
            """,
            uuid.UUID(verification_id), "kyc", document_type.value,
            file.filename, file_path, len(file_content), file.content_type,
            json.dumps(ocr_result) if ocr_result else None,
            json.dumps(validation_result), verification_score, "pending_verification"
        )
        
        await svc.workflow.submit_document(
            verification['workflow_id'],
            {
                "type": document_type.value,
                "fileId": str(result['id']),
                "fileName": file.filename
            }
        )
    
    return {
        "document_id": str(result['id']),
        "verification_id": verification_id,
        "document_type": document_type.value,
        "file_name": file.filename,
        "verification_score": verification_score,
        "status": "pending_verification"
    }


@app.put("/kyc/{verification_id}/approve")
async def approve_kyc_verification(
    verification_id: str,
    reviewer_id: str,
    notes: Optional[str] = None,
    svc: ServiceContainer = Depends(get_services)
):
    """Approve KYC verification"""
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM kyc_verifications WHERE id = $1",
            uuid.UUID(verification_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Verification not found")
        
        if result['status'] not in [VerificationStatus.PENDING.value, VerificationStatus.MANUAL_REVIEW.value, VerificationStatus.IN_PROGRESS.value]:
            raise HTTPException(status_code=400, detail=f"Cannot approve verification in status: {result['status']}")
        
        await conn.execute(
            """
            UPDATE kyc_verifications
            SET status = $1, reviewer_id = $2, reviewer_notes = $3, approved_at = $4, updated_at = $5
            WHERE id = $6
            """,
            VerificationStatus.APPROVED.value, reviewer_id, notes,
            datetime.utcnow(), datetime.utcnow(), uuid.UUID(verification_id)
        )
        
        await conn.execute(
            """
            INSERT INTO verification_audit_log (
                verification_id, verification_type, action, actor_id, actor_type, details
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(verification_id), "kyc", "verification_approved", reviewer_id, "reviewer",
            json.dumps({"notes": notes})
        )
    
    event_data = {
        "event_type": "kyc.verification_approved",
        "verification_id": verification_id,
        "agent_id": result['agent_id'],
        "reviewer_id": reviewer_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("kyc-events", result['agent_id'], event_data)
    await svc.lakehouse.write_event("kyc_events", event_data)
    
    return {"success": True, "verification_id": verification_id, "status": "approved"}


@app.put("/kyc/{verification_id}/reject")
async def reject_kyc_verification(
    verification_id: str,
    reviewer_id: str,
    reason: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Reject KYC verification"""
    
    async with svc.db.transaction() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM kyc_verifications WHERE id = $1",
            uuid.UUID(verification_id)
        )
        if not result:
            raise HTTPException(status_code=404, detail="Verification not found")
        
        await conn.execute(
            """
            UPDATE kyc_verifications
            SET status = $1, reviewer_id = $2, rejection_reason = $3, rejected_at = $4, updated_at = $5
            WHERE id = $6
            """,
            VerificationStatus.REJECTED.value, reviewer_id, reason,
            datetime.utcnow(), datetime.utcnow(), uuid.UUID(verification_id)
        )
        
        await conn.execute(
            """
            INSERT INTO verification_audit_log (
                verification_id, verification_type, action, actor_id, actor_type, details
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            uuid.UUID(verification_id), "kyc", "verification_rejected", reviewer_id, "reviewer",
            json.dumps({"reason": reason})
        )
    
    event_data = {
        "event_type": "kyc.verification_rejected",
        "verification_id": verification_id,
        "agent_id": result['agent_id'],
        "reviewer_id": reviewer_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat()
    }
    await svc.kafka.send_event("kyc-events", result['agent_id'], event_data)
    await svc.lakehouse.write_event("kyc_events", event_data)
    
    return {"success": True, "verification_id": verification_id, "status": "rejected"}


@app.get("/agent/{agent_id}/verification-status")
async def get_agent_verification_status(
    agent_id: str,
    svc: ServiceContainer = Depends(get_services)
):
    """Get all verification statuses for an agent"""
    
    async with svc.db.acquire() as conn:
        kyc_result = await conn.fetchrow(
            """
            SELECT * FROM kyc_verifications 
            WHERE agent_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            agent_id
        )
        
        kyb_result = await conn.fetchrow(
            """
            SELECT * FROM kyb_verifications 
            WHERE agent_id = $1 
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            agent_id
        )
    
    return {
        "agent_id": agent_id,
        "kyc": {
            "verification_id": str(kyc_result['id']) if kyc_result else None,
            "status": kyc_result['status'] if kyc_result else "not_started",
            "risk_level": kyc_result['risk_level'] if kyc_result else None,
            "expires_at": kyc_result['expires_at'].isoformat() if kyc_result and kyc_result['expires_at'] else None
        } if kyc_result else {"status": "not_started"},
        "kyb": {
            "verification_id": str(kyb_result['id']) if kyb_result else None,
            "status": kyb_result['status'] if kyb_result else "not_started",
            "risk_level": kyb_result['risk_level'] if kyb_result else None,
            "expires_at": kyb_result['expires_at'].isoformat() if kyb_result and kyb_result['expires_at'] else None
        } if kyb_result else {"status": "not_started"},
        "overall_status": _calculate_overall_status(kyc_result, kyb_result)
    }


def _calculate_overall_status(kyc_result, kyb_result) -> str:
    """Calculate overall verification status"""
    if not kyc_result and not kyb_result:
        return "not_started"
    
    kyc_status = kyc_result['status'] if kyc_result else "not_started"
    kyb_status = kyb_result['status'] if kyb_result else "not_started"
    
    if kyc_status == "rejected" or kyb_status == "rejected":
        return "rejected"
    
    if kyc_status == "approved" and kyb_status == "approved":
        return "fully_verified"
    
    if kyc_status == "approved" and kyb_status == "not_started":
        return "kyc_verified"
    
    if kyc_status == "manual_review" or kyb_status == "manual_review":
        return "manual_review"
    
    if kyc_status == "in_progress" or kyb_status == "in_progress":
        return "in_progress"
    
    return "pending"


@app.get("/health")
async def health_check(svc: ServiceContainer = Depends(get_services)):
    """Health check endpoint"""
    
    health_status = {
        "status": "healthy",
        "service": "KYC/KYB Verification Service (Production)",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    try:
        async with svc.db.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    try:
        await svc.redis.client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8029)
