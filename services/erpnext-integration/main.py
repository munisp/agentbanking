import uvicorn
import os
import threading
from datetime import datetime
import logging
import httpx
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from router import router
from config import engine
from service import Base

logger = logging.getLogger(__name__)
AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")

app = FastAPI(
    title="Erpnext-integration Service",
    version="1.0.0",
    description="54agent Platform — erpnext-integration service",
)


def emit_audit_event(request: Request, status_code: int):
    event_type_map = {
        "POST": "CREATE",
        "PUT": "UPDATE",
        "PATCH": "UPDATE",
        "DELETE": "DELETE",
    }
    event_type = event_type_map.get(request.method)
    if not event_type:
        return

    tenant_id = request.headers.get("x-tenant-id") or "54agent"
    actor_id = request.headers.get("x-keycloak-id") or "system"

    payload = {
        "actor_id": actor_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "event_data": {
            "service": "erpnext-integration",
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "query": str(request.url.query),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    def _send():
        try:
            with httpx.Client(timeout=5.0) as client:
                client.post(
                    f"{AUDIT_SVC_URL}/audits",
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-tenant-id": tenant_id,
                        "x-keycloak-id": actor_id,
                    },
                )
        except Exception:
            logger.warning("Failed to emit audit event")

    threading.Thread(target=_send, daemon=True).start()


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 500
        and not request.url.path.startswith(("/docs", "/openapi", "/redoc"))
    ):
        emit_audit_event(request, response.status_code)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "erpnext-integration"}


if __name__ == "__main__":
    port = int(os.getenv("SERVICE_PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
