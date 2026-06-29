import os
import uuid
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/qr-tickets", tags=["qr-ticket-verification"])

QR_SECRET_KEY = os.getenv("QR_TICKET_SECRET_KEY", "default-qr-secret-change-in-production")
QR_DEFAULT_TTL_HOURS = int(os.getenv("QR_TICKET_TTL_HOURS", "24"))


class TicketType(str, Enum):
    EVENT = "event"
    TRANSPORT = "transport"
    VOUCHER = "voucher"
    ACCESS_PASS = "access_pass"
    LOTTERY = "lottery"
    RECEIPT = "receipt"


class TicketStatus(str, Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class BulkVerifyRequest(BaseModel):
    qr_codes: List[str] = Field(..., description="List of raw QR code data strings to verify")
    scanner_agent_id: Optional[str] = None
    scanner_location: Optional[str] = None


class BulkVerifyResponse(BaseModel):
    total: int
    verified: int
    failed: int
    results: List[Dict[str, Any]]
    verified_at: str


class TicketCreate(BaseModel):
    ticket_type: TicketType
    event_name: str = Field(..., description="Event/service name")
    holder_name: Optional[str] = None
    holder_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = Field(default="NGN")
    valid_from: str = Field(..., description="ISO datetime")
    valid_until: str = Field(..., description="ISO datetime")
    ttl_hours: Optional[int] = Field(default=None, description="Override default TTL in hours")
    max_uses: int = Field(default=1, ge=1, description="Max scan/verification count")
    venue: Optional[str] = None
    seat_info: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None


class TicketResponse(BaseModel):
    ticket_id: str
    ticket_type: TicketType
    event_name: str
    holder_name: Optional[str] = None
    holder_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str
    valid_from: str
    valid_until: str
    max_uses: int
    use_count: int = 0
    status: TicketStatus
    venue: Optional[str] = None
    seat_info: Optional[str] = None
    qr_code_data: str
    qr_signature: str
    metadata: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None
    created_at: str


class VerifyRequest(BaseModel):
    qr_data: str = Field(..., description="Raw QR code data scanned from ticket")
    scanner_agent_id: Optional[str] = None
    scanner_location: Optional[str] = None


class VerifyResponse(BaseModel):
    valid: bool
    ticket_id: Optional[str] = None
    status: str
    message: str
    ticket_details: Optional[Dict[str, Any]] = None
    verified_at: str
    remaining_uses: Optional[int] = None


_tickets: Dict[str, TicketResponse] = {}
_scan_log: List[Dict[str, Any]] = []


def _generate_qr_data(ticket_id: str, ticket_type: str, event_name: str, valid_until: str) -> str:
    payload = {
        "tid": ticket_id,
        "type": ticket_type,
        "event": event_name,
        "exp": valid_until,
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _sign_qr_data(qr_data: str) -> str:
    return hmac.new(
        QR_SECRET_KEY.encode(),
        qr_data.encode(),
        hashlib.sha256
    ).hexdigest()


def _parse_qr_data(qr_data: str) -> Optional[Dict[str, Any]]:
    try:
        decoded = base64.urlsafe_b64decode(qr_data.encode()).decode()
        return json.loads(decoded)
    except Exception:
        return None


@router.post("/create", response_model=TicketResponse)
async def create_ticket(request: TicketCreate):
    ticket_id = f"TKT-{uuid.uuid4().hex[:12].upper()}"

    ttl = request.ttl_hours if request.ttl_hours is not None else QR_DEFAULT_TTL_HOURS
    now_dt = datetime.utcnow()
    enforced_valid_until = request.valid_until
    try:
        req_until = datetime.fromisoformat(request.valid_until.replace("Z", ""))
        max_expiry = now_dt + timedelta(hours=ttl)
        if req_until > max_expiry:
            enforced_valid_until = max_expiry.isoformat()
    except (ValueError, TypeError):
        pass

    qr_data = _generate_qr_data(ticket_id, request.ticket_type.value, request.event_name, enforced_valid_until)
    qr_signature = _sign_qr_data(qr_data)
    full_qr = f"{qr_data}.{qr_signature}"

    now = now_dt.isoformat()
    ticket = TicketResponse(
        ticket_id=ticket_id,
        ticket_type=request.ticket_type,
        event_name=request.event_name,
        holder_name=request.holder_name,
        holder_id=request.holder_id,
        amount=request.amount,
        currency=request.currency,
        valid_from=request.valid_from,
        valid_until=enforced_valid_until,
        max_uses=request.max_uses,
        use_count=0,
        status=TicketStatus.ACTIVE,
        venue=request.venue,
        seat_info=request.seat_info,
        qr_code_data=full_qr,
        qr_signature=qr_signature,
        metadata=request.metadata,
        agent_id=request.agent_id,
        created_at=now,
    )
    _tickets[ticket_id] = ticket
    return ticket


@router.post("/verify", response_model=VerifyResponse)
async def verify_ticket(request: VerifyRequest):
    now = datetime.utcnow()
    now_iso = now.isoformat()

    parts = request.qr_data.rsplit(".", 1)
    if len(parts) != 2:
        _log_scan(None, request, "invalid_format", now_iso)
        return VerifyResponse(
            valid=False, status="invalid", message="Invalid QR code format",
            verified_at=now_iso,
        )

    qr_data, received_sig = parts

    expected_sig = _sign_qr_data(qr_data)
    if not hmac.compare_digest(expected_sig, received_sig):
        _log_scan(None, request, "invalid_signature", now_iso)
        return VerifyResponse(
            valid=False, status="tampered", message="QR code signature verification failed - possible tampering",
            verified_at=now_iso,
        )

    payload = _parse_qr_data(qr_data)
    if not payload:
        _log_scan(None, request, "parse_error", now_iso)
        return VerifyResponse(
            valid=False, status="invalid", message="Could not parse QR code data",
            verified_at=now_iso,
        )

    ticket_id = payload.get("tid")
    if ticket_id not in _tickets:
        _log_scan(ticket_id, request, "not_found", now_iso)
        return VerifyResponse(
            valid=False, ticket_id=ticket_id, status="not_found",
            message="Ticket not found in system",
            verified_at=now_iso,
        )

    ticket = _tickets[ticket_id]

    if ticket.status == TicketStatus.CANCELLED:
        _log_scan(ticket_id, request, "cancelled", now_iso)
        return VerifyResponse(
            valid=False, ticket_id=ticket_id, status="cancelled",
            message="This ticket has been cancelled",
            verified_at=now_iso,
        )

    if ticket.status == TicketStatus.SUSPENDED:
        _log_scan(ticket_id, request, "suspended", now_iso)
        return VerifyResponse(
            valid=False, ticket_id=ticket_id, status="suspended",
            message="This ticket is suspended - contact support",
            verified_at=now_iso,
        )

    try:
        valid_until = datetime.fromisoformat(ticket.valid_until.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        valid_until = datetime.fromisoformat(ticket.valid_until)
    if now > valid_until:
        ticket.status = TicketStatus.EXPIRED
        _log_scan(ticket_id, request, "expired", now_iso)
        return VerifyResponse(
            valid=False, ticket_id=ticket_id, status="expired",
            message=f"Ticket expired on {ticket.valid_until}",
            verified_at=now_iso,
        )

    if ticket.use_count >= ticket.max_uses:
        ticket.status = TicketStatus.USED
        _log_scan(ticket_id, request, "already_used", now_iso)
        return VerifyResponse(
            valid=False, ticket_id=ticket_id, status="already_used",
            message=f"Ticket already used {ticket.use_count}/{ticket.max_uses} times",
            verified_at=now_iso, remaining_uses=0,
        )

    ticket.use_count += 1
    remaining = ticket.max_uses - ticket.use_count
    if remaining == 0:
        ticket.status = TicketStatus.USED

    _log_scan(ticket_id, request, "verified", now_iso)

    return VerifyResponse(
        valid=True,
        ticket_id=ticket_id,
        status="verified",
        message=f"Ticket verified successfully ({ticket.use_count}/{ticket.max_uses} uses)",
        ticket_details={
            "event_name": ticket.event_name,
            "ticket_type": ticket.ticket_type.value,
            "holder_name": ticket.holder_name,
            "venue": ticket.venue,
            "seat_info": ticket.seat_info,
            "amount": ticket.amount,
        },
        verified_at=now_iso,
        remaining_uses=remaining,
    )


def _log_scan(ticket_id: Optional[str], request: VerifyRequest, result: str, timestamp: str):
    _scan_log.append({
        "ticket_id": ticket_id,
        "scanner_agent_id": request.scanner_agent_id,
        "scanner_location": request.scanner_location,
        "result": result,
        "scanned_at": timestamp,
    })


@router.get("/tickets", response_model=List[TicketResponse])
async def list_tickets(
    ticket_type: Optional[TicketType] = None,
    status: Optional[TicketStatus] = None,
    event_name: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = Query(default=50, le=500),
):
    tickets = list(_tickets.values())
    if ticket_type:
        tickets = [t for t in tickets if t.ticket_type == ticket_type]
    if status:
        tickets = [t for t in tickets if t.status == status]
    if event_name:
        tickets = [t for t in tickets if event_name.lower() in t.event_name.lower()]
    if agent_id:
        tickets = [t for t in tickets if t.agent_id == agent_id]
    return tickets[-limit:]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str):
    if ticket_id not in _tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _tickets[ticket_id]


@router.post("/tickets/{ticket_id}/cancel")
async def cancel_ticket(ticket_id: str, reason: Optional[str] = None):
    if ticket_id not in _tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = _tickets[ticket_id]
    if ticket.status == TicketStatus.USED:
        raise HTTPException(status_code=400, detail="Cannot cancel a used ticket")
    ticket.status = TicketStatus.CANCELLED
    return {"status": "cancelled", "ticket_id": ticket_id, "reason": reason}


@router.post("/tickets/{ticket_id}/suspend")
async def suspend_ticket(ticket_id: str, reason: Optional[str] = None):
    if ticket_id not in _tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    _tickets[ticket_id].status = TicketStatus.SUSPENDED
    return {"status": "suspended", "ticket_id": ticket_id, "reason": reason}


@router.post("/tickets/{ticket_id}/reactivate")
async def reactivate_ticket(ticket_id: str):
    if ticket_id not in _tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket = _tickets[ticket_id]
    if ticket.status not in (TicketStatus.SUSPENDED, TicketStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot reactivate ticket with status {ticket.status}")
    ticket.status = TicketStatus.ACTIVE
    return {"status": "reactivated", "ticket_id": ticket_id}


@router.post("/batch-create")
async def batch_create_tickets(
    ticket_type: TicketType,
    event_name: str,
    valid_from: str,
    valid_until: str,
    count: int = Field(..., ge=1, le=1000),
    amount: Optional[float] = None,
    venue: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    tickets = []
    for _ in range(count):
        req = TicketCreate(
            ticket_type=ticket_type,
            event_name=event_name,
            valid_from=valid_from,
            valid_until=valid_until,
            amount=amount,
            venue=venue,
            agent_id=agent_id,
        )
        ticket = await create_ticket(req)
        tickets.append(ticket.ticket_id)
    return {"created": len(tickets), "ticket_ids": tickets}


@router.get("/scan-log")
async def get_scan_log(
    ticket_id: Optional[str] = None,
    result: Optional[str] = None,
    scanner_agent_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    logs = _scan_log
    if ticket_id:
        logs = [l for l in logs if l.get("ticket_id") == ticket_id]
    if result:
        logs = [l for l in logs if l.get("result") == result]
    if scanner_agent_id:
        logs = [l for l in logs if l.get("scanner_agent_id") == scanner_agent_id]
    return {"total": len(logs), "logs": logs[-limit:]}


@router.post("/bulk-verify", response_model=BulkVerifyResponse)
async def bulk_verify_tickets(request: BulkVerifyRequest):
    """Verify multiple QR codes in a single request for auditor batch scanning."""
    now = datetime.utcnow()
    now_iso = now.isoformat()
    results = []
    verified_count = 0
    failed_count = 0
    for qr_code in request.qr_codes:
        single_req = VerifyRequest(
            qr_data=qr_code,
            scanner_agent_id=request.scanner_agent_id,
            scanner_location=request.scanner_location,
        )
        result = await verify_ticket(single_req)
        entry = {
            "qr_data_prefix": qr_code[:20] + "..." if len(qr_code) > 20 else qr_code,
            "valid": result.valid,
            "status": result.status,
            "message": result.message,
            "ticket_id": result.ticket_id,
        }
        results.append(entry)
        if result.valid:
            verified_count += 1
        else:
            failed_count += 1
    return BulkVerifyResponse(
        total=len(request.qr_codes),
        verified=verified_count,
        failed=failed_count,
        results=results,
        verified_at=now_iso,
    )


@router.get("/stats")
async def get_ticket_stats():
    total = len(_tickets)
    by_status = {}
    by_type = {}
    for t in _tickets.values():
        by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
        by_type[t.ticket_type.value] = by_type.get(t.ticket_type.value, 0) + 1

    scan_results = {}
    for s in _scan_log:
        r = s.get("result", "unknown")
        scan_results[r] = scan_results.get(r, 0) + 1

    return {
        "total_tickets": total,
        "by_status": by_status,
        "by_type": by_type,
        "total_scans": len(_scan_log),
        "scan_results": scan_results,
        "verification_rate": round(
            scan_results.get("verified", 0) / max(len(_scan_log), 1) * 100, 1
        ),
    }
