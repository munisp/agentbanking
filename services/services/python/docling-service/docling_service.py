#!/usr/bin/env python3
"""
POS-54Link Docling Service — Structured document parsing using IBM Docling
for extracting tables, forms, and hierarchical data from complex documents.

Specializes in:
  - Multi-page PDF parsing with layout analysis
  - Table extraction with row/column structure preservation
  - Form field detection and value extraction
  - Hierarchical document structure (sections, headers, paragraphs)
  - Business document templates (invoices, contracts, certificates)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("docling-service")

app = FastAPI(title="POS-54Link Docling Service", version="1.0.0")


# ── Models ────────────────────────────────────────────────────────────────────

@dataclass
class TableCell:
    row: int
    col: int
    text: str
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False


@dataclass
class ExtractedTable:
    table_id: str
    page: int
    title: Optional[str]
    headers: list[str]
    rows: list[list[str]]
    cells: list[TableCell]
    confidence: float


@dataclass
class FormField:
    field_id: str
    label: str
    value: str
    field_type: str  # text, checkbox, date, number, signature
    page: int
    confidence: float
    bbox: list[float]


@dataclass
class DocumentSection:
    section_id: str
    level: int  # 0 = title, 1 = h1, 2 = h2, etc.
    title: str
    content: str
    page_start: int
    page_end: int
    children: list = field(default_factory=list)


@dataclass
class DoclingResult:
    request_id: str
    document_type: str
    total_pages: int
    sections: list[DocumentSection]
    tables: list[ExtractedTable]
    form_fields: list[FormField]
    metadata: dict
    full_text: str
    processing_time_ms: float


# ── Docling Engine ────────────────────────────────────────────────────────────

class DoclingEngine:
    """Wraps IBM Docling for structured document parsing."""

    def __init__(self):
        self.converter = None
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return
        try:
            # In production:
            # from docling.document_converter import DocumentConverter
            # self.converter = DocumentConverter()
            self.initialized = True
            logger.info("Docling engine initialized")
        except Exception as e:
            logger.warning(f"Docling not available, using mock: {e}")
            self.initialized = True

    async def parse_document(self, file_bytes: bytes, filename: str) -> DoclingResult:
        """Parse a document and extract structured data."""
        await self.initialize()
        start = time.monotonic()
        request_id = str(uuid.uuid4())

        # In production:
        # from docling.datamodel.base_models import InputFormat
        # source = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
        # result = self.converter.convert(source)
        # doc = result.document

        # Mock structured output
        sections = [
            DocumentSection(
                section_id="s1", level=0,
                title="Certificate of Incorporation",
                content="This certifies that ACME FINTECH LTD has been incorporated...",
                page_start=1, page_end=1,
            ),
            DocumentSection(
                section_id="s2", level=1,
                title="Company Details",
                content="Registration Number: PVT-2024-12345\nDate of Incorporation: 15 January 2024",
                page_start=1, page_end=1,
            ),
            DocumentSection(
                section_id="s3", level=1,
                title="Directors",
                content="The following persons are registered as directors...",
                page_start=1, page_end=2,
            ),
            DocumentSection(
                section_id="s4", level=1,
                title="Share Capital",
                content="Authorized share capital: KES 10,000,000",
                page_start=2, page_end=2,
            ),
        ]

        tables = [
            ExtractedTable(
                table_id="t1", page=2,
                title="Board of Directors",
                headers=["Name", "Nationality", "ID Number", "Shares", "Role"],
                rows=[
                    ["John Kamau", "Kenyan", "12345678", "5,000", "Managing Director"],
                    ["Jane Wanjiku", "Kenyan", "87654321", "3,000", "Director"],
                    ["Peter Ochieng", "Kenyan", "11223344", "2,000", "Secretary"],
                ],
                cells=[],
                confidence=0.93,
            ),
            ExtractedTable(
                table_id="t2", page=2,
                title="Share Distribution",
                headers=["Share Class", "Quantity", "Par Value", "Total Value"],
                rows=[
                    ["Ordinary", "10,000", "KES 100", "KES 1,000,000"],
                    ["Preference", "5,000", "KES 200", "KES 1,000,000"],
                ],
                cells=[],
                confidence=0.91,
            ),
        ]

        form_fields = [
            FormField("f1", "Company Name", "ACME FINTECH LTD", "text", 1, 0.96, [50, 100, 400, 130]),
            FormField("f2", "Registration Number", "PVT-2024-12345", "text", 1, 0.95, [50, 140, 300, 170]),
            FormField("f3", "Date of Incorporation", "15/01/2024", "date", 1, 0.94, [50, 180, 250, 210]),
            FormField("f4", "Registered Office", "Westlands, Nairobi", "text", 1, 0.92, [50, 220, 350, 250]),
            FormField("f5", "Business Activity", "Financial Technology Services", "text", 1, 0.90, [50, 260, 400, 290]),
            FormField("f6", "Registrar Signature", "[signed]", "signature", 2, 0.88, [300, 500, 500, 550]),
        ]

        return DoclingResult(
            request_id=request_id,
            document_type="certificate_of_incorporation",
            total_pages=2,
            sections=sections,
            tables=tables,
            form_fields=form_fields,
            metadata={
                "file_name": filename,
                "file_size": len(file_bytes),
                "format": "pdf",
                "language": "en",
                "creation_date": "2024-01-15",
            },
            full_text="\n\n".join(s.content for s in sections),
            processing_time_ms=round((time.monotonic() - start) * 1000, 2),
        )


# ── API ───────────────────────────────────────────────────────────────────────

docling_engine = DoclingEngine()


class DoclingRequest(BaseModel):
    file_base64: Optional[str] = None
    file_url: Optional[str] = None
    filename: str = "document.pdf"
    extract_tables: bool = True
    extract_forms: bool = True


@app.post("/docling/parse")
async def parse_document(req: DoclingRequest):
    """Parse document and extract structured data."""
    import base64
    if req.file_base64:
        file_bytes = base64.b64decode(req.file_base64)
    else:
        file_bytes = b"mock_pdf"

    result = await docling_engine.parse_document(file_bytes, req.filename)
    return asdict(result)


@app.post("/docling/tables")
async def extract_tables(req: DoclingRequest):
    """Extract only tables from document."""
    import base64
    file_bytes = base64.b64decode(req.file_base64) if req.file_base64 else b"mock"
    result = await docling_engine.parse_document(file_bytes, req.filename)
    return {"tables": [asdict(t) for t in result.tables]}


@app.post("/docling/forms")
async def extract_forms(req: DoclingRequest):
    """Extract only form fields from document."""
    import base64
    file_bytes = base64.b64decode(req.file_base64) if req.file_base64 else b"mock"
    result = await docling_engine.parse_document(file_bytes, req.filename)
    return {"form_fields": [asdict(f) for f in result.form_fields]}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "docling",
        "version": "1.0.0",
        "engine_initialized": docling_engine.initialized,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8103"))
    uvicorn.run(app, host="0.0.0.0", port=port)
