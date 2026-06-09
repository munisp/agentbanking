"""
DeepSeek-OCR Service Router
FastAPI endpoints for document verification
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
import os
import shutil
from pathlib import Path
from .deepseek_ocr_verifier import (
    verify_kyc_document,
    extract_document_text,
    DocumentType
)

router = APIRouter(prefix="/api/v1/deepseek-ocr", tags=["deepseek-ocr"])

# Upload directory
UPLOAD_DIR = Path("/tmp/kyc_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/verify-document", response_model=dict)
async def verify_document_endpoint(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    user_id: str = Form(...)
):
    """
    Verify KYC document using DeepSeek-OCR
    
    Args:
        file: Document image file
        document_type: Type of document (national_id, passport, drivers_license, etc.)
        user_id: User ID for tracking
        
    Returns:
        Verification result with extracted data and confidence scores
    """
    try:
        # Validate document type
        valid_types = [dt.value for dt in DocumentType]
        if document_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid document type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Save uploaded file
        file_path = UPLOAD_DIR / f"{user_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Verify document
        result = await verify_kyc_document(
            image_path=str(file_path),
            document_type=document_type,
            user_id=user_id
        )
        
        # Clean up uploaded file
        os.remove(file_path)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-text", response_model=dict)
async def extract_text_endpoint(
    file: UploadFile = File(...),
    output_format: str = Form("json")
):
    """
    Extract text from document using DeepSeek-OCR
    
    Args:
        file: Document image file
        output_format: Output format (json, markdown, text)
        
    Returns:
        Extracted text and data
    """
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract text
        result = await extract_document_text(
            image_path=str(file_path),
            output_format=output_format
        )
        
        # Clean up uploaded file
        os.remove(file_path)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/document-types", response_model=dict)
async def get_document_types():
    """
    Get list of supported document types
    
    Returns:
        List of supported document types
    """
    return {
        "document_types": [
            {
                "value": dt.value,
                "name": dt.value.replace('_', ' ').title()
            }
            for dt in DocumentType
        ]
    }


@router.get("/health", response_model=dict)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "deepseek-ocr",
        "version": "1.0.0"
    }
