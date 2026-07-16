from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["Monitoring"])
async def health_check():
    return {"status": "healthy", "service": "support-comms-service"}
