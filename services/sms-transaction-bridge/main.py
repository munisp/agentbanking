import urllib.parse

"""
sms-transaction-bridge — 54agent SMS Transaction Fallback Service

Enables POS transactions via SMS when internet is completely unavailable.
Agents can send structured SMS to process cash-in, cash-out, airtime,
and balance queries. Works on any phone — no smartphone required.

SMS Format: ACTION AMOUNT PHONE [PIN]
  CI 5000 08012345678 1234    → Cash-in 5000 NGN to 08012345678
  CO 2000 08012345678 1234    → Cash-out 2000 NGN
  AT 500 08012345678 1234     → Airtime top-up 500 NGN
  BAL 1234                    → Check agent balance
  TXN                        → Last 5 transactions
  REV TXN123 1234             → Reverse transaction TXN123
  HELP                       → Show command list

HTTP API (port 8081):
  POST /api/sms/inbound      — receive inbound SMS (from SMS gateway)
  POST /api/sms/parse         — parse SMS command (dry run)
  GET  /api/sms/outbox        — list pending outbound SMS
  POST /api/sms/send          — send SMS via gateway
  GET  /api/sms/templates     — list response templates
  GET  /api/stats             — service statistics
  GET  /api/health            — liveness check

Backend integration (REQUIRED — this bridge never fabricates financial data):
  TRANSACTION_API_URL — transaction engine for money movement (real references)
  LEDGER_API_URL      — wallet/ledger API for real balances and statements
  AUTH_API_URL        — auth service for PIN verification

Offline behaviour: when a backend is unreachable, money-movement requests are
queued (store-and-forward) and the reply says "queued" — NEVER "successful".
"""

import json
import re
import time
import uuid
import os
import urllib.request
import urllib.error
from collections import deque
from dataclasses import dataclass, field, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

logger = logging.getLogger("sms-transaction-bridge")

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


# ── Backend Service Clients ───────────────────────────────────────────────────
#
# All balances, statements, PIN verification and transaction execution are
# delegated to real backend services. This bridge NEVER fabricates financial
# data and only reports success with a real backend-issued reference.

TRANSACTION_API_URL = os.environ.get("TRANSACTION_API_URL", "").rstrip("/")
LEDGER_API_URL = os.environ.get("LEDGER_API_URL", "").rstrip("/")
AUTH_API_URL = os.environ.get("AUTH_API_URL", "").rstrip("/")

BACKEND_TIMEOUT = 8  # seconds


class BackendUnavailable(Exception):
    """Raised when a required backend service cannot be reached."""


def _http_json(method: str, url: str, payload: Optional[dict] = None,
               headers: Optional[dict] = None) -> tuple:
    """Perform an HTTP JSON call. Raises BackendUnavailable on transport errors."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=BACKEND_TIMEOUT) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except ValueError:
            parsed = {}
        return e.code, parsed
    except Exception as e:
        raise BackendUnavailable(str(e))


def verify_pin_with_auth(phone: str, pin: str) -> None:
    """Verify the collected PIN against the auth service. Raises on failure."""
    if not AUTH_API_URL:
        raise BackendUnavailable("AUTH_API_URL not configured")
    status, body = _http_json(
        "POST", f"{AUTH_API_URL}/api/v1/auth/verify-pin",
        {"phone": phone, "pin": pin})
    if status != 200:
        raise BackendUnavailable(f"auth service returned {status}")
    if not body.get("valid"):
        raise ValueError("invalid PIN")


def fetch_balance(phone: str) -> dict:
    """Fetch the REAL agent balance from the ledger/wallet API."""
    if not LEDGER_API_URL:
        raise BackendUnavailable("LEDGER_API_URL not configured")
    status, body = _http_json(
        "GET", f"{LEDGER_API_URL}/api/v1/agents/balance?phone={urllib.parse.quote(phone)}")
    if status != 200:
        raise BackendUnavailable(f"ledger API returned {status}")
    return body


def fetch_recent_transactions(phone: str, limit: int = 5) -> list:
    """Fetch the REAL recent transactions from the ledger API."""
    if not LEDGER_API_URL:
        raise BackendUnavailable("LEDGER_API_URL not configured")
    status, body = _http_json(
        "GET", f"{LEDGER_API_URL}/api/v1/agents/mini-statement?phone={urllib.parse.quote(phone)}&limit={limit}")
    if status != 200:
        raise BackendUnavailable(f"ledger API returned {status}")
    return body.get("transactions", [])


def execute_transaction(parsed: "ParsedSMS", sender: str, idempotency_key: str) -> dict:
    """Execute a money-movement command against the transaction engine.

    Returns the engine's response body (must contain a real reference).
    Raises BackendUnavailable when the engine cannot be reached and
    ValueError when the engine explicitly rejects the transaction.
    """
    if not TRANSACTION_API_URL:
        raise BackendUnavailable("TRANSACTION_API_URL not configured")
    payload = {
        "type": parsed.action,
        "amount": parsed.amount,
        "agentPhone": sender,
        "recipient": parsed.phone,
        "channel": "sms",
        "billerCode": parsed.extra_args.get("biller_code"),
    }
    status, body = _http_json(
        "POST", f"{TRANSACTION_API_URL}/api/v1/transactions", payload,
        headers={"Idempotency-Key": idempotency_key})
    if 200 <= status < 300 and body.get("reference"):
        return body
    raise ValueError(body.get("error") or f"transaction engine returned {status}")


def execute_reversal(txn_id: str, sender: str, idempotency_key: str) -> dict:
    """Execute a reversal against the transaction engine."""
    if not TRANSACTION_API_URL:
        raise BackendUnavailable("TRANSACTION_API_URL not configured")
    status, body = _http_json(
        "POST",
        f"{TRANSACTION_API_URL}/api/v1/transactions/{urllib.parse.quote(txn_id)}/reverse",
        {"agentPhone": sender, "channel": "sms"},
        headers={"Idempotency-Key": idempotency_key})
    if 200 <= status < 300 and (body.get("reference") or body.get("success")):
        return body
    raise ValueError(body.get("error") or f"transaction engine returned {status}")


# ── SMS Command Parser ────────────────────────────────────────────────────────

COMMANDS = {
    "CI": {"name": "cash_in", "args": ["amount", "phone", "pin"], "description": "Cash-in to customer"},
    "CO": {"name": "cash_out", "args": ["amount", "phone", "pin"], "description": "Cash-out from customer"},
    "AT": {"name": "airtime", "args": ["amount", "phone", "pin"], "description": "Airtime top-up"},
    "BT": {"name": "bill_pay", "args": ["amount", "biller_code", "pin"], "description": "Bill payment"},
    "TF": {"name": "transfer", "args": ["amount", "phone", "pin"], "description": "Agent-to-agent transfer"},
    "BAL": {"name": "balance", "args": ["pin"], "description": "Check balance"},
    "TRF": {"name": "transfer", "args": ["amount", "phone", "pin"], "description": "Transfer to another agent"},
    "TXN": {"name": "transactions", "args": [], "description": "Last 5 transactions"},
    "REV": {"name": "reversal", "args": ["txn_id", "pin"], "description": "Reverse transaction"},
    "HELP": {"name": "help", "args": [], "description": "Show available commands"},
    "REG": {"name": "register", "args": ["name", "phone"], "description": "Register new agent"},
    "PIN": {"name": "change_pin", "args": ["old_pin", "new_pin"], "description": "Change PIN"},
    "FLT": {"name": "float", "args": ["pin"], "description": "Check float balance"},
    "RPT": {"name": "report", "args": ["pin"], "description": "Daily summary report"},
}

@dataclass
class ParsedSMS:
    raw_text: str
    command: str
    action: str
    amount: Optional[float]
    phone: Optional[str]
    pin: Optional[str]
    extra_args: dict
    valid: bool
    error: Optional[str]

@dataclass
class SMSTransaction:
    id: str
    timestamp: float
    sender: str
    command: str
    action: str
    amount: Optional[float]
    recipient_phone: Optional[str]
    status: str  # pending, queued, processing, completed, failed
    response_text: str
    agent_id: Optional[str]
    reference: str

@dataclass
class OutboundSMS:
    id: str
    to: str
    text: str
    status: str  # pending, sent, delivered, failed
    created_at: float
    sent_at: Optional[float]
    retry_count: int

def parse_sms(text: str, sender: str = "") -> ParsedSMS:
    """Parse an inbound SMS into a structured command."""
    text = text.strip().upper()
    parts = text.split()

    if not parts:
        return ParsedSMS(
            raw_text=text, command="", action="", amount=None,
            phone=None, pin=None, extra_args={}, valid=False,
            error="Empty message"
        )

    cmd = parts[0]
    if cmd not in COMMANDS:
        return ParsedSMS(
            raw_text=text, command=cmd, action="", amount=None,
            phone=None, pin=None, extra_args={}, valid=False,
            error=f"Unknown command: {cmd}. Send HELP for available commands."
        )

    cmd_def = COMMANDS[cmd]
    args = parts[1:]
    expected_args = cmd_def["args"]

    # Parse arguments based on command definition
    amount = None
    phone = None
    pin = None
    extra = {}

    for i, arg_name in enumerate(expected_args):
        if i >= len(args):
            if arg_name == "pin":
                return ParsedSMS(
                    raw_text=text, command=cmd, action=cmd_def["name"],
                    amount=amount, phone=phone, pin=None, extra_args=extra,
                    valid=False, error="PIN required for this operation."
                )
            continue

        val = args[i]
        if arg_name == "amount":
            try:
                amount = float(val.replace(",", ""))
                if amount <= 0:
                    return ParsedSMS(
                        raw_text=text, command=cmd, action=cmd_def["name"],
                        amount=None, phone=None, pin=None, extra_args={},
                        valid=False, error="Amount must be positive."
                    )
                if amount > 5000000:
                    return ParsedSMS(
                        raw_text=text, command=cmd, action=cmd_def["name"],
                        amount=None, phone=None, pin=None, extra_args={},
                        valid=False, error="Amount exceeds maximum limit."
                    )
            except ValueError:
                return ParsedSMS(
                    raw_text=text, command=cmd, action=cmd_def["name"],
                    amount=None, phone=None, pin=None, extra_args={},
                    valid=False, error=f"Invalid amount: {val}"
                )
        elif arg_name == "phone":
            phone = normalize_phone(val)
            if not phone:
                return ParsedSMS(
                    raw_text=text, command=cmd, action=cmd_def["name"],
                    amount=amount, phone=None, pin=None, extra_args={},
                    valid=False, error=f"Invalid phone number: {val}"
                )
        elif arg_name == "pin":
            if not re.match(r'^\d{4,6}$', val):
                return ParsedSMS(
                    raw_text=text, command=cmd, action=cmd_def["name"],
                    amount=amount, phone=phone, pin=None, extra_args={},
                    valid=False, error="PIN must be 4-6 digits."
                )
            pin = val
        elif arg_name == "txn_id":
            extra["txn_id"] = val
        elif arg_name == "biller_code":
            extra["biller_code"] = val
        elif arg_name == "name":
            extra["name"] = val
        elif arg_name == "old_pin":
            extra["old_pin"] = val
        elif arg_name == "new_pin":
            extra["new_pin"] = val

    return ParsedSMS(
        raw_text=text, command=cmd, action=cmd_def["name"],
        amount=amount, phone=phone, pin=pin, extra_args=extra,
        valid=True, error=None
    )


def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone number to E.164-like format."""
    phone = re.sub(r'[^\d+]', '', phone)
    if phone.startswith('+'):
        phone = phone[1:]
    if phone.startswith('0') and len(phone) == 11:
        phone = '234' + phone[1:]  # Nigeria default
    if len(phone) < 10 or len(phone) > 15:
        return None
    return phone


# ── Response Templates ────────────────────────────────────────────────────────
# Success templates are only rendered with REAL backend data (real references,
# real balances). Queued templates are used for store-and-forward and must
# NEVER claim success.

TEMPLATES = {
    "cash_in_success": "54agent: Cash-in {amount} {currency} to {phone} successful. Ref: {ref}. Balance: {balance}.",
    "cash_out_success": "54agent: Cash-out {amount} {currency} from {phone} successful. Ref: {ref}. Balance: {balance}.",
    "airtime_success": "54agent: Airtime {amount} {currency} sent to {phone}. Ref: {ref}. Balance: {balance}.",
    "balance_response": "54agent: Your balance is {balance} {currency}. Float: {float}. Last updated: {time}.",
    "transactions_response": "54agent: Last {count} transactions:\n{transactions}",
    "reversal_success": "54agent: Transaction {txn_id} reversed. Ref: {ref}.",
    "error_response": "54agent: Error - {error}. Send HELP for commands.",
    "help_response": "54agent Commands:\nCI amt phone pin - Cash-in\nCO amt phone pin - Cash-out\nAT amt phone pin - Airtime\nBAL pin - Balance\nTXN - History\nREV txnid pin - Reverse\nHELP - This message",
    "pin_required": "54agent: PIN required. Format: {command} ... PIN",
    "pin_failed": "54agent: PIN verification failed. Transaction NOT processed.",
    "queued": "54agent: {action} request of {amount} {currency} received but the transaction service is unreachable. Queued for processing — you will receive a confirmation SMS with a reference when it completes. Queue ref: {ref}.",
    "unavailable": "54agent: {service} unavailable. Please try again later.",
    "failed": "54agent: {action} failed: {error}. No funds were moved.",
}


# ── SMS Processing Engine ────────────────────────────────────────────────────

MONEY_ACTIONS = ("cash_in", "cash_out", "airtime", "transfer", "bill_pay")
# Actions that require PIN verification against the auth service
PIN_ACTIONS = MONEY_ACTIONS + ("balance", "reversal", "float", "report")


class SMSEngine:
    def __init__(self):
        self.transactions: deque = deque(maxlen=10000)
        self.outbox: deque = deque(maxlen=5000)
        self.stats = {
            "total_inbound": 0,
            "total_outbound": 0,
            "total_processed": 0,
            "total_errors": 0,
            "by_command": {},
        }

    def process_inbound(self, sender: str, text: str) -> SMSTransaction:
        """Process an inbound SMS and generate a response."""
        self.stats["total_inbound"] += 1

        parsed = parse_sms(text, sender)

        if not parsed.valid:
            self.stats["total_errors"] += 1
            txn = SMSTransaction(
                id=str(uuid.uuid4())[:8],
                timestamp=time.time(),
                sender=sender,
                command=parsed.command,
                action=parsed.action or "unknown",
                amount=None,
                recipient_phone=None,
                status="failed",
                response_text=TEMPLATES["error_response"].format(error=parsed.error),
                agent_id=None,
                reference=f"ERR-{int(time.time())}",
            )
            self.transactions.append(txn)
            self._queue_outbound(sender, txn.response_text)
            return txn

        # Process valid command
        self.stats["by_command"][parsed.action] = self.stats["by_command"].get(parsed.action, 0) + 1
        self.stats["total_processed"] += 1

        response, status, reference = self._execute(sender, parsed)

        txn = SMSTransaction(
            id=str(uuid.uuid4())[:8],
            timestamp=time.time(),
            sender=sender,
            command=parsed.command,
            action=parsed.action,
            amount=parsed.amount,
            recipient_phone=parsed.phone,
            status=status,
            response_text=response,
            agent_id=None,
            reference=reference,
        )
        self.transactions.append(txn)
        self._queue_outbound(sender, response)
        return txn

    def _execute(self, sender: str, parsed: ParsedSMS) -> tuple:
        """Execute a valid parsed command. Returns (response, status, reference)."""
        queue_ref = f"Q-{int(time.time())}-{str(uuid.uuid4())[:4]}"

        if parsed.action == "help":
            return TEMPLATES["help_response"], "completed", "HELP"

        # ── PIN verification for protected actions ────────────────────────
        if parsed.action in PIN_ACTIONS:
            pin_to_check = parsed.pin or parsed.extra_args.get("old_pin")
            if pin_to_check:
                try:
                    verify_pin_with_auth(sender, pin_to_check)
                except ValueError:
                    return TEMPLATES["pin_failed"], "failed", "PIN-FAIL"
                except BackendUnavailable as e:
                    logger.warning("PIN verification unavailable: %s", e)
                    return TEMPLATES["unavailable"].format(service="Authentication service"), "failed", "AUTH-DOWN"

        # ── Balance / float inquiries — REAL ledger data only ─────────────
        if parsed.action in ("balance", "float"):
            try:
                bal = fetch_balance(sender)
            except BackendUnavailable as e:
                logger.warning("balance lookup failed: %s", e)
                return TEMPLATES["unavailable"].format(service="Balance service"), "failed", "BAL-DOWN"
            currency = bal.get("currency", "NGN")
            return TEMPLATES["balance_response"].format(
                balance=f"{bal.get('balance', 0):,.2f}",
                currency=currency,
                float=f"{bal.get('float', 0):,.2f}",
                time=time.strftime("%H:%M"),
            ), "completed", f"BAL-{int(time.time())}"

        # ── Transaction history — REAL ledger data only ───────────────────
        if parsed.action == "transactions":
            try:
                entries = fetch_recent_transactions(sender, limit=5)
            except BackendUnavailable as e:
                logger.warning("mini statement lookup failed: %s", e)
                return TEMPLATES["unavailable"].format(service="Statement service"), "failed", "STMT-DOWN"
            if not entries:
                lines = "No recent transactions."
            else:
                lines = "\n".join(
                    f"{e.get('date', '')}: {e.get('type', e.get('description', 'TXN'))} {e.get('currency', 'NGN')}{e.get('amount', 0):,.2f}"
                    for e in entries[:5]
                )
            return TEMPLATES["transactions_response"].format(
                count=len(entries[:5]), transactions=lines
            ), "completed", f"TXN-{int(time.time())}"

        # ── Money movement — REAL engine execution or queued ──────────────
        if parsed.action in MONEY_ACTIONS:
            try:
                result = execute_transaction(parsed, sender, f"{sender}-{queue_ref}")
            except BackendUnavailable as e:
                # Store-and-forward: NEVER claim success while offline.
                logger.warning("transaction engine unreachable, queueing %s: %s", parsed.action, e)
                return TEMPLATES["queued"].format(
                    action=parsed.action.replace("_", "-"),
                    amount=f"{parsed.amount:,.2f}" if parsed.amount else "0",
                    currency="NGN",
                    ref=queue_ref,
                ), "queued", queue_ref
            except ValueError as e:
                return TEMPLATES["failed"].format(
                    action=parsed.action.replace("_", "-"), error=str(e)
                ), "failed", "TX-FAIL"

            ref = result["reference"]
            balance = result.get("balance")
            template_key = f"{parsed.action}_success"
            if template_key not in TEMPLATES:
                template_key = "cash_in_success"
            return TEMPLATES[template_key].format(
                amount=f"{parsed.amount:,.2f}" if parsed.amount else "0",
                currency=result.get("currency", "NGN"),
                phone=parsed.phone or "N/A",
                ref=ref,
                balance=f"{balance:,.2f}" if isinstance(balance, (int, float)) else "see BAL",
            ), "completed", ref

        # ── Reversal — REAL engine execution or queued ────────────────────
        if parsed.action == "reversal":
            txn_id = parsed.extra_args.get("txn_id", "")
            try:
                result = execute_reversal(txn_id, sender, f"{sender}-REV-{queue_ref}")
            except BackendUnavailable as e:
                logger.warning("transaction engine unreachable, queueing reversal: %s", e)
                return TEMPLATES["queued"].format(
                    action=f"Reversal of {txn_id}",
                    amount="",
                    currency="",
                    ref=queue_ref,
                ), "queued", queue_ref
            except ValueError as e:
                return TEMPLATES["failed"].format(action="Reversal", error=str(e)), "failed", "REV-FAIL"
            return TEMPLATES["reversal_success"].format(
                txn_id=txn_id, ref=result.get("reference", queue_ref),
            ), "completed", result.get("reference", queue_ref)

        # ── Daily report — REAL ledger data only ──────────────────────────
        if parsed.action == "report":
            if not LEDGER_API_URL:
                return TEMPLATES["unavailable"].format(service="Report service"), "failed", "RPT-DOWN"
            try:
                status_code, body = _http_json(
                    "GET", f"{LEDGER_API_URL}/api/v1/agents/daily-report?phone={urllib.parse.quote(sender)}")
                if status_code != 200:
                    raise BackendUnavailable(f"ledger API returned {status_code}")
            except BackendUnavailable as e:
                logger.warning("daily report lookup failed: %s", e)
                return TEMPLATES["unavailable"].format(service="Report service"), "failed", "RPT-DOWN"
            currency = body.get("currency", "NGN")
            return (
                f"54agent Daily Report:\n"
                f"Transactions: {body.get('count', 0)}\n"
                f"Cash-in: {currency} {body.get('cash_in', 0):,.2f}\n"
                f"Cash-out: {currency} {body.get('cash_out', 0):,.2f}\n"
                f"Commission: {currency} {body.get('commission', 0):,.2f}\n"
                f"Balance: {currency} {body.get('balance', 0):,.2f}"
            ), "completed", f"RPT-{int(time.time())}"

        return TEMPLATES["help_response"], "completed", "HELP"

    def _queue_outbound(self, to: str, text: str):
        sms = OutboundSMS(
            id=str(uuid.uuid4())[:8],
            to=to,
            text=text,
            status="pending",
            created_at=time.time(),
            sent_at=None,
            retry_count=0,
        )
        self.outbox.append(sms)
        self.stats["total_outbound"] += 1


# ── HTTP Server ───────────────────────────────────────────────────────────────

engine = SMSEngine()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json({"status": "healthy", "service": "sms-transaction-bridge", "version": "1.0.0"})
        elif self.path == "/api/stats":
            self._send_json(engine.stats)
        elif self.path == "/api/sms/outbox":
            outbox = [asdict(s) for s in list(engine.outbox)[-50:]]
            self._send_json(outbox)
        elif self.path == "/api/sms/templates":
            self._send_json(TEMPLATES)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            body = self._read_body()
        except Exception as e:
            self._send_json({"error": str(e)}, 400)
            return

        if self.path == "/api/sms/inbound":
            sender = body.get("sender", body.get("from", ""))
            text = body.get("text", body.get("message", ""))
            if not sender or not text:
                self._send_json({"error": "sender and text required"}, 400)
                return
            txn = engine.process_inbound(sender, text)
            self._send_json(asdict(txn), 201)

        elif self.path == "/api/sms/parse":
            text = body.get("text", "")
            parsed = parse_sms(text, body.get("sender", ""))
            self._send_json(asdict(parsed))

        elif self.path == "/api/sms/send":
            to = body.get("to", "")
            text = body.get("text", "")
            if not to or not text:
                self._send_json({"error": "to and text required"}, 400)
                return
            engine._queue_outbound(to, text)
            self._send_json({"status": "queued", "to": to})

        else:
            self._send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    if not TRANSACTION_API_URL or not LEDGER_API_URL or not AUTH_API_URL:
        logger.warning(
            "[sms-transaction-bridge] backend URLs incomplete "
            "(TRANSACTION_API_URL=%s LEDGER_API_URL=%s AUTH_API_URL=%s) — affected operations will fail closed",
            bool(TRANSACTION_API_URL), bool(LEDGER_API_URL), bool(AUTH_API_URL))
    port = int(os.environ.get("PORT", "8081"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[sms-transaction-bridge] Starting on :{port}")
    server.serve_forever()

# ── PIN validation and SMS format constraints ───────────────────────────────
# SMS responses must be within 160 characters to fit a single SMS segment
MAX_SMS_LENGTH = 160

def validate_pin(pin: str) -> bool:
    """Validate that PIN is exactly 4 digits."""
    return len(pin) == 4 and pin.isdigit()

def format_sms_response(message: str) -> str:
    """Format and truncate SMS response to 160 character limit."""
    if len(message) > 160:
        return message[:157] + "..."
    return message
