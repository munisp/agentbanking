import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Comprehensive Multi-OCR Service
Integrates PaddleOCR, EasyOCR, and OLMOCR for document processing
Port: 8024
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("comprehensive-multi-ocr-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import uuid
import os
import io
import base64
import asyncio
import httpx
from PIL import Image
import numpy as np

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, Float, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID, JSONB
import boto3

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://agent_user:agent_password@localhost/ocr_db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=40)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "remittance-documents")

# OLMOCR Configuration
OLMOCR_API_URL = os.getenv("OLMOCR_API_URL", "https://api.olmocr.com/v1")
OLMOCR_API_KEY = os.getenv("OLMOCR_API_KEY", "")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
) if AWS_ACCESS_KEY_ID else None

# ==================== DATABASE MODELS ====================

class OCRJob(Base):
    __tablename__ = "ocr_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Document info
    document_type = Column(String(50), index=True)
    document_id = Column(String(100), index=True)
    file_name = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # Storage
    s3_key = Column(String(500))
    s3_url = Column(String(1000))
    
    # OCR engines used
    engines_used = Column(JSONB)  # ['paddleocr', 'easyocr', 'olmocr']
    
    # Results
    paddle_result = Column(JSONB)
    easy_result = Column(JSONB)
    olm_result = Column(JSONB)
    
    # Aggregated result
    final_text = Column(Text)
    confidence_score = Column(Float)
    extracted_fields = Column(JSONB)
    
    # Status
    status = Column(String(20), default="pending", index=True)
    error_message = Column(Text)
    
    # Timing
    processing_time_seconds = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_job_document', 'document_type', 'document_id'),
    )

# Create tables
Base.metadata.create_all(bind=engine)

# ==================== PYDANTIC MODELS ====================

class OCRRequest(BaseModel):
    document_type: Optional[str] = "general"
    document_id: Optional[str] = None
    engines: Optional[List[str]] = ["paddleocr", "easyocr", "olmocr"]
    extract_fields: Optional[bool] = True

class OCRResponse(BaseModel):
    job_id: str
    status: str
    text: Optional[str] = None
    confidence_score: Optional[float] = None
    extracted_fields: Optional[Dict[str, Any]] = {}

# ==================== HELPER FUNCTIONS ====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def upload_to_s3(file_content: bytes, file_name: str) -> Tuple[str, str]:
    """Upload file to S3 and return key and URL"""
    if not s3_client:
        raise HTTPException(status_code=500, detail="S3 not configured")
    
    try:
        s3_key = f"ocr-documents/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}-{file_name}"
        
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType="image/jpeg"
        )
        
        s3_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        
        return s3_key, s3_url
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

def preprocess_image(image: Image.Image) -> np.ndarray:
    """Preprocess image for OCR"""
    # Convert to RGB if necessary
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize if too large
    max_size = 2000
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        image = image.resize(new_size, Image.LANCZOS)
    
    return np.array(image)

async def run_paddleocr(image_array: np.ndarray) -> Dict[str, Any]:
    """Run PaddleOCR on image"""
    try:
        # Lazy import to avoid loading if not needed
        from paddleocr import PaddleOCR
        
        ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
        result = ocr.ocr(image_array, cls=True)
        
        # Extract text and confidence
        texts = []
        confidences = []
        
        if result and len(result) > 0:
            for line in result[0]:
                if line:
                    text = line[1][0]
                    confidence = line[1][1]
                    texts.append(text)
                    confidences.append(confidence)
        
        return {
            "engine": "paddleocr",
            "text": " ".join(texts),
            "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "raw_result": result
        }
    except Exception as e:
        return {
            "engine": "paddleocr",
            "error": str(e),
            "text": "",
            "confidence": 0.0
        }

async def run_easyocr(image_array: np.ndarray) -> Dict[str, Any]:
    """Run EasyOCR on image"""
    try:
        # Lazy import
        import easyocr
        
        reader = easyocr.Reader(['en'], gpu=False)
        result = reader.readtext(image_array)
        
        # Extract text and confidence
        texts = []
        confidences = []
        
        for detection in result:
            text = detection[1]
            confidence = detection[2]
            texts.append(text)
            confidences.append(confidence)
        
        return {
            "engine": "easyocr",
            "text": " ".join(texts),
            "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "raw_result": result
        }
    except Exception as e:
        return {
            "engine": "easyocr",
            "error": str(e),
            "text": "",
            "confidence": 0.0
        }

async def run_olmocr(image_content: bytes, document_type: str) -> Dict[str, Any]:
    """Run OLMOCR API on image"""
    try:
        if not OLMOCR_API_KEY:
            return {
                "engine": "olmocr",
                "error": "OLMOCR API key not configured",
                "text": "",
                "confidence": 0.0
            }
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_content).decode('utf-8')
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLMOCR_API_URL}/ocr",
                json={
                    "image": image_b64,
                    "document_type": document_type,
                    "extract_fields": True
                },
                headers={"Authorization": f"Bearer {OLMOCR_API_KEY}"},
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
        
        return {
            "engine": "olmocr",
            "text": result.get("text", ""),
            "confidence": result.get("confidence", 0.0),
            "extracted_fields": result.get("fields", {}),
            "raw_result": result
        }
    except Exception as e:
        return {
            "engine": "olmocr",
            "error": str(e),
            "text": "",
            "confidence": 0.0
        }

def aggregate_ocr_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate results from multiple OCR engines"""
    
    # Filter out failed results
    valid_results = [r for r in results if r.get("text") and not r.get("error")]
    
    if not valid_results:
        return {
            "text": "",
            "confidence": 0.0,
            "extracted_fields": {},
            "engines_used": [r["engine"] for r in results]
        }
    
    # Use weighted average based on confidence
    total_confidence = sum(r["confidence"] for r in valid_results)
    
    if total_confidence > 0:
        # Weighted text selection (use highest confidence)
        best_result = max(valid_results, key=lambda r: r["confidence"])
        final_text = best_result["text"]
        final_confidence = best_result["confidence"]
    else:
        # Fallback to first result
        final_text = valid_results[0]["text"]
        final_confidence = 0.0
    
    # Merge extracted fields from OLMOCR
    extracted_fields = {}
    for result in valid_results:
        if "extracted_fields" in result:
            extracted_fields.update(result["extracted_fields"])
    
    return {
        "text": final_text,
        "confidence": final_confidence,
        "extracted_fields": extracted_fields,
        "engines_used": [r["engine"] for r in valid_results]
    }

# ==================== FASTAPI APP ====================

app = FastAPI(
    title="Comprehensive Multi-OCR Service",
    description="Integrates PaddleOCR, EasyOCR, and OLMOCR",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check"""
    
    engines_available = {
        "paddleocr": True,  # Always available if installed
        "easyocr": True,    # Always available if installed
        "olmocr": bool(OLMOCR_API_KEY)
    }
    
    return {
        "status": "healthy",
        "service": "multi-ocr",
        "version": "1.0.0",
        "port": 8024,
        "engines": engines_available,
        "features": [
            "paddleocr_integration",
            "easyocr_integration",
            "olmocr_integration",
            "multi_engine_aggregation",
            "field_extraction",
            "s3_storage"
        ]
    }

@app.post("/ocr", response_model=OCRResponse)
async def process_ocr(
    file: UploadFile = File(...),
    document_type: str = "general",
    document_id: Optional[str] = None,
    engines: str = "paddleocr,easyocr,olmocr",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """Process document with multiple OCR engines"""
    
    # Read file content
    file_content = await file.read()
    
    # Create job
    job = OCRJob(
        job_id=f"OCR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
        document_type=document_type,
        document_id=document_id,
        file_name=file.filename,
        file_size=len(file_content),
        mime_type=file.content_type,
        engines_used=engines.split(","),
        status="processing"
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    start_time = datetime.utcnow()
    
    try:
        # Upload to S3
        if s3_client:
            s3_key, s3_url = await upload_to_s3(file_content, file.filename)
            job.s3_key = s3_key
            job.s3_url = s3_url
            db.commit()
        
        # Load and preprocess image
        image = Image.open(io.BytesIO(file_content))
        image_array = preprocess_image(image)
        
        # Run OCR engines in parallel
        tasks = []
        engine_list = engines.split(",")
        
        if "paddleocr" in engine_list:
            tasks.append(run_paddleocr(image_array))
        if "easyocr" in engine_list:
            tasks.append(run_easyocr(image_array))
        if "olmocr" in engine_list:
            tasks.append(run_olmocr(file_content, document_type))
        
        results = await asyncio.gather(*tasks)
        
        # Store individual results
        for result in results:
            engine = result["engine"]
            if engine == "paddleocr":
                job.paddle_result = result
            elif engine == "easyocr":
                job.easy_result = result
            elif engine == "olmocr":
                job.olm_result = result
        
        # Aggregate results
        aggregated = aggregate_ocr_results(results)
        
        job.final_text = aggregated["text"]
        job.confidence_score = aggregated["confidence"]
        job.extracted_fields = aggregated["extracted_fields"]
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.processing_time_seconds = (job.completed_at - start_time).total_seconds()
        
        db.commit()
        
        return OCRResponse(
            job_id=job.job_id,
            status=job.status,
            text=job.final_text,
            confidence_score=job.confidence_score,
            extracted_fields=job.extracted_fields
        )
        
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()
        job.processing_time_seconds = (job.completed_at - start_time).total_seconds()
        db.commit()
        
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

@app.get("/ocr/{job_id}")
async def get_ocr_job(job_id: str, db: Session = Depends(get_db)):
    """Get OCR job status and results"""
    
    job = db.query(OCRJob).filter(OCRJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "document_type": job.document_type,
        "text": job.final_text,
        "confidence_score": job.confidence_score,
        "extracted_fields": job.extracted_fields,
        "engines_used": job.engines_used,
        "processing_time_seconds": job.processing_time_seconds,
        "s3_url": job.s3_url,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }

@app.get("/ocr")
async def list_ocr_jobs(
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List OCR jobs"""
    
    query = db.query(OCRJob)
    
    if document_type:
        query = query.filter(OCRJob.document_type == document_type)
    if status:
        query = query.filter(OCRJob.status == status)
    
    jobs = query.order_by(OCRJob.created_at.desc()).limit(limit).all()
    
    return {
        "jobs": [
            {
                "job_id": j.job_id,
                "document_type": j.document_type,
                "status": j.status,
                "confidence_score": j.confidence_score,
                "created_at": j.created_at.isoformat()
            }
            for j in jobs
        ],
        "total": len(jobs)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8024)
