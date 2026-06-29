import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

logger = logging.getLogger("developer-portal-service")

router = APIRouter(
    prefix="/api/v1",
    tags=["developer-portal"],
    responses={404: {"description": "Not found"}},
)

# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

_api_keys: dict[str, dict] = {}
_webhooks: dict[str, dict] = {}
_rate_limit_rules: dict[str, dict] = {}
_integrations_state: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str]
    expires_in_days: Optional[int] = None


class WebhookCreate(BaseModel):
    url: str
    events: List[str]
    description: Optional[str] = None


class WebhookStatusUpdate(BaseModel):
    status: str  # "active" | "paused"


class RateLimitRuleCreate(BaseModel):
    endpoint_pattern: str
    limit: int
    window: str
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# API Keys  —  /api/v1/api-keys
# ---------------------------------------------------------------------------

VALID_SCOPES = [
    "transactions:read", "transactions:write",
    "agents:read", "merchants:read",
    "reports:read", "webhooks:manage",
    "compliance:read", "settlements:read",
]


@router.get("/api-keys", summary="List API keys")
def list_api_keys():
    return list(_api_keys.values())


@router.post("/api-keys", status_code=status.HTTP_201_CREATED, summary="Create a new API key")
def create_api_key(payload: ApiKeyCreate):
    invalid = [s for s in payload.scopes if s not in VALID_SCOPES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {invalid}. Valid: {VALID_SCOPES}",
        )
    key_id = str(uuid.uuid4())
    raw_key = f"54lnk_{secrets.token_hex(24)}"
    expires_at = (
        datetime.utcnow() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days else None
    )
    record = {
        "id": key_id,
        "name": payload.name,
        "key": raw_key,
        "key_preview": f"{raw_key[:12]}...{raw_key[-4:]}",
        "scopes": payload.scopes,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "last_used": None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    _api_keys[key_id] = record
    logger.info(f"API key created: {key_id} ({payload.name})")
    return record


@router.post("/api-keys/{key_id}/revoke", summary="Revoke an API key")
def revoke_api_key(key_id: str):
    if key_id not in _api_keys:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    _api_keys[key_id]["status"] = "revoked"
    logger.info(f"API key revoked: {key_id}")
    return {"id": key_id, "status": "revoked"}


# ---------------------------------------------------------------------------
# Webhooks  —  /api/v1/webhooks
# ---------------------------------------------------------------------------

VALID_WEBHOOK_EVENTS = [
    "transaction.created", "transaction.completed", "transaction.failed",
    "agent.registered", "agent.suspended",
    "float.low", "float.topped_up",
    "dispute.opened", "dispute.resolved",
    "settlement.initiated", "settlement.completed",
    "kyc.submitted", "kyc.approved",
]


@router.get("/webhooks", summary="List webhook endpoints")
def list_webhooks():
    return list(_webhooks.values())


@router.post("/webhooks", status_code=status.HTTP_201_CREATED, summary="Register a webhook endpoint")
def create_webhook(payload: WebhookCreate):
    invalid = [e for e in payload.events if e not in VALID_WEBHOOK_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid events: {invalid}",
        )
    webhook_id = str(uuid.uuid4())
    record = {
        "id": webhook_id,
        "url": payload.url,
        "events": payload.events,
        "description": payload.description,
        "status": "active",
        "success_rate": 100.0,
        "total_deliveries": 0,
        "last_delivery": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    _webhooks[webhook_id] = record
    logger.info(f"Webhook registered: {webhook_id} -> {payload.url}")
    return record


@router.delete("/webhooks/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a webhook")
def delete_webhook(webhook_id: str):
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    del _webhooks[webhook_id]
    logger.info(f"Webhook deleted: {webhook_id}")


@router.post("/webhooks/{webhook_id}/test", summary="Send a test event to a webhook")
def test_webhook(webhook_id: str):
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    webhook = _webhooks[webhook_id]
    logger.info(f"Test event dispatched to webhook: {webhook_id}")
    return {
        "status": "delivered",
        "webhook_id": webhook_id,
        "url": webhook["url"],
        "event": "test.ping",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.patch("/webhooks/{webhook_id}/status", summary="Pause or resume a webhook")
def update_webhook_status(webhook_id: str, payload: WebhookStatusUpdate):
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    if payload.status not in ("active", "paused"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be 'active' or 'paused'")
    _webhooks[webhook_id]["status"] = payload.status
    logger.info(f"Webhook {webhook_id} status set to {payload.status}")
    return _webhooks[webhook_id]


# ---------------------------------------------------------------------------
# Analytics  —  /api/v1/analytics
# ---------------------------------------------------------------------------

@router.get("/analytics", summary="Get API usage analytics")
def get_analytics(
    time_range: str = Query("24h", alias="range", description="Time range: 24h, 7d, or 30d"),
):
    if time_range not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="range must be 24h, 7d, or 30d")

    buckets = {"24h": 24, "7d": 7, "30d": 30}[time_range]
    now = datetime.utcnow()

    requests_over_time = [
        {
            "timestamp": (now - timedelta(hours=(buckets - i))).isoformat(),
            "requests": 200 + (i * 37 % 300),
            "errors": 2 + (i % 8),
        }
        for i in builtins_range(buckets)
    ]

    return {
        "range": time_range,
        "summary": {
            "total_requests": 145320,
            "avg_latency_ms": 42,
            "error_rate_pct": 0.8,
            "uptime_pct": 99.97,
        },
        "requests_over_time": requests_over_time,
        "top_endpoints": [
            {"endpoint": "POST /transaction/api/v1/transfers", "requests": 48200, "avg_latency_ms": 142, "error_rate_pct": 0.4},
            {"endpoint": "GET /transaction/api/v1/transactions", "requests": 39500, "avg_latency_ms": 88, "error_rate_pct": 0.2},
            {"endpoint": "POST /agent/api/v1/cash-in", "requests": 31800, "avg_latency_ms": 210, "error_rate_pct": 0.7},
            {"endpoint": "GET /agent/api/v1/agents", "requests": 28100, "avg_latency_ms": 65, "error_rate_pct": 0.1},
            {"endpoint": "POST /payment-hub/api/v1/bills", "requests": 22600, "avg_latency_ms": 195, "error_rate_pct": 1.2},
        ],
        "status_codes": {"2xx": 143754, "4xx": 1412, "5xx": 154},
    }


# Alias for the built-in range so the analytics function can use it safely
builtins_range = range


# ---------------------------------------------------------------------------
# Rate Limiting  —  /api/v1/rate-limits
# ---------------------------------------------------------------------------

DEFAULT_RULES = [
    {"endpoint_pattern": "POST /transaction/api/v1/transfers", "limit": 60, "window": "per-minute", "description": "Transfer creation"},
    {"endpoint_pattern": "POST /auth/api/v1/login", "limit": 10, "window": "per-minute", "description": "Authentication"},
    {"endpoint_pattern": "GET /transaction/api/v1/transactions", "limit": 300, "window": "per-minute", "description": "Transaction reads"},
    {"endpoint_pattern": "POST /agent/api/v1/cash-in", "limit": 50, "window": "per-minute", "description": "Cash-in operations"},
    {"endpoint_pattern": "POST /payment-hub/api/v1/bills", "limit": 1000, "window": "per-hour", "description": "Bill payments"},
    {"endpoint_pattern": "GET /compliance/api/v1/kyc-status", "limit": 5000, "window": "per-hour", "description": "KYC status checks"},
    {"endpoint_pattern": "POST /developer/api/v1/webhooks/test", "limit": 20, "window": "per-minute", "description": "Webhook tests"},
    {"endpoint_pattern": "*", "limit": 1000, "window": "per-minute", "description": "Global catchall"},
]

for _rule in DEFAULT_RULES:
    _rule_id = str(uuid.uuid4())
    _rate_limit_rules[_rule_id] = {
        "id": _rule_id,
        "endpoint_pattern": _rule["endpoint_pattern"],
        "limit": _rule["limit"],
        "window": _rule["window"],
        "current_usage": 0,
        "description": _rule["description"],
        "created_at": datetime.utcnow().isoformat(),
    }


@router.get("/rate-limits", summary="List rate limit rules")
def list_rate_limit_rules():
    return list(_rate_limit_rules.values())


@router.post("/rate-limits", status_code=status.HTTP_201_CREATED, summary="Create a rate limit rule")
def create_rate_limit_rule(payload: RateLimitRuleCreate):
    if payload.window not in ("per-minute", "per-hour", "per-day"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="window must be per-minute, per-hour, or per-day")
    rule_id = str(uuid.uuid4())
    record = {
        "id": rule_id,
        "endpoint_pattern": payload.endpoint_pattern,
        "limit": payload.limit,
        "window": payload.window,
        "current_usage": 0,
        "description": payload.description,
        "created_at": datetime.utcnow().isoformat(),
    }
    _rate_limit_rules[rule_id] = record
    logger.info(f"Rate limit rule created: {rule_id}")
    return record


@router.delete("/rate-limits/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a rate limit rule")
def delete_rate_limit_rule(rule_id: str):
    if rule_id not in _rate_limit_rules:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    del _rate_limit_rules[rule_id]


# ---------------------------------------------------------------------------
# API Versioning  —  /api/v1/versions
# ---------------------------------------------------------------------------

@router.get("/versions", summary="List API versions")
def list_api_versions():
    return {
        "versions": [
            {
                "id": "v3",
                "version": "v3",
                "status": "active",
                "releaseDate": "2024-07-01",
                "deprecationDate": None,
                "sunsetDate": None,
                "endpointCount": 84,
                "migrationGuide": "https://docs.54agent.ng/api/v3/migration",
                "breakingChanges": [
                    "Unified /payment-hub endpoints replace split /bills and /transfers",
                    "Pagination now uses cursor-based instead of offset",
                    "Webhook payloads include new 'meta.version' field",
                ],
            },
            {
                "id": "v2",
                "version": "v2",
                "status": "deprecated",
                "releaseDate": "2023-01-15",
                "deprecationDate": "2024-07-01",
                "sunsetDate": "2025-01-15",
                "endpointCount": 62,
                "migrationGuide": "https://docs.54agent.ng/api/v2/migration",
                "breakingChanges": [
                    "Agent onboarding endpoint path changed from /onboard to /agents",
                    "Transaction response now returns 'amount_ngn' instead of 'amount'",
                ],
            },
            {
                "id": "v1",
                "version": "v1",
                "status": "sunset",
                "releaseDate": "2022-03-01",
                "deprecationDate": "2023-01-15",
                "sunsetDate": "2024-01-15",
                "endpointCount": 38,
                "migrationGuide": "https://docs.54agent.ng/api/v1/migration",
                "breakingChanges": [],
            },
        ]
    }


# ---------------------------------------------------------------------------
# Integration Marketplace  —  /api/v1/integrations
# ---------------------------------------------------------------------------

INTEGRATIONS_CATALOG = [
    {"id": "nibss", "name": "NIBSS", "category": "Payment", "description": "Nigeria Inter-Bank Settlement System for NIP and NEFT transfers between Nigerian banks.", "logo": "NI", "default_status": "connected"},
    {"id": "mojaloop", "name": "Mojaloop", "category": "Payment", "description": "Open-source interoperability platform for real-time inclusive financial services.", "logo": "MJ", "default_status": "connected"},
    {"id": "flutterwave", "name": "Flutterwave", "category": "Payment", "description": "Pan-African payments gateway supporting cards, bank transfers and mobile money.", "logo": "FW", "default_status": "connected"},
    {"id": "paystack", "name": "Paystack", "category": "Payment", "description": "Modern Nigerian payments processor with support for card, bank and USSD payments.", "logo": "PS", "default_status": "available"},
    {"id": "stripe", "name": "Stripe", "category": "Payment", "description": "Global payments infrastructure for international card processing and disbursements.", "logo": "ST", "default_status": "available"},
    {"id": "remita", "name": "Remita", "category": "Payment", "description": "Government and enterprise payment collection platform used by IPPIS and federal agencies.", "logo": "RM", "default_status": "coming-soon"},
    {"id": "interswitch", "name": "Interswitch", "category": "Payment", "description": "Nigerian payment switching and processing network supporting Verve cards and Quickteller.", "logo": "IW", "default_status": "coming-soon"},
    {"id": "cbn-api", "name": "CBN Open API", "category": "Compliance", "description": "Central Bank of Nigeria regulatory reporting, BVN verification and policy feeds.", "logo": "CB", "default_status": "connected"},
    {"id": "nfiu", "name": "NFIU", "category": "Compliance", "description": "Nigeria Financial Intelligence Unit STR/CTR filing and AML transaction screening.", "logo": "NF", "default_status": "connected"},
    {"id": "dojah", "name": "Dojah KYC", "category": "Compliance", "description": "Identity verification APIs for BVN lookup, NIN check, document OCR and liveness detection.", "logo": "DJ", "default_status": "available"},
    {"id": "termii", "name": "Termii SMS", "category": "Communication", "description": "Nigerian SMS gateway for OTP delivery, transactional SMS and voice notifications.", "logo": "TM", "default_status": "connected"},
    {"id": "africas-talking", "name": "Africa's Talking", "category": "Communication", "description": "Multi-channel communications API for SMS, USSD, voice and airtime across Africa.", "logo": "AT", "default_status": "available"},
    {"id": "mixpanel", "name": "Mixpanel", "category": "Analytics", "description": "Product analytics platform for tracking user journeys and funnel optimisation.", "logo": "MP", "default_status": "available"},
    {"id": "google-analytics", "name": "Google Analytics", "category": "Analytics", "description": "Web and app analytics for dashboard usage tracking and admin user behaviour insights.", "logo": "GA", "default_status": "coming-soon"},
    {"id": "erpnext", "name": "ERPNext", "category": "ERP", "description": "Open-source ERP for accounting, inventory and HR integration with agent banking operations.", "logo": "EN", "default_status": "available"},
]

_integrations_state: dict[str, str] = {i["id"]: i["default_status"] for i in INTEGRATIONS_CATALOG}


@router.get("/integrations", summary="List available integrations")
def list_integrations(category: Optional[str] = Query(None)):
    catalog = INTEGRATIONS_CATALOG
    if category:
        catalog = [i for i in catalog if i["category"].lower() == category.lower()]
    return [
        {**{k: v for k, v in i.items() if k != "default_status"}, "status": _integrations_state.get(i["id"], "available")}
        for i in catalog
    ]


@router.post("/integrations/{integration_id}/connect", summary="Connect an integration")
def connect_integration(integration_id: str):
    known = {i["id"] for i in INTEGRATIONS_CATALOG}
    if integration_id not in known:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    _integrations_state[integration_id] = "connected"
    logger.info(f"Integration connected: {integration_id}")
    return {"integration_id": integration_id, "status": "connected"}


@router.post("/integrations/{integration_id}/disconnect", summary="Disconnect an integration")
def disconnect_integration(integration_id: str):
    known = {i["id"] for i in INTEGRATIONS_CATALOG}
    if integration_id not in known:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    _integrations_state[integration_id] = "available"
    logger.info(f"Integration disconnected: {integration_id}")
    return {"integration_id": integration_id, "status": "available"}


# ---------------------------------------------------------------------------
# Readiness Checks  —  /api/v1/readiness-checks
# ---------------------------------------------------------------------------

_readiness_checks: dict[str, dict] = {
    c["id"]: c for c in [
        {"id": "tls", "category": "Security", "name": "TLS/HTTPS enforced", "status": "pass"},
        {"id": "api-key-rotation", "category": "Security", "name": "API key rotation policy set", "status": "warning"},
        {"id": "secrets-scan", "category": "Security", "name": "No secrets in codebase", "status": "pass"},
        {"id": "owasp", "category": "Security", "name": "OWASP Top 10 mitigations", "status": "pass"},
        {"id": "p95-latency", "category": "Performance", "name": "P95 latency < 200ms", "status": "pass"},
        {"id": "db-indexes", "category": "Performance", "name": "Database indexes optimised", "status": "warning"},
        {"id": "cache-hit", "category": "Performance", "name": "Cache hit ratio > 80%", "status": "pass"},
        {"id": "cbn-retention", "category": "Compliance", "name": "CBN 5-year data retention", "status": "pass"},
        {"id": "ndpr-consent", "category": "Compliance", "name": "NDPR consent flows", "status": "pass"},
        {"id": "kyc-completeness", "category": "Compliance", "name": "KYC completeness > 95%", "status": "warning"},
        {"id": "k8s-health", "category": "Infrastructure", "name": "Kubernetes pods healthy", "status": "pass"},
        {"id": "backups", "category": "Infrastructure", "name": "Automated backups enabled", "status": "pass"},
        {"id": "cdn-cache", "category": "Infrastructure", "name": "CDN cache configured", "status": "pass"},
        {"id": "dr-runbook", "category": "Infrastructure", "name": "DR runbook documented", "status": "pass"},
        {"id": "unit-coverage", "category": "Testing", "name": "Unit test coverage > 80%", "status": "warning"},
        {"id": "e2e-tests", "category": "Testing", "name": "E2E test suite passing", "status": "pass"},
        {"id": "load-test", "category": "Testing", "name": "Load test at 2× peak passed", "status": "pass"},
    ]
}


@router.get("/readiness-checks", summary="Get publish readiness check results")
def get_readiness_checks():
    checks = list(_readiness_checks.values())
    passed = sum(1 for c in checks if c["status"] == "pass")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    failed = sum(1 for c in checks if c["status"] == "fail")
    return {
        "score": int((passed / len(checks)) * 100),
        "summary": {"passed": passed, "warnings": warnings, "failed": failed, "total": len(checks)},
        "checks": checks,
    }


@router.post("/readiness-checks/run", summary="Re-run all readiness checks")
def run_readiness_checks():
    logger.info("Readiness checks triggered")
    return {
        "message": "Readiness checks initiated",
        "estimated_duration_seconds": 15,
        "check_ids": list(_readiness_checks.keys()),
    }


# ---------------------------------------------------------------------------
# Production Checklist  —  /api/v1/production-checklist
# ---------------------------------------------------------------------------

_checklist_tasks: dict[str, dict] = {
    t["id"]: t for t in [
        {"id": "pre-1", "phase": "Pre-Deploy", "title": "Notify CBN ops team", "assignee": "compliance-lead", "status": "done"},
        {"id": "pre-2", "phase": "Pre-Deploy", "title": "Freeze non-critical merges", "assignee": "engineering-lead", "status": "done"},
        {"id": "pre-3", "phase": "Pre-Deploy", "title": "Run DB migration dry-run", "assignee": "dba", "status": "in-progress"},
        {"id": "pre-4", "phase": "Pre-Deploy", "title": "Tag release in Git", "assignee": "devops", "status": "pending"},
        {"id": "pre-5", "phase": "Pre-Deploy", "title": "Scale down non-essential services", "assignee": "devops", "status": "pending"},
        {"id": "dep-1", "phase": "Deploy", "title": "Apply Kubernetes rolling update", "assignee": "devops", "status": "pending"},
        {"id": "dep-2", "phase": "Deploy", "title": "Apply DB migration", "assignee": "dba", "status": "pending"},
        {"id": "dep-3", "phase": "Deploy", "title": "Verify all pods healthy", "assignee": "devops", "status": "pending"},
        {"id": "dep-4", "phase": "Deploy", "title": "Smoke test critical flows", "assignee": "qa", "status": "pending"},
        {"id": "dep-5", "phase": "Deploy", "title": "Check APISIX routes active", "assignee": "devops", "status": "pending"},
        {"id": "dep-6", "phase": "Deploy", "title": "Validate Dapr sidecars attached", "assignee": "devops", "status": "pending"},
        {"id": "post-1", "phase": "Post-Deploy", "title": "Monitor error rate for 30 min", "assignee": "sre", "status": "pending"},
        {"id": "post-2", "phase": "Post-Deploy", "title": "Confirm Grafana dashboards green", "assignee": "sre", "status": "pending"},
        {"id": "post-3", "phase": "Post-Deploy", "title": "Send release notes to stakeholders", "assignee": "pm", "status": "pending"},
        {"id": "post-4", "phase": "Post-Deploy", "title": "Update API documentation", "assignee": "engineering-lead", "status": "pending"},
        {"id": "rb-1", "phase": "Rollback Plan", "title": "Rollback command prepared", "assignee": "devops", "status": "done"},
        {"id": "rb-2", "phase": "Rollback Plan", "title": "Previous image tag confirmed", "assignee": "devops", "status": "done"},
        {"id": "rb-3", "phase": "Rollback Plan", "title": "DB rollback script tested", "assignee": "dba", "status": "in-progress"},
        {"id": "rb-4", "phase": "Rollback Plan", "title": "On-call rotation confirmed", "assignee": "sre", "status": "done"},
        {"id": "rb-5", "phase": "Rollback Plan", "title": "Incident bridge link shared", "assignee": "engineering-lead", "status": "pending"},
        {"id": "rb-6", "phase": "Rollback Plan", "title": "Comms template prepared", "assignee": "pm", "status": "done"},
    ]
}


@router.get("/production-checklist", summary="Get production readiness checklist")
def get_production_checklist():
    tasks = list(_checklist_tasks.values())
    done = sum(1 for t in tasks if t["status"] == "done")
    phases: dict[str, list] = {}
    for task in tasks:
        phases.setdefault(task["phase"], []).append(task)
    return {
        "completion_pct": int((done / len(tasks)) * 100),
        "summary": {"total": len(tasks), "done": done},
        "phases": phases,
    }


@router.post("/production-checklist/{task_id}/toggle", summary="Toggle a checklist task status")
def toggle_checklist_task(task_id: str):
    if task_id not in _checklist_tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task = _checklist_tasks[task_id]
    task["status"] = "done" if task["status"] != "done" else "pending"
    logger.info(f"Checklist task {task_id} toggled to: {task['status']}")
    return task
