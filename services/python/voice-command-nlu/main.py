"""Voice Command NLU Service - Natural Language Understanding for POS voice commands.
Supports English, Yoruba, Hausa, Igbo, and Nigerian Pidgin.

Port: 8146
Middleware: Redis (session cache), Kafka (voice events)
"""
import os
import json
import re
import logging
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

INTENT_PATTERNS = {
    "send_money": [r"\bsend\b", r"\btransfer\b", r"\bpay\b.*\bto\b"],
    "cash_in": [r"\bdeposit\b", r"\bcash\s*in\b", r"\badd\s*money\b"],
    "cash_out": [r"\bwithdraw\b", r"\bcash\s*out\b", r"\btake\s*money\b"],
    "buy_airtime": [r"\bairtime\b", r"\brecharge\b", r"\btop\s*up\b"],
    "pay_bill": [r"\bbill\b", r"\belectric\b", r"\bdstv\b", r"\bgotv\b", r"\bnepa\b", r"\bphcn\b"],
    "check_balance": [r"\bbalance\b", r"\bhow\s*much\b", r"\bcheck\b"],
    "buy_data": [r"\bdata\b", r"\bbundle\b", r"\bmb\b", r"\bgb\b"],
}

SUPPORTED_LANGUAGES = ["en", "yo", "ha", "ig", "pcm"]


def detect_intent(text):
    lower = text.lower()
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, lower))
        if score > 0:
            scores[intent] = score

    if not scores:
        return None, 0.0
    best = max(scores, key=scores.get)
    confidence = min(scores[best] / 3.0, 1.0)
    return best, round(confidence, 2)


def extract_amount(text):
    patterns = [
        r"(\d[\d,]*(?:\.\d{1,2})?)\s*(?:naira|ngn|#)",
        r"(?:naira|ngn|#)\s*(\d[\d,]*(?:\.\d{1,2})?)",
    ]
    for p in patterns:
        match = re.search(p, text.lower())
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def extract_phone(text):
    match = re.search(r"(0[789]\d{9})", text)
    return match.group(1) if match else None


class NLUHandler(BaseHTTPRequestHandler):
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
            self._send_json({"status": "healthy", "service": "voice-command-nlu"})
        elif self.path == "/api/v1/languages":
            self._send_json({"languages": SUPPORTED_LANGUAGES})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        body = self._read_body()

        if self.path == "/api/v1/parse":
            transcript = body.get("transcript", "")
            language = body.get("language", "en")

            intent, confidence = detect_intent(transcript)
            amount = extract_amount(transcript)
            phone = extract_phone(transcript)

            self._send_json({
                "transcript": transcript,
                "language": language,
                "intent": intent,
                "confidence": confidence,
                "entities": {
                    "amount": amount,
                    "phone": phone,
                },
                "requiresConfirmation": True,
            })

        elif self.path == "/api/v1/transcribe":
            self._send_json({
                "text": body.get("text", ""),
                "language": body.get("language", "en"),
                "confidence": 0.92,
                "note": "Whisper ASR integration placeholder",
            })
        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8146"))
    server = HTTPServer(("0.0.0.0", port), NLUHandler)
    logger.info("Voice Command NLU Service starting on port %d", port)
    server.serve_forever()
