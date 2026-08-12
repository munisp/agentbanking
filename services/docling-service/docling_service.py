#!/usr/bin/env python3
"""
POS-54agent Docling Service — Structured document parsing using IBM Docling
for extracting tables, forms, and hierarchical data from complex documents.

Specializes in:
  - Multi-page PDF parsing with layout analysis
  - Table extraction with row/column structure preservation
  - Form field detection and value extraction
  - Hierarchical document structure (sections, headers, paragraphs)
  - Business document templates (invoices, contracts, certificates)

NOTE: All parsed output comes from the real Docling engine. When Docling is
not installed or parsing fails, endpoints return HTTP 503/422 — the service
never returns fabricated document content.
"""

import asyncio
import base64
import io
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

app = FastAPI(title="POS-54agent Docling Service", version="1.0.0")


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
        self.init_error: Optional[str] = None

    async def initialize(self):
        """Initialize the real Docling converter. Fails closed — no mock mode."""
        if self.initialized:
            return
        try:
            from docling.document_converter import DocumentConverter
            self.converter = DocumentConverter()
            self.initialized = True
            self.init_error = None
            logger.info("Docling engine initialized")
        except Exception as e:
            self.converter = None
            self.initialized = False
            self.init_error = str(e)
            logger.error(f"Docling engine unavailable: {e}")

    async def parse_document(self, file_bytes: bytes, filename: str) -> DoclingResult:
        """Parse a document and extract structured data using Docling.

        Raises HTTP 503 when the engine is unavailable — never returns
        fabricated sections/tables/fields.
        """
        await self.initialize()
        if not self.initialized or self.converter is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Docling engine unavailable: "
                    f"{self.init_error or 'docling is not installed or failed to initialize'}. "
                    "Document parsing cannot be performed."
                ),
            )

        start = time.monotonic()
        request_id = str(uuid.uuid4())

        from docling.datamodel.base_models import DocumentStream

        source = DocumentStream(name=filename, stream=io.BytesIO(file_bytes))
        try:
            conversion = self.converter.convert(source)
        except Exception as e:
            logger.error(f"Docling conversion failed for {filename}: {e}")
            raise HTTPException(
                status_code=422,
                detail=f"Docling failed to parse document '{filename}': {e}",
            )

        doc = conversion.document

        # ── Sections from the real document text items ──
        sections: list[DocumentSection] = []
        sec_idx = 0
        for item in getattr(doc, "texts", []) or []:
            label = str(getattr(item, "label", "text")).lower()
            text = (getattr(item, "text", "") or "").strip()
            if not text:
                continue
            page = 1
            prov = getattr(item, "prov", None)
            if prov:
                try:
                    page = int(getattr(prov[0], "page_no", 1))
                except Exception:
                    page = 1
            if "title" in label:
                level = 0
            elif "section_header" in label or "header" in label:
                level = 1
            else:
                level = 2
            sec_idx += 1
            sections.append(DocumentSection(
                section_id=f"s{sec_idx}",
                level=level,
                title=text[:120] if level <= 1 else "",
                content=text,
                page_start=page,
                page_end=page,
            ))

        # ── Tables from the real document ──
        tables: list[ExtractedTable] = []
        for t_idx, table in enumerate(getattr(doc, "tables", []) or [], start=1):
            headers: list[str] = []
            rows: list[list[str]] = []
            page = 1
            try:
                df = table.export_to_dataframe(doc=doc)
                headers = [str(c) for c in df.columns]
                rows = [[str(v) for v in row] for row in df.values.tolist()]
            except Exception as e:
                logger.warning(f"Could not export table {t_idx} to dataframe: {e}")
            prov = getattr(table, "prov", None)
            if prov:
                try:
                    page = int(getattr(prov[0], "page_no", 1))
                except Exception:
                    page = 1
            tables.append(ExtractedTable(
                table_id=f"t{t_idx}",
                page=page,
                title=None,
                headers=headers,
                rows=rows,
                cells=[],
                confidence=None,  # Docling does not emit per-table confidence
            ))

        # Docling does not perform form-field value extraction; return an
        # empty list honestly rather than fabricated fields.
        form_fields: list[FormField] = []

        try:
            full_text = doc.export_to_markdown()
        except Exception:
            full_text = "\n\n".join(s.content for s in sections)

        total_pages = 1
        try:
            total_pages = len(getattr(doc, "pages", {}) or {}) or 1
        except Exception:
            total_pages = 1

        return DoclingResult(
            request_id=request_id,
            document_type=getattr(conversion, "input", None) and "document" or "document",
            total_pages=total_pages,
            sections=sections,
            tables=tables,
            form_fields=form_fields,
            metadata={
                "file_name": filename,
                "file_size": len(file_bytes),
                "parser": "ibm-docling",
                "form_fields_note": "Form field extraction is not supported by the Docling engine; list is empty by design.",
            },
            full_text=full_text,
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


def _resolve_file_bytes(req: DoclingRequest) -> bytes:
    """Resolve uploaded document bytes. Raises 400/502 — never substitutes mock bytes."""
    if req.file_base64:
        try:
            return base64.b64decode(req.file_base64)
        except Exception as e:
            raise HTTPException(400, f"Invalid base64 file data: {e}")
    if req.file_url:
        import urllib.request
        try:
            with urllib.request.urlopen(req.file_url, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            raise HTTPException(502, f"Failed to download file from URL: {e}")
    raise HTTPException(400, "Provide file_base64 or file_url")


@app.post("/docling/parse")
async def parse_document(req: DoclingRequest):
    """Parse document and extract structured data."""
    file_bytes = _resolve_file_bytes(req)
    result = await docling_engine.parse_document(file_bytes, req.filename)
    return asdict(result)


@app.post("/docling/tables")
async def extract_tables(req: DoclingRequest):
    """Extract only tables from document."""
    file_bytes = _resolve_file_bytes(req)
    result = await docling_engine.parse_document(file_bytes, req.filename)
    return {"tables": [asdict(t) for t in result.tables]}


@app.post("/docling/forms")
async def extract_forms(req: DoclingRequest):
    """Extract only form fields from document."""
    file_bytes = _resolve_file_bytes(req)
    result = await docling_engine.parse_document(file_bytes, req.filename)
    return {
        "form_fields": [asdict(f) for f in result.form_fields],
        "note": "Form field extraction is not supported by the Docling engine; list is empty by design.",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy" if docling_engine.initialized else "degraded",
        "service": "docling",
        "version": "1.0.0",
        "engine_initialized": docling_engine.initialized,
        "engine_error": docling_engine.init_error,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8103"))
    uvicorn.run(app, host="0.0.0.0", port=port)
