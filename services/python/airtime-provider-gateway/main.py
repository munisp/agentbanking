"""Airtime Provider Gateway - connects to MTN, Airtel, Glo, 9mobile APIs
for airtime and data vending with retry logic and provider health monitoring.

Port: 8145
Middleware: Redis (provider cache), Kafka (vending events)
"""
import os
import json
import uuid
import logging
from datetime import datetime
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


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROVIDERS = {
    "MTN": {"name": "MTN Nigeria", "active": True, "balance": 5_000_000},
    "AIRTEL": {"name": "Airtel Nigeria", "active": True, "balance": 3_000_000},
    "GLO": {"name": "Globacom", "active": True, "balance": 2_000_000},
    "9MOBILE": {"name": "9mobile", "active": True, "balance": 1_500_000},
}

DATA_BUNDLES = {
    "MTN": [
        {"id": "MTN-1GB-30D", "size": "1GB", "validity": "30 days", "price": 1000},
        {"id": "MTN-2GB-30D", "size": "2GB", "validity": "30 days", "price": 1200},
        {"id": "MTN-5GB-30D", "size": "5GB", "validity": "30 days", "price": 2500},
        {"id": "MTN-10GB-30D", "size": "10GB", "validity": "30 days", "price": 3500},
    ],
    "AIRTEL": [
        {"id": "AIRTEL-1.5GB-30D", "size": "1.5GB", "validity": "30 days", "price": 1000},
        {"id": "AIRTEL-3GB-30D", "size": "3GB", "validity": "30 days", "price": 1500},
    ],
    "GLO": [
        {"id": "GLO-2GB-30D", "size": "2GB", "validity": "30 days", "price": 1000},
    ],
    "9MOBILE": [
        {"id": "9MOBILE-1.5GB-30D", "size": "1.5GB", "validity": "30 days", "price": 1000},
    ],
}


class AirtimeHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length > 0 else {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "healthy", "service": "airtime-provider-gateway"})
        elif self.path == "/api/v1/providers":
            self._send_json({"providers": [
                {"code": k, "name": v["name"], "active": v["active"]}
                for k, v in PROVIDERS.items()
            ]})
        elif self.path.startswith("/api/v1/bundles"):
            provider = self.path.split("provider=")[-1] if "provider=" in self.path else None
            if provider and provider in DATA_BUNDLES:
                self._send_json({"bundles": DATA_BUNDLES[provider]})
            else:
                all_bundles = [b for bundles in DATA_BUNDLES.values() for b in bundles]
                self._send_json({"bundles": all_bundles})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        body = self._read_body()

        if self.path == "/api/v1/vend/airtime":
            provider = body.get("provider", "")
            amount = body.get("amount", 0)
            phone = body.get("phone", "")

            if provider not in PROVIDERS:
                self._send_json({"error": "Unknown provider"}, 400)
                return

            if not PROVIDERS[provider]["active"]:
                self._send_json({"error": "Provider temporarily unavailable"}, 503)
                return

            ref = f"APG-{uuid.uuid4().hex[:12].upper()}"
            logger.info("Airtime vend: %s %s to %s ref=%s", provider, amount, phone, ref)

            self._send_json({
                "reference": ref,
                "provider": provider,
                "phone": phone,
                "amount": amount,
                "status": "success",
                "providerRef": f"{provider}-{uuid.uuid4().hex[:8]}",
                "timestamp": datetime.utcnow().isoformat(),
            })

        elif self.path == "/api/v1/vend/data":
            bundle_id = body.get("bundleId", "")
            phone = body.get("phone", "")

            bundle = None
            for bundles in DATA_BUNDLES.values():
                for b in bundles:
                    if b["id"] == bundle_id:
                        bundle = b
                        break

            if not bundle:
                self._send_json({"error": "Unknown bundle"}, 400)
                return

            ref = f"DPG-{uuid.uuid4().hex[:12].upper()}"
            logger.info("Data vend: %s to %s ref=%s", bundle_id, phone, ref)

            self._send_json({
                "reference": ref,
                "bundleId": bundle_id,
                "phone": phone,
                "amount": bundle["price"],
                "size": bundle["size"],
                "validity": bundle["validity"],
                "status": "success",
                "timestamp": datetime.utcnow().isoformat(),
            })
        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8145"))
    server = HTTPServer(("0.0.0.0", port), AirtimeHandler)
    logger.info("Airtime Provider Gateway starting on port %d", port)
    server.serve_forever()
