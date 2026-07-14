from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BANK_STATEMENT = "bank_statement"
    UTILITY_BILL = "utility_bill"
    CORPORATE_REGISTRATION = "corporate_registration"
    TAX_DOCUMENT = "tax_document"
    LOAN_APPLICATION = "loan_application"
    FINANCIAL_STATEMENT = "financial_statement"
    UNKNOWN = "unknown"

class ProcessingStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentResult(BaseModel):
    document_id: str
    document_type: DocumentType
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    parsed_fields: Dict[str, Any] = {}
    tables: List[Dict[str, Any]] = []
    images: List[str] = []
    metadata: Dict[str, Any] = {}
    processing_time_ms: int
