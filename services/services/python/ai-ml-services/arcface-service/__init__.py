"""
ArcFace Face Matching Service
High-accuracy face recognition with 95%+ accuracy
"""

from .arcface_face_matcher import ArcFaceMatcher, FaceMatchResult, FaceEmbedding
from .router import router

__version__ = "1.0.0"
__all__ = ["ArcFaceMatcher", "FaceMatchResult", "FaceEmbedding", "router"]
