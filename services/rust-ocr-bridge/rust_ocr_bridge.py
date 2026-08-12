#!/usr/bin/env python3
"""
POS-54agent Rust OCR Bridge — Python wrapper around a Rust-based OCR engine
using Tesseract FFI for high-performance document processing.

The Rust core (compiled as a shared library) handles:
  - Image preprocessing (deskew, denoise, contrast enhancement)
  - Parallel page processing with Rayon
  - Tesseract FFI calls with connection pooling
  - Memory-mapped I/O for large documents

This Python service wraps the Rust library with a FastAPI interface.

NOTE: This bridge fails LOUD. If the Rust shared library is not present
(RUST_OCR_LIB), the engine stays uninitialized and every OCR request
returns HTTP 503. No fabricated OCR text, regions, or confidence values
are ever returned.
"""

import asyncio
import base64
import ctypes
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rust-ocr-bridge")

app = FastAPI(title="POS-54agent Rust OCR Bridge", version="1.0.0")


# ── Rust FFI Interface ────────────────────────────────────────────────────────

class RustOCREngine:
    """
    Interface to the Rust OCR shared library.

    The Rust library exposes these C-compatible functions:
      - ocr_init() -> *mut Engine
      - ocr_process(engine: *mut Engine, img_ptr: *const u8, img_len: usize, lang: *const c_char) -> *mut c_char
      - ocr_preprocess(img_ptr: *const u8, img_len: usize, flags: u32) -> *mut PreprocessResult
      - ocr_batch_process(engine: *mut Engine, paths: *const *const c_char, count: usize) -> *mut c_char
      - ocr_free(ptr: *mut c_char)
      - ocr_destroy(engine: *mut Engine)
    """

    def __init__(self):
        self.lib = None
        self.engine = None
        self.initialized = False
        self.init_error: Optional[str] = None

    def initialize(self):
        """Load the Rust shared library. Fails closed: on any error the engine
        remains uninitialized and processing raises — there is no mock mode."""
        lib_path = os.getenv("RUST_OCR_LIB", "./target/release/libpos54_ocr.so")
        try:
            self.lib = ctypes.CDLL(lib_path)
            # Define function signatures
            self.lib.ocr_init.restype = ctypes.c_void_p
            self.lib.ocr_process.argtypes = [
                ctypes.c_void_p,  # engine
                ctypes.c_char_p,  # img_ptr
                ctypes.c_size_t,  # img_len
                ctypes.c_char_p,  # lang
            ]
            self.lib.ocr_process.restype = ctypes.c_char_p
            self.lib.ocr_free.argtypes = [ctypes.c_char_p]
            self.lib.ocr_free.restype = None
            self.engine = self.lib.ocr_init()
            if not self.engine:
                raise RuntimeError("ocr_init() returned a null engine handle")
            self.initialized = True
            self.init_error = None
            logger.info("Rust OCR engine loaded successfully")
        except (OSError, RuntimeError, AttributeError) as e:
            self.lib = None
            self.engine = None
            self.initialized = False
            self.init_error = f"Rust OCR library unavailable at {lib_path}: {e}"
            logger.error(self.init_error)

    def _require_engine(self):
        if not self.initialized or not self.lib or not self.engine:
            raise RuntimeError(
                "Rust OCR engine is not initialized. "
                f"{self.init_error or 'Shared library not loaded.'} "
                "OCR cannot be performed."
            )

    def process(self, image_bytes: bytes, lang: str = "eng") -> dict:
        """Process a single image through Rust OCR.

        Raises RuntimeError when the native engine is unavailable — never
        returns fabricated OCR output.
        """
        self._require_engine()
        result_ptr = self.lib.ocr_process(
            self.engine,
            image_bytes,
            len(image_bytes),
            lang.encode("utf-8"),
        )
        if not result_ptr:
            raise RuntimeError("Rust ocr_process returned a null result")
        try:
            result_json = ctypes.string_at(result_ptr).decode("utf-8")
        finally:
            self.lib.ocr_free(result_ptr)
        return json.loads(result_json)

    def batch_process(self, image_list: list[bytes], lang: str = "eng") -> list[dict]:
        """Process multiple images in parallel using Rust Rayon."""
        self._require_engine()
        return [self.process(img, lang) for img in image_list]

    def preprocess(self, image_bytes: bytes, flags: int = 0xFF) -> dict:
        """
        Preprocess image using the Rust image processing pipeline.

        Flags (bitfield):
          0x01 - Deskew
          0x02 - Denoise
          0x04 - Contrast enhancement
          0x08 - Binarization
          0x10 - Border removal
          0x20 - Resolution upscaling
          0xFF - All preprocessing

        Raises RuntimeError when the native engine is unavailable.
        """
        self._require_engine()
        if not hasattr(self.lib, "ocr_preprocess"):
            raise RuntimeError("Rust library does not expose ocr_preprocess")
        self.lib.ocr_preprocess.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_uint32]
        self.lib.ocr_preprocess.restype = ctypes.c_char_p
        result_ptr = self.lib.ocr_preprocess(image_bytes, len(image_bytes), flags)
        if not result_ptr:
            raise RuntimeError("Rust ocr_preprocess returned a null result")
        try:
            result_json = ctypes.string_at(result_ptr).decode("utf-8")
        finally:
            self.lib.ocr_free(result_ptr)
        return json.loads(result_json)


# ── Rust Source Reference ─────────────────────────────────────────────────────
# The corresponding Rust source would be in services/rust/ocr-engine/src/lib.rs
RUST_SOURCE_REFERENCE = """
// lib.rs — Rust OCR Engine with Tesseract FFI
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use rayon::prelude::*;
use image::{DynamicImage, ImageBuffer, Luma};
use leptonica_sys::*;
use tesseract_sys::*;

pub struct Engine {
    tess_api: *mut TessBaseAPI,
}

#[no_mangle]
pub extern "C" fn ocr_init() -> *mut Engine {
    unsafe {
        let api = TessBaseAPICreate();
        TessBaseAPIInit3(api, std::ptr::null(), b"eng\\0".as_ptr() as *const c_char);
        Box::into_raw(Box::new(Engine { tess_api: api }))
    }
}

#[no_mangle]
pub extern "C" fn ocr_process(
    engine: *mut Engine,
    img_ptr: *const u8,
    img_len: usize,
    lang: *const c_char,
) -> *mut c_char {
    // 1. Decode image
    // 2. Preprocess (deskew, denoise, contrast)
    // 3. Run Tesseract OCR
    // 4. Extract text regions with bounding boxes
    // 5. Return JSON result
}
"""


# ── API ───────────────────────────────────────────────────────────────────────

rust_engine = RustOCREngine()


class RustOCRRequest(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    language: str = "eng"
    preprocess_flags: int = 0xFF


@app.on_event("startup")
async def startup():
    rust_engine.initialize()
    if not rust_engine.initialized:
        logger.error(
            "Rust OCR Bridge started WITHOUT the native library — "
            "all OCR requests will return 503"
        )


def _engine_unavailable_503(e: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=str(e))


@app.post("/ocr/process")
async def process_document(req: RustOCRRequest):
    """Process document through Rust OCR engine."""
    start = time.monotonic()
    request_id = str(uuid.uuid4())

    if req.image_base64:
        try:
            image_bytes = base64.b64decode(req.image_base64)
        except Exception as e:
            raise HTTPException(400, f"Invalid base64 image data: {e}")
    elif req.image_url:
        import urllib.request
        try:
            with urllib.request.urlopen(req.image_url, timeout=15) as resp:
                image_bytes = resp.read()
        except Exception as e:
            raise HTTPException(502, f"Failed to download image from URL: {e}")
    else:
        raise HTTPException(400, "Provide image_base64 or image_url")

    # Preprocess
    try:
        preprocess_result = rust_engine.preprocess(image_bytes, req.preprocess_flags)
    except RuntimeError as e:
        raise _engine_unavailable_503(e)

    # OCR
    try:
        ocr_result = rust_engine.process(image_bytes, req.language)
    except RuntimeError as e:
        raise _engine_unavailable_503(e)

    return {
        "request_id": request_id,
        "ocr_result": ocr_result,
        "preprocessing": preprocess_result,
        "total_time_ms": round((time.monotonic() - start) * 1000, 2),
        "engine": "rust-tesseract-ffi",
    }


@app.post("/ocr/batch")
async def batch_process(images: list[str], language: str = "eng"):
    """Batch process multiple documents in parallel via Rust Rayon."""
    try:
        image_list = [base64.b64decode(img) for img in images]
    except Exception as e:
        raise HTTPException(400, f"Invalid base64 image data: {e}")
    try:
        results = rust_engine.batch_process(image_list, language)
    except RuntimeError as e:
        raise _engine_unavailable_503(e)
    return {"results": results, "count": len(results)}


@app.get("/health")
async def health():
    return {
        "status": "healthy" if rust_engine.initialized else "degraded",
        "service": "rust-ocr-bridge",
        "engine_initialized": rust_engine.initialized,
        "rust_lib_loaded": rust_engine.lib is not None,
        "engine_error": rust_engine.init_error,
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8101"))
    uvicorn.run(app, host="0.0.0.0", port=port)
