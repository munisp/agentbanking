import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Advanced OCR Processing Service
Integrates OLMOCR and GOT-OCR2.0 for high-accuracy document text extraction
"""

import asyncio
import json
import logging
import os
import uuid
import base64
import tempfile
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import io

import httpx
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("advanced-ocr-processing-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
import aioredis
import torch
from transformers import AutoProcessor, AutoModelForCausalLM
import pdf2image
import pytesseract
import easyocr
from paddleocr import PaddleOCR

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/ocr_processing")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DocumentType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    SCANNED_DOCUMENT = "scanned_document"
    HANDWRITTEN = "handwritten"
    FORM = "form"
    TABLE = "table"
    CHART = "chart"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    CONTRACT = "contract"
    ID_DOCUMENT = "id_document"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"

class OCREngine(str, Enum):
    OLMOCR = "olmocr"
    GOT_OCR2 = "got_ocr2"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    PADDLEOCR = "paddleocr"
    HYBRID = "hybrid"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class OCRResult:
    text: str
    confidence: float
    engine_used: str
    processing_time: float
    word_boxes: List[Dict[str, Any]]
    line_boxes: List[Dict[str, Any]]
    paragraph_boxes: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    forms: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class OCRProcessingJob(Base):
    __tablename__ = "ocr_processing_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String, nullable=False, unique=True, index=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String)
    document_type = Column(String, index=True)
    ocr_engine = Column(String, index=True)
    status = Column(String, default=ProcessingStatus.PENDING.value, index=True)
    progress = Column(Float, default=0.0)
    extracted_text = Column(Text)
    confidence_score = Column(Float)
    processing_time = Column(Float)
    word_boxes = Column(JSON)
    line_boxes = Column(JSON)
    paragraph_boxes = Column(JSON)
    tables_data = Column(JSON)
    forms_data = Column(JSON)
    metadata = Column(JSON)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    requested_by = Column(String)

class OCRPreprocessingLog(Base):
    __tablename__ = "ocr_preprocessing_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(String, nullable=False, index=True)
    preprocessing_step = Column(String, nullable=False)
    parameters = Column(JSON)
    before_image_path = Column(String)
    after_image_path = Column(String)
    improvement_score = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class AdvancedOCRService:
    def __init__(self):
        self.redis_client = None
        self.olmocr_model = None
        self.got_ocr_model = None
        self.got_ocr_processor = None
        self.easyocr_reader = None
        self.paddleocr_reader = None
        
        # Model paths and configurations
        self.olmocr_model_path = os.getenv("OLMOCR_MODEL_PATH", "allenai/olmOCR-7B-0725")
        self.got_ocr_model_path = os.getenv("GOT_OCR_MODEL_PATH", "stepfun-ai/GOT-OCR-2.0-hf")
        
        # Processing configurations
        self.max_image_size = (2048, 2048)
        self.supported_formats = {'.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp'}
        
        # Device configuration
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
    
    async def initialize(self):
        """Initialize the OCR service with models"""
        try:
            # Initialize Redis for caching
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = await aioredis.from_url(redis_url)
            
            # Initialize models in background
            asyncio.create_task(self._load_models())
            
            logger.info("Advanced OCR Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OCR Service: {e}")
            self.redis_client = None
    
    async def _load_models(self):
        """Load OCR models"""
        try:
            # Load OLMOCR model
            logger.info("Loading OLMOCR model...")
            self.olmocr_processor = AutoProcessor.from_pretrained(self.olmocr_model_path)
            self.olmocr_model = AutoModelForCausalLM.from_pretrained(
                self.olmocr_model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )
            logger.info("OLMOCR model loaded successfully")
            
            # Load GOT-OCR2.0 model
            logger.info("Loading GOT-OCR2.0 model...")
            self.got_ocr_processor = AutoProcessor.from_pretrained(self.got_ocr_model_path)
            self.got_ocr_model = AutoModelForCausalLM.from_pretrained(
                self.got_ocr_model_path,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map="auto" if self.device == "cuda" else None
            )
            logger.info("GOT-OCR2.0 model loaded successfully")
            
            # Initialize EasyOCR
            logger.info("Initializing EasyOCR...")
            self.easyocr_reader = easyocr.Reader(['en'], gpu=self.device == "cuda")
            logger.info("EasyOCR initialized successfully")
            
            # Initialize PaddleOCR
            logger.info("Initializing PaddleOCR...")
            self.paddleocr_reader = PaddleOCR(
                use_angle_cls=True,
                lang='en',
                use_gpu=self.device == "cuda",
                show_log=False
            )
            logger.info("PaddleOCR initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to load OCR models: {e}")
    
    async def process_document(self, file: UploadFile, document_type: DocumentType,
                             ocr_engine: OCREngine, requested_by: str,
                             preprocessing_options: Optional[Dict[str, Any]] = None) -> str:
        """Process document with OCR"""
        db = SessionLocal()
        try:
            # Generate job ID
            job_id = str(uuid.uuid4())
            
            # Save uploaded file
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in self.supported_formats:
                raise HTTPException(status_code=400, detail=f"Unsupported file format: {file_extension}")
            
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, f"{job_id}{file_extension}")
            
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            
            # Create processing job
            job = OCRProcessingJob(
                job_id=job_id,
                file_name=file.filename,
                file_path=file_path,
                file_size=len(content),
                mime_type=file.content_type,
                document_type=document_type.value,
                ocr_engine=ocr_engine.value,
                requested_by=requested_by,
                metadata=preprocessing_options or {}
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            
            # Start processing in background
            asyncio.create_task(self._process_document_async(job_id))
            
            return job_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to start document processing: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def _process_document_async(self, job_id: str):
        """Process document asynchronously"""
        db = SessionLocal()
        try:
            job = db.query(OCRProcessingJob).filter(OCRProcessingJob.job_id == job_id).first()
            if not job:
                return
            
            # Update status
            job.status = ProcessingStatus.PROCESSING.value
            job.started_at = datetime.utcnow()
            db.commit()
            
            start_time = datetime.utcnow()
            
            # Convert PDF to images if needed
            images = await self._prepare_images(job.file_path, job.document_type)
            
            # Preprocess images
            preprocessed_images = []
            for i, image in enumerate(images):
                preprocessed_image = await self._preprocess_image(
                    image, job_id, i, job.metadata.get("preprocessing", {})
                )
                preprocessed_images.append(preprocessed_image)
                
                # Update progress
                job.progress = (i + 1) / len(images) * 0.3  # Preprocessing is 30% of work
                db.commit()
            
            # Perform OCR
            ocr_results = []
            for i, image in enumerate(preprocessed_images):
                result = await self._perform_ocr(image, job.ocr_engine, job.document_type)
                ocr_results.append(result)
                
                # Update progress
                job.progress = 0.3 + (i + 1) / len(preprocessed_images) * 0.6  # OCR is 60% of work
                db.commit()
            
            # Combine results
            combined_result = await self._combine_ocr_results(ocr_results)
            
            # Post-process results
            final_result = await self._post_process_results(combined_result, job.document_type)
            
            # Update job with results
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            job.status = ProcessingStatus.COMPLETED.value
            job.progress = 1.0
            job.extracted_text = final_result.text
            job.confidence_score = final_result.confidence
            job.processing_time = processing_time
            job.word_boxes = final_result.word_boxes
            job.line_boxes = final_result.line_boxes
            job.paragraph_boxes = final_result.paragraph_boxes
            job.tables_data = final_result.tables
            job.forms_data = final_result.forms
            job.completed_at = datetime.utcnow()
            
            db.commit()
            
            # Clean up temporary files
            if os.path.exists(job.file_path):
                shutil.rmtree(os.path.dirname(job.file_path), ignore_errors=True)
            
        except Exception as e:
            logger.error(f"OCR processing failed for job {job_id}: {e}")
            
            job.status = ProcessingStatus.FAILED.value
            job.error_message = str(e)
            job.retry_count += 1
            
            # Retry logic
            if job.retry_count < 3:
                job.status = ProcessingStatus.RETRYING.value
                db.commit()
                
                # Retry after delay
                await asyncio.sleep(60 * job.retry_count)  # Exponential backoff
                asyncio.create_task(self._process_document_async(job_id))
            else:
                db.commit()
        finally:
            db.close()
    
    async def _prepare_images(self, file_path: str, document_type: str) -> List[Image.Image]:
        """Convert document to images"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                # Convert PDF to images
                images = pdf2image.convert_from_path(
                    file_path,
                    dpi=300,
                    fmt='RGB'
                )
                return images
            else:
                # Load image directly
                image = Image.open(file_path)
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                return [image]
                
        except Exception as e:
            logger.error(f"Failed to prepare images: {e}")
            raise
    
    async def _preprocess_image(self, image: Image.Image, job_id: str, page_num: int,
                              preprocessing_options: Dict[str, Any]) -> Image.Image:
        """Preprocess image for better OCR results"""
        db = SessionLocal()
        try:
            original_image = image.copy()
            processed_image = image.copy()
            
            # Convert to OpenCV format
            cv_image = cv2.cvtColor(np.array(processed_image), cv2.COLOR_RGB2BGR)
            
            # Apply preprocessing steps
            preprocessing_steps = []
            
            # 1. Noise reduction
            if preprocessing_options.get("denoise", True):
                cv_image = cv2.fastNlMeansDenoisingColored(cv_image, None, 10, 10, 7, 21)
                preprocessing_steps.append("denoise")
            
            # 2. Contrast enhancement
            if preprocessing_options.get("enhance_contrast", True):
                lab = cv2.cvtColor(cv_image, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l = clahe.apply(l)
                cv_image = cv2.merge([l, a, b])
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_LAB2BGR)
                preprocessing_steps.append("enhance_contrast")
            
            # 3. Sharpening
            if preprocessing_options.get("sharpen", True):
                kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
                cv_image = cv2.filter2D(cv_image, -1, kernel)
                preprocessing_steps.append("sharpen")
            
            # 4. Deskewing
            if preprocessing_options.get("deskew", True):
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                coords = np.column_stack(np.where(gray > 0))
                if len(coords) > 0:
                    angle = cv2.minAreaRect(coords)[-1]
                    if angle < -45:
                        angle = -(90 + angle)
                    else:
                        angle = -angle
                    
                    if abs(angle) > 0.5:  # Only rotate if significant skew
                        (h, w) = cv_image.shape[:2]
                        center = (w // 2, h // 2)
                        M = cv2.getRotationMatrix2D(center, angle, 1.0)
                        cv_image = cv2.warpAffine(cv_image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                        preprocessing_steps.append(f"deskew_{angle:.2f}")
            
            # 5. Binarization for text documents
            if preprocessing_options.get("binarize", False) or "text" in job_id.lower():
                gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
                cv_image = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2BGR)
                preprocessing_steps.append("binarize")
            
            # Convert back to PIL Image
            processed_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
            
            # Resize if too large
            if processed_image.size[0] > self.max_image_size[0] or processed_image.size[1] > self.max_image_size[1]:
                processed_image.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
                preprocessing_steps.append("resize")
            
            # Log preprocessing steps
            preprocessing_log = OCRPreprocessingLog(
                job_id=job_id,
                preprocessing_step=",".join(preprocessing_steps),
                parameters=preprocessing_options,
                improvement_score=0.0  # Would calculate actual improvement in production
            )
            db.add(preprocessing_log)
            db.commit()
            
            return processed_image
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image  # Return original if preprocessing fails
        finally:
            db.close()
    
    async def _perform_ocr(self, image: Image.Image, ocr_engine: str, document_type: str) -> OCRResult:
        """Perform OCR using specified engine"""
        try:
            if ocr_engine == OCREngine.OLMOCR.value:
                return await self._olmocr_extract(image, document_type)
            elif ocr_engine == OCREngine.GOT_OCR2.value:
                return await self._got_ocr_extract(image, document_type)
            elif ocr_engine == OCREngine.TESSERACT.value:
                return await self._tesseract_extract(image, document_type)
            elif ocr_engine == OCREngine.EASYOCR.value:
                return await self._easyocr_extract(image, document_type)
            elif ocr_engine == OCREngine.PADDLEOCR.value:
                return await self._paddleocr_extract(image, document_type)
            elif ocr_engine == OCREngine.HYBRID.value:
                return await self._hybrid_ocr_extract(image, document_type)
            else:
                raise ValueError(f"Unsupported OCR engine: {ocr_engine}")
                
        except Exception as e:
            logger.error(f"OCR extraction failed with {ocr_engine}: {e}")
            # Fallback to Tesseract
            return await self._tesseract_extract(image, document_type)
    
    async def _olmocr_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using OLMOCR"""
        try:
            start_time = datetime.utcnow()
            
            if not self.olmocr_model or not self.olmocr_processor:
                raise ValueError("OLMOCR model not loaded")
            
            # Prepare inputs
            inputs = self.olmocr_processor(images=image, return_tensors="pt")
            
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate text
            with torch.no_grad():
                generated_ids = self.olmocr_model.generate(
                    **inputs,
                    max_new_tokens=2048,
                    do_sample=False,
                    temperature=0.0
                )
            
            # Decode text
            extracted_text = self.olmocr_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # OLMOCR provides high-quality text but limited layout information
            return OCRResult(
                text=extracted_text,
                confidence=0.95,  # OLMOCR typically has high confidence
                engine_used="olmocr",
                processing_time=processing_time,
                word_boxes=[],  # OLMOCR doesn't provide detailed layout
                line_boxes=[],
                paragraph_boxes=[],
                tables=[],
                forms=[],
                metadata={"model": self.olmocr_model_path}
            )
            
        except Exception as e:
            logger.error(f"OLMOCR extraction failed: {e}")
            raise
    
    async def _got_ocr_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using GOT-OCR2.0"""
        try:
            start_time = datetime.utcnow()
            
            if not self.got_ocr_model or not self.got_ocr_processor:
                raise ValueError("GOT-OCR2.0 model not loaded")
            
            # Prepare prompt based on document type
            if document_type == DocumentType.TABLE.value:
                prompt = "OCR with format: <table>"
            elif document_type == DocumentType.FORM.value:
                prompt = "OCR with format: <form>"
            elif document_type == DocumentType.CHART.value:
                prompt = "OCR with format: <chart>"
            else:
                prompt = "OCR:"
            
            # Prepare inputs
            inputs = self.got_ocr_processor(
                text=prompt,
                images=image,
                return_tensors="pt"
            )
            
            if self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate text
            with torch.no_grad():
                generated_ids = self.got_ocr_model.generate(
                    **inputs,
                    max_new_tokens=4096,
                    do_sample=False,
                    temperature=0.0
                )
            
            # Decode text
            extracted_text = self.got_ocr_processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Parse structured output from GOT-OCR2.0
            tables, forms = self._parse_got_ocr_output(extracted_text)
            
            return OCRResult(
                text=extracted_text,
                confidence=0.92,  # GOT-OCR2.0 has high confidence
                engine_used="got_ocr2",
                processing_time=processing_time,
                word_boxes=[],  # GOT-OCR2.0 focuses on content over layout
                line_boxes=[],
                paragraph_boxes=[],
                tables=tables,
                forms=forms,
                metadata={"model": self.got_ocr_model_path, "prompt": prompt}
            )
            
        except Exception as e:
            logger.error(f"GOT-OCR2.0 extraction failed: {e}")
            raise
    
    def _parse_got_ocr_output(self, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Parse structured output from GOT-OCR2.0"""
        tables = []
        forms = []
        
        # Parse table structures
        import re
        table_pattern = r'<table>(.*?)</table>'
        table_matches = re.findall(table_pattern, text, re.DOTALL)
        
        for i, table_content in enumerate(table_matches):
            # Simple table parsing - would be more sophisticated in production
            rows = table_content.strip().split('\n')
            table_data = []
            for row in rows:
                if '|' in row:
                    cells = [cell.strip() for cell in row.split('|') if cell.strip()]
                    if cells:
                        table_data.append(cells)
            
            if table_data:
                tables.append({
                    "id": f"table_{i}",
                    "rows": table_data,
                    "row_count": len(table_data),
                    "col_count": len(table_data[0]) if table_data else 0
                })
        
        # Parse form structures
        form_pattern = r'<form>(.*?)</form>'
        form_matches = re.findall(form_pattern, text, re.DOTALL)
        
        for i, form_content in enumerate(form_matches):
            # Simple form parsing
            fields = []
            field_pattern = r'(\w+):\s*([^\n]+)'
            field_matches = re.findall(field_pattern, form_content)
            
            for field_name, field_value in field_matches:
                fields.append({
                    "name": field_name,
                    "value": field_value.strip()
                })
            
            if fields:
                forms.append({
                    "id": f"form_{i}",
                    "fields": fields
                })
        
        return tables, forms
    
    async def _tesseract_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using Tesseract OCR"""
        try:
            start_time = datetime.utcnow()
            
            # Configure Tesseract based on document type
            config = '--oem 3 --psm 6'  # Default config
            
            if document_type == DocumentType.TABLE.value:
                config = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
            elif document_type == DocumentType.HANDWRITTEN.value:
                config = '--oem 3 --psm 8'
            elif document_type == DocumentType.ID_DOCUMENT.value:
                config = '--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz '
            
            # Extract text
            extracted_text = pytesseract.image_to_string(image, config=config)
            
            # Get detailed data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=config)
            
            # Calculate confidence
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract word boxes
            word_boxes = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:
                    word_boxes.append({
                        "text": data['text'][i],
                        "confidence": int(data['conf'][i]),
                        "bbox": [
                            data['left'][i],
                            data['top'][i],
                            data['left'][i] + data['width'][i],
                            data['top'][i] + data['height'][i]
                        ]
                    })
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return OCRResult(
                text=extracted_text,
                confidence=avg_confidence / 100.0,
                engine_used="tesseract",
                processing_time=processing_time,
                word_boxes=word_boxes,
                line_boxes=[],  # Would implement line detection
                paragraph_boxes=[],  # Would implement paragraph detection
                tables=[],
                forms=[],
                metadata={"config": config}
            )
            
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")
            raise
    
    async def _easyocr_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using EasyOCR"""
        try:
            start_time = datetime.utcnow()
            
            if not self.easyocr_reader:
                raise ValueError("EasyOCR not initialized")
            
            # Convert PIL image to numpy array
            image_array = np.array(image)
            
            # Perform OCR
            results = self.easyocr_reader.readtext(image_array, detail=1)
            
            # Extract text and metadata
            extracted_text = ""
            word_boxes = []
            total_confidence = 0
            
            for (bbox, text, confidence) in results:
                extracted_text += text + " "
                word_boxes.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": [
                        int(min(point[0] for point in bbox)),
                        int(min(point[1] for point in bbox)),
                        int(max(point[0] for point in bbox)),
                        int(max(point[1] for point in bbox))
                    ]
                })
                total_confidence += confidence
            
            avg_confidence = total_confidence / len(results) if results else 0
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return OCRResult(
                text=extracted_text.strip(),
                confidence=avg_confidence,
                engine_used="easyocr",
                processing_time=processing_time,
                word_boxes=word_boxes,
                line_boxes=[],
                paragraph_boxes=[],
                tables=[],
                forms=[],
                metadata={"languages": ["en"]}
            )
            
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            raise
    
    async def _paddleocr_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using PaddleOCR"""
        try:
            start_time = datetime.utcnow()
            
            if not self.paddleocr_reader:
                raise ValueError("PaddleOCR not initialized")
            
            # Convert PIL image to numpy array
            image_array = np.array(image)
            
            # Perform OCR
            results = self.paddleocr_reader.ocr(image_array, cls=True)
            
            # Extract text and metadata
            extracted_text = ""
            word_boxes = []
            line_boxes = []
            total_confidence = 0
            line_count = 0
            
            if results and results[0]:
                for line_result in results[0]:
                    if len(line_result) >= 2:
                        bbox_points = line_result[0]
                        text_info = line_result[1]
                        
                        if isinstance(text_info, tuple) and len(text_info) >= 2:
                            text = text_info[0]
                            confidence = text_info[1]
                        else:
                            text = str(text_info)
                            confidence = 0.9  # Default confidence
                        
                        extracted_text += text + " "
                        
                        # Convert bbox points to standard format
                        x_coords = [point[0] for point in bbox_points]
                        y_coords = [point[1] for point in bbox_points]
                        bbox = [
                            int(min(x_coords)),
                            int(min(y_coords)),
                            int(max(x_coords)),
                            int(max(y_coords))
                        ]
                        
                        # Add line box
                        line_boxes.append({
                            "text": text,
                            "confidence": confidence,
                            "bbox": bbox,
                            "points": [[int(p[0]), int(p[1])] for p in bbox_points]
                        })
                        
                        # Split into words for word boxes
                        words = text.split()
                        if words:
                            word_width = (bbox[2] - bbox[0]) / len(words)
                            for i, word in enumerate(words):
                                word_bbox = [
                                    int(bbox[0] + i * word_width),
                                    bbox[1],
                                    int(bbox[0] + (i + 1) * word_width),
                                    bbox[3]
                                ]
                                word_boxes.append({
                                    "text": word,
                                    "confidence": confidence,
                                    "bbox": word_bbox
                                })
                        
                        total_confidence += confidence
                        line_count += 1
            
            avg_confidence = total_confidence / line_count if line_count > 0 else 0
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Detect tables in the text (simple heuristic)
            tables = self._detect_tables_from_paddleocr(line_boxes)
            
            return OCRResult(
                text=extracted_text.strip(),
                confidence=avg_confidence,
                engine_used="paddleocr",
                processing_time=processing_time,
                word_boxes=word_boxes,
                line_boxes=line_boxes,
                paragraph_boxes=[],  # Would implement paragraph detection
                tables=tables,
                forms=[],
                metadata={
                    "language": "en",
                    "angle_classification": True,
                    "line_count": line_count
                }
            )
            
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")
            raise
    
    def _detect_tables_from_paddleocr(self, line_boxes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect table structures from PaddleOCR line boxes"""
        tables = []
        
        if not line_boxes:
            return tables
        
        # Simple table detection based on alignment
        # Group lines by Y coordinate (rows)
        rows = {}
        for line_box in line_boxes:
            y_center = (line_box["bbox"][1] + line_box["bbox"][3]) / 2
            
            # Find existing row or create new one
            row_key = None
            for existing_y in rows.keys():
                if abs(y_center - existing_y) < 20:  # 20 pixel tolerance
                    row_key = existing_y
                    break
            
            if row_key is None:
                row_key = y_center
                rows[row_key] = []
            
            rows[row_key].append(line_box)
        
        # Sort rows by Y coordinate
        sorted_rows = sorted(rows.items())
        
        # Check if we have a table-like structure
        if len(sorted_rows) >= 3:  # At least 3 rows
            row_lengths = [len(row[1]) for row in sorted_rows]
            avg_cols = sum(row_lengths) / len(row_lengths)
            
            # If most rows have similar number of columns, it might be a table
            consistent_rows = sum(1 for length in row_lengths if abs(length - avg_cols) <= 1)
            
            if consistent_rows >= len(sorted_rows) * 0.7:  # 70% of rows are consistent
                # Extract table data
                table_data = []
                for y_coord, line_boxes_in_row in sorted_rows:
                    # Sort columns by X coordinate
                    sorted_cols = sorted(line_boxes_in_row, key=lambda box: box["bbox"][0])
                    row_data = [box["text"] for box in sorted_cols]
                    table_data.append(row_data)
                
                if table_data:
                    tables.append({
                        "id": "table_0",
                        "rows": table_data,
                        "row_count": len(table_data),
                        "col_count": len(table_data[0]) if table_data else 0,
                        "detection_method": "paddleocr_alignment"
                    })
        
        return tables
    
    async def _hybrid_ocr_extract(self, image: Image.Image, document_type: str) -> OCRResult:
        """Extract text using hybrid approach with multiple engines"""
        try:
            start_time = datetime.utcnow()
            
            # Run multiple OCR engines
            results = []
            
            # Try OLMOCR for high-quality text
            try:
                olmocr_result = await self._olmocr_extract(image, document_type)
                results.append(olmocr_result)
            except Exception as e:
                logger.warning(f"OLMOCR failed in hybrid mode: {e}")
            
            # Try GOT-OCR2.0 for structured content
            try:
                got_ocr_result = await self._got_ocr_extract(image, document_type)
                results.append(got_ocr_result)
            except Exception as e:
                logger.warning(f"GOT-OCR2.0 failed in hybrid mode: {e}")
            
            # Try EasyOCR for layout information
            try:
                easyocr_result = await self._easyocr_extract(image, document_type)
                results.append(easyocr_result)
            except Exception as e:
                logger.warning(f"EasyOCR failed in hybrid mode: {e}")
            
            # Try PaddleOCR for robust text detection
            try:
                paddleocr_result = await self._paddleocr_extract(image, document_type)
                results.append(paddleocr_result)
            except Exception as e:
                logger.warning(f"PaddleOCR failed in hybrid mode: {e}")
            
            # Fallback to Tesseract
            if not results:
                tesseract_result = await self._tesseract_extract(image, document_type)
                results.append(tesseract_result)
            
            # Combine results intelligently
            best_result = max(results, key=lambda r: r.confidence)
            
            # Merge layout information from EasyOCR or PaddleOCR if available
            layout_results = [r for r in results if r.engine_used in ["easyocr", "paddleocr"]]
            if layout_results:
                # Prefer PaddleOCR for layout if available, otherwise use EasyOCR
                paddleocr_results = [r for r in layout_results if r.engine_used == "paddleocr"]
                if paddleocr_results:
                    best_result.word_boxes = paddleocr_results[0].word_boxes
                    best_result.line_boxes = paddleocr_results[0].line_boxes
                else:
                    easyocr_results = [r for r in layout_results if r.engine_used == "easyocr"]
                    if easyocr_results:
                        best_result.word_boxes = easyocr_results[0].word_boxes
            
            # Merge structured data from GOT-OCR2.0 or PaddleOCR if available
            got_ocr_results = [r for r in results if r.engine_used == "got_ocr2"]
            paddleocr_results = [r for r in results if r.engine_used == "paddleocr"]
            
            if got_ocr_results:
                best_result.tables = got_ocr_results[0].tables
                best_result.forms = got_ocr_results[0].forms
            elif paddleocr_results and paddleocr_results[0].tables:
                # Use PaddleOCR tables if GOT-OCR2.0 not available
                best_result.tables = paddleocr_results[0].tables
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return OCRResult(
                text=best_result.text,
                confidence=best_result.confidence,
                engine_used="hybrid",
                processing_time=processing_time,
                word_boxes=best_result.word_boxes,
                line_boxes=best_result.line_boxes,
                paragraph_boxes=best_result.paragraph_boxes,
                tables=best_result.tables,
                forms=best_result.forms,
                metadata={
                    "engines_used": [r.engine_used for r in results],
                    "best_engine": best_result.engine_used
                }
            )
            
        except Exception as e:
            logger.error(f"Hybrid OCR extraction failed: {e}")
            raise
    
    async def _combine_ocr_results(self, results: List[OCRResult]) -> OCRResult:
        """Combine OCR results from multiple pages"""
        if not results:
            raise ValueError("No OCR results to combine")
        
        if len(results) == 1:
            return results[0]
        
        # Combine text
        combined_text = "\n\n".join(result.text for result in results)
        
        # Average confidence
        avg_confidence = sum(result.confidence for result in results) / len(results)
        
        # Sum processing time
        total_processing_time = sum(result.processing_time for result in results)
        
        # Combine layout information
        all_word_boxes = []
        all_line_boxes = []
        all_paragraph_boxes = []
        all_tables = []
        all_forms = []
        
        page_offset = 0
        for i, result in enumerate(results):
            # Adjust coordinates for multi-page documents
            for box in result.word_boxes:
                adjusted_box = box.copy()
                adjusted_box["page"] = i
                adjusted_box["bbox"][1] += page_offset  # Adjust Y coordinate
                adjusted_box["bbox"][3] += page_offset
                all_word_boxes.append(adjusted_box)
            
            for table in result.tables:
                table_copy = table.copy()
                table_copy["page"] = i
                all_tables.append(table_copy)
            
            for form in result.forms:
                form_copy = form.copy()
                form_copy["page"] = i
                all_forms.append(form_copy)
            
            # Estimate page height for offset
            page_offset += 1000  # Approximate page height
        
        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            engine_used=results[0].engine_used,
            processing_time=total_processing_time,
            word_boxes=all_word_boxes,
            line_boxes=all_line_boxes,
            paragraph_boxes=all_paragraph_boxes,
            tables=all_tables,
            forms=all_forms,
            metadata={
                "page_count": len(results),
                "engines_used": list(set(result.engine_used for result in results))
            }
        )
    
    async def _post_process_results(self, result: OCRResult, document_type: str) -> OCRResult:
        """Post-process OCR results for better accuracy"""
        try:
            # Clean up text
            cleaned_text = self._clean_text(result.text)
            
            # Apply document-specific post-processing
            if document_type == DocumentType.BANK_STATEMENT.value:
                cleaned_text = self._post_process_bank_statement(cleaned_text)
            elif document_type == DocumentType.ID_DOCUMENT.value:
                cleaned_text = self._post_process_id_document(cleaned_text)
            elif document_type == DocumentType.INVOICE.value:
                cleaned_text = self._post_process_invoice(cleaned_text)
            
            # Update result
            result.text = cleaned_text
            
            return result
            
        except Exception as e:
            logger.error(f"Post-processing failed: {e}")
            return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors
        text = text.replace('0', 'O').replace('1', 'I').replace('5', 'S')  # Common character confusions
        
        # Remove non-printable characters
        text = ''.join(char for char in text if char.isprintable() or char.isspace())
        
        return text.strip()
    
    def _post_process_bank_statement(self, text: str) -> str:
        """Post-process bank statement text"""
        import re
        
        # Fix common currency formatting issues
        text = re.sub(r'(\d+)[,.](\d{2})\s*([A-Z]{3})', r'\1.\2 \3', text)
        
        # Fix date formatting
        text = re.sub(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', r'\1/\2/\3', text)
        
        return text
    
    def _post_process_id_document(self, text: str) -> str:
        """Post-process ID document text"""
        import re
        
        # Fix common ID number patterns
        text = re.sub(r'([A-Z]{2})(\d+)', r'\1 \2', text)  # License format
        
        # Fix date of birth patterns
        text = re.sub(r'DOB[:\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})', r'DOB: \1/\2/\3', text)
        
        return text
    
    def _post_process_invoice(self, text: str) -> str:
        """Post-process invoice text"""
        import re
        
        # Fix invoice number patterns
        text = re.sub(r'Invoice[#\s]*(\w+)', r'Invoice #\1', text, flags=re.IGNORECASE)
        
        # Fix amount formatting
        text = re.sub(r'Total[:\s]*\$?(\d+[.,]\d{2})', r'Total: $\1', text, flags=re.IGNORECASE)
        
        return text
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get OCR job status"""
        db = SessionLocal()
        try:
            job = db.query(OCRProcessingJob).filter(OCRProcessingJob.job_id == job_id).first()
            
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            result = {
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress,
                "file_name": job.file_name,
                "document_type": job.document_type,
                "ocr_engine": job.ocr_engine,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "processing_time": job.processing_time,
                "error_message": job.error_message
            }
            
            if job.status == ProcessingStatus.COMPLETED.value:
                result.update({
                    "extracted_text": job.extracted_text,
                    "confidence_score": job.confidence_score,
                    "word_boxes": job.word_boxes,
                    "line_boxes": job.line_boxes,
                    "paragraph_boxes": job.paragraph_boxes,
                    "tables": job.tables_data,
                    "forms": job.forms_data,
                    "metadata": job.metadata
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            db.close()
    
    async def extract_text_simple(self, file: UploadFile) -> Dict[str, Any]:
        """Simple text extraction endpoint"""
        try:
            # Use hybrid OCR for best results
            job_id = await self.process_document(
                file, DocumentType.OTHER, OCREngine.HYBRID, "api_user"
            )
            
            # Wait for completion (for simple API)
            max_wait = 300  # 5 minutes
            wait_time = 0
            
            while wait_time < max_wait:
                status = await self.get_job_status(job_id)
                
                if status["status"] == ProcessingStatus.COMPLETED.value:
                    return {
                        "text": status["extracted_text"],
                        "confidence": status["confidence_score"],
                        "processing_time": status["processing_time"],
                        "metadata": status["metadata"]
                    }
                elif status["status"] == ProcessingStatus.FAILED.value:
                    raise HTTPException(status_code=500, detail=status["error_message"])
                
                await asyncio.sleep(2)
                wait_time += 2
            
            raise HTTPException(status_code=408, detail="Processing timeout")
            
        except Exception as e:
            logger.error(f"Simple text extraction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        db = SessionLocal()
        try:
            # Check database connection
            db.execute("SELECT 1")
            db_healthy = True
        except Exception:
            db_healthy = False
        finally:
            db.close()
        
        # Check Redis connection
        redis_healthy = False
        if self.redis_client:
            try:
                await self.redis_client.ping()
                redis_healthy = True
            except Exception:
                redis_healthy = False
        
        # Check model availability
        models_loaded = {
            "olmocr": self.olmocr_model is not None,
            "got_ocr2": self.got_ocr_model is not None,
            "easyocr": self.easyocr_reader is not None,
            "paddleocr": self.paddleocr_reader is not None
        }
        
        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "advanced-ocr-service",
            "version": "1.0.0",
            "components": {
                "database": db_healthy,
                "redis": redis_healthy,
                "models": models_loaded,
                "device": self.device
            }
        }

# FastAPI application
app = FastAPI(title="Advanced OCR Processing Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
ocr_service = AdvancedOCRService()

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await ocr_service.initialize()

@app.post("/process-document")
async def process_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    ocr_engine: OCREngine = Form(OCREngine.HYBRID),
    requested_by: str = Form("api_user"),
    preprocessing_options: Optional[str] = Form(None)
):
    """Process document with advanced OCR"""
    preprocessing = json.loads(preprocessing_options) if preprocessing_options else {}
    
    job_id = await ocr_service.process_document(
        file, document_type, ocr_engine, requested_by, preprocessing
    )
    
    return {"job_id": job_id, "status": "processing_started"}

@app.get("/job/{job_id}/status")
async def get_job_status(job_id: str):
    """Get OCR job status"""
    return await ocr_service.get_job_status(job_id)

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Simple text extraction endpoint"""
    return await ocr_service.extract_text_simple(file)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await ocr_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8014)
