import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())

_shutdown_handlers = []  # function registry — must stay in-process (wave-8 revert of wave-7 overreach)  # round-11 wave-7 persistence

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


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import httpx
import os

app = FastAPI(
    title="Multi-lingual Integration Service",
    description="Platform-wide translation for Nigerian languages",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("multi-lingual-integration-service")
app.include_router(metrics_router)

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

