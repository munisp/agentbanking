import os
import threading
from datetime import datetime

import httpx
from fastapi import FastAPI, Request
from router import router

AUDIT_SVC_URL = os.getenv("AUDIT_SVC_URL", "https://54agent.upi.dev/audit")


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
            "service": "storefront-advertising",
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
            pass

    threading.Thread(target=_send, daemon=True).start()

app = FastAPI(title="Storefront Advertising Service", version="1.0.0")


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

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "storefront-advertising"}
