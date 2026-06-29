"""
Document Processing Service with Docling + DeepSeek OCR
Handles KYC/KYB document verification, compliance processing, receipt analysis
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

import boto3
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from redis import Redis
import httpx

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


# Docling imports
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
except ImportError:
    print("Warning: Docling not installed. Install with: pip install docling")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Document Processing Service", version="1.0.0")

# Database setup
DATABASE_URL = "postgresql://user:password@localhost:5432/docprocessing"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# Redis for job queue
redis_client = Redis(host='localhost', port=6379, decode_responses=True)

# S3 client
s3_client = boto3.client('s3', region_name='us-east-1')
S3_BUCKET = "remittance-documents"

# Document types
class DocumentType(str, Enum):
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    UTILITY_BILL = "utility_bill"
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN = "tax_return"
    BUSINESS_REGISTRATION = "business_registration"
    TRANSACTION_RECEIPT = "transaction_receipt"
    CONTRACT = "contract"
    COMPLIANCE_REPORT = "compliance_report"
    UNKNOWN = "unknown"

# Processing status
class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    VALIDATED = "validated"
    REJECTED = "rejected"

# Database models
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    document_type = Column(SQLEnum(DocumentType), nullable=False)
    original_filename = Column(String, nullable=False)
    s3_key = Column(String, nullable=False)
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    extracted_data = Column(JSON)
    validation_result = Column(JSON)
    confidence_score = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    error_message = Column(String)

Base.metadata.create_all(engine)

# Pydantic models
class DocumentUploadResponse(BaseModel):
    document_id: str
    status: ProcessingStatus
    message: str

class ExtractedEntity(BaseModel):
    field: str
    value: str
    confidence: float
    bounding_box: Optional[Dict[str, float]] = None

class DocumentProcessingResult(BaseModel):
    document_id: str
    document_type: DocumentType
    status: ProcessingStatus
    extracted_entities: List[ExtractedEntity]
    raw_text: str
    markdown_content: str
    confidence_score: float
    validation_result: Optional[Dict[str, Any]] = None
    processing_time_seconds: float

class ValidationRule(BaseModel):
    field: str
    required: bool
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None

# Document type configurations
DOCUMENT_CONFIGS = {
    DocumentType.PASSPORT: {
        "required_fields": ["full_name", "passport_number", "date_of_birth", "nationality", "expiry_date"],
        "validation_rules": [
            ValidationRule(field="passport_number", required=True, pattern=r"^[A-Z0-9]{6,9}$"),
            ValidationRule(field="full_name", required=True, min_length=3, max_length=100),
        ]
    },
    DocumentType.NATIONAL_ID: {
        "required_fields": ["full_name", "id_number", "date_of_birth", "address"],
        "validation_rules": [
            ValidationRule(field="id_number", required=True, pattern=r"^\d{11}$"),
            ValidationRule(field="full_name", required=True, min_length=3, max_length=100),
        ]
    },
    DocumentType.BANK_STATEMENT: {
        "required_fields": ["account_holder", "account_number", "bank_name", "statement_period"],
        "validation_rules": [
            ValidationRule(field="account_number", required=True, pattern=r"^\d{10}$"),
        ]
    },
    DocumentType.UTILITY_BILL: {
        "required_fields": ["customer_name", "address", "bill_date", "amount"],
        "validation_rules": [
            ValidationRule(field="customer_name", required=True, min_length=3),
            ValidationRule(field="address", required=True, min_length=10),
        ]
    }
}

class DoclingProcessor:
    """Document processor using Docling + DeepSeek OCR"""
    
    def __init__(self):
        # Initialize Docling converter
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pipeline_options,
            }
        )
        
        logger.info("DoclingProcessor initialized")
    
    async def process_document(
        self,
        file_path: Path,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """Process document with Docling"""
        
        start_time = datetime.utcnow()
        
        try:
            # Convert document
            logger.info(f"Processing document: {file_path}")
            result = self.converter.convert(str(file_path))
            
            # Extract content
            markdown_content = result.document.export_to_markdown()
            raw_text = result.document.export_to_text()
            
            # Extract entities based on document type
            extracted_entities = await self._extract_entities(
                result.document,
                document_type,
                markdown_content
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence(extracted_entities)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "extracted_entities": extracted_entities,
                "raw_text": raw_text,
                "markdown_content": markdown_content,
                "confidence_score": confidence_score,
                "processing_time_seconds": processing_time,
                "page_count": len(result.document.pages) if hasattr(result.document, 'pages') else 1,
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")
    
    async def _extract_entities(
        self,
        document: Any,
        document_type: DocumentType,
        markdown_content: str
    ) -> List[ExtractedEntity]:
        """Extract entities from document based on type"""
        
        entities = []
        
        # Get document configuration
        config = DOCUMENT_CONFIGS.get(document_type, {})
        required_fields = config.get("required_fields", [])
        
        # Extract entities using pattern matching and NER
        # This is a simplified version - in production, use ML models
        
        if document_type == DocumentType.PASSPORT:
            entities = self._extract_passport_entities(markdown_content)
        elif document_type == DocumentType.NATIONAL_ID:
            entities = self._extract_national_id_entities(markdown_content)
        elif document_type == DocumentType.BANK_STATEMENT:
            entities = self._extract_bank_statement_entities(markdown_content)
        elif document_type == DocumentType.UTILITY_BILL:
            entities = self._extract_utility_bill_entities(markdown_content)
        else:
            # Generic extraction
            entities = self._extract_generic_entities(markdown_content)
        
        return entities
    
    def _extract_passport_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract passport-specific entities"""
        import re
        
        entities = []
        
        # Extract passport number (pattern: A12345678)
        passport_pattern = r'(?:Passport\s+(?:No|Number)[:\s]+)?([A-Z]\d{8})'
        match = re.search(passport_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="passport_number",
                value=match.group(1),
                confidence=0.95
            ))
        
        # Extract full name (usually in capital letters)
        name_pattern = r'(?:Name|Surname)[:\s]+([A-Z\s]+)'
        match = re.search(name_pattern, text)
        if match:
            entities.append(ExtractedEntity(
                field="full_name",
                value=match.group(1).strip(),
                confidence=0.90
            ))
        
        # Extract date of birth
        dob_pattern = r'(?:Date of Birth|DOB)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})'
        match = re.search(dob_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="date_of_birth",
                value=match.group(1),
                confidence=0.92
            ))
        
        # Extract nationality
        nationality_pattern = r'(?:Nationality)[:\s]+([A-Z\s]+)'
        match = re.search(nationality_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="nationality",
                value=match.group(1).strip(),
                confidence=0.88
            ))
        
        return entities
    
    def _extract_national_id_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract national ID entities"""
        import re
        
        entities = []
        
        # Extract ID number (11 digits for Nigerian NIN)
        id_pattern = r'(?:ID\s+(?:No|Number)|NIN)[:\s]+(\d{11})'
        match = re.search(id_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="id_number",
                value=match.group(1),
                confidence=0.96
            ))
        
        # Extract full name
        name_pattern = r'(?:Name|Full Name)[:\s]+([A-Z\s]+)'
        match = re.search(name_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="full_name",
                value=match.group(1).strip(),
                confidence=0.90
            ))
        
        return entities
    
    def _extract_bank_statement_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract bank statement entities"""
        import re
        
        entities = []
        
        # Extract account number
        account_pattern = r'(?:Account\s+(?:No|Number))[:\s]+(\d{10})'
        match = re.search(account_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="account_number",
                value=match.group(1),
                confidence=0.94
            ))
        
        # Extract account holder name
        name_pattern = r'(?:Account\s+(?:Name|Holder))[:\s]+([A-Z\s]+)'
        match = re.search(name_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="account_holder",
                value=match.group(1).strip(),
                confidence=0.88
            ))
        
        # Extract bank name
        bank_pattern = r'([A-Z\s]+Bank)'
        match = re.search(bank_pattern, text)
        if match:
            entities.append(ExtractedEntity(
                field="bank_name",
                value=match.group(1).strip(),
                confidence=0.85
            ))
        
        return entities
    
    def _extract_utility_bill_entities(self, text: str) -> List[ExtractedEntity]:
        """Extract utility bill entities"""
        import re
        
        entities = []
        
        # Extract customer name
        name_pattern = r'(?:Customer\s+Name|Name)[:\s]+([A-Z\s]+)'
        match = re.search(name_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="customer_name",
                value=match.group(1).strip(),
                confidence=0.87
            ))
        
        # Extract address (simplified)
        address_pattern = r'(?:Address)[:\s]+(.+?)(?:\n|$)'
        match = re.search(address_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="address",
                value=match.group(1).strip(),
                confidence=0.82
            ))
        
        # Extract amount
        amount_pattern = r'(?:Amount|Total)[:\s]+(?:NGN|₦)?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        match = re.search(amount_pattern, text, re.IGNORECASE)
        if match:
            entities.append(ExtractedEntity(
                field="amount",
                value=match.group(1),
                confidence=0.91
            ))
        
        return entities
    
    def _extract_generic_entities(self, text: str) -> List[ExtractedEntity]:
        """Generic entity extraction"""
        import re
        
        entities = []
        
        # Extract dates
        date_pattern = r'\d{2}[/-]\d{2}[/-]\d{4}'
        dates = re.findall(date_pattern, text)
        for i, date in enumerate(dates[:3]):  # Limit to first 3 dates
            entities.append(ExtractedEntity(
                field=f"date_{i+1}",
                value=date,
                confidence=0.80
            ))
        
        # Extract amounts
        amount_pattern = r'(?:NGN|₦|USD|\$)\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        amounts = re.findall(amount_pattern, text)
        for i, amount in enumerate(amounts[:3]):  # Limit to first 3 amounts
            entities.append(ExtractedEntity(
                field=f"amount_{i+1}",
                value=amount,
                confidence=0.85
            ))
        
        return entities
    
    def _calculate_confidence(self, entities: List[ExtractedEntity]) -> float:
        """Calculate overall confidence score"""
        if not entities:
            return 0.0
        
        total_confidence = sum(e.confidence for e in entities)
        return round(total_confidence / len(entities), 2)

# Initialize processor
docling_processor = DoclingProcessor()

# API endpoints
@app.post("/api/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "user123",
    document_type: DocumentType = DocumentType.UNKNOWN,
    background_tasks: BackgroundTasks = None
):
    """Upload document for processing"""
    
    # Generate document ID
    document_id = str(uuid4())
    
    # Save file temporarily
    temp_path = Path(f"/tmp/{document_id}_{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Upload to S3
    s3_key = f"documents/{user_id}/{document_id}/{file.filename}"
    try:
        s3_client.upload_file(str(temp_path), S3_BUCKET, s3_key)
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")
    
    # Create database record
    db = SessionLocal()
    document = Document(
        id=document_id,
        user_id=user_id,
        document_type=document_type,
        original_filename=file.filename,
        s3_key=s3_key,
        status=ProcessingStatus.PENDING
    )
    db.add(document)
    db.commit()
    db.close()
    
    # Queue for processing
    redis_client.lpush("document_queue", document_id)
    
    # Process in background
    if background_tasks:
        background_tasks.add_task(process_document_task, document_id, temp_path, document_type)
    
    return DocumentUploadResponse(
        document_id=document_id,
        status=ProcessingStatus.PENDING,
        message="Document uploaded successfully and queued for processing"
    )

async def process_document_task(document_id: str, file_path: Path, document_type: DocumentType):
    """Background task to process document"""
    
    db = SessionLocal()
    document = db.query(Document).filter(Document.id == document_id).first()
    
    if not document:
        logger.error(f"Document not found: {document_id}")
        return
    
    try:
        # Update status
        document.status = ProcessingStatus.PROCESSING
        db.commit()
        
        # Process with Docling
        result = await docling_processor.process_document(file_path, document_type)
        
        # Validate extracted data
        validation_result = validate_extracted_data(
            result["extracted_entities"],
            document_type
        )
        
        # Update database
        document.status = ProcessingStatus.COMPLETED
        document.extracted_data = {
            "entities": [e.dict() for e in result["extracted_entities"]],
            "raw_text": result["raw_text"][:1000],  # Store first 1000 chars
            "page_count": result["page_count"]
        }
        document.validation_result = validation_result
        document.confidence_score = str(result["confidence_score"])
        document.processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Document processed successfully: {document_id}")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        document.status = ProcessingStatus.FAILED
        document.error_message = str(e)
        db.commit()
    
    finally:
        db.close()
        # Clean up temp file
        if file_path.exists():
            file_path.unlink()

def validate_extracted_data(
    entities: List[ExtractedEntity],
    document_type: DocumentType
) -> Dict[str, Any]:
    """Validate extracted data against document type rules"""
    
    config = DOCUMENT_CONFIGS.get(document_type, {})
    required_fields = config.get("required_fields", [])
    validation_rules = config.get("validation_rules", [])
    
    extracted_fields = {e.field: e.value for e in entities}
    
    validation_result = {
        "valid": True,
        "missing_fields": [],
        "invalid_fields": [],
        "warnings": []
    }
    
    # Check required fields
    for field in required_fields:
        if field not in extracted_fields:
            validation_result["missing_fields"].append(field)
            validation_result["valid"] = False
    
    # Validate field patterns
    import re
    for rule in validation_rules:
        if rule.field in extracted_fields:
            value = extracted_fields[rule.field]
            
            if rule.pattern and not re.match(rule.pattern, value):
                validation_result["invalid_fields"].append({
                    "field": rule.field,
                    "reason": "Pattern mismatch"
                })
                validation_result["valid"] = False
            
            if rule.min_length and len(value) < rule.min_length:
                validation_result["invalid_fields"].append({
                    "field": rule.field,
                    "reason": f"Too short (min: {rule.min_length})"
                })
                validation_result["valid"] = False
    
    return validation_result

@app.get("/api/v1/documents/{document_id}", response_model=DocumentProcessingResult)
async def get_document_status(document_id: str):
    """Get document processing status and results"""
    
    db = SessionLocal()
    document = db.query(Document).filter(Document.id == document_id).first()
    db.close()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    extracted_entities = []
    if document.extracted_data and "entities" in document.extracted_data:
        extracted_entities = [
            ExtractedEntity(**e) for e in document.extracted_data["entities"]
        ]
    
    return DocumentProcessingResult(
        document_id=document.id,
        document_type=document.document_type,
        status=document.status,
        extracted_entities=extracted_entities,
        raw_text=document.extracted_data.get("raw_text", "") if document.extracted_data else "",
        markdown_content="",  # Not stored in DB
        confidence_score=float(document.confidence_score) if document.confidence_score else 0.0,
        validation_result=document.validation_result,
        processing_time_seconds=0.0  # Calculate from timestamps if needed
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "document-processing",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8040)
