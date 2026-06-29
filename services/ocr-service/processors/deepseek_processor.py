"""
DeepSeek OCR Processor
Enhanced OCR with context optical compression
"""

import os
import base64
import httpx
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

class DeepSeekProcessor:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self.api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        
    async def process_document(
        self,
        file_path: str,
        docling_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process document with DeepSeek OCR
        """
        if not self.api_key:
            logger.warning("DeepSeek API key not configured, using fallback")
            return self._fallback_ocr(file_path)
        
        try:
            # Read and encode image
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Prepare request
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{image_data}"
                                        }
                                    },
                                    {
                                        "type": "text",
                                        "text": "Extract all text from this document, preserving structure and layout. Include tables, forms, and any handwritten text."
                                    }
                                ]
                            }
                        ]
                    }
                )
            
            if response.status_code == 200:
                result = response.json()
                text = result["choices"][0]["message"]["content"]
                
                return {
                    "text": text,
                    "confidence": 0.98,
                    "method": "deepseek_ocr"
                }
            else:
                logger.error(f"DeepSeek API error: {response.status_code}")
                return self._fallback_ocr(file_path)
                
        except Exception as e:
            logger.error(f"DeepSeek OCR failed: {str(e)}")
            return self._fallback_ocr(file_path)
    
    def _fallback_ocr(self, file_path: str) -> Dict[str, Any]:
        """Fallback to Tesseract OCR"""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            
            return {
                "text": text,
                "confidence": 0.85,
                "method": "tesseract_fallback"
            }
        except Exception as e:
            logger.error(f"Fallback OCR failed: {str(e)}")
            return {
                "text": "",
                "confidence": 0.0,
                "method": "none"
            }
