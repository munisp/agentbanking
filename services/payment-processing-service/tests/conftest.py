"""Pytest bootstrap for the payment-processing-service funds-flow unit tests.

The service's heavy infrastructure — Dapr, the TigerBeetle client, the Kafka
event bus and the 13 downstream adapters — is replaced at the module boundary
BEFORE the production modules are imported, so tests exercise the real
api/payment.py, services/payment.py, services/qr.py and api/transactions.py
code paths against controllable fakes.

The REAL utils/enums.py is loaded (it is dependency-free) so currency and
status semantics under test are exactly the production ones.
"""
import hashlib
import importlib.util
import logging
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# api/payment.py fails closed at import time without these (NF-FF-21).
os.environ.setdefault("TB_LEDGER_ID", "1")
os.environ.setdefault("TB_MINT_ACCOUNT_ID", "999")
os.environ.setdefault("STATE_STORE_NAME", "statestore")
os.environ.setdefault("ENVIRONMENT", "test")


# ── utils package: real enums, stubbed loggers/config/qr/coa ────────────────
def _load_real_enums():
    spec = importlib.util.spec_from_file_location(
        "utils.enums", SERVICE_ROOT / "utils" / "enums.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_enums = _load_real_enums()

utils_pkg = types.ModuleType("utils")
utils_pkg.__path__ = [str(SERVICE_ROOT / "utils")]
for _name in ("TransactionStatus", "CurrencyEnum", "CurrencyLedgerId", "PubsubTopics"):
    setattr(utils_pkg, _name, getattr(_enums, _name))


def _create_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


class _Config:
    STATE_STORE_NAME = os.environ.get("STATE_STORE_NAME", "statestore")


utils_pkg.create_logger = _create_logger
utils_pkg.get_config = lambda: _Config()
utils_pkg.generate_qr_base64 = (
    lambda data: "qr:" + hashlib.sha256(data.encode()).hexdigest()[:24]
)

sys.modules["utils"] = utils_pkg
sys.modules["utils.enums"] = _enums

coa_mod = types.ModuleType("utils.coa_client")
coa_mod.CoAClient = MagicMock
sys.modules["utils.coa_client"] = coa_mod


# ── dapr stubs (StateOptions so the first-write claim path is exercised) ────
dapr_pkg = types.ModuleType("dapr")
dapr_pkg.__path__ = []
dapr_clients = types.ModuleType("dapr.clients")


class _DaprClientPlaceholder:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "tests must inject a fake Dapr client (module._dapr = fake)"
        )


dapr_clients.DaprClient = _DaprClientPlaceholder
dapr_grpc = types.ModuleType("dapr.clients.grpc")
dapr_state = types.ModuleType("dapr.clients.grpc._state")


class Concurrency:
    first_write = "first_write"


class Consistency:
    strong = "strong"


class StateOptions:
    def __init__(self, consistency=None, concurrency=None):
        self.consistency = consistency
        self.concurrency = concurrency


dapr_state.Concurrency = Concurrency
dapr_state.Consistency = Consistency
dapr_state.StateOptions = StateOptions

sys.modules["dapr"] = dapr_pkg
sys.modules["dapr.clients"] = dapr_clients
sys.modules["dapr.clients.grpc"] = dapr_grpc
sys.modules["dapr.clients.grpc._state"] = dapr_state


# ── adapters stub: real business-error type, mock adapters ──────────────────
adapters_mod = types.ModuleType("adapters")
adapters_mod.__path__ = []


class TigerBeetleBusinessError(Exception):
    """Stand-in matching the adapter contract used by api/payment.py."""


adapters_mod.TigerBeetleBusinessError = TigerBeetleBusinessError
for _name in (
    "TigerBeetleAdapter",
    "AccountServiceAdapter",
    "LoanServiceAdapter",
    "LpoServiceAdapter",
    "InsuranceServiceAdapter",
    "SupplyChainServiceAdapter",
    "AuditServiceAdapter",
    "ExchangeRateServiceAdapter",
    "FraudEngineAdapter",
    "CommissionServiceAdapter",
    "ComplianceServiceAdapter",
    "LoyaltyServiceAdapter",
    "NetworkOpsAdapter",
):
    setattr(adapters_mod, _name, MagicMock(name=_name))
adapters_mod.payment_rails_connector_adapter = MagicMock(
    name="payment_rails_connector_adapter"
)
sys.modules["adapters"] = adapters_mod


# ── events + database stubs ─────────────────────────────────────────────────
events_mod = types.ModuleType("events")
events_mod.publish_transaction_event = MagicMock(name="publish_transaction_event")
sys.modules["events"] = events_mod

database_mod = types.ModuleType("database")
database_mod.get_session = lambda: None
sys.modules["database"] = database_mod


# api/__init__.py eagerly imports sibling routers with their own heavy
# dependency chains; stub the ones not under test so `import api.payment`
# stays hermetic regardless of what is installed.
for _mod_name, _router_attr in (
    ("api.health", "health_router"),
    ("api.qr", "qr_router"),
    ("api.system", "system_router"),
    ("api.charges", "charges_router"),
    ("api.transfers", "transfers_router"),
):
    _stub = types.ModuleType(_mod_name)
    setattr(_stub, _router_attr, MagicMock(name=_router_attr))
    sys.modules[_mod_name] = _stub
