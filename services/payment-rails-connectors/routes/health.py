from fastapi import APIRouter

health_router = APIRouter()


@health_router.get("")
@health_router.get("/")
def health_check():
    return {"status": "ok", "service": "payment-rails-connectors"}
