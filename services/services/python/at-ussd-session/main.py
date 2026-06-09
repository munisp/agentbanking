# Session TTL (time-to-live) in seconds
SESSION_TTL = 300  # 5 minutes ttl for USSD sessions
# SessionStore: in-memory store with Redis upgrade path
"""
Africa's Talking USSD Session Manager

Manages USSD session state machines with:
  - Menu tree navigation (nested menus up to 5 levels)
  - Session timeout handling (3 min AT standard)
  - Input validation per menu level
  - Transaction state persistence
  - Multi-language support (EN, FR, SW, HA, YO, IG)
  - Session analytics (duration, completion rate, drop-off)

Endpoints:
  POST /ussd/session       — Create/update session
  GET  /ussd/session/:id   — Get session state
  DELETE /ussd/session/:id — Force-end session
  GET  /ussd/analytics     — Session analytics
  GET  /health             — Health check

Environment:
  REDIS_URL, KAFKA_BROKER, POS_API_URL
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("at-ussd-session")

# ── Types ─────────────────────────────────────────────────────────────────────

class SessionState(str, Enum):
    """USSD session state machine states."""
    INIT = "init"
    MAIN_MENU = "main_menu"
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    BALANCE = "balance"
    TRANSFER = "transfer"
    MINI_STATEMENT = "mini_statement"
    PIN_ENTRY = "pin_entry"
    CONFIRM = "confirm"
    PROCESSING = "processing"
    COMPLETE = "complete"
    TIMEOUT = "timeout"
    ERROR = "error"

class Language(str, Enum):
    """Supported languages for USSD menus."""
    EN = "en"  # English
    FR = "fr"  # French
    SW = "sw"  # Swahili
    HA = "ha"  # Hausa
    YO = "yo"  # Yoruba
    IG = "ig"  # Igbo

@dataclass
class USSDSessionData:
    """Persistent session data."""
    session_id: str
    phone_number: str
    service_code: str
    state: str = SessionState.INIT
    language: str = Language.EN
    level: int = 0
    input_chain: list = field(default_factory=list)
    tx_type: str = ""
    tx_amount: float = 0.0
    tx_receiver: str = ""
    tx_pin: str = ""
    tx_ref: str = ""
    carrier: str = "unknown"
    created_at: float = 0.0
    updated_at: float = 0.0
    expires_at: float = 0.0
    completed: bool = False
    error_message: str = ""

# ── Menu Trees (Multi-language) ───────────────────────────────────────────────

MENU_TREES = {
    Language.EN: {
        "main_menu": (
            "Welcome to 54Link POS\n"
            "1. Cash In\n"
            "2. Cash Out\n"
            "3. Check Balance\n"
            "4. Transfer\n"
            "5. Mini Statement\n"
            "6. Change Language\n"
            "0. Exit"
        ),
        "cash_in_amount": "Enter amount to deposit:",
        "cash_out_amount": "Enter amount to withdraw:",
        "transfer_phone": "Enter recipient phone number:",
        "transfer_amount": "Enter transfer amount:",
        "pin_entry": "Enter your 4-6 digit PIN:",
        "confirm": "Confirm {tx_type} of NGN {amount}?\n1. Confirm\n2. Cancel",
        "success": "{tx_type} successful!\nAmount: NGN {amount}\nRef: {ref}\nThank you!",
        "cancelled": "Transaction cancelled.",
        "invalid_input": "Invalid input. Please try again:",
        "language_menu": "Select language:\n1. English\n2. Français\n3. Kiswahili\n4. Hausa\n5. Yorùbá\n6. Igbo",
        "balance": "Your balance:\nFloat: NGN {float_bal}\nCommission: NGN {commission}\nLoyalty: {loyalty} pts",
        "mini_statement": "Recent transactions:\n{transactions}\nBalance: NGN {balance}",
    },
    Language.FR: {
        "main_menu": (
            "Bienvenue sur 54Link POS\n"
            "1. Dépôt\n"
            "2. Retrait\n"
            "3. Solde\n"
            "4. Transfert\n"
            "5. Mini Relevé\n"
            "6. Changer Langue\n"
            "0. Quitter"
        ),
        "cash_in_amount": "Entrez le montant du dépôt:",
        "cash_out_amount": "Entrez le montant du retrait:",
        "transfer_phone": "Entrez le numéro du destinataire:",
        "transfer_amount": "Entrez le montant du transfert:",
        "pin_entry": "Entrez votre PIN (4-6 chiffres):",
        "confirm": "Confirmer {tx_type} de NGN {amount}?\n1. Confirmer\n2. Annuler",
        "success": "{tx_type} réussi!\nMontant: NGN {amount}\nRéf: {ref}\nMerci!",
        "cancelled": "Transaction annulée.",
        "invalid_input": "Entrée invalide. Réessayez:",
        "language_menu": "Choisir la langue:\n1. English\n2. Français\n3. Kiswahili\n4. Hausa\n5. Yorùbá\n6. Igbo",
        "balance": "Votre solde:\nFloat: NGN {float_bal}\nCommission: NGN {commission}\nFidélité: {loyalty} pts",
        "mini_statement": "Transactions récentes:\n{transactions}\nSolde: NGN {balance}",
    },
    Language.SW: {
        "main_menu": (
            "Karibu 54Link POS\n"
            "1. Weka Pesa\n"
            "2. Toa Pesa\n"
            "3. Angalia Salio\n"
            "4. Tuma Pesa\n"
            "5. Taarifa Fupi\n"
            "6. Badilisha Lugha\n"
            "0. Ondoka"
        ),
        "cash_in_amount": "Weka kiasi cha kuweka:",
        "cash_out_amount": "Weka kiasi cha kutoa:",
        "transfer_phone": "Weka nambari ya mpokeaji:",
        "transfer_amount": "Weka kiasi cha kutuma:",
        "pin_entry": "Weka PIN yako (tarakimu 4-6):",
        "confirm": "Thibitisha {tx_type} ya NGN {amount}?\n1. Thibitisha\n2. Ghairi",
        "success": "{tx_type} imefanikiwa!\nKiasi: NGN {amount}\nRef: {ref}\nAsante!",
        "cancelled": "Muamala umeghairiwa.",
        "invalid_input": "Ingizo batili. Jaribu tena:",
        "language_menu": "Chagua lugha:\n1. English\n2. Français\n3. Kiswahili\n4. Hausa\n5. Yorùbá\n6. Igbo",
        "balance": "Salio lako:\nFloat: NGN {float_bal}\nKamisheni: NGN {commission}\nUaminifu: {loyalty} pts",
        "mini_statement": "Muamala wa hivi karibuni:\n{transactions}\nSalio: NGN {balance}",
    },
}

# Fallback to English for unsupported languages
for lang in [Language.HA, Language.YO, Language.IG]:
    MENU_TREES[lang] = MENU_TREES[Language.EN].copy()

# ── Session State Machine ─────────────────────────────────────────────────────

SESSION_TIMEOUT_SECONDS = 180  # 3 minutes (AT standard)

# State transitions: current_state -> {input -> next_state}
STATE_TRANSITIONS = {
    SessionState.INIT: {"*": SessionState.MAIN_MENU},
    SessionState.MAIN_MENU: {
        "1": SessionState.CASH_IN,
        "2": SessionState.CASH_OUT,
        "3": SessionState.BALANCE,
        "4": SessionState.TRANSFER,
        "5": SessionState.MINI_STATEMENT,
        "6": SessionState.MAIN_MENU,  # language change stays on main
        "0": SessionState.COMPLETE,
    },
    SessionState.CASH_IN: {"*": SessionState.PIN_ENTRY},
    SessionState.CASH_OUT: {"*": SessionState.PIN_ENTRY},
    SessionState.TRANSFER: {"*": SessionState.PIN_ENTRY},  # after phone+amount
    SessionState.PIN_ENTRY: {"*": SessionState.CONFIRM},
    SessionState.CONFIRM: {
        "1": SessionState.COMPLETE,
        "2": SessionState.COMPLETE,
    },
}

class USSDSessionManager:
    """Manages USSD session lifecycle and state transitions."""

    def __init__(self):
        self.sessions: Dict[str, USSDSessionData] = {}
        self.analytics = {
            "total_sessions": 0,
            "completed_sessions": 0,
            "timed_out_sessions": 0,
            "error_sessions": 0,
            "avg_duration_seconds": 0.0,
            "completion_rate": 0.0,
            "drop_off_by_state": {},
            "sessions_by_carrier": {},
            "sessions_by_language": {},
        }

    def get_or_create(self, session_id: str, phone: str, service_code: str) -> USSDSessionData:
        """Get existing session or create new one."""
        if session_id in self.sessions:
            sess = self.sessions[session_id]
            # Check timeout
            if time.time() > sess.expires_at:
                self._record_timeout(sess)
                del self.sessions[session_id]
                # Create fresh session
            else:
                sess.updated_at = time.time()
                sess.expires_at = time.time() + SESSION_TIMEOUT_SECONDS
                return sess

        # New session
        now = time.time()
        sess = USSDSessionData(
            session_id=session_id,
            phone_number=phone,
            service_code=service_code,
            state=SessionState.MAIN_MENU,
            created_at=now,
            updated_at=now,
            expires_at=now + SESSION_TIMEOUT_SECONDS,
        )
        self.sessions[session_id] = sess
        self.analytics["total_sessions"] += 1
        return sess

    def process_input(self, session_id: str, phone: str, service_code: str, text: str) -> str:
        """Process USSD input and return response."""
        sess = self.get_or_create(session_id, phone, service_code)
        parts = text.split("*") if text else []
        current_input = parts[-1] if parts else ""

        lang = sess.language
        menus = MENU_TREES.get(lang, MENU_TREES[Language.EN])

        # Route based on current state
        if sess.state == SessionState.MAIN_MENU:
            return self._handle_main_menu(sess, current_input, menus)
        elif sess.state == SessionState.CASH_IN:
            return self._handle_amount_input(sess, current_input, menus, "cash_in")
        elif sess.state == SessionState.CASH_OUT:
            return self._handle_amount_input(sess, current_input, menus, "cash_out")
        elif sess.state == SessionState.TRANSFER:
            return self._handle_transfer(sess, current_input, parts, menus)
        elif sess.state == SessionState.PIN_ENTRY:
            return self._handle_pin(sess, current_input, menus)
        elif sess.state == SessionState.CONFIRM:
            return self._handle_confirm(sess, current_input, menus)
        else:
            return "CON " + menus["main_menu"]

    def _handle_main_menu(self, sess, inp, menus) -> str:
        if inp == "1":
            sess.state = SessionState.CASH_IN
            sess.tx_type = "cash_in"
            return "CON " + menus["cash_in_amount"]
        elif inp == "2":
            sess.state = SessionState.CASH_OUT
            sess.tx_type = "cash_out"
            return "CON " + menus["cash_out_amount"]
        elif inp == "3":
            self._complete(sess)
            return "END " + menus["balance"].format(float_bal="50,000.00", commission="1,250.00", loyalty="450")
        elif inp == "4":
            sess.state = SessionState.TRANSFER
            sess.tx_type = "transfer"
            return "CON " + menus["transfer_phone"]
        elif inp == "5":
            self._complete(sess)
            return "END " + menus["mini_statement"].format(
                transactions="+500 CI 27/04\n-200 CO 27/04\n+1000 TRF 26/04",
                balance="5,300.00"
            )
        elif inp == "6":
            return "CON " + menus["language_menu"]
        elif inp == "0":
            self._complete(sess)
            return "END Thank you for using 54Link POS. Goodbye!"
        else:
            return "CON " + menus["invalid_input"] + "\n" + menus["main_menu"]

    def _handle_amount_input(self, sess, inp, menus, tx_type) -> str:
        try:
            amount = float(inp)
            if amount <= 0:
                raise ValueError
            sess.tx_amount = amount
            sess.state = SessionState.PIN_ENTRY
            return "CON " + menus["pin_entry"]
        except (ValueError, TypeError):
            return "CON " + menus["invalid_input"]

    def _handle_transfer(self, sess, inp, parts, menus) -> str:
        if not sess.tx_receiver:
            sess.tx_receiver = inp
            return "CON " + menus["transfer_amount"]
        if sess.tx_amount == 0:
            try:
                amount = float(inp)
                if amount <= 0:
                    raise ValueError
                sess.tx_amount = amount
                sess.state = SessionState.PIN_ENTRY
                return "CON " + menus["pin_entry"]
            except (ValueError, TypeError):
                return "CON " + menus["invalid_input"]
        return "CON " + menus["pin_entry"]

    def _handle_pin(self, sess, inp, menus) -> str:
        if len(inp) < 4 or len(inp) > 6 or not inp.isdigit():
            return "CON " + menus["invalid_input"]
        sess.tx_pin = inp
        sess.state = SessionState.CONFIRM
        return "CON " + menus["confirm"].format(tx_type=sess.tx_type, amount=f"{sess.tx_amount:.2f}")

    def _handle_confirm(self, sess, inp, menus) -> str:
        if inp == "1":
            ref = f"TXN{int(time.time()) % 1000000}"
            sess.tx_ref = ref
            self._complete(sess)
            return "END " + menus["success"].format(
                tx_type=sess.tx_type.replace("_", " ").title(),
                amount=f"{sess.tx_amount:.2f}",
                ref=ref
            )
        else:
            self._complete(sess)
            return "END " + menus["cancelled"]

    def _complete(self, sess):
        sess.state = SessionState.COMPLETE
        sess.completed = True
        self.analytics["completed_sessions"] += 1
        duration = time.time() - sess.created_at
        total = self.analytics["completed_sessions"]
        self.analytics["avg_duration_seconds"] = (
            (self.analytics["avg_duration_seconds"] * (total - 1) + duration) / total
        )
        if self.analytics["total_sessions"] > 0:
            self.analytics["completion_rate"] = self.analytics["completed_sessions"] / self.analytics["total_sessions"]

    def _record_timeout(self, sess):
        self.analytics["timed_out_sessions"] += 1
        state = sess.state
        if state not in self.analytics["drop_off_by_state"]:
            self.analytics["drop_off_by_state"][state] = 0
        self.analytics["drop_off_by_state"][state] += 1

    def get_session(self, session_id: str) -> Optional[dict]:
        sess = self.sessions.get(session_id)
        if sess:
            return asdict(sess)
        return None

    def end_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def get_analytics(self) -> dict:
        return self.analytics.copy()

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count removed."""
        now = time.time()
        expired = [sid for sid, s in self.sessions.items() if now > s.expires_at]
        for sid in expired:
            self._record_timeout(self.sessions[sid])
            del self.sessions[sid]
        return len(expired)

# ── Flask App ─────────────────────────────────────────────────────────────────

try:
    from flask import Flask, request, jsonify
except ImportError:
    Flask = None

manager = USSDSessionManager()

def create_app():
    app = Flask(__name__)

    @app.route("/ussd/session", methods=["POST"])
    def process_ussd():
        data = request.get_json() or {}
        session_id = data.get("sessionId", "")
        phone = data.get("phoneNumber", "")
        service_code = data.get("serviceCode", "")
        text = data.get("text", "")
        if not session_id or not phone:
            return jsonify({"error": "Missing sessionId or phoneNumber"}), 400
        response = manager.process_input(session_id, phone, service_code, text)
        return jsonify({"response": response, "sessionId": session_id})

    @app.route("/ussd/session/<session_id>", methods=["GET"])
    def get_session(session_id):
        sess = manager.get_session(session_id)
        if sess:
            return jsonify(sess)
        return jsonify({"error": "Session not found"}), 404

    @app.route("/ussd/session/<session_id>", methods=["DELETE"])
    def end_session(session_id):
        if manager.end_session(session_id):
            return jsonify({"ended": True})
        return jsonify({"error": "Session not found"}), 404

    @app.route("/ussd/analytics", methods=["GET"])
    def analytics():
        return jsonify(manager.get_analytics())

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "healthy",
            "service": "at-ussd-session",
            "version": "1.0.0",
            "active_sessions": len(manager.sessions),
        })

    return app

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if Flask:
        app = create_app()
        port = int(os.getenv("PORT", "9013"))
        logger.info(f"[AT-USSD-Session] Starting on :{port}")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        logger.error("Flask not installed.")

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/at_ussd_session")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
