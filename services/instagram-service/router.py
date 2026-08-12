"""
Router for instagram-service service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses and referenced undefined names
(Message/OrderMessage/BackgroundTasks/Request/Optional), so they could not
even be imported. The real send/order/webhook/metrics logic lives in this
service's main.py. Until this stub is removed from every registration site,
endpoints fail loudly with 501 Not Implemented instead of pretending
messages/orders were processed.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/instagram-service", tags=["instagram-service"])

_STUB_DETAIL = "instagram-service stub endpoint disabled: use the real implementation in this service's main.py"


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/")
async def root():
    _not_implemented()


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; real implementation is in main.py"}


@router.post("/api/v1/send")
async def send_message():
    _not_implemented()


@router.post("/api/v1/order")
async def create_order():
    _not_implemented()


@router.post("/webhook")
async def webhook_handler():
    _not_implemented()


@router.get("/api/v1/messages")
async def get_messages(limit: int = 50, offset: int = 0):
    _not_implemented()


@router.get("/api/v1/orders")
async def get_orders(status: str = None, limit: int = 50):
    _not_implemented()


@router.get("/api/v1/metrics")
async def get_metrics():
    _not_implemented()
