import os
import threading
from datetime import datetime

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from router import router
from event_consumer import consumer_router
from scheduler import start_scheduler, stop_scheduler

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
            "service": "nigeria-vat-service",
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


app = FastAPI(
    title="Nigeria VAT Management Service",
    version="1.0.0",
    description=(
        "Automated VAT management for agent businesses. "
        "Auto-records VAT on every agent transaction, generates monthly "
        "Form 002 returns, and optionally auto-files with FIRS."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and response.status_code < 500
        and not request.url.path.startswith(("/docs", "/openapi", "/redoc", "/dapr", "/events"))
    ):
        emit_audit_event(request, response.status_code)
    return response


# VAT REST API
app.include_router(router)

# Dapr event subscription endpoints
app.include_router(consumer_router)


@app.on_event("startup")
async def startup():
    start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "nigeria-vat-service"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
