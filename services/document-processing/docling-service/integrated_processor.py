"""
Integrated Document Processor - Docling + DeepSeek OCR
Combines Docling's document parsing with DeepSeek's advanced OCR
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

# Docling imports
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logging.warning("Docling not available")

# DeepSeek OCR import
import sys
sys.path.append(str(Path(__file__).parent.parent / "deepseek-ocr"))
from deepseek_processor import (
    DeepSeekOCRProcessor,
    create_ocr_processor,
    OCRMode,
    OCRResult
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedDocumentProcessor:
    """
    Integrated processor combining Docling and DeepSeek OCR
    
    Pipeline:
    1. Docling extracts document structure (pages, layout, tables)
    2. DeepSeek OCR extracts text with context understanding
    3. Combine results for optimal accuracy
    """
    
    def __init__(
        self,
        use_deepseek: bool = True,
        use_gpu: bool = True,
        deepseek_model: str = "deepseek-ai/deepseek-vl-7b-chat"
    ):
        """
        Initialize integrated processor
        
        Args:
            use_deepseek: Whether to use DeepSeek OCR
            use_gpu: Whether to use GPU for DeepSeek
            deepseek_model: DeepSeek model name
        """
        self.use_deepseek = use_deepseek
        
        # Initialize Docling
        if DOCLING_AVAILABLE:
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True  # Docling's basic OCR as fallback
            pipeline_options.do_table_structure = True
            
            self.docling_converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: pipeline_options,
                }
            )
            logger.info("Docling initialized")
        else:
            self.docling_converter = None
            logger.warning("Docling not available")
        
        # Initialize DeepSeek OCR
        if use_deepseek:
            try:
                self.deepseek_processor = create_ocr_processor(
                    use_deepseek=True,
                    use_gpu=use_gpu,
                    model_name=deepseek_model
                )
                logger.info("DeepSeek OCR initialized")
            except Exception as e:
                logger.error(f"Failed to initialize DeepSeek: {e}")
                self.deepseek_processor = create_ocr_processor(use_deepseek=False)
        else:
            self.deepseek_processor = create_ocr_processor(use_deepseek=False)
    
    async def process_document(
        self,
        file_path: Path,
        document_type: str = "unknown",
        extract_entities: bool = True,
        extract_tables: bool = True
    ) -> Dict[str, Any]:
        """
        Process document with integrated pipeline
        
        Args:
            file_path: Path to document
            document_type: Type of document (passport, invoice, etc.)
            extract_entities: Whether to extract entities
            extract_tables: Whether to extract tables
        
        Returns:
            Comprehensive processing result
        """
        start_time = datetime.utcnow()
        
        result = {
            "file_path": str(file_path),
            "document_type": document_type,
            "processing_method": "integrated",
            "docling_result": None,
            "deepseek_result": None,
            "combined_text": "",
            "entities": [],
            "tables": [],
            "confidence": 0.0,
            "processing_time_seconds": 0.0
        }
        
        try:
            # Step 1: Process with Docling (structure + basic OCR)
            docling_result = await self._process_with_docling(file_path)
            result["docling_result"] = docling_result
            
            # Step 2: Process with DeepSeek OCR (advanced text extraction)
            deepseek_result = await self._process_with_deepseek(
                file_path,
                document_type,
                extract_entities,
                extract_tables
            )
            result["deepseek_result"] = deepseek_result
            
            # Step 3: Combine results
            combined = self._combine_results(docling_result, deepseek_result)
            result.update(combined)
            
            # Calculate processing time
            result["processing_time_seconds"] = (
                datetime.utcnow() - start_time
            ).total_seconds()
            
            logger.info(
                f"Document processed: {file_path.name}, "
                f"confidence: {result['confidence']:.2f}, "
                f"time: {result['processing_time_seconds']:.2f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            result["error"] = str(e)
            return result
    
    async def _process_with_docling(self, file_path: Path) -> Optional[Dict]:
        """Process document with Docling"""
        
        if not self.docling_converter:
            return None
        
        try:
            # Convert document
            conversion_result = self.docling_converter.convert(str(file_path))
            
            # Extract content
            markdown = conversion_result.document.export_to_markdown()
            text = conversion_result.document.export_to_text()
            
            # Extract tables
            tables = []
            if hasattr(conversion_result.document, 'tables'):
                for table in conversion_result.document.tables:
                    tables.append({
                        "data": table.data if hasattr(table, 'data') else [],
                        "rows": table.num_rows if hasattr(table, 'num_rows') else 0,
                        "cols": table.num_cols if hasattr(table, 'num_cols') else 0
                    })
            
            # Get page count
            page_count = (
                len(conversion_result.document.pages)
                if hasattr(conversion_result.document, 'pages')
                else 1
            )
            
            return {
                "text": text,
                "markdown": markdown,
                "tables": tables,
                "page_count": page_count,
                "confidence": 0.85  # Docling basic OCR confidence
            }
            
        except Exception as e:
            logger.error(f"Docling processing error: {e}")
            return None
    
    async def _process_with_deepseek(
        self,
        file_path: Path,
        document_type: str,
        extract_entities: bool,
        extract_tables: bool
    ) -> Optional[Dict]:
        """Process document with DeepSeek OCR"""
        
        if not self.deepseek_processor:
            return None
        
        try:
            # Determine OCR mode based on document type
            if document_type in ["invoice", "receipt", "form"]:
                mode = OCRMode.STRUCTURED
            elif document_type in ["passport", "id_card", "license"]:
                mode = OCRMode.ENTITIES
            else:
                mode = OCRMode.FULL_TEXT
            
            # Process document
            ocr_results = await self.deepseek_processor.process_document(
                file_path,
                mode=mode
            )
            
            # Get first page result (or combine all pages)
            if not ocr_results:
                return None
            
            main_result = ocr_results[0]
            
            # Extract entities if requested
            entities = []
            if extract_entities:
                entity_types = self._get_entity_types_for_document(document_type)
                entities_dict = await self.deepseek_processor.extract_entities(
                    file_path,
                    entity_types,
                    document_type
                )
                entities = self._format_entities(entities_dict)
            
            # Extract tables if requested
            tables = []
            if extract_tables:
                tables = await self.deepseek_processor.extract_tables(file_path)
            
            return {
                "text": main_result.text,
                "entities": entities,
                "tables": tables,
                "confidence": main_result.confidence,
                "language": main_result.language,
                "layout_preserved": main_result.layout_preserved
            }
            
        except Exception as e:
            logger.error(f"DeepSeek processing error: {e}")
            return None
    
    def _combine_results(
        self,
        docling_result: Optional[Dict],
        deepseek_result: Optional[Dict]
    ) -> Dict[str, Any]:
        """Combine Docling and DeepSeek results"""
        
        combined = {
            "combined_text": "",
            "entities": [],
            "tables": [],
            "confidence": 0.0,
            "markdown": "",
            "page_count": 1
        }
        
        # Prioritize DeepSeek text (higher accuracy)
        if deepseek_result and deepseek_result.get("text"):
            combined["combined_text"] = deepseek_result["text"]
            combined["confidence"] = deepseek_result.get("confidence", 0.95)
        elif docling_result and docling_result.get("text"):
            combined["combined_text"] = docling_result["text"]
            combined["confidence"] = docling_result.get("confidence", 0.85)
        
        # Use DeepSeek entities (ML-based)
        if deepseek_result and deepseek_result.get("entities"):
            combined["entities"] = deepseek_result["entities"]
        
        # Combine tables (prefer Docling's table structure)
        if docling_result and docling_result.get("tables"):
            combined["tables"].extend(docling_result["tables"])
        if deepseek_result and deepseek_result.get("tables"):
            # Add DeepSeek tables if not duplicates
            combined["tables"].extend(deepseek_result["tables"])
        
        # Use Docling markdown (better structure)
        if docling_result and docling_result.get("markdown"):
            combined["markdown"] = docling_result["markdown"]
        
        # Use Docling page count
        if docling_result and docling_result.get("page_count"):
            combined["page_count"] = docling_result["page_count"]
        
        return combined
    
    def _get_entity_types_for_document(self, document_type: str) -> List[str]:
        """Get relevant entity types for document type"""
        
        entity_map = {
            "passport": ["full_name", "passport_number", "date_of_birth", "nationality", "expiry_date", "issue_date"],
            "national_id": ["full_name", "id_number", "date_of_birth", "address", "issue_date"],
            "drivers_license": ["full_name", "license_number", "date_of_birth", "address", "expiry_date"],
            "utility_bill": ["customer_name", "address", "bill_date", "amount", "account_number"],
            "bank_statement": ["account_holder", "account_number", "bank_name", "statement_period", "balance"],
            "invoice": ["invoice_number", "date", "seller", "buyer", "amount", "tax", "total"],
            "receipt": ["merchant", "date", "amount", "items", "payment_method"],
            "business_registration": ["business_name", "registration_number", "registration_date", "address", "directors"],
            "contract": ["parties", "date", "terms", "amount", "signatures"]
        }
        
        return entity_map.get(document_type, ["name", "date", "amount", "address"])
    
    def _format_entities(self, entities_dict: Dict[str, Any]) -> List[Dict]:
        """Format entities dictionary to list"""
        
        formatted = []
        for key, value in entities_dict.items():
            if value:
                formatted.append({
                    "field": key,
                    "value": str(value),
                    "confidence": 0.95,  # DeepSeek high confidence
                    "source": "deepseek_ocr"
                })
        
        return formatted
    
    async def extract_kyc_data(self, file_path: Path, document_type: str) -> Dict[str, Any]:
        """
        Extract KYC-specific data from document
        
        Args:
            file_path: Path to KYC document
            document_type: Type (passport, national_id, etc.)
        
        Returns:
            Structured KYC data
        """
        # Process document
        result = await self.process_document(
            file_path,
            document_type=document_type,
            extract_entities=True,
            extract_tables=False
        )
        
        # Extract KYC fields
        kyc_data = {
            "document_type": document_type,
            "full_name": None,
            "document_number": None,
            "date_of_birth": None,
            "nationality": None,
            "address": None,
            "expiry_date": None,
            "confidence": result.get("confidence", 0.0),
            "raw_text": result.get("combined_text", "")[:500]  # First 500 chars
        }
        
        # Map entities to KYC fields
        for entity in result.get("entities", []):
            field = entity.get("field", "")
            value = entity.get("value", "")
            
            if field in ["full_name", "name"]:
                kyc_data["full_name"] = value
            elif field in ["passport_number", "id_number", "license_number"]:
                kyc_data["document_number"] = value
            elif field in ["date_of_birth", "dob"]:
                kyc_data["date_of_birth"] = value
            elif field == "nationality":
                kyc_data["nationality"] = value
            elif field == "address":
                kyc_data["address"] = value
            elif field in ["expiry_date", "expiration_date"]:
                kyc_data["expiry_date"] = value
        
        return kyc_data
    
    async def extract_kyb_data(self, file_path: Path, document_type: str) -> Dict[str, Any]:
        """
        Extract KYB-specific data from business document
        
        Args:
            file_path: Path to KYB document
            document_type: Type (business_registration, articles, etc.)
        
        Returns:
            Structured KYB data
        """
        # Process document
        result = await self.process_document(
            file_path,
            document_type=document_type,
            extract_entities=True,
            extract_tables=True
        )
        
        # Extract KYB fields
        kyb_data = {
            "document_type": document_type,
            "business_name": None,
            "registration_number": None,
            "registration_date": None,
            "business_address": None,
            "directors": [],
            "shareholders": [],
            "confidence": result.get("confidence", 0.0),
            "raw_text": result.get("combined_text", "")[:500]
        }
        
        # Map entities to KYB fields
        for entity in result.get("entities", []):
            field = entity.get("field", "")
            value = entity.get("value", "")
            
            if field in ["business_name", "company_name"]:
                kyb_data["business_name"] = value
            elif field in ["registration_number", "company_number"]:
                kyb_data["registration_number"] = value
            elif field in ["registration_date", "incorporation_date"]:
                kyb_data["registration_date"] = value
            elif field in ["address", "business_address"]:
                kyb_data["business_address"] = value
            elif field == "directors":
                kyb_data["directors"] = value.split(",") if isinstance(value, str) else value
        
        # Extract directors/shareholders from tables
        for table in result.get("tables", []):
            # Look for director/shareholder tables
            rows = table.get("rows", [])
            if any("director" in str(row).lower() for row in rows[:2]):
                kyb_data["directors"].extend(self._parse_director_table(rows))
            elif any("shareholder" in str(row).lower() for row in rows[:2]):
                kyb_data["shareholders"].extend(self._parse_shareholder_table(rows))
        
        return kyb_data
    
    def _parse_director_table(self, rows: List[str]) -> List[Dict]:
        """Parse director information from table rows"""
        directors = []
        # Simplified parsing - in production, use more robust logic
        for row in rows[1:]:  # Skip header
            if row.strip():
                directors.append({"name": row.strip()})
        return directors
    
    def _parse_shareholder_table(self, rows: List[str]) -> List[Dict]:
        """Parse shareholder information from table rows"""
        shareholders = []
        # Simplified parsing
        for row in rows[1:]:
            if row.strip():
                shareholders.append({"name": row.strip()})
        return shareholders
    
    def get_processor_info(self) -> Dict[str, Any]:
        """Get processor information"""
        return {
            "docling_available": self.docling_converter is not None,
            "deepseek_info": self.deepseek_processor.get_model_info() if self.deepseek_processor else None,
            "integrated": True
        }


# Example usage
if __name__ == "__main__":
    async def test_integrated():
        processor = IntegratedDocumentProcessor(use_deepseek=True, use_gpu=True)
        
        info = processor.get_processor_info()
        print(f"Processor info: {info}")
        
        # Test KYC extraction
        # kyc_data = await processor.extract_kyc_data(
        #     Path("passport.jpg"),
        #     "passport"
        # )
        # print(f"KYC data: {kyc_data}")
    
    asyncio.run(test_integrated())
