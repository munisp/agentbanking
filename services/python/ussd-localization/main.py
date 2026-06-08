import os
"""USSD Menu Localization — Sprint 76
Multi-language USSD menus: English, French, Swahili, Hausa, Yoruba
"""
import json, os
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

SERVICE_NAME = "ussd-localization"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 9109

TRANSLATIONS = {
    "en": {
        "welcome": "Welcome to 54Link POS",
        "select_option": "Select an option:",
        "cash_in": "1. Cash In",
        "cash_out": "2. Cash Out",
        "balance": "3. Balance Inquiry",
        "transfer": "4. Transfer",
        "airtime": "5. Airtime Purchase",
        "bills": "6. Bill Payment",
        "enter_amount": "Enter amount:",
        "enter_phone": "Enter phone number:",
        "enter_pin": "Enter PIN:",
        "confirm": "Confirm transaction? (1=Yes, 2=No)",
        "success": "Transaction successful!",
        "failed": "Transaction failed. Please try again.",
        "insufficient_funds": "Insufficient funds.",
        "invalid_input": "Invalid input. Please try again.",
        "session_expired": "Session expired. Please dial again.",
        "receipt": "Ref: {ref}\nAmount: {currency} {amount}\nDate: {date}",
        "thank_you": "Thank you for using 54Link!",
    },
    "fr": {
        "welcome": "Bienvenue sur 54Link POS",
        "select_option": "Choisissez une option:",
        "cash_in": "1. Depot",
        "cash_out": "2. Retrait",
        "balance": "3. Consultation de solde",
        "transfer": "4. Transfert",
        "airtime": "5. Achat de credit",
        "bills": "6. Paiement de facture",
        "enter_amount": "Entrez le montant:",
        "enter_phone": "Entrez le numero de telephone:",
        "enter_pin": "Entrez votre PIN:",
        "confirm": "Confirmer la transaction? (1=Oui, 2=Non)",
        "success": "Transaction reussie!",
        "failed": "Transaction echouee. Veuillez reessayer.",
        "insufficient_funds": "Fonds insuffisants.",
        "invalid_input": "Saisie invalide. Veuillez reessayer.",
        "session_expired": "Session expiree. Veuillez recomposer.",
        "receipt": "Ref: {ref}\nMontant: {currency} {amount}\nDate: {date}",
        "thank_you": "Merci d'utiliser 54Link!",
    },
    "sw": {
        "welcome": "Karibu 54Link POS",
        "select_option": "Chagua chaguo:",
        "cash_in": "1. Weka Pesa",
        "cash_out": "2. Toa Pesa",
        "balance": "3. Angalia Salio",
        "transfer": "4. Tuma Pesa",
        "airtime": "5. Nunua Muda wa Maongezi",
        "bills": "6. Lipa Bili",
        "enter_amount": "Weka kiasi:",
        "enter_phone": "Weka nambari ya simu:",
        "enter_pin": "Weka PIN:",
        "confirm": "Thibitisha muamala? (1=Ndiyo, 2=Hapana)",
        "success": "Muamala umefanikiwa!",
        "failed": "Muamala umeshindwa. Tafadhali jaribu tena.",
        "insufficient_funds": "Salio haitoshi.",
        "invalid_input": "Ingizo batili. Tafadhali jaribu tena.",
        "session_expired": "Kipindi kimeisha. Tafadhali piga tena.",
        "receipt": "Ref: {ref}\nKiasi: {currency} {amount}\nTarehe: {date}",
        "thank_you": "Asante kwa kutumia 54Link!",
    },
    "ha": {
        "welcome": "Barka da zuwa 54Link POS",
        "select_option": "Zabi wani zabin:",
        "cash_in": "1. Saka Kudi",
        "cash_out": "2. Cire Kudi",
        "balance": "3. Duba Ragowar Kudi",
        "transfer": "4. Aikawa Kudi",
        "airtime": "5. Sayen Katin Waya",
        "bills": "6. Biyan Kudin Wuta/Ruwa",
        "enter_amount": "Shigar da adadin kudi:",
        "enter_phone": "Shigar da lambar waya:",
        "enter_pin": "Shigar da PIN:",
        "confirm": "Tabbatar da ciniki? (1=Eh, 2=A'a)",
        "success": "Ciniki ya yi nasara!",
        "failed": "Ciniki bai yi nasara ba. Da fatan za a sake gwadawa.",
        "insufficient_funds": "Kudin bai isa ba.",
        "invalid_input": "Shigarwar ba daidai ba. Da fatan za a sake gwadawa.",
        "session_expired": "Lokaci ya kare. Da fatan za a sake bugawa.",
        "receipt": "Ref: {ref}\nAdadi: {currency} {amount}\nRana: {date}",
        "thank_you": "Na gode da amfani da 54Link!",
    },
    "yo": {
        "welcome": "Kaabo si 54Link POS",
        "select_option": "Yan aṣayan kan:",
        "cash_in": "1. Fi Owo Si",
        "cash_out": "2. Gba Owo Jade",
        "balance": "3. Wo Iye Owo",
        "transfer": "4. Firanṣe Owo",
        "airtime": "5. Ra Akoko Ipe",
        "bills": "6. San Owo Inawo",
        "enter_amount": "Tẹ iye owo:",
        "enter_phone": "Tẹ nọmba foonu:",
        "enter_pin": "Tẹ PIN:",
        "confirm": "Jẹrisi idunadura? (1=Bẹẹni, 2=Rara)",
        "success": "Idunadura ti ṣaṣeyọri!",
        "failed": "Idunadura ko ṣaṣeyọri. Jọwọ gbiyanju lẹẹkansi.",
        "insufficient_funds": "Owo ko to.",
        "invalid_input": "Titẹ ko tọ. Jọwọ gbiyanju lẹẹkansi.",
        "session_expired": "Akoko ti pari. Jọwọ pe lẹẹkansi.",
        "receipt": "Ref: {ref}\nIye: {currency} {amount}\nOjọ: {date}",
        "thank_you": "E ṣe fun lilo 54Link!",
    },
}

COUNTRY_DEFAULT_LOCALE = {"NG": "en", "KE": "sw", "SN": "fr", "GH": "en", "ZA": "en"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "healthy", "locales": list(TRANSLATIONS.keys())})
        elif self.path.startswith("/api/locale/"):
            locale = self.path.split("/")[-1]
            if locale in TRANSLATIONS:
                self._json(TRANSLATIONS[locale])
            else:
                self._json(TRANSLATIONS["en"])
        elif self.path.startswith("/api/locales"):
            self._json({"locales": list(TRANSLATIONS.keys()), "countryDefaults": COUNTRY_DEFAULT_LOCALE})
        elif self.path.startswith("/api/menu/"):
            parts = self.path.split("/")
            locale = parts[-1] if len(parts) > 3 else "en"
            t = TRANSLATIONS.get(locale, TRANSLATIONS["en"])
            menu = f"CON {t['welcome']}\n{t['select_option']}\n{t['cash_in']}\n{t['cash_out']}\n{t['balance']}\n{t['transfer']}\n{t['airtime']}\n{t['bills']}"
            self._json({"locale": locale, "menu": menu})
        else:
            self.send_error(404)

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    print(f"[{SERVICE_NAME}] v{SERVICE_VERSION} listening on :{port}")
    HTTPServer(("", port), Handler).serve_forever()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/ussd_localization")

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
