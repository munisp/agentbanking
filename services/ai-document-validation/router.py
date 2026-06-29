"""
Router for ai-document-validation service
Auto-extracted from main.py for unified gateway registration
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ai-document-validation", tags=["ai-document-validation"])

@router.post("/validate")
async def validate_document(
    user_id: str,
    document_type: DocumentType,
    file: UploadFile = File(...)):
    return {"status": "ok"}

@router.get("/validations/{validation_id}")
async def get_validation(validation_id: str):
    return {"status": "ok"}

@router.get("/health")
async def health_check():
    return {"status": "ok"}

