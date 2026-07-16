"""
54Bank Docling Service
Advanced document processing with DeepSeek OCR integration
"""

import os
import asyncio
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

from processors.docling_processor import DoclingProcessor
from processors.deepseek_processor import DeepSeekProcessor
from parsers.banking_parsers import BankingDocumentParser
from models.document import DocumentType, ProcessingStatus, DocumentResult

# Configure logging
logger = structlog.get_logger()

# Initialize FastAPI app
app = FastAPI(
    title="54agent OCR Service",
    description="Advanced document processing with DeepSeek OCR and Docling integration",
    version="1.0.0"
)

# Initialize processors
docling_processor = DoclingProcessor()
deepseek_processor = DeepSeekProcessor()
banking_parser = BankingDocumentParser()

# In-memory storage for demo (replace with database in production)
document_store: Dict[str, Dict[str, Any]] = {}

# ==================== HELPER FUNCTIONS ====================

async def download_or_decode_document(content: str, document_id: str) -> str:
    """
    Download document from URL or decode base64 content
    Returns: file path to saved document
    """
    import base64
    import httpx
    import tempfile
    
    # Check if content is URL or base64
    if content.startswith(('http://', 'https://')):
        # Download from URL
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(content)
            response.raise_for_status()
            file_content = response.content
            
            # Determine file extension from content-type
            content_type = response.headers.get('content-type', '')
            if 'pdf' in content_type:
                ext = '.pdf'
            elif 'image' in content_type:
                ext = '.jpg'
            else:
                ext = '.bin'
    else:
        # Decode base64
        try:
            file_content = base64.b64decode(content)
            ext = '.pdf'  # Default to PDF
        except Exception:
            raise ValueError("Invalid base64 content")
    
    # Save to temporary file
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{document_id}{ext}")
    
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    logger.info(f"Saved document to {file_path}")
    return file_path

# ==================== REQUEST/RESPONSE MODELS ====================

class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    message: str
    estimated_processing_time: int  # seconds

class DocumentStatusResponse(BaseModel):
    document_id: str
    status: ProcessingStatus
    progress: int  # 0-100
    result: Optional[DocumentResult] = None
    error: Optional[str] = None

class BatchUploadRequest(BaseModel):
    documents: List[str]  # List of document URLs or base64 encoded content
    document_type: Optional[DocumentType] = None
    tenant_id: str


# ==================== BACKGROUND PROCESSING ====================

async def process_document_async(
    document_id: str,
    file_path: str,
    document_type: Optional[DocumentType],
    tenant_id: str
):
    """
    Background task for asynchronous document processing
    """
    try:
        # Update status to processing
        document_store[document_id]["status"] = ProcessingStatus.PROCESSING
        document_store[document_id]["progress"] = 10
        
        logger.info(f"Starting processing for document {document_id}")
        
        # Step 1: Detect document type if not provided
        if not document_type:
            document_type = await docling_processor.detect_document_type(file_path)
            document_store[document_id]["document_type"] = document_type
            document_store[document_id]["progress"] = 20
        
        # Step 2: Process with Docling
        docling_result = await docling_processor.process_document(
            file_path=file_path,
            document_type=document_type
        )
        document_store[document_id]["progress"] = 50
        
        # Step 3: Enhance with DeepSeek OCR if needed
        if docling_result.get("requires_ocr", False):
            deepseek_result = await deepseek_processor.process_document(
                file_path=file_path,
                docling_context=docling_result
            )
            # Merge results
            docling_result["text"] = deepseek_result.get("text", docling_result.get("text"))
            docling_result["confidence"] = deepseek_result.get("confidence", docling_result.get("confidence"))
        
        document_store[document_id]["progress"] = 70
        
        # Step 4: Parse banking-specific fields
        if document_type in [DocumentType.NATIONAL_ID, DocumentType.PASSPORT, 
                            DocumentType.DRIVERS_LICENSE, DocumentType.BANK_STATEMENT]:
            parsed_fields = banking_parser.parse_document(
                text=docling_result.get("text", ""),
                document_type=document_type,
                structured_data=docling_result.get("tables", [])
            )
            docling_result["parsed_fields"] = parsed_fields
        
        document_store[document_id]["progress"] = 90
        
        # Step 5: Store results
        result = DocumentResult(
            document_id=document_id,
            document_type=document_type,
            text=docling_result.get("text", ""),
            confidence=docling_result.get("confidence", 0.0),
            parsed_fields=docling_result.get("parsed_fields", {}),
            tables=docling_result.get("tables", []),
            images=docling_result.get("images", []),
            metadata=docling_result.get("metadata", {}),
            processing_time_ms=docling_result.get("processing_time_ms", 0)
        )
        
        document_store[document_id]["status"] = ProcessingStatus.COMPLETED
        document_store[document_id]["progress"] = 100
        document_store[document_id]["result"] = result.dict()
        document_store[document_id]["completed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Completed processing for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        document_store[document_id]["status"] = ProcessingStatus.FAILED
        document_store[document_id]["error"] = str(e)


# ==================== API ENDPOINTS ====================

@app.post("/api/v1/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Optional[DocumentType] = None,
    tenant_id: str = Header(..., alias="x-tenant-id"), 
):
    """
    Upload and process a document
    
    Supports: PDF, DOCX, PPTX, XLSX, images (PNG, JPEG, TIFF)
    """
    try:
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Validate file type
        allowed_extensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.png', '.jpg', '.jpeg', '.tiff']

        filename = getattr(file, "filename", None) or getattr(file, "name", None)
        if not filename:
            return None

        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Save file temporarily
        file_path = f"{os.getenv('TMP_PATH', '/tmp')}/docling_{document_id}{file_ext}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Initialize document record
        document_store[document_id] = {
            "document_id": document_id,
            "filename": file.filename,
            "file_path": file_path,
            "document_type": document_type,
            "tenant_id": tenant_id,
            "status": ProcessingStatus.QUEUED,
            "progress": 0,
            "created_at": datetime.utcnow().isoformat(),
            "result": None,
            "error": None
        }

        logger.info(f"Uploaded document {document_id} by tenant {tenant_id}")
        
        # Start background processing
        background_tasks.add_task(
            process_document_async,
            document_id=document_id,
            file_path=file_path,
            document_type=document_type,
            tenant_id=tenant_id
        )
        
        # Estimate processing time based on file size
        file_size_mb = len(content) / (1024 * 1024)
        estimated_time = int(file_size_mb * 10) + 5  # ~10 seconds per MB + 5 seconds overhead
        
        return DocumentUploadResponse(
            document_id=document_id,
            status="queued",
            message=f"Document {file.filename} uploaded successfully and queued for processing",
            estimated_processing_time=estimated_time
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/v1/documents/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Get processing status and results for a document
    """
    if document_id not in document_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = document_store[document_id]
    
    # Verify tenant access
    if doc["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return DocumentStatusResponse(
        document_id=document_id,
        status=doc["status"],
        progress=doc["progress"],
        result=doc.get("result"),
        error=doc.get("error")
    )


@app.get("/api/v1/documents/{document_id}/result")
async def get_document_result(
    document_id: str,
    format: str = "json",  # json, markdown, html
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """
    Get document processing result in specified format
    """
    if document_id not in document_store:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = document_store[document_id]
    
    # Verify tenant access
    if doc["tenant_id"] != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if doc["status"] != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document processing not completed. Current status: {doc['status']}"
        )
    
    result = doc["result"]
    
    if format == "json":
        return JSONResponse(content=result)
    elif format == "markdown":
        # Convert to markdown
        markdown_content = f"# Document: {doc['filename']}\n\n"
        markdown_content += f"## Extracted Text\n\n{result['text']}\n\n"
        if result.get("parsed_fields"):
            markdown_content += "## Parsed Fields\n\n"
            for key, value in result["parsed_fields"].items():
                markdown_content += f"- **{key}**: {value}\n"
        return {"content": markdown_content, "format": "markdown"}
    elif format == "html":
        # Convert to HTML
        html_content = f"<h1>Document: {doc['filename']}</h1>"
        html_content += f"<h2>Extracted Text</h2><p>{result['text']}</p>"
        if result.get("parsed_fields"):
            html_content += "<h2>Parsed Fields</h2><ul>"
            for key, value in result["parsed_fields"].items():
                html_content += f"<li><strong>{key}</strong>: {value}</li>"
            html_content += "</ul>"
        return {"content": html_content, "format": "html"}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@app.post("/api/v1/documents/batch")
async def batch_upload(
    request: BatchUploadRequest,
    background_tasks: BackgroundTasks
):
    """
    Upload and process multiple documents in batch
    """
    document_ids = []
    
    for doc_content in request.documents:
        document_id = str(uuid.uuid4())
        document_ids.append(document_id)
        
        try:
            # Download document from URL or decode base64
            file_path = await download_or_decode_document(doc_content, document_id)
            
            # Queue the processing
            document_store[document_id] = {
                "document_id": document_id,
                "status": ProcessingStatus.QUEUED,
                "tenant_id": request.tenant_id,
                "created_at": datetime.utcnow().isoformat(),
                "file_path": file_path
            }
            
            # Start background processing
            background_tasks.add_task(
                process_document_async,
                document_id,
                file_path,
                request.document_type,
                request.tenant_id
            )
            
        except Exception as e:
            logger.error(f"Failed to download/decode document: {str(e)}")
            document_store[document_id] = {
                "document_id": document_id,
                "status": ProcessingStatus.FAILED,
                "tenant_id": request.tenant_id,
                "error": f"Download failed: {str(e)}",
                "created_at": datetime.utcnow().isoformat()
            }
    
    return {
        "batch_id": str(uuid.uuid4()),
        "document_ids": document_ids,
        "total_documents": len(document_ids),
        "message": "Batch processing initiated"
    }


@app.get("/api/v1/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "docling-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "processors": {
            "docling": "ready",
            "deepseek": "ready"
        }
    }


@app.get("/api/v1/metrics")
async def get_metrics():
    """
    Get service metrics
    """
    total_documents = len(document_store)
    completed = sum(1 for doc in document_store.values() if doc["status"] == ProcessingStatus.COMPLETED)
    failed = sum(1 for doc in document_store.values() if doc["status"] == ProcessingStatus.FAILED)
    processing = sum(1 for doc in document_store.values() if doc["status"] == ProcessingStatus.PROCESSING)
    queued = sum(1 for doc in document_store.values() if doc["status"] == ProcessingStatus.QUEUED)
    
    return {
        "total_documents": total_documents,
        "completed": completed,
        "failed": failed,
        "processing": processing,
        "queued": queued,
        "success_rate": (completed / total_documents * 100) if total_documents > 0 else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8026)))
