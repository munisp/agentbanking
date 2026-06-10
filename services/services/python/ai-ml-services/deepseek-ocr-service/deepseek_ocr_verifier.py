"""
DeepSeek-OCR Document Verification Service
Enhanced KYC document verification using DeepSeek-OCR
"""

import os
import torch
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from PIL import Image
import json
import re
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class DocumentType(Enum):
    """Supported document types"""
    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    VOTERS_CARD = "voters_card"
    PROOF_OF_ADDRESS = "proof_of_address"
    BANK_STATEMENT = "bank_statement"
    UTILITY_BILL = "utility_bill"

class VerificationStatus(Enum):
    """Verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"

@dataclass
class DocumentData:
    """Extracted document data"""
    document_type: str
    document_number: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    address: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    raw_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None

@dataclass
class VerificationResult:
    """Document verification result"""
    verification_id: str
    status: str
    confidence: float
    document_type: str
    extracted_data: DocumentData
    authenticity_score: float
    quality_score: float
    issues: List[str]
    warnings: List[str]
    timestamp: str
    processing_time_ms: float

class DeepSeekOCRVerifier:
    """
    DeepSeek-OCR Document Verification Service
    Provides advanced OCR and document verification for KYC
    """
    
    def __init__(self, model_path: str = "deepseek-ai/DeepSeek-OCR", device: str = "cuda"):
        """
        Initialize DeepSeek-OCR verifier
        
        Args:
            model_path: Path to DeepSeek-OCR model
            device: Device to run model on (cuda/cpu)
        """
        self.model_path = model_path
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tokenizer = None
        self.is_initialized = False
        
        logger.info(f"Initializing DeepSeek-OCR verifier on {self.device}")
    
    def initialize(self):
        """Initialize the DeepSeek-OCR model"""
        try:
            from transformers import AutoModel, AutoTokenizer
            
            logger.info(f"Loading DeepSeek-OCR model from {self.model_path}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                trust_remote_code=True
            )
            
            self.model = AutoModel.from_pretrained(
                self.model_path,
                _attn_implementation='flash_attention_2',
                trust_remote_code=True,
                use_safetensors=True
            )
            
            self.model = self.model.eval().to(self.device).to(torch.bfloat16)
            self.is_initialized = True
            
            logger.info("DeepSeek-OCR model loaded successfully")
            
        except Exception as e:
            logger.error(f"Error initializing DeepSeek-OCR: {str(e)}")
            raise
    
    def verify_document(
        self,
        image_path: str,
        document_type: DocumentType,
        user_id: str,
        verification_id: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify a document using DeepSeek-OCR
        
        Args:
            image_path: Path to document image
            document_type: Type of document
            user_id: User ID for tracking
            verification_id: Optional verification ID
            
        Returns:
            VerificationResult with extracted data and verification status
        """
        start_time = datetime.utcnow()
        
        if not self.is_initialized:
            self.initialize()
        
        if verification_id is None:
            verification_id = f"VER_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        try:
            # Extract text and data from document
            extracted_data = self._extract_document_data(image_path, document_type)
            
            # Verify document authenticity
            authenticity_score = self._verify_authenticity(image_path, extracted_data)
            
            # Check document quality
            quality_score = self._check_quality(image_path)
            
            # Validate extracted data
            issues, warnings = self._validate_data(extracted_data, document_type)
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                authenticity_score,
                quality_score,
                len(issues),
                len(warnings)
            )
            
            # Determine verification status
            status = self._determine_status(confidence, issues)
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = VerificationResult(
                verification_id=verification_id,
                status=status.value,
                confidence=confidence,
                document_type=document_type.value,
                extracted_data=extracted_data,
                authenticity_score=authenticity_score,
                quality_score=quality_score,
                issues=issues,
                warnings=warnings,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=processing_time
            )
            
            logger.info(f"Document verification completed: {verification_id} - {status.value}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying document: {str(e)}")
            raise
    
    def _extract_document_data(
        self,
        image_path: str,
        document_type: DocumentType
    ) -> DocumentData:
        """
        Extract data from document using DeepSeek-OCR
        
        Args:
            image_path: Path to document image
            document_type: Type of document
            
        Returns:
            DocumentData with extracted information
        """
        try:
            # Prepare prompt based on document type
            prompt = self._get_prompt_for_document_type(document_type)
            
            # Run DeepSeek-OCR inference
            output_path = f"/tmp/ocr_output_{int(datetime.utcnow().timestamp())}"
            os.makedirs(output_path, exist_ok=True)
            
            result = self.model.infer(
                self.tokenizer,
                prompt=prompt,
                image_file=image_path,
                output_path=output_path,
                base_size=1024,
                image_size=640,
                crop_mode=True,
                save_results=True,
                test_compress=True
            )
            
            # Parse OCR result
            raw_text = result.get('text', '')
            
            # Extract structured data based on document type
            structured_data = self._parse_document_text(raw_text, document_type)
            
            document_data = DocumentData(
                document_type=document_type.value,
                document_number=structured_data.get('document_number'),
                full_name=structured_data.get('full_name'),
                date_of_birth=structured_data.get('date_of_birth'),
                issue_date=structured_data.get('issue_date'),
                expiry_date=structured_data.get('expiry_date'),
                address=structured_data.get('address'),
                nationality=structured_data.get('nationality'),
                gender=structured_data.get('gender'),
                raw_text=raw_text,
                structured_data=structured_data
            )
            
            return document_data
            
        except Exception as e:
            logger.error(f"Error extracting document data: {str(e)}")
            raise
    
    def _get_prompt_for_document_type(self, document_type: DocumentType) -> str:
        """Get appropriate prompt for document type"""
        prompts = {
            DocumentType.NATIONAL_ID: "<image>\n<|grounding|>Extract all text from this Nigerian National ID card. Include: ID number, full name, date of birth, gender, state of origin, and expiry date.",
            DocumentType.PASSPORT: "<image>\n<|grounding|>Extract all text from this passport. Include: passport number, full name, nationality, date of birth, gender, issue date, and expiry date.",
            DocumentType.DRIVERS_LICENSE: "<image>\n<|grounding|>Extract all text from this driver's license. Include: license number, full name, date of birth, address, issue date, and expiry date.",
            DocumentType.VOTERS_CARD: "<image>\n<|grounding|>Extract all text from this voter's card. Include: voter ID number, full name, date of birth, gender, and state.",
            DocumentType.PROOF_OF_ADDRESS: "<image>\n<|grounding|>Extract all text from this proof of address document. Include: full name, address, date, and issuing organization.",
            DocumentType.BANK_STATEMENT: "<image>\n<|grounding|>Convert this bank statement to markdown format. Extract account holder name, account number, statement period, and address.",
            DocumentType.UTILITY_BILL: "<image>\n<|grounding|>Extract all text from this utility bill. Include: customer name, address, bill date, and account number."
        }
        
        return prompts.get(document_type, "<image>\n<|grounding|>OCR this document and extract all text.")
    
    def _parse_document_text(
        self,
        raw_text: str,
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Parse raw OCR text into structured data
        
        Args:
            raw_text: Raw text from OCR
            document_type: Type of document
            
        Returns:
            Dictionary with structured data
        """
        structured_data = {}
        
        try:
            # Nigerian National ID patterns
            if document_type == DocumentType.NATIONAL_ID:
                # ID Number (11 digits)
                id_match = re.search(r'\b\d{11}\b', raw_text)
                if id_match:
                    structured_data['document_number'] = id_match.group()
                
                # Date of Birth (DD/MM/YYYY or DD-MM-YYYY)
                dob_match = re.search(r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b', raw_text)
                if dob_match:
                    structured_data['date_of_birth'] = dob_match.group()
                
                # Gender
                gender_match = re.search(r'\b(MALE|FEMALE|M|F)\b', raw_text, re.IGNORECASE)
                if gender_match:
                    structured_data['gender'] = gender_match.group().upper()
            
            # Passport patterns
            elif document_type == DocumentType.PASSPORT:
                # Passport Number (A followed by 8 digits for Nigerian passport)
                passport_match = re.search(r'\bA\d{8}\b', raw_text)
                if passport_match:
                    structured_data['document_number'] = passport_match.group()
                
                # Nationality
                if 'NIGERIA' in raw_text.upper() or 'NIGERIAN' in raw_text.upper():
                    structured_data['nationality'] = 'NIGERIA'
            
            # Extract name (usually in all caps)
            name_match = re.search(r'\b([A-Z]{2,}\s+[A-Z]{2,}(?:\s+[A-Z]{2,})?)\b', raw_text)
            if name_match:
                structured_data['full_name'] = name_match.group()
            
            # Extract dates (issue and expiry)
            date_matches = re.findall(r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b', raw_text)
            if len(date_matches) >= 2:
                structured_data['issue_date'] = date_matches[0]
                structured_data['expiry_date'] = date_matches[1]
            
            return structured_data
            
        except Exception as e:
            logger.error(f"Error parsing document text: {str(e)}")
            return structured_data
    
    def _verify_authenticity(
        self,
        image_path: str,
        extracted_data: DocumentData
    ) -> float:
        """
        Verify document authenticity
        
        Args:
            image_path: Path to document image
            extracted_data: Extracted document data
            
        Returns:
            Authenticity score (0-1)
        """
        try:
            score = 0.0
            
            # Check if required fields are present
            if extracted_data.document_number:
                score += 0.3
            if extracted_data.full_name:
                score += 0.2
            if extracted_data.date_of_birth:
                score += 0.2
            
            # Check image quality indicators
            image = Image.open(image_path)
            width, height = image.size
            
            # Check resolution (higher is better)
            if width >= 1024 and height >= 768:
                score += 0.15
            elif width >= 640 and height >= 480:
                score += 0.10
            
            # Check if image is not too small
            if width >= 400 and height >= 300:
                score += 0.15
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error verifying authenticity: {str(e)}")
            return 0.5
    
    def _check_quality(self, image_path: str) -> float:
        """
        Check document image quality
        
        Args:
            image_path: Path to document image
            
        Returns:
            Quality score (0-1)
        """
        try:
            image = Image.open(image_path)
            width, height = image.size
            
            score = 0.0
            
            # Resolution check
            if width >= 1920 and height >= 1080:
                score += 0.4
            elif width >= 1280 and height >= 720:
                score += 0.3
            elif width >= 640 and height >= 480:
                score += 0.2
            else:
                score += 0.1
            
            # Aspect ratio check (should be reasonable)
            aspect_ratio = width / height
            if 0.7 <= aspect_ratio <= 1.5:
                score += 0.3
            
            # File size check (not too compressed)
            file_size = os.path.getsize(image_path)
            if file_size > 500000:  # > 500KB
                score += 0.3
            elif file_size > 200000:  # > 200KB
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error checking quality: {str(e)}")
            return 0.5
    
    def _validate_data(
        self,
        extracted_data: DocumentData,
        document_type: DocumentType
    ) -> Tuple[List[str], List[str]]:
        """
        Validate extracted data
        
        Args:
            extracted_data: Extracted document data
            document_type: Type of document
            
        Returns:
            Tuple of (issues, warnings)
        """
        issues = []
        warnings = []
        
        # Check required fields
        if not extracted_data.full_name:
            issues.append("Full name not found")
        
        if document_type in [DocumentType.NATIONAL_ID, DocumentType.PASSPORT, DocumentType.DRIVERS_LICENSE]:
            if not extracted_data.document_number:
                issues.append("Document number not found")
            
            if not extracted_data.date_of_birth:
                warnings.append("Date of birth not found")
        
        # Check expiry date
        if extracted_data.expiry_date:
            try:
                # Parse expiry date and check if expired
                # This is a simplified check
                if "2020" in extracted_data.expiry_date or "2021" in extracted_data.expiry_date:
                    warnings.append("Document may be expired")
            except:
                pass
        
        return issues, warnings
    
    def _calculate_confidence(
        self,
        authenticity_score: float,
        quality_score: float,
        num_issues: int,
        num_warnings: int
    ) -> float:
        """Calculate overall confidence score"""
        base_confidence = (authenticity_score * 0.6 + quality_score * 0.4)
        
        # Reduce confidence for issues and warnings
        confidence = base_confidence - (num_issues * 0.15) - (num_warnings * 0.05)
        
        return max(0.0, min(1.0, confidence))
    
    def _determine_status(
        self,
        confidence: float,
        issues: List[str]
    ) -> VerificationStatus:
        """Determine verification status based on confidence and issues"""
        if len(issues) > 2:
            return VerificationStatus.REJECTED
        elif confidence >= 0.85:
            return VerificationStatus.VERIFIED
        elif confidence >= 0.70:
            return VerificationStatus.MANUAL_REVIEW
        else:
            return VerificationStatus.REJECTED
    
    def batch_verify(
        self,
        documents: List[Tuple[str, DocumentType, str]]
    ) -> List[VerificationResult]:
        """
        Batch verify multiple documents
        
        Args:
            documents: List of (image_path, document_type, user_id) tuples
            
        Returns:
            List of VerificationResult
        """
        results = []
        
        for image_path, document_type, user_id in documents:
            try:
                result = self.verify_document(image_path, document_type, user_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch verification: {str(e)}")
                continue
        
        return results


# API endpoint functions
async def verify_kyc_document(
    image_path: str,
    document_type: str,
    user_id: str
) -> Dict[str, Any]:
    """
    API endpoint for KYC document verification
    
    Args:
        image_path: Path to document image
        document_type: Type of document
        user_id: User ID
        
    Returns:
        Verification result dictionary
    """
    try:
        verifier = DeepSeekOCRVerifier()
        
        # Convert string to DocumentType enum
        doc_type = DocumentType(document_type.lower())
        
        # Verify document
        result = verifier.verify_document(image_path, doc_type, user_id)
        
        return {
            "success": True,
            "verification_id": result.verification_id,
            "status": result.status,
            "confidence": result.confidence,
            "document_type": result.document_type,
            "extracted_data": asdict(result.extracted_data),
            "authenticity_score": result.authenticity_score,
            "quality_score": result.quality_score,
            "issues": result.issues,
            "warnings": result.warnings,
            "timestamp": result.timestamp,
            "processing_time_ms": result.processing_time_ms
        }
        
    except Exception as e:
        logger.error(f"Error in verify_kyc_document: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def extract_document_text(
    image_path: str,
    output_format: str = "json"
) -> Dict[str, Any]:
    """
    API endpoint for document text extraction
    
    Args:
        image_path: Path to document image
        output_format: Output format (json, markdown, text)
        
    Returns:
        Extracted text and data
    """
    try:
        verifier = DeepSeekOCRVerifier()
        verifier.initialize()
        
        # Run OCR
        output_path = f"/tmp/ocr_output_{int(datetime.utcnow().timestamp())}"
        os.makedirs(output_path, exist_ok=True)
        
        prompt = "<image>\n<|grounding|>Convert the document to markdown."
        
        result = verifier.model.infer(
            verifier.tokenizer,
            prompt=prompt,
            image_file=image_path,
            output_path=output_path,
            base_size=1024,
            image_size=640,
            crop_mode=True,
            save_results=True,
            test_compress=True
        )
        
        return {
            "success": True,
            "text": result.get('text', ''),
            "format": output_format,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in extract_document_text: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
