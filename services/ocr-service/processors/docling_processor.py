"""
Docling Document Processor
Handles multi-format document processing with advanced PDF understanding
"""

import os
import time
from typing import Dict, Any, Optional
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import InputFormat
from models.document import DocumentType
import structlog

logger = structlog.get_logger()

class DoclingProcessor:
    def __init__(self):
        self.converter = DocumentConverter()
        
    async def detect_document_type(self, file_path: str) -> DocumentType:
        """Detect document type from content"""
        # Simple heuristic based on filename and content
        filename = os.path.basename(file_path).lower()
        
        if any(x in filename for x in ['passport', 'international']):
            return DocumentType.PASSPORT
        elif any(x in filename for x in ['license', 'driver']):
            return DocumentType.DRIVERS_LICENSE
        elif any(x in filename for x in ['statement', 'bank']):
            return DocumentType.BANK_STATEMENT
        elif any(x in filename for x in ['utility', 'bill', 'nepa', 'phcn']):
            return DocumentType.UTILITY_BILL
        elif any(x in filename for x in ['cac', 'registration', 'corporate']):
            return DocumentType.CORPORATE_REGISTRATION
        elif any(x in filename for x in ['tax', 'tin', 'firs']):
            return DocumentType.TAX_DOCUMENT
        elif any(x in filename for x in ['loan', 'application']):
            return DocumentType.LOAN_APPLICATION
        elif any(x in filename for x in ['financial', 'balance', 'income']):
            return DocumentType.FINANCIAL_STATEMENT
        else:
            return DocumentType.UNKNOWN
    
    async def process_document(
        self,
        file_path: str,
        document_type: Optional[DocumentType] = None
    ) -> Dict[str, Any]:
        """
        Process document with Docling
        """
        start_time = time.time()
        
        try:
            # Convert document
            result = self.converter.convert(file_path)
            
            # Extract text
            text = result.document.export_to_markdown()
            
            # Extract tables
            tables = []
            if hasattr(result.document, 'tables'):
                for table in result.document.tables:
                    tables.append({
                        "rows": table.num_rows if hasattr(table, 'num_rows') else 0,
                        "cols": table.num_cols if hasattr(table, 'num_cols') else 0,
                        "data": str(table)
                    })
            
            # Extract images
            images = []
            if hasattr(result.document, 'pictures'):
                images = [str(img) for img in result.document.pictures]
            
            # Check if OCR is needed (scanned document)
            requires_ocr = self._check_if_scanned(text)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                "text": text,
                "confidence": 0.95 if not requires_ocr else 0.70,
                "tables": tables,
                "images": images,
                "requires_ocr": requires_ocr,
                "metadata": {
                    "page_count": result.document.page_count if hasattr(result.document, 'page_count') else 1,
                    "format": os.path.splitext(file_path)[1]
                },
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Docling processing failed: {str(e)}")
            raise
    
    def _check_if_scanned(self, text: str) -> bool:
        """Check if document appears to be scanned (low text extraction)"""
        return len(text.strip()) < 100
