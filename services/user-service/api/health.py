from fastapi import APIRouter
from utils import create_logger

health_router = APIRouter()

logger = create_logger(__name__)

@health_router.get("/health")
def health():
    return {
        "message": "Api is healthy!"
    }