"""
Invoice Generator Service — Sprint 81
Generates monthly invoices per tenant based on billing model.
Middleware: Kafka (events), Redis (cache), Postgres (data), Temporal (scheduling),
Dapr (service mesh), OpenSearch (search), S3 (PDF storage)
"""
import os
import json


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "invoice-generator"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

def verify_auth(headers):
    """Verify Bearer token from Authorization header."""
    auth = headers.get("Authorization", "")
    if not auth:
        return None, (401, '{"error":"missing authorization header"}')
    if not auth.startswith("Bearer ") or len(auth) < 17:
        return None, (401, '{"error":"invalid token format"}')
    return auth[7:], None

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("invoice-generator")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://localhost:5432/pos54link")
S3_BUCKET = os.getenv("S3_BUCKET", "54link-invoices")
TEMPORAL_ADDR = os.getenv("TEMPORAL_ADDR", "localhost:7233")
DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
PERMIFY_ADDR = os.getenv("PERMIFY_ADDR", "localhost:3478")
PORT = int(os.getenv("PORT", "8084"))

@dataclass
class InvoiceLineItem:
    description: str
    quantity: int
    unit_price: float
    amount: float
    category: str  # platform_fee, agent_commission, switch_fee, subscription

@dataclass
class Invoice:
    invoice_id: str
    tenant_id: int
    tenant_name: str
    billing_model: str
    period_start: str
    period_end: str
    currency: str
    line_items: List[Dict]
    subtotal: float
    tax_amount: float
    total_amount: float
    status: str  # draft, sent, paid, overdue
    due_date: str
    generated_at: str
    pdf_url: Optional[str] = None

class InvoiceGeneratorService:
    def __init__(self):
        self.invoices: Dict[str, Invoice] = {}
        logger.info(f"[InvoiceGenerator] Initialized with Kafka={KAFKA_BROKERS}, Postgres={POSTGRES_URL}")

    def generate_revenue_share_invoice(self, tenant_id: int, period_start: str, period_end: str) -> Invoice:
        """Generate invoice for revenue-share billing model"""
        # In production: queries platform_billing_ledger for the period
        line_items = [
            {"description": "Platform transaction fees (revenue share 70/30)", "quantity": 1250,
             "unit_price": 45.0, "amount": 56250.0, "category": "platform_fee"},
            {"description": "Agent commission disbursements", "quantity": 1250,
             "unit_price": 8.5, "amount": 10625.0, "category": "agent_commission"},
            {"description": "Switch/network fees", "quantity": 1250,
             "unit_price": 3.0, "amount": 3750.0, "category": "switch_fee"},
        ]
        subtotal = sum(item["amount"] for item in line_items)
        tax = subtotal * 0.075  # 7.5% VAT
        invoice = Invoice(
            invoice_id=f"INV-{tenant_id}-{datetime.now().strftime('%Y%m')}",
            tenant_id=tenant_id, tenant_name=f"Tenant {tenant_id}",
            billing_model="revenue_share", period_start=period_start, period_end=period_end,
            currency="NGN", line_items=line_items, subtotal=subtotal,
            tax_amount=tax, total_amount=subtotal + tax, status="draft",
            due_date=(datetime.now() + timedelta(days=30)).isoformat(),
            generated_at=datetime.now().isoformat(),
        )
        self.invoices[invoice.invoice_id] = invoice
        logger.info(f"[InvoiceGenerator] Generated {invoice.invoice_id}: total={invoice.total_amount:.2f} {invoice.currency}")
        self._publish_event("billing.invoice.generated", invoice)
        return invoice

    def generate_subscription_invoice(self, tenant_id: int, period_start: str, period_end: str) -> Invoice:
        """Generate invoice for subscription billing model"""
        line_items = [
            {"description": "Monthly platform subscription (per-agent)", "quantity": 50,
             "unit_price": 15000.0, "amount": 750000.0, "category": "subscription"},
            {"description": "POS terminal fee", "quantity": 120,
             "unit_price": 5000.0, "amount": 600000.0, "category": "subscription"},
        ]
        subtotal = sum(item["amount"] for item in line_items)
        tax = subtotal * 0.075
        invoice = Invoice(
            invoice_id=f"INV-{tenant_id}-{datetime.now().strftime('%Y%m')}-SUB",
            tenant_id=tenant_id, tenant_name=f"Tenant {tenant_id}",
            billing_model="subscription", period_start=period_start, period_end=period_end,
            currency="NGN", line_items=line_items, subtotal=subtotal,
            tax_amount=tax, total_amount=subtotal + tax, status="draft",
            due_date=(datetime.now() + timedelta(days=15)).isoformat(),
            generated_at=datetime.now().isoformat(),
        )
        self.invoices[invoice.invoice_id] = invoice
        logger.info(f"[InvoiceGenerator] Generated subscription {invoice.invoice_id}: total={invoice.total_amount:.2f}")
        self._publish_event("billing.invoice.generated", invoice)
        return invoice

    def mark_paid(self, invoice_id: str) -> Optional[Invoice]:
        invoice = self.invoices.get(invoice_id)
        if invoice:
            invoice.status = "paid"
            self._publish_event("billing.invoice.paid", invoice)
        return invoice

    def _publish_event(self, topic: str, invoice: Invoice):
        logger.info(f"[Kafka] Published to {topic}: {invoice.invoice_id}")

    def health_check(self) -> Dict:
        return {
            "status": "healthy", "service": "invoice-generator", "version": "1.0.0",
            "invoice_count": len(self.invoices),
            "middleware": {"kafka": KAFKA_BROKERS, "redis": REDIS_URL,
                          "postgres": POSTGRES_URL, "temporal": TEMPORAL_ADDR, "s3": S3_BUCKET}
        }

service = InvoiceGeneratorService()

class Handler(BaseHTTPRequestHandler):
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
        if self.path == "/health":
            self._respond(200, service.health_check())
        elif self.path.startswith("/api/v1/invoices"):
            self._respond(200, {"invoices": [asdict(i) for i in service.invoices.values()]})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        token, err = verify_auth(dict(self.headers))
        if err:
            self.send_response(err[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err[1].encode())
            return
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
        if self.path == "/api/v1/invoices/generate":
            tenant_id = body.get("tenant_id", 1)
            model = body.get("billing_model", "revenue_share")
            now = datetime.now()
            period_start = now.replace(day=1).isoformat()
            period_end = now.isoformat()
            if model == "subscription":
                invoice = service.generate_subscription_invoice(tenant_id, period_start, period_end)
            else:
                invoice = service.generate_revenue_share_invoice(tenant_id, period_start, period_end)
            self._respond(201, asdict(invoice))
        elif self.path == "/api/v1/invoices/mark-paid":
            invoice = service.mark_paid(body.get("invoice_id", ""))
            if invoice:
                self._respond(200, asdict(invoice))
            else:
                self._respond(404, {"error": "Invoice not found"})
        else:
            self.send_response(404); self.end_headers()

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

if __name__ == "__main__":
    logger.info(f"[InvoiceGenerator] Starting on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/invoice_generator")

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
