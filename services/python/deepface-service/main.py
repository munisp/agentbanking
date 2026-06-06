#!/usr/bin/env python3
"""
POS-54Link DeepFace Service — Production-grade face recognition and facial
attribute analysis powered by serengil/deepface.

Capabilities:
  - Face verification (1:1) with 10 model backends:
    VGG-Face, FaceNet, FaceNet512, OpenFace, DeepFace, DeepID,
    ArcFace, Dlib, SFace, GhostFaceNet
  - Face recognition (1:N) against enrolled gallery
  - Facial attribute analysis: age, gender, emotion, race
  - Multi-model ensemble verification (consensus across models)
  - Face detection with 9 detector backends:
    opencv, ssd, dlib, mtcnn, fastmtcnn, retinaface,
    mediapipe, yolov8, yunet, centerface
  - Face anti-spoofing detection
  - Embedding extraction for external storage/matching
  - Gallery management (enroll, search, delete)

Middleware integration:
  - Redis: face embedding cache, gallery storage
  - Kafka: verification event streaming
  - PostgreSQL: audit trail persistence (via upstream orchestrator)

Port: 8133
"""

import base64
import hashlib
import io
import json
import logging
import os
import tempfile
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


# ── Conditional imports ──────────────────────────────────────────────────────

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from confluent_kafka import Producer as KafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("deepface-service")

# ── Configuration ────────────────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/5")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
GALLERY_DIR = os.getenv("DEEPFACE_GALLERY_DIR", "/data/deepface/gallery")
DEFAULT_MODEL = os.getenv("DEEPFACE_DEFAULT_MODEL", "ArcFace")
DEFAULT_DETECTOR = os.getenv("DEEPFACE_DEFAULT_DETECTOR", "retinaface")
DEFAULT_DISTANCE_METRIC = os.getenv("DEEPFACE_DISTANCE_METRIC", "cosine")
PORT = int(os.getenv("PORT", "8133"))

SUPPORTED_MODELS = [
    "VGG-Face", "Facenet", "Facenet512", "OpenFace", "DeepFace",
    "DeepID", "ArcFace", "Dlib", "SFace", "GhostFaceNet",
]
SUPPORTED_DETECTORS = [
    "opencv", "ssd", "dlib", "mtcnn", "fastmtcnn",
    "retinaface", "mediapipe", "yolov8", "yunet", "centerface",
]
SUPPORTED_METRICS = ["cosine", "euclidean", "euclidean_l2"]

# ── Enums ────────────────────────────────────────────────────────────────────

class VerificationResult(str, Enum):
    MATCH = "match"
    NO_MATCH = "no_match"
    ERROR = "error"


class EmotionLabel(str, Enum):
    ANGRY = "angry"
    DISGUST = "disgust"
    FEAR = "fear"
    HAPPY = "happy"
    SAD = "sad"
    SURPRISE = "surprise"
    NEUTRAL = "neutral"


# ── Request / Response Models ────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    image1_base64: str = Field(..., min_length=100, description="Base64-encoded first image")
    image2_base64: str = Field(..., min_length=100, description="Base64-encoded second image")
    model_name: str = Field(default=DEFAULT_MODEL, description="Recognition model")
    detector_backend: str = Field(default=DEFAULT_DETECTOR, description="Face detector")
    distance_metric: str = Field(default=DEFAULT_DISTANCE_METRIC, description="Distance metric")
    enforce_detection: bool = Field(default=True, description="Raise error if no face found")
    align: bool = Field(default=True, description="Align faces before comparison")
    anti_spoofing: bool = Field(default=False, description="Run anti-spoofing check")


class EnsembleVerifyRequest(BaseModel):
    image1_base64: str = Field(..., min_length=100)
    image2_base64: str = Field(..., min_length=100)
    models: List[str] = Field(
        default=["ArcFace", "Facenet512", "VGG-Face"],
        description="Models to use for ensemble verification",
    )
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Consensus threshold (fraction of models that must agree)")
    anti_spoofing: bool = Field(default=False)


class AnalyzeRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    actions: List[str] = Field(
        default=["age", "gender", "emotion", "race"],
        description="Analysis actions to perform",
    )
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    enforce_detection: bool = Field(default=True)
    align: bool = Field(default=True)
    anti_spoofing: bool = Field(default=False)


class DetectRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    enforce_detection: bool = Field(default=True)
    align: bool = Field(default=True)
    anti_spoofing: bool = Field(default=False)


class EmbeddingRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    model_name: str = Field(default=DEFAULT_MODEL)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    enforce_detection: bool = Field(default=True)
    align: bool = Field(default=True)


class EnrollRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    identity: str = Field(..., min_length=1, description="Unique identity label (e.g. user ID)")
    model_name: str = Field(default=DEFAULT_MODEL)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Extra metadata to store")


class SearchRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    model_name: str = Field(default=DEFAULT_MODEL)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    distance_metric: str = Field(default=DEFAULT_DISTANCE_METRIC)
    top_k: int = Field(default=5, ge=1, le=50)
    threshold: Optional[float] = Field(default=None, description="Max distance threshold")


class AntiSpoofRequest(BaseModel):
    image_base64: str = Field(..., min_length=100)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)


class CompareMultipleRequest(BaseModel):
    reference_base64: str = Field(..., min_length=100, description="Reference face image")
    candidate_base64_list: List[str] = Field(..., min_length=1, description="Candidate face images")
    model_name: str = Field(default=DEFAULT_MODEL)
    detector_backend: str = Field(default=DEFAULT_DETECTOR)
    distance_metric: str = Field(default=DEFAULT_DISTANCE_METRIC)


# ── Middleware Clients ───────────────────────────────────────────────────────

class RedisClient:
    """Redis client for embedding cache and gallery metadata."""

    def __init__(self):
        self.client = None
        if REDIS_AVAILABLE:
            try:
                self.client = redis.from_url(REDIS_URL, decode_responses=False)
                self.client.ping()
                logger.info(f"Redis connected: {REDIS_URL}")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self.client = None

    def cache_embedding(self, image_hash: str, model: str, embedding: list) -> None:
        if not self.client:
            return
        try:
            key = f"deepface:emb:{model}:{image_hash}"
            self.client.setex(key, 3600, json.dumps(embedding))
        except Exception:
            pass

    def get_cached_embedding(self, image_hash: str, model: str) -> Optional[list]:
        if not self.client:
            return None
        try:
            key = f"deepface:emb:{model}:{image_hash}"
            data = self.client.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    def store_gallery_entry(self, identity: str, model: str, embedding: list, metadata: dict) -> None:
        if not self.client:
            return
        try:
            key = f"deepface:gallery:{model}:{identity}"
            self.client.set(key, json.dumps({
                "embedding": embedding,
                "metadata": metadata,
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception:
            pass

    def get_gallery_entries(self, model: str) -> Dict[str, dict]:
        if not self.client:
            return {}
        try:
            pattern = f"deepface:gallery:{model}:*"
            entries = {}
            for key in self.client.scan_iter(match=pattern, count=100):
                identity = key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
                data = self.client.get(key)
                if data:
                    entries[identity] = json.loads(data)
            return entries
        except Exception:
            return {}

    def delete_gallery_entry(self, identity: str, model: str) -> bool:
        if not self.client:
            return False
        try:
            key = f"deepface:gallery:{model}:{identity}"
            return bool(self.client.delete(key))
        except Exception:
            return False


class KafkaClient:
    """Kafka producer for verification event streaming."""

    def __init__(self):
        self.producer = None
        if KAFKA_AVAILABLE:
            try:
                self.producer = KafkaProducer({
                    "bootstrap.servers": KAFKA_BROKERS,
                    "client.id": "deepface-service",
                    "acks": "all",
                })
                logger.info(f"Kafka producer connected: {KAFKA_BROKERS}")
            except Exception as e:
                logger.warning(f"Kafka connection failed: {e}")

    def publish_event(self, topic: str, event: dict) -> None:
        if not self.producer:
            return
        try:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()
            event["service"] = "deepface-service"
            self.producer.produce(
                topic,
                key=event.get("event_id", str(uuid.uuid4())).encode(),
                value=json.dumps(event, default=str).encode(),
            )
            self.producer.flush(timeout=5)
        except Exception as e:
            logger.warning(f"Kafka publish failed: {e}")


# ── DeepFace Engine ──────────────────────────────────────────────────────────

class DeepFaceEngine:
    """Core engine wrapping serengil/deepface with caching and gallery management."""

    def __init__(self):
        self.redis = RedisClient()
        self.kafka = KafkaClient()
        self.gallery_dir = GALLERY_DIR
        self.stats = {
            "verifications": 0,
            "analyses": 0,
            "detections": 0,
            "enrollments": 0,
            "searches": 0,
            "anti_spoof_checks": 0,
            "errors": 0,
        }

        os.makedirs(self.gallery_dir, exist_ok=True)
        logger.info(f"DeepFace engine initialized. Gallery: {self.gallery_dir}")

    @staticmethod
    def _decode_image(base64_str: str) -> np.ndarray:
        """Decode base64 image to numpy array (BGR)."""
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image from base64")
        return img

    @staticmethod
    def _image_hash(base64_str: str) -> str:
        """Compute SHA-256 hash of image data for caching."""
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        return hashlib.sha256(base64_str.encode()).hexdigest()[:16]

    @staticmethod
    def _save_temp_image(img: np.ndarray) -> str:
        """Save image to a temporary file and return path."""
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        cv2.imwrite(path, img)
        return path

    def verify(
        self,
        image1_b64: str,
        image2_b64: str,
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR,
        distance_metric: str = DEFAULT_DISTANCE_METRIC,
        enforce_detection: bool = True,
        align: bool = True,
        anti_spoofing: bool = False,
    ) -> dict:
        """1:1 face verification between two images."""
        start = time.monotonic()
        event_id = str(uuid.uuid4())

        img1 = self._decode_image(image1_b64)
        img2 = self._decode_image(image2_b64)
        path1 = self._save_temp_image(img1)
        path2 = self._save_temp_image(img2)

        try:
            result = DeepFace.verify(
                img1_path=path1,
                img2_path=path2,
                model_name=model_name,
                detector_backend=detector_backend,
                distance_metric=distance_metric,
                enforce_detection=enforce_detection,
                align=align,
                anti_spoofing=anti_spoofing,
            )

            processing_ms = round((time.monotonic() - start) * 1000, 2)
            self.stats["verifications"] += 1

            output = {
                "verified": result.get("verified", False),
                "distance": round(result.get("distance", 0), 6),
                "threshold": round(result.get("threshold", 0), 6),
                "model": result.get("model", model_name),
                "detector_backend": result.get("detector_backend", detector_backend),
                "similarity_metric": result.get("similarity_metric", distance_metric),
                "facial_areas": result.get("facial_areas", {}),
                "processing_time_ms": processing_ms,
                "event_id": event_id,
            }

            self.kafka.publish_event("deepface.verification", {
                "event_id": event_id,
                "event_type": "face_verification",
                "verified": output["verified"],
                "distance": output["distance"],
                "model": model_name,
                "processing_time_ms": processing_ms,
            })

            return output

        finally:
            for p in [path1, path2]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def ensemble_verify(
        self,
        image1_b64: str,
        image2_b64: str,
        models: List[str],
        detector_backend: str = DEFAULT_DETECTOR,
        consensus_threshold: float = 0.6,
        anti_spoofing: bool = False,
    ) -> dict:
        """Multi-model ensemble verification for higher confidence."""
        start = time.monotonic()
        event_id = str(uuid.uuid4())

        img1 = self._decode_image(image1_b64)
        img2 = self._decode_image(image2_b64)
        path1 = self._save_temp_image(img1)
        path2 = self._save_temp_image(img2)

        results_per_model = []
        verified_count = 0

        try:
            for model in models:
                if model not in SUPPORTED_MODELS:
                    results_per_model.append({
                        "model": model,
                        "error": f"Unsupported model: {model}",
                        "verified": False,
                    })
                    continue

                try:
                    result = DeepFace.verify(
                        img1_path=path1,
                        img2_path=path2,
                        model_name=model,
                        detector_backend=detector_backend,
                        enforce_detection=True,
                        anti_spoofing=anti_spoofing,
                    )
                    is_verified = result.get("verified", False)
                    if is_verified:
                        verified_count += 1

                    results_per_model.append({
                        "model": model,
                        "verified": is_verified,
                        "distance": round(result.get("distance", 0), 6),
                        "threshold": round(result.get("threshold", 0), 6),
                    })
                except Exception as e:
                    results_per_model.append({
                        "model": model,
                        "verified": False,
                        "error": str(e),
                    })

            valid_models = [r for r in results_per_model if "error" not in r]
            total_valid = len(valid_models)
            consensus_ratio = verified_count / total_valid if total_valid > 0 else 0
            ensemble_verified = consensus_ratio >= consensus_threshold

            processing_ms = round((time.monotonic() - start) * 1000, 2)
            self.stats["verifications"] += 1

            output = {
                "ensemble_verified": ensemble_verified,
                "consensus_ratio": round(consensus_ratio, 4),
                "consensus_threshold": consensus_threshold,
                "models_agreed": verified_count,
                "models_total": total_valid,
                "results_per_model": results_per_model,
                "processing_time_ms": processing_ms,
                "event_id": event_id,
            }

            self.kafka.publish_event("deepface.ensemble_verification", {
                "event_id": event_id,
                "event_type": "ensemble_verification",
                "ensemble_verified": ensemble_verified,
                "consensus_ratio": consensus_ratio,
                "models_used": [r["model"] for r in results_per_model],
                "processing_time_ms": processing_ms,
            })

            return output

        finally:
            for p in [path1, path2]:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def analyze(
        self,
        image_b64: str,
        actions: List[str] = None,
        detector_backend: str = DEFAULT_DETECTOR,
        enforce_detection: bool = True,
        align: bool = True,
        anti_spoofing: bool = False,
    ) -> dict:
        """Analyze facial attributes: age, gender, emotion, race."""
        start = time.monotonic()
        if actions is None:
            actions = ["age", "gender", "emotion", "race"]

        img = self._decode_image(image_b64)
        path = self._save_temp_image(img)

        try:
            results = DeepFace.analyze(
                img_path=path,
                actions=actions,
                detector_backend=detector_backend,
                enforce_detection=enforce_detection,
                align=align,
                anti_spoofing=anti_spoofing,
            )

            processing_ms = round((time.monotonic() - start) * 1000, 2)
            self.stats["analyses"] += 1

            faces = []
            result_list = results if isinstance(results, list) else [results]

            for face_result in result_list:
                face_data = {
                    "region": face_result.get("region", {}),
                    "face_confidence": face_result.get("face_confidence", 0),
                }

                if "age" in actions:
                    face_data["age"] = face_result.get("age")

                if "gender" in actions:
                    face_data["dominant_gender"] = face_result.get("dominant_gender")
                    face_data["gender"] = face_result.get("gender", {})

                if "emotion" in actions:
                    face_data["dominant_emotion"] = face_result.get("dominant_emotion")
                    face_data["emotion"] = face_result.get("emotion", {})

                if "race" in actions:
                    face_data["dominant_race"] = face_result.get("dominant_race")
                    face_data["race"] = face_result.get("race", {})

                faces.append(face_data)

            self.kafka.publish_event("deepface.analysis", {
                "event_type": "facial_analysis",
                "faces_detected": len(faces),
                "actions": actions,
                "processing_time_ms": processing_ms,
            })

            return {
                "faces": faces,
                "faces_count": len(faces),
                "actions_performed": actions,
                "processing_time_ms": processing_ms,
            }

        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def detect_faces(
        self,
        image_b64: str,
        detector_backend: str = DEFAULT_DETECTOR,
        enforce_detection: bool = True,
        align: bool = True,
        anti_spoofing: bool = False,
    ) -> dict:
        """Detect faces in an image with bounding boxes and confidence."""
        start = time.monotonic()

        img = self._decode_image(image_b64)
        path = self._save_temp_image(img)

        try:
            results = DeepFace.extract_faces(
                img_path=path,
                detector_backend=detector_backend,
                enforce_detection=enforce_detection,
                align=align,
                anti_spoofing=anti_spoofing,
            )

            processing_ms = round((time.monotonic() - start) * 1000, 2)
            self.stats["detections"] += 1

            faces = []
            for face in results:
                face_info = {
                    "facial_area": face.get("facial_area", {}),
                    "confidence": round(face.get("confidence", 0), 4),
                }
                if "is_real" in face:
                    face_info["is_real"] = face["is_real"]
                    face_info["antispoof_score"] = round(face.get("antispoof_score", 0), 4)

                faces.append(face_info)

            return {
                "faces": faces,
                "faces_count": len(faces),
                "detector_backend": detector_backend,
                "processing_time_ms": processing_ms,
            }

        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def extract_embedding(
        self,
        image_b64: str,
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR,
        enforce_detection: bool = True,
        align: bool = True,
    ) -> dict:
        """Extract face embedding vector for external use."""
        start = time.monotonic()
        img_hash = self._image_hash(image_b64)

        cached = self.redis.get_cached_embedding(img_hash, model_name)
        if cached is not None:
            return {
                "embedding": cached,
                "embedding_dim": len(cached),
                "model": model_name,
                "cached": True,
                "processing_time_ms": round((time.monotonic() - start) * 1000, 2),
            }

        img = self._decode_image(image_b64)
        path = self._save_temp_image(img)

        try:
            results = DeepFace.represent(
                img_path=path,
                model_name=model_name,
                detector_backend=detector_backend,
                enforce_detection=enforce_detection,
                align=align,
            )

            processing_ms = round((time.monotonic() - start) * 1000, 2)

            if not results:
                raise ValueError("No face detected for embedding extraction")

            embedding = results[0].get("embedding", [])
            facial_area = results[0].get("facial_area", {})

            self.redis.cache_embedding(img_hash, model_name, embedding)

            return {
                "embedding": embedding,
                "embedding_dim": len(embedding),
                "model": model_name,
                "facial_area": facial_area,
                "cached": False,
                "processing_time_ms": processing_ms,
            }

        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def enroll_face(
        self,
        image_b64: str,
        identity: str,
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Enroll a face into the gallery for 1:N recognition."""
        start = time.monotonic()

        emb_result = self.extract_embedding(
            image_b64, model_name, detector_backend,
        )
        embedding = emb_result["embedding"]

        identity_dir = os.path.join(self.gallery_dir, identity)
        os.makedirs(identity_dir, exist_ok=True)

        img = self._decode_image(image_b64)
        img_filename = f"{uuid.uuid4().hex[:12]}.jpg"
        img_path = os.path.join(identity_dir, img_filename)
        cv2.imwrite(img_path, img)

        entry_metadata = {
            "identity": identity,
            "model": model_name,
            "embedding_dim": len(embedding),
            "image_file": img_filename,
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {}),
        }

        self.redis.store_gallery_entry(identity, model_name, embedding, entry_metadata)

        processing_ms = round((time.monotonic() - start) * 1000, 2)
        self.stats["enrollments"] += 1

        self.kafka.publish_event("deepface.enrollment", {
            "event_type": "face_enrollment",
            "identity": identity,
            "model": model_name,
            "processing_time_ms": processing_ms,
        })

        return {
            "enrolled": True,
            "identity": identity,
            "model": model_name,
            "embedding_dim": len(embedding),
            "image_stored": img_path,
            "processing_time_ms": processing_ms,
        }

    def search_gallery(
        self,
        image_b64: str,
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR,
        distance_metric: str = DEFAULT_DISTANCE_METRIC,
        top_k: int = 5,
        threshold: Optional[float] = None,
    ) -> dict:
        """Search the gallery for matching faces (1:N recognition)."""
        start = time.monotonic()

        probe_result = self.extract_embedding(
            image_b64, model_name, detector_backend,
        )
        probe_embedding = np.array(probe_result["embedding"])

        gallery_entries = self.redis.get_gallery_entries(model_name)

        if not gallery_entries:
            return {
                "matches": [],
                "gallery_size": 0,
                "model": model_name,
                "processing_time_ms": round((time.monotonic() - start) * 1000, 2),
            }

        matches = []
        for identity, entry in gallery_entries.items():
            gallery_emb = np.array(entry.get("embedding", []))
            if len(gallery_emb) == 0:
                continue

            if distance_metric == "cosine":
                dot = np.dot(probe_embedding, gallery_emb)
                norm = np.linalg.norm(probe_embedding) * np.linalg.norm(gallery_emb)
                distance = 1 - (dot / (norm + 1e-10))
            elif distance_metric == "euclidean":
                distance = float(np.linalg.norm(probe_embedding - gallery_emb))
            else:
                probe_norm = probe_embedding / (np.linalg.norm(probe_embedding) + 1e-10)
                gallery_norm = gallery_emb / (np.linalg.norm(gallery_emb) + 1e-10)
                distance = float(np.linalg.norm(probe_norm - gallery_norm))

            if threshold is not None and distance > threshold:
                continue

            matches.append({
                "identity": identity,
                "distance": round(float(distance), 6),
                "metadata": entry.get("metadata", {}),
            })

        matches.sort(key=lambda m: m["distance"])
        matches = matches[:top_k]

        processing_ms = round((time.monotonic() - start) * 1000, 2)
        self.stats["searches"] += 1

        return {
            "matches": matches,
            "gallery_size": len(gallery_entries),
            "model": model_name,
            "distance_metric": distance_metric,
            "processing_time_ms": processing_ms,
        }

    def anti_spoof_check(
        self,
        image_b64: str,
        detector_backend: str = DEFAULT_DETECTOR,
    ) -> dict:
        """Run DeepFace anti-spoofing detection."""
        start = time.monotonic()

        img = self._decode_image(image_b64)
        path = self._save_temp_image(img)

        try:
            results = DeepFace.extract_faces(
                img_path=path,
                detector_backend=detector_backend,
                enforce_detection=True,
                anti_spoofing=True,
            )

            processing_ms = round((time.monotonic() - start) * 1000, 2)
            self.stats["anti_spoof_checks"] += 1

            faces = []
            overall_real = True
            for face in results:
                is_real = face.get("is_real", True)
                score = face.get("antispoof_score", 0)
                if not is_real:
                    overall_real = False
                faces.append({
                    "facial_area": face.get("facial_area", {}),
                    "is_real": is_real,
                    "antispoof_score": round(score, 4),
                    "confidence": round(face.get("confidence", 0), 4),
                })

            self.kafka.publish_event("deepface.anti_spoof", {
                "event_type": "anti_spoof_check",
                "is_real": overall_real,
                "faces_checked": len(faces),
                "processing_time_ms": processing_ms,
            })

            return {
                "is_real": overall_real,
                "faces": faces,
                "faces_count": len(faces),
                "processing_time_ms": processing_ms,
            }

        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def compare_multiple(
        self,
        reference_b64: str,
        candidate_b64_list: List[str],
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR,
        distance_metric: str = DEFAULT_DISTANCE_METRIC,
    ) -> dict:
        """Compare one reference face against multiple candidates."""
        start = time.monotonic()

        ref_img = self._decode_image(reference_b64)
        ref_path = self._save_temp_image(ref_img)

        comparisons = []
        try:
            for i, cand_b64 in enumerate(candidate_b64_list):
                cand_img = self._decode_image(cand_b64)
                cand_path = self._save_temp_image(cand_img)

                try:
                    result = DeepFace.verify(
                        img1_path=ref_path,
                        img2_path=cand_path,
                        model_name=model_name,
                        detector_backend=detector_backend,
                        distance_metric=distance_metric,
                        enforce_detection=True,
                    )

                    comparisons.append({
                        "candidate_index": i,
                        "verified": result.get("verified", False),
                        "distance": round(result.get("distance", 0), 6),
                        "threshold": round(result.get("threshold", 0), 6),
                    })
                except Exception as e:
                    comparisons.append({
                        "candidate_index": i,
                        "verified": False,
                        "error": str(e),
                    })
                finally:
                    try:
                        os.unlink(cand_path)
                    except OSError:
                        pass

            best_match = None
            for c in comparisons:
                if c.get("verified") and (best_match is None or c["distance"] < best_match["distance"]):
                    best_match = c

            processing_ms = round((time.monotonic() - start) * 1000, 2)

            return {
                "comparisons": comparisons,
                "best_match": best_match,
                "total_candidates": len(candidate_b64_list),
                "matches_found": sum(1 for c in comparisons if c.get("verified")),
                "model": model_name,
                "processing_time_ms": processing_ms,
            }

        finally:
            try:
                os.unlink(ref_path)
            except OSError:
                pass


# ── App Lifecycle ────────────────────────────────────────────────────────────

engine = DeepFaceEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DeepFace service starting up...")
    yield
    logger.info("DeepFace service shutting down...")


app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/deepface_service")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="POS-54Link DeepFace Service",
    version="1.0.0",
    description="Face recognition and facial attribute analysis powered by DeepFace",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "deepface-service",
        "version": "1.0.0",
        "deepface_available": DEEPFACE_AVAILABLE,
        "supported_models": SUPPORTED_MODELS,
        "supported_detectors": SUPPORTED_DETECTORS,
        "default_model": DEFAULT_MODEL,
        "default_detector": DEFAULT_DETECTOR,
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "deepface-service",
        "deepface_available": DEEPFACE_AVAILABLE,
        "redis_connected": engine.redis.client is not None,
        "kafka_connected": engine.kafka.producer is not None,
        "stats": engine.stats,
        "capabilities": {
            "verification": True,
            "ensemble_verification": True,
            "facial_analysis": True,
            "face_detection": True,
            "embedding_extraction": True,
            "gallery_management": True,
            "anti_spoofing": True,
            "compare_multiple": True,
        },
    }


@app.post("/verify")
async def verify_faces(req: VerifyRequest):
    """1:1 face verification between two images."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    if req.model_name not in SUPPORTED_MODELS:
        raise HTTPException(400, f"Unsupported model: {req.model_name}. Supported: {SUPPORTED_MODELS}")

    try:
        return engine.verify(
            image1_b64=req.image1_base64,
            image2_b64=req.image2_base64,
            model_name=req.model_name,
            detector_backend=req.detector_backend,
            distance_metric=req.distance_metric,
            enforce_detection=req.enforce_detection,
            align=req.align,
            anti_spoofing=req.anti_spoofing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Verification failed: {e}")
        raise HTTPException(500, f"Verification failed: {str(e)}")


@app.post("/verify/ensemble")
async def ensemble_verify_faces(req: EnsembleVerifyRequest):
    """Multi-model ensemble verification for higher confidence."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    try:
        return engine.ensemble_verify(
            image1_b64=req.image1_base64,
            image2_b64=req.image2_base64,
            models=req.models,
            detector_backend=req.detector_backend,
            consensus_threshold=req.threshold,
            anti_spoofing=req.anti_spoofing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Ensemble verification failed: {e}")
        raise HTTPException(500, f"Ensemble verification failed: {str(e)}")


@app.post("/analyze")
async def analyze_face(req: AnalyzeRequest):
    """Analyze facial attributes: age, gender, emotion, race."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    valid_actions = {"age", "gender", "emotion", "race"}
    invalid = set(req.actions) - valid_actions
    if invalid:
        raise HTTPException(400, f"Invalid actions: {invalid}. Valid: {valid_actions}")

    try:
        return engine.analyze(
            image_b64=req.image_base64,
            actions=req.actions,
            detector_backend=req.detector_backend,
            enforce_detection=req.enforce_detection,
            align=req.align,
            anti_spoofing=req.anti_spoofing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@app.post("/detect")
async def detect_faces(req: DetectRequest):
    """Detect faces in an image with bounding boxes and confidence scores."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    try:
        return engine.detect_faces(
            image_b64=req.image_base64,
            detector_backend=req.detector_backend,
            enforce_detection=req.enforce_detection,
            align=req.align,
            anti_spoofing=req.anti_spoofing,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Detection failed: {e}")
        raise HTTPException(500, f"Detection failed: {str(e)}")


@app.post("/represent")
async def extract_embedding(req: EmbeddingRequest):
    """Extract face embedding vector for external use."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    if req.model_name not in SUPPORTED_MODELS:
        raise HTTPException(400, f"Unsupported model: {req.model_name}")

    try:
        return engine.extract_embedding(
            image_b64=req.image_base64,
            model_name=req.model_name,
            detector_backend=req.detector_backend,
            enforce_detection=req.enforce_detection,
            align=req.align,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Embedding extraction failed: {e}")
        raise HTTPException(500, f"Embedding extraction failed: {str(e)}")


@app.post("/gallery/enroll")
async def enroll_face(req: EnrollRequest):
    """Enroll a face into the gallery for 1:N recognition."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    try:
        return engine.enroll_face(
            image_b64=req.image_base64,
            identity=req.identity,
            model_name=req.model_name,
            detector_backend=req.detector_backend,
            metadata=req.metadata,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Enrollment failed: {e}")
        raise HTTPException(500, f"Enrollment failed: {str(e)}")


@app.post("/gallery/search")
async def search_gallery(req: SearchRequest):
    """Search the gallery for matching faces (1:N recognition)."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    try:
        return engine.search_gallery(
            image_b64=req.image_base64,
            model_name=req.model_name,
            detector_backend=req.detector_backend,
            distance_metric=req.distance_metric,
            top_k=req.top_k,
            threshold=req.threshold,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Gallery search failed: {e}")
        raise HTTPException(500, f"Gallery search failed: {str(e)}")


@app.delete("/gallery/{identity}")
async def delete_from_gallery(identity: str, model_name: str = DEFAULT_MODEL):
    """Remove an identity from the gallery."""
    deleted = engine.redis.delete_gallery_entry(identity, model_name)

    identity_dir = os.path.join(engine.gallery_dir, identity)
    if os.path.exists(identity_dir):
        import shutil
        shutil.rmtree(identity_dir, ignore_errors=True)

    return {"deleted": deleted or os.path.exists(identity_dir) is False, "identity": identity}


@app.post("/anti-spoof")
async def anti_spoof(req: AntiSpoofRequest):
    """Run anti-spoofing detection on a face image."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    try:
        return engine.anti_spoof_check(
            image_b64=req.image_base64,
            detector_backend=req.detector_backend,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Anti-spoof check failed: {e}")
        raise HTTPException(500, f"Anti-spoof check failed: {str(e)}")


@app.post("/compare-multiple")
async def compare_multiple(req: CompareMultipleRequest):
    """Compare one reference face against multiple candidates."""
    if not DEEPFACE_AVAILABLE:
        raise HTTPException(503, "DeepFace library not installed")

    if len(req.candidate_base64_list) > 20:
        raise HTTPException(400, "Maximum 20 candidates per request")

    try:
        return engine.compare_multiple(
            reference_b64=req.reference_base64,
            candidate_b64_list=req.candidate_base64_list,
            model_name=req.model_name,
            detector_backend=req.detector_backend,
            distance_metric=req.distance_metric,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        engine.stats["errors"] += 1
        logger.error(f"Multi-compare failed: {e}")
        raise HTTPException(500, f"Multi-compare failed: {str(e)}")


@app.get("/models")
async def list_models():
    """List all supported recognition models and detectors."""
    return {
        "recognition_models": SUPPORTED_MODELS,
        "detector_backends": SUPPORTED_DETECTORS,
        "distance_metrics": SUPPORTED_METRICS,
        "default_model": DEFAULT_MODEL,
        "default_detector": DEFAULT_DETECTOR,
        "default_distance_metric": DEFAULT_DISTANCE_METRIC,
    }


@app.get("/stats")
async def get_stats():
    """Get service usage statistics."""
    return {
        "stats": engine.stats,
        "gallery_dir": engine.gallery_dir,
        "redis_connected": engine.redis.client is not None,
        "kafka_connected": engine.kafka.producer is not None,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
