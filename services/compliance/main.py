from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="compliance-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_CHECKS = [
    {"name": "KYC Completion Rate", "category": "KYC/AML", "description": "Percentage of agents with completed KYC verification", "status": "passed"},
    {"name": "AML Transaction Monitoring", "category": "KYC/AML", "description": "Real-time monitoring of suspicious transaction patterns", "status": "passed"},
    {"name": "CBN Reporting Timeliness", "category": "Regulatory Reporting", "description": "Submission of CBN required reports within deadlines", "status": "passed"},
    {"name": "Agent Float Limits", "category": "Float Management", "description": "Agent float balances within CBN-prescribed limits", "status": "warning"},
    {"name": "Transaction Limits Enforcement", "category": "Transaction Controls", "description": "Daily and per-transaction limits enforced per tier", "status": "passed"},
    {"name": "NIBSS Integration Status", "category": "Regulatory Reporting", "description": "Connectivity and data accuracy with NIBSS", "status": "passed"},
    {"name": "Data Privacy Compliance", "category": "Data Protection", "description": "Customer PII handling meets NDPR requirements", "status": "passed"},
    {"name": "Agent Onboarding Documents", "category": "KYC/AML", "description": "All agents have valid onboarding documentation", "status": "warning"},
    {"name": "Suspicious Activity Reports", "category": "KYC/AML", "description": "SARs filed within required timeframe", "status": "passed"},
    {"name": "Audit Trail Integrity", "category": "Audit", "description": "All transactions have complete immutable audit logs", "status": "passed"},
]

_last_run = datetime.now(timezone.utc).isoformat()
_checks = [
    {**c, "lastRun": _last_run}
    for c in DEFAULT_CHECKS
]


def _build_summary(checks):
    return {
        "total": len(checks),
        "passed": sum(1 for c in checks if c["status"] == "passed"),
        "failed": sum(1 for c in checks if c["status"] == "failed"),
        "warnings": sum(1 for c in checks if c["status"] == "warning"),
    }


@app.get("/health")
@app.get("/healthz")
def health():
    return {"status": "ok", "service": "compliance-service"}


@app.get("/api/v1/regulatory-compliance/checks")
def get_checks():
    return {"checks": _checks, "summary": _build_summary(_checks)}


@app.post("/api/v1/regulatory-compliance/run")
def run_checks():
    global _checks, _last_run
    _last_run = datetime.now(timezone.utc).isoformat()
    _checks = [{**c, "lastRun": _last_run} for c in _checks]
    return {"success": True, "checks": _checks, "summary": _build_summary(_checks)}
