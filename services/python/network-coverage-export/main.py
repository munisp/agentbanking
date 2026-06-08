import os
"""Network Coverage Map Data Export — Sprint 76
CSV/JSON export of coverage data per region/carrier
"""
import json, time, os, csv, io
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

SERVICE_NAME = "network-coverage-export"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 9116

COVERAGE_DATA = [
    {"region": "Lagos", "country": "NG", "carrier": "MTN", "coverage_2g": 99, "coverage_3g": 95, "coverage_4g": 85, "coverage_5g": 15, "population_covered_pct": 98, "towers": 2450},
    {"region": "Lagos", "country": "NG", "carrier": "Airtel", "coverage_2g": 98, "coverage_3g": 92, "coverage_4g": 80, "coverage_5g": 10, "population_covered_pct": 95, "towers": 1980},
    {"region": "Lagos", "country": "NG", "carrier": "Glo", "coverage_2g": 95, "coverage_3g": 85, "coverage_4g": 65, "coverage_5g": 0, "population_covered_pct": 88, "towers": 1450},
    {"region": "Lagos", "country": "NG", "carrier": "9mobile", "coverage_2g": 92, "coverage_3g": 78, "coverage_4g": 55, "coverage_5g": 0, "population_covered_pct": 82, "towers": 980},
    {"region": "Nairobi", "country": "KE", "carrier": "Safaricom", "coverage_2g": 99, "coverage_3g": 97, "coverage_4g": 90, "coverage_5g": 25, "population_covered_pct": 99, "towers": 3200},
    {"region": "Nairobi", "country": "KE", "carrier": "Airtel_KE", "coverage_2g": 96, "coverage_3g": 88, "coverage_4g": 72, "coverage_5g": 5, "population_covered_pct": 90, "towers": 1800},
    {"region": "Accra", "country": "GH", "carrier": "MTN_GH", "coverage_2g": 98, "coverage_3g": 93, "coverage_4g": 82, "coverage_5g": 8, "population_covered_pct": 96, "towers": 1650},
    {"region": "Accra", "country": "GH", "carrier": "Vodafone_GH", "coverage_2g": 97, "coverage_3g": 90, "coverage_4g": 75, "coverage_5g": 5, "population_covered_pct": 92, "towers": 1400},
    {"region": "Dakar", "country": "SN", "carrier": "Orange_SN", "coverage_2g": 97, "coverage_3g": 90, "coverage_4g": 78, "coverage_5g": 3, "population_covered_pct": 94, "towers": 1200},
    {"region": "Johannesburg", "country": "ZA", "carrier": "MTN_ZA", "coverage_2g": 99, "coverage_3g": 96, "coverage_4g": 88, "coverage_5g": 30, "population_covered_pct": 98, "towers": 2800},
    {"region": "Johannesburg", "country": "ZA", "carrier": "Vodacom_ZA", "coverage_2g": 99, "coverage_3g": 97, "coverage_4g": 90, "coverage_5g": 35, "population_covered_pct": 99, "towers": 3100},
    {"region": "Kigali", "country": "RW", "carrier": "MTN_RW", "coverage_2g": 96, "coverage_3g": 88, "coverage_4g": 70, "coverage_5g": 2, "population_covered_pct": 90, "towers": 800},
    {"region": "Dar es Salaam", "country": "TZ", "carrier": "Vodacom_TZ", "coverage_2g": 95, "coverage_3g": 85, "coverage_4g": 65, "coverage_5g": 0, "population_covered_pct": 85, "towers": 1100},
    {"region": "Kampala", "country": "UG", "carrier": "MTN_UG", "coverage_2g": 94, "coverage_3g": 82, "coverage_4g": 60, "coverage_5g": 0, "population_covered_pct": 82, "towers": 950},
    {"region": "Abidjan", "country": "CI", "carrier": "Orange_CI", "coverage_2g": 96, "coverage_3g": 88, "coverage_4g": 72, "coverage_5g": 5, "population_covered_pct": 91, "towers": 1300},
]

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "healthy", "regions": len(set(d["region"] for d in COVERAGE_DATA))})
        elif self.path.startswith("/api/coverage/json"):
            region = self._get_param("region")
            country = self._get_param("country")
            filtered = [d for d in COVERAGE_DATA if (not region or d["region"].lower() == region.lower()) and (not country or d["country"] == country)]
            self._json(filtered)
        elif self.path.startswith("/api/coverage/csv"):
            region = self._get_param("region")
            country = self._get_param("country")
            filtered = [d for d in COVERAGE_DATA if (not region or d["region"].lower() == region.lower()) and (not country or d["country"] == country)]
            output = io.StringIO()
            if filtered:
                writer = csv.DictWriter(output, fieldnames=filtered[0].keys())
                writer.writeheader()
                writer.writerows(filtered)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", "attachment; filename=coverage-data.csv")
            self.end_headers()
            self.wfile.write(output.getvalue().encode())
        elif self.path.startswith("/api/coverage/summary"):
            regions = {}
            for d in COVERAGE_DATA:
                r = d["region"]
                if r not in regions:
                    regions[r] = {"region": r, "country": d["country"], "carriers": 0, "avg4g": 0, "totalTowers": 0}
                regions[r]["carriers"] += 1
                regions[r]["avg4g"] += d["coverage_4g"]
                regions[r]["totalTowers"] += d["towers"]
            for r in regions.values():
                r["avg4g"] = round(r["avg4g"] / r["carriers"], 1)
            self._json(list(regions.values()))
        else:
            self.send_error(404)

    def _get_param(self, name):
        if "?" in self.path:
            params = dict(p.split("=") for p in self.path.split("?")[1].split("&") if "=" in p)
            return params.get(name, "")
        return ""

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

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/network_coverage_export")

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
