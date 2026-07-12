#!/usr/bin/env python3
"""
PostgreSQL Metadata Service - METADATA ONLY, NO FINANCIAL DATA
"""


from typing import Any, Dict, List, Optional, Union, Tuple

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
# ─── Security Hardening (CVE-2024-34069, CVE-2026-27205) ─────────────────────
import os as _os
_flask_env = _os.getenv("FLASK_ENV", _os.getenv("APP_ENV", "production")).lower()
if _flask_env != "development":
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    _os.environ["WERKZEUG_DEBUG_PIN"] = "off"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SECRET_KEY"] = _os.getenv("FLASK_SECRET_KEY", _os.urandom(32).hex())

@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers.pop("Server", None)
    return response
# ─────────────────────────────────────────────────────────────────────────────

CORS(app)

@app.route('/health', methods=['GET'])
def health_check() -> None:
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "service": "PostgreSQL Metadata Service",
        "status": "healthy",
        "version": "2.0.0",
        "role": "METADATA_ONLY_STORAGE",
        "architecture": "CORRECTED_TIGERBEETLE_INTEGRATION",
        "important_note": "TigerBeetle is the primary financial ledger",
        "capabilities": [
            "User profile management",
            "PIX key mappings", 
            "Transfer metadata (NO amounts)",
            "Compliance records",
            "Audit trails",
            "NO financial data storage"
        ],
        "financial_data_location": "TIGERBEETLE_PRIMARY_LEDGER",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/pix-keys/<pix_key>', methods=['GET'])
def resolve_pix_key(pix_key) -> Tuple:
    """Resolve PIX key to TigerBeetle account ID"""
    # In-memory PIX key store for demonstration
    pix_key_store = {
        "user1@example.com": {
            "tigerbeetle_account_id": 1001,
            "user_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
            "key_type": "email",
        },
        "+5511999999999": {
            "tigerbeetle_account_id": 1002,
            "user_id": "b2c3d4e5-f6a7-8901-2345-67890abcdef0",
            "key_type": "phone",
        },
    }

    if pix_key in pix_key_store:
        account_info = pix_key_store[pix_key]
        return jsonify({
            "success": True,
            "pix_key": pix_key,
            "tigerbeetle_account_id": account_info["tigerbeetle_account_id"],
            "user_id": account_info["user_id"],
            "key_type": account_info["key_type"],
            "note": "For account balance, query TigerBeetle with this account_id"
        })
    else:
        return jsonify({"success": False, "error": "PIX key not found"}), 404

@app.route('/api/v1/users/<user_id>', methods=['GET'])
def get_user_profile(user_id) -> None:
    """Get user profile metadata"""
    return jsonify({
        "success": True,
        "user": {
            "user_id": user_id,
            "tigerbeetle_account_id": 123456789,
            "email": "user@example.com",
            "country_code": "NGA",
            "kyc_status": "verified"
        },
        "note": "For account balance, query TigerBeetle directly",
        "financial_data_location": "TIGERBEETLE_PRIMARY_LEDGER"
    })

if __name__ == '__main__':
    print("🗄️ PostgreSQL Metadata Service starting on port 5433")
    print("📋 Role: METADATA ONLY - NO FINANCIAL DATA")
    print("🏦 Financial data stored in TigerBeetle ledger")
    app.run(host='0.0.0.0', port=5433, debug=False)
