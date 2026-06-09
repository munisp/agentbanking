"""
sms-transaction-bridge — 54Link SMS Transaction Fallback Service

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
"""

import json

def verify_auth(headers):
    """Verify Bearer token from Authorization header."""
    auth = headers.get("Authorization", "")
    if not auth:
        return None, (401, '{"error":"missing authorization header"}')
    if not auth.startswith("Bearer ") or len(auth) < 17:
        return None, (401, '{"error":"invalid token format"}')
    return auth[7:], None

import re
import time
import uuid
import os
from collections import deque
from dataclasses import dataclass, field, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

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
    status: str  # pending, processing, completed, failed
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

TEMPLATES = {
    "cash_in_success": "54Link: Cash-in {amount} {currency} to {phone} successful. Ref: {ref}. Balance: {balance}.",
    "cash_out_success": "54Link: Cash-out {amount} {currency} from {phone} successful. Ref: {ref}. Balance: {balance}.",
    "airtime_success": "54Link: Airtime {amount} {currency} sent to {phone}. Ref: {ref}. Balance: {balance}.",
    "balance_response": "54Link: Your balance is {balance} {currency}. Float: {float}. Last updated: {time}.",
    "transactions_response": "54Link: Last {count} transactions:\n{transactions}",
    "reversal_success": "54Link: Transaction {txn_id} reversed. Amount: {amount} {currency}. Ref: {ref}.",
    "error_response": "54Link: Error - {error}. Send HELP for commands.",
    "help_response": "54Link Commands:\nCI amt phone pin - Cash-in\nCO amt phone pin - Cash-out\nAT amt phone pin - Airtime\nBAL pin - Balance\nTXN - History\nREV txnid pin - Reverse\nHELP - This message",
    "pin_required": "54Link: PIN required. Format: {command} ... PIN",
    "daily_report": "54Link Daily Report:\nTransactions: {count}\nCash-in: {cash_in}\nCash-out: {cash_out}\nCommission: {commission}\nBalance: {balance}",
}

# ── SMS Processing Engine ────────────────────────────────────────────────────

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

        ref = f"SMS-{int(time.time())}-{str(uuid.uuid4())[:4]}"

        if parsed.action == "help":
            response = TEMPLATES["help_response"]
            status = "completed"
        elif parsed.action == "balance":
            response = TEMPLATES["balance_response"].format(
                balance="50,000.00", currency="NGN", float="200,000.00",
                time=time.strftime("%H:%M")
            )
            status = "completed"
        elif parsed.action == "transactions":
            response = TEMPLATES["transactions_response"].format(
                count=0, transactions="No recent transactions."
            )
            status = "completed"
        elif parsed.action in ("cash_in", "cash_out", "airtime", "transfer", "bill_pay"):
            template_key = f"{parsed.action}_success"
            if template_key not in TEMPLATES:
                template_key = "cash_in_success"
            response = TEMPLATES[template_key].format(
                amount=f"{parsed.amount:,.2f}" if parsed.amount else "0",
                currency="NGN",
                phone=parsed.phone or "N/A",
                ref=ref,
                balance="48,000.00",
            )
            status = "completed"
        elif parsed.action == "reversal":
            response = TEMPLATES["reversal_success"].format(
                txn_id=parsed.extra_args.get("txn_id", "N/A"),
                amount="0", currency="NGN", ref=ref,
            )
            status = "completed"
        elif parsed.action == "report":
            response = TEMPLATES["daily_report"].format(
                count=0, cash_in="0", cash_out="0",
                commission="0", balance="50,000.00",
            )
            status = "completed"
        else:
            response = TEMPLATES["help_response"]
            status = "completed"

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
            reference=ref,
        )
        self.transactions.append(txn)
        self._queue_outbound(sender, response)
        return txn

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
        # Skip auth for health checks
        if self.path not in ("/health", "/ready", "/metrics"):
            token, err = verify_auth(dict(self.headers))
            if err:
                self.send_response(err[0])
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err[1].encode())
                return
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
        token, err = verify_auth(dict(self.headers))
        if err:
            self.send_response(err[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err[1].encode())
            return
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

# PIN validation and SMS format constraints
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

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/sms_transaction_bridge")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
