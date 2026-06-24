import os
import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Multi-lingual Integration Service
Provides comprehensive translation across all platform modules:
- Remittance Platform
- E-commerce
- Inventory Management
- Customer Portal
- Admin Portal
- Partner Portal
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("multi-lingual-integration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import httpx

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/multilingual_integration_service")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()


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
    title="Multi-lingual Integration Service",
    description="Platform-wide translation for Nigerian languages",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Translation Service URL
TRANSLATION_SERVICE = "http://localhost:8095"

# Comprehensive UI translations for all modules
UI_TRANSLATIONS = {
    # Remittance Platform Module
    "remittance": {
        "dashboard": {
            "en": "Dashboard",
            "yo": "Pátákó",
            "ig": "Dashibodu",
            "ha": "Dashboard",
            "pcm": "Dashboard"
        },
        "balance": {
            "en": "Balance",
            "yo": "Iye owo",
            "ig": "Ego",
            "ha": "Ma'auni",
            "pcm": "Balance"
        },
        "deposit": {
            "en": "Deposit",
            "yo": "Fi owo sii",
            "ig": "Tinye ego",
            "ha": "Ajiya",
            "pcm": "Deposit"
        },
        "withdrawal": {
            "en": "Withdrawal",
            "yo": "Yọ owo jade",
            "ig": "Wepụ ego",
            "ha": "Cire kudi",
            "pcm": "Withdraw"
        },
        "transfer": {
            "en": "Transfer",
            "yo": "Fi owo ranṣẹ",
            "ig": "Zipu ego",
            "ha": "Tura kudi",
            "pcm": "Transfer"
        },
        "transaction_history": {
            "en": "Transaction History",
            "yo": "Itan Iṣowo",
            "ig": "Akụkọ Azụmahịa",
            "ha": "Tarihin Ciniki",
            "pcm": "Transaction History"
        },
        "customers": {
            "en": "Customers",
            "yo": "Awọn alabara",
            "ig": "Ndị ahịa",
            "ha": "Abokan ciniki",
            "pcm": "Customers"
        },
        "commission": {
            "en": "Commission",
            "yo": "Ere",
            "ig": "Ọrụ",
            "ha": "Lada",
            "pcm": "Commission"
        }
    },
    
    # E-commerce Module
    "ecommerce": {
        "products": {
            "en": "Products",
            "yo": "Awọn ọja",
            "ig": "Ngwaahịa",
            "ha": "Kayayyaki",
            "pcm": "Products"
        },
        "cart": {
            "en": "Shopping Cart",
            "yo": "Apoti rira",
            "ig": "Ụgbọala ịzụ ahịa",
            "ha": "Katon siyayya",
            "pcm": "Shopping Cart"
        },
        "checkout": {
            "en": "Checkout",
            "yo": "Sanwo",
            "ig": "Kwụọ ụgwọ",
            "ha": "Biya",
            "pcm": "Checkout"
        },
        "add_to_cart": {
            "en": "Add to Cart",
            "yo": "Fi kun apoti",
            "ig": "Tinye n'ụgbọala",
            "ha": "Saka a katon",
            "pcm": "Add to Cart"
        },
        "price": {
            "en": "Price",
            "yo": "Iye owo",
            "ig": "Ọnụ ahịa",
            "ha": "Farashi",
            "pcm": "Price"
        },
        "quantity": {
            "en": "Quantity",
            "yo": "Iye",
            "ig": "Ọnụ ọgụgụ",
            "ha": "Adadi",
            "pcm": "Quantity"
        },
        "total": {
            "en": "Total",
            "yo": "Lapapọ",
            "ig": "Ngụkọta",
            "ha": "Jimla",
            "pcm": "Total"
        },
        "order": {
            "en": "Order",
            "yo": "Aṣẹ",
            "ig": "Ọda",
            "ha": "Oda",
            "pcm": "Order"
        },
        "place_order": {
            "en": "Place Order",
            "yo": "Fi aṣẹ silẹ",
            "ig": "Tinye ọda",
            "ha": "Sanya oda",
            "pcm": "Place Order"
        }
    },
    
    # Inventory Management
    "inventory": {
        "inventory": {
            "en": "Inventory",
            "yo": "Akojọ ọja",
            "ig": "Ndekọ ngwaahịa",
            "ha": "Lissafin kayayyaki",
            "pcm": "Inventory"
        },
        "stock": {
            "en": "Stock",
            "yo": "Ipamọ",
            "ig": "Ngwaahịa",
            "ha": "Kayayyaki",
            "pcm": "Stock"
        },
        "in_stock": {
            "en": "In Stock",
            "yo": "Wa ninu ipamọ",
            "ig": "Nọ na ngwaahịa",
            "ha": "Akwai a cikin kayayyaki",
            "pcm": "Dey for stock"
        },
        "out_of_stock": {
            "en": "Out of Stock",
            "yo": "Ko si ninu ipamọ",
            "ig": "Agwụla",
            "ha": "Ba a cikin kayayyaki",
            "pcm": "No dey for stock"
        },
        "restock": {
            "en": "Restock",
            "yo": "Tun fi kun",
            "ig": "Mejupụta",
            "ha": "Sake cika",
            "pcm": "Restock"
        },
        "supplier": {
            "en": "Supplier",
            "yo": "Olupese",
            "ig": "Onye na-enye",
            "ha": "Mai bayarwa",
            "pcm": "Supplier"
        }
    },
    
    # Common UI Elements
    "common": {
        "login": {
            "en": "Login",
            "yo": "Wọle",
            "ig": "Banye",
            "ha": "Shiga",
            "pcm": "Login"
        },
        "logout": {
            "en": "Logout",
            "yo": "Jade",
            "ig": "Pụọ",
            "ha": "Fita",
            "pcm": "Logout"
        },
        "save": {
            "en": "Save",
            "yo": "Fi pamọ",
            "ig": "Chekwaa",
            "ha": "Ajiye",
            "pcm": "Save"
        },
        "cancel": {
            "en": "Cancel",
            "yo": "Fagilee",
            "ig": "Kagbuo",
            "ha": "Soke",
            "pcm": "Cancel"
        },
        "submit": {
            "en": "Submit",
            "yo": "Fi silẹ",
            "ig": "Nyefee",
            "ha": "Tura",
            "pcm": "Submit"
        },
        "search": {
            "en": "Search",
            "yo": "Wa",
            "ig": "Chọọ",
            "ha": "Nema",
            "pcm": "Search"
        },
        "filter": {
            "en": "Filter",
            "yo": "Ṣẹ",
            "ig": "Họrọ",
            "ha": "Tace",
            "pcm": "Filter"
        },
        "export": {
            "en": "Export",
            "yo": "Gbe jade",
            "ig": "Bupụ",
            "ha": "Fitar",
            "pcm": "Export"
        },
        "print": {
            "en": "Print",
            "yo": "Tẹ jade",
            "ig": "Bipụta",
            "ha": "Buga",
            "pcm": "Print"
        },
        "settings": {
            "en": "Settings",
            "yo": "Eto",
            "ig": "Ntọala",
            "ha": "Saiti",
            "pcm": "Settings"
        },
        "help": {
            "en": "Help",
            "yo": "Iranlọwọ",
            "ig": "Enyemaka",
            "ha": "Taimako",
            "pcm": "Help"
        },
        "profile": {
            "en": "Profile",
            "yo": "Profaili",
            "ig": "Profaịlụ",
            "ha": "Bayanan",
            "pcm": "Profile"
        }
    },
    
    # Messages and Notifications
    "messages": {
        "success": {
            "en": "Operation successful!",
            "yo": "Iṣẹ ṣaṣeyọri!",
            "ig": "Ọrụ gara nke ọma!",
            "ha": "Aikin ya yi nasara!",
            "pcm": "Operation don successful!"
        },
        "error": {
            "en": "An error occurred. Please try again.",
            "yo": "Aṣiṣe kan ṣẹlẹ. Jọwọ gbiyanju lẹẹkansi.",
            "ig": "Njehie mere. Biko nwaa ọzọ.",
            "ha": "Kuskure ya faru. Don Allah sake gwadawa.",
            "pcm": "Error happen. Abeg try again."
        },
        "loading": {
            "en": "Loading...",
            "yo": "N ṣiṣẹ...",
            "ig": "Na-ebu...",
            "ha": "Ana lodawa...",
            "pcm": "Dey load..."
        },
        "confirm": {
            "en": "Are you sure?",
            "yo": "Ṣe o da ọ loju?",
            "ig": "Ị ji n'aka?",
            "ha": "Ka tabbata?",
            "pcm": "You sure?"
        },
        "delete_confirm": {
            "en": "Are you sure you want to delete this?",
            "yo": "Ṣe o da ọ loju pe o fẹ pa eyi rẹ?",
            "ig": "Ị ji n'aka na ịchọrọ ihicha nke a?",
            "ha": "Ka tabbata kana son share wannan?",
            "pcm": "You sure say you wan delete this?"
        }
    }
}

# Models
class TranslateUIRequest(BaseModel):
    module: str  # remittance, ecommerce, inventory, common, messages
    keys: List[str]  # List of UI keys to translate
    target_language: str

class TranslateTextRequest(BaseModel):
    text: str
    source_language: str = "en"
    target_language: str
    context: Optional[str] = None

class GetModuleTranslationsRequest(BaseModel):
    module: str
    target_language: str

# Statistics
stats = {
    "ui_translations": 0,
    "text_translations": 0,
    "start_time": datetime.now()
}

@app.get("/")
async def root():
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("root", "multilingual-integration-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    return {
        "service": "multilingual-integration-service",
        "version": "1.0.0",
        "modules": list(UI_TRANSLATIONS.keys()),
        "languages": ["en", "yo", "ig", "ha", "pcm"],
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "ui_translations": stats["ui_translations"],
        "text_translations": stats["text_translations"]
    }

@app.post("/translate/ui")
async def translate_ui(request: TranslateUIRequest):
    """Translate UI elements for a specific module"""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("translate_ui_" + str(int(_time.time() * 1000)), _json.dumps({"action": "translate_ui", "timestamp": _time.time()}), "multilingual-integration-service")

    
    if request.module not in UI_TRANSLATIONS:
        raise HTTPException(status_code=400, detail=f"Unknown module: {request.module}")
    
    module_translations = UI_TRANSLATIONS[request.module]
    
    result = {}
    for key in request.keys:
        if key in module_translations:
            result[key] = module_translations[key].get(
                request.target_language,
                module_translations[key]["en"]  # Fallback to English
            )
        else:
            result[key] = key  # Return key if not found
    
    stats["ui_translations"] += len(result)
    
    return {
        "module": request.module,
        "target_language": request.target_language,
        "translations": result
    }

@app.post("/translate/text")
async def translate_text(request: TranslateTextRequest):
    """Translate arbitrary text using the translation service"""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("translate_text_" + str(int(_time.time() * 1000)), _json.dumps({"action": "translate_text", "timestamp": _time.time()}), "multilingual-integration-service")

    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TRANSLATION_SERVICE}/translate",
                json={
                    "text": request.text,
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "context": request.context
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                stats["text_translations"] += 1
                return response.json()
    except:
        pass
    
    raise HTTPException(status_code=500, detail="Translation service unavailable")

@app.get("/translations/{module}")
async def get_module_translations(module: str, language: str = "en"):
    """Get all translations for a specific module"""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_module_translations", "multilingual-integration-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    
    if module not in UI_TRANSLATIONS:
        raise HTTPException(status_code=404, detail=f"Module not found: {module}")
    
    module_translations = UI_TRANSLATIONS[module]
    
    result = {}
    for key, translations in module_translations.items():
        result[key] = translations.get(language, translations["en"])
    
    return {
        "module": module,
        "language": language,
        "translations": result,
        "total": len(result)
    }

@app.get("/translations")
async def get_all_translations(language: str = "en"):
    """Get all translations for all modules in a specific language"""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_all_translations", "multilingual-integration-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    
    result = {}
    
    for module, module_translations in UI_TRANSLATIONS.items():
        result[module] = {}
        for key, translations in module_translations.items():
            result[module][key] = translations.get(language, translations["en"])
    
    return {
        "language": language,
        "modules": result,
        "total_keys": sum(len(m) for m in result.values())
    }

@app.get("/modules")
async def get_modules():
    """Get list of all supported modules"""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_modules", "multilingual-integration-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    
    modules = []
    for module_name, module_translations in UI_TRANSLATIONS.items():
        modules.append({
            "name": module_name,
            "keys_count": len(module_translations)
        })
    
    return {
        "modules": modules,
        "total": len(modules)
    }

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    # Load persisted state from PostgreSQL
    _pg_cached = await pg_get("get_stats", "multilingual-integration-service")
    if _pg_cached is not None:
        import json as _json
        try:
            return _json.loads(_pg_cached) if isinstance(_pg_cached, str) else _pg_cached
        except Exception:
            pass

    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    
    total_keys = sum(len(m) for m in UI_TRANSLATIONS.values())
    
    return {
        "uptime_seconds": int(uptime),
        "ui_translations": stats["ui_translations"],
        "text_translations": stats["text_translations"],
        "modules": len(UI_TRANSLATIONS),
        "total_ui_keys": total_keys,
        "languages": 5
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8097)

