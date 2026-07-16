from fastapi import APIRouter

health_router = APIRouter()

@health_router.get("/health")
def health():
    return {
        "message": "Api is healthy!"
    }