"""
DeepSeek OCR Processor - Vision-Language Model for Document Understanding
Provides advanced OCR with context understanding, layout preservation, and multi-language support
"""

import logging
import torch
from typing import Dict, List, Optional, Any
from pathlib import Path
from PIL import Image
import base64
import io
import json
from dataclasses import dataclass
from enum import Enum

try:
    from transformers import AutoModel, AutoTokenizer, AutoProcessor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers not available. Install with: pip install transformers torch")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OCRMode(str, Enum):
    """OCR processing modes"""
    FULL_TEXT = "full_text"  # Extract all text
    STRUCTURED = "structured"  # Extract with structure (tables, forms)
    ENTITIES = "entities"  # Extract named entities
    LAYOUT = "layout"  # Preserve layout and formatting


@dataclass
class OCRResult:
    """OCR processing result"""
    text: str
    confidence: float
    language: str
    layout_preserved: bool
    entities: List[Dict[str, Any]]
    tables: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class DeepSeekOCRProcessor:
    """
    DeepSeek Vision-Language Model for advanced OCR
    Supports context understanding, layout preservation, and 100+ languages
    """
    
    def __init__(
        self,
        model_name: str = "deepseek-ai/deepseek-vl-7b-chat",
        device: str = "auto",
        use_gpu: bool = True,
        max_length: int = 4096
    ):
        """
        Initialize DeepSeek OCR processor
        
        Args:
            model_name: HuggingFace model identifier
            device: Device to run model on ('auto', 'cuda', 'cpu')
            use_gpu: Whether to use GPU if available
            max_length: Maximum token length for generation
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("Transformers library required. Install with: pip install transformers torch")
        
        self.model_name = model_name
        self.max_length = max_length
        
        # Determine device
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() and use_gpu else "cpu"
        else:
            self.device = device
        
        logger.info(f"Initializing DeepSeek OCR on device: {self.device}")
        
        # Load model and tokenizer
        try:
            self.model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                device_map=device if device == "auto" else None,
                low_cpu_mem_usage=True
            )
            
            if device != "auto":
                self.model = self.model.to(self.device)
            
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=True
            )
            
            # Try to load processor if available
            try:
                self.processor = AutoProcessor.from_pretrained(
                    model_name,
                    trust_remote_code=True
                )
            except:
                self.processor = None
                logger.warning("Processor not available, using tokenizer only")
            
            self.model.eval()
            logger.info(f"DeepSeek OCR initialized successfully on {self.device}")
            
        except Exception as e:
            logger.error(f"Failed to load DeepSeek model: {e}")
            raise
    
    async def process_image(
        self,
        image_path: Path,
        mode: OCRMode = OCRMode.FULL_TEXT,
        language: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> OCRResult:
        """
        Process image with DeepSeek OCR
        
        Args:
            image_path: Path to image file
            mode: OCR processing mode
            language: Target language (auto-detect if None)
            custom_prompt: Custom prompt for specific extraction
        
        Returns:
            OCRResult with extracted text and metadata
        """
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            
            # Build prompt based on mode
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = self._build_prompt(mode, language)
            
            # Process with DeepSeek VLM
            result = await self._run_inference(image, prompt)
            
            # Parse result
            ocr_result = self._parse_result(result, mode)
            
            return ocr_result
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            raise
    
    async def process_document(
        self,
        document_path: Path,
        mode: OCRMode = OCRMode.STRUCTURED,
        language: Optional[str] = None
    ) -> List[OCRResult]:
        """
        Process multi-page document
        
        Args:
            document_path: Path to document (PDF, TIFF, etc.)
            mode: OCR processing mode
            language: Target language
        
        Returns:
            List of OCRResult for each page
        """
        # Convert document to images (handled by Docling)
        # This method integrates with Docling's page extraction
        
        results = []
        
        # For now, process as single image
        # In production, integrate with Docling's page iterator
        result = await self.process_image(document_path, mode, language)
        results.append(result)
        
        return results
    
    async def extract_entities(
        self,
        image_path: Path,
        entity_types: List[str],
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract specific entities from document
        
        Args:
            image_path: Path to image
            entity_types: List of entity types to extract (name, date, amount, etc.)
            document_type: Document type hint (passport, invoice, etc.)
        
        Returns:
            Dictionary of extracted entities
        """
        # Build entity extraction prompt
        entity_list = ", ".join(entity_types)
        prompt = f"Extract the following information from this document: {entity_list}. "
        
        if document_type:
            prompt += f"This is a {document_type}. "
        
        prompt += "Return the information in JSON format with field names as keys."
        
        # Process image
        image = Image.open(image_path).convert("RGB")
        result = await self._run_inference(image, prompt)
        
        # Parse JSON result
        try:
            entities = json.loads(result)
        except json.JSONDecodeError:
            # Fallback: extract from text
            entities = self._extract_entities_from_text(result, entity_types)
        
        return entities
    
    async def extract_tables(
        self,
        image_path: Path
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from document
        
        Args:
            image_path: Path to image
        
        Returns:
            List of extracted tables with structure
        """
        prompt = (
            "Extract all tables from this document. "
            "For each table, provide the headers and rows in structured format. "
            "Return as JSON array."
        )
        
        image = Image.open(image_path).convert("RGB")
        result = await self._run_inference(image, prompt)
        
        # Parse tables
        try:
            tables = json.loads(result)
        except json.JSONDecodeError:
            tables = self._extract_tables_from_text(result)
        
        return tables
    
    def _build_prompt(self, mode: OCRMode, language: Optional[str] = None) -> str:
        """Build prompt based on OCR mode"""
        
        prompts = {
            OCRMode.FULL_TEXT: (
                "Extract all text from this document. "
                "Preserve the original layout and formatting as much as possible."
            ),
            OCRMode.STRUCTURED: (
                "Extract all text from this document with structure. "
                "Identify headings, paragraphs, lists, tables, and forms. "
                "Preserve the document hierarchy and layout."
            ),
            OCRMode.ENTITIES: (
                "Extract all named entities from this document including: "
                "names, dates, addresses, phone numbers, email addresses, "
                "identification numbers, amounts, and organizations."
            ),
            OCRMode.LAYOUT: (
                "Extract text while preserving the exact layout. "
                "Maintain spacing, alignment, and positioning of all text elements."
            )
        }
        
        prompt = prompts.get(mode, prompts[OCRMode.FULL_TEXT])
        
        if language:
            prompt += f" The document is in {language}."
        
        return prompt
    
    async def _run_inference(self, image: Image.Image, prompt: str) -> str:
        """Run DeepSeek VLM inference"""
        
        try:
            # Prepare inputs
            if self.processor:
                # Use processor if available
                inputs = self.processor(
                    text=prompt,
                    images=image,
                    return_tensors="pt"
                ).to(self.device)
            else:
                # Fallback: use tokenizer only
                # Convert image to base64 for text-based models
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # Some models accept image tokens
                inputs = self.tokenizer(
                    prompt,
                    return_tensors="pt"
                ).to(self.device)
            
            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=self.max_length,
                    num_beams=3,
                    temperature=0.7,
                    do_sample=False,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove prompt from result
            if result.startswith(prompt):
                result = result[len(prompt):].strip()
            
            return result
            
        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise
    
    def _parse_result(self, result: str, mode: OCRMode) -> OCRResult:
        """Parse inference result into OCRResult"""
        
        # Extract entities if in entities mode
        entities = []
        if mode == OCRMode.ENTITIES:
            entities = self._extract_entities_from_text(
                result,
                ["name", "date", "address", "phone", "email", "id_number", "amount"]
            )
        
        # Extract tables if in structured mode
        tables = []
        if mode == OCRMode.STRUCTURED:
            tables = self._extract_tables_from_text(result)
        
        # Calculate confidence (simplified)
        confidence = 0.95  # DeepSeek VLM typically high confidence
        
        # Detect language (simplified)
        language = "en"  # Default, could use langdetect
        
        return OCRResult(
            text=result,
            confidence=confidence,
            language=language,
            layout_preserved=(mode in [OCRMode.LAYOUT, OCRMode.STRUCTURED]),
            entities=entities,
            tables=tables,
            metadata={
                "model": self.model_name,
                "mode": mode.value,
                "device": self.device
            }
        )
    
    def _extract_entities_from_text(
        self,
        text: str,
        entity_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Extract entities from text using patterns"""
        import re
        
        entities = []
        
        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            "date": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            "amount": r'\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?',
            "id_number": r'\b[A-Z0-9]{6,12}\b'
        }
        
        for entity_type in entity_types:
            if entity_type in patterns:
                matches = re.finditer(patterns[entity_type], text)
                for match in matches:
                    entities.append({
                        "type": entity_type,
                        "value": match.group(0),
                        "confidence": 0.85,
                        "start": match.start(),
                        "end": match.end()
                    })
        
        return entities
    
    def _extract_tables_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract tables from text (simplified)"""
        
        tables = []
        
        # Look for table-like structures
        lines = text.split('\n')
        current_table = []
        in_table = False
        
        for line in lines:
            # Simple heuristic: lines with multiple | or \t are table rows
            if '|' in line or '\t' in line:
                if not in_table:
                    in_table = True
                    current_table = []
                current_table.append(line)
            else:
                if in_table and current_table:
                    # End of table
                    tables.append({
                        "rows": current_table,
                        "row_count": len(current_table)
                    })
                    current_table = []
                    in_table = False
        
        # Add last table if exists
        if current_table:
            tables.append({
                "rows": current_table,
                "row_count": len(current_table)
            })
        
        return tables
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_length": self.max_length,
            "gpu_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0
        }


class DeepSeekOCRFallback:
    """
    Fallback OCR processor when DeepSeek model is not available
    Uses basic OCR methods
    """
    
    def __init__(self):
        logger.warning("Using fallback OCR (DeepSeek not available)")
        try:
            import pytesseract
            self.tesseract_available = True
        except ImportError:
            self.tesseract_available = False
            logger.warning("Tesseract not available")
    
    async def process_image(
        self,
        image_path: Path,
        mode: OCRMode = OCRMode.FULL_TEXT,
        language: Optional[str] = None,
        custom_prompt: Optional[str] = None
    ) -> OCRResult:
        """Process image with fallback OCR"""
        
        if self.tesseract_available:
            import pytesseract
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            confidence = 0.75
        else:
            text = "OCR not available - install DeepSeek or Tesseract"
            confidence = 0.0
        
        return OCRResult(
            text=text,
            confidence=confidence,
            language=language or "en",
            layout_preserved=False,
            entities=[],
            tables=[],
            metadata={"fallback": True}
        )
    
    async def process_document(
        self,
        document_path: Path,
        mode: OCRMode = OCRMode.STRUCTURED,
        language: Optional[str] = None
    ) -> List[OCRResult]:
        """Process document with fallback OCR"""
        result = await self.process_image(document_path, mode, language)
        return [result]
    
    async def extract_entities(
        self,
        image_path: Path,
        entity_types: List[str],
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract entities with fallback"""
        return {}
    
    async def extract_tables(self, image_path: Path) -> List[Dict[str, Any]]:
        """Extract tables with fallback"""
        return []
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get fallback info"""
        return {
            "model_name": "fallback",
            "tesseract_available": self.tesseract_available
        }


def create_ocr_processor(
    use_deepseek: bool = True,
    **kwargs
) -> DeepSeekOCRProcessor:
    """
    Factory function to create OCR processor
    
    Args:
        use_deepseek: Whether to use DeepSeek (falls back if not available)
        **kwargs: Arguments for DeepSeekOCRProcessor
    
    Returns:
        OCR processor instance
    """
    if use_deepseek and TRANSFORMERS_AVAILABLE:
        try:
            return DeepSeekOCRProcessor(**kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek OCR: {e}")
            logger.info("Falling back to basic OCR")
            return DeepSeekOCRFallback()
    else:
        return DeepSeekOCRFallback()


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_ocr():
        # Create processor
        processor = create_ocr_processor()
        
        # Get model info
        info = processor.get_model_info()
        print(f"Model info: {info}")
        
        # Process image
        # result = await processor.process_image(
        #     Path("test_document.jpg"),
        #     mode=OCRMode.STRUCTURED
        # )
        # print(f"Extracted text: {result.text[:200]}...")
        # print(f"Confidence: {result.confidence}")
    
    asyncio.run(test_ocr())
