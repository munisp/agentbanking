"""Carrier Billing Integration — Sprint 76
Track data/SMS costs per carrier per agent, billing reconciliation
"""
import json, time, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
from threading import Lock

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


SERVICE_NAME = "carrier-billing"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 9115

class BillingService:
    def __init__(self):
        self.lock = Lock()
        self.records = []
        self.agent_totals = defaultdict(lambda: defaultdict(float))
        self.carrier_totals = defaultdict(lambda: defaultdict(float))

    def record_usage(self, agent_id, carrier, usage_type, quantity, cost_usd, cost_local, currency):
        with self.lock:
            record = {
                "id": f"BILL-{int(time.time()*1000)}-{len(self.records)}",
                "agentId": agent_id, "carrier": carrier, "type": usage_type,
                "quantity": quantity, "costUsd": cost_usd, "costLocal": cost_local,
                "currency": currency, "timestamp": int(time.time() * 1000),
            }
            self.records.append(record)
            self.agent_totals[agent_id][f"{carrier}_{usage_type}"] += cost_usd
            self.agent_totals[agent_id]["total"] += cost_usd
            self.carrier_totals[carrier][usage_type] += cost_usd
            self.carrier_totals[carrier]["total"] += cost_usd
            return record

    def get_agent_summary(self, agent_id):
        with self.lock:
            return dict(self.agent_totals.get(agent_id, {}))

    def get_carrier_summary(self):
        with self.lock:
            return {k: dict(v) for k, v in self.carrier_totals.items()}

    def get_records(self, limit=100):
        with self.lock:
            return self.records[-limit:]

billing = BillingService()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "healthy", "records": len(billing.records)})
        elif self.path.startswith("/api/billing/carrier-summary"):
            self._json(billing.get_carrier_summary())
        elif self.path.startswith("/api/billing/agent/"):
            agent_id = self.path.split("/")[-1]
            self._json(billing.get_agent_summary(agent_id))
        elif self.path.startswith("/api/billing/records"):
            self._json(billing.get_records())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/billing/record":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            result = billing.record_usage(body["agentId"], body["carrier"], body["type"], body.get("quantity", 1), body.get("costUsd", 0), body.get("costLocal", 0), body.get("currency", "USD"))
            self._json(result)
        else:
            self.send_error(404)

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    print(f"[{SERVICE_NAME}] v{SERVICE_VERSION} listening on :{port}")
    HTTPServer(("", port), Handler).serve_forever()
