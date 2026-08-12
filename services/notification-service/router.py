"""
Router for notification-service service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): these endpoints were auto-generated stubs that
returned fabricated {"status": "ok"} responses and referenced undefined names
(Item/Dict/Any), so they could not even be imported. Until this stub is
removed from every registration site, all endpoints fail loudly with
501 Not Implemented instead of fabricating success.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/notification-service", tags=["notification-service"])

_STUB_DETAIL = "notification-service stub endpoint disabled: no real handler is implemented in this auto-generated router"


def _not_implemented():
    raise HTTPException(status_code=501, detail=_STUB_DETAIL)


@router.get("/")
async def root():
    _not_implemented()


@router.get("/health")
async def health_check():
    return {"status": "ok", "note": "stub router only; no real handlers"}


@router.post("/items")
async def create_item():
    _not_implemented()


@router.get("/items")
async def list_items(skip: int = 0, limit: int = 100):
    _not_implemented()


@router.get("/items/{item_id}")
async def get_item(item_id: str):
    _not_implemented()


@router.put("/items/{item_id}")
async def update_item(item_id: str):
    _not_implemented()


@router.delete("/items/{item_id}")
async def delete_item(item_id: str):
    _not_implemented()


@router.post("/process")
async def process_data():
    _not_implemented()


@router.get("/search")
async def search_items(query: str):
    _not_implemented()


@router.get("/stats")
async def get_statistics():
    _not_implemented()
