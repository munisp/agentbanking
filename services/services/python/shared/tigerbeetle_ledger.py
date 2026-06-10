"""
TigerBeetle Ledger Client for 54Agent Banking Platform

Provides a high-performance double-entry accounting interface backed by
TigerBeetle for all financial operations (transfers, settlements, float,
commissions).

Usage::

    from shared.tigerbeetle_ledger import TigerBeetleLedger

    ledger = TigerBeetleLedger()
    await ledger.connect()
    await ledger.create_account(agent_id="A1", ledger=1, code=100)
    await ledger.create_transfer(debit="A1", credit="FLOAT", amount=50000, ledger=1)
    balance = await ledger.get_balance("A1")
    await ledger.close()
"""

import os
import logging
import uuid
import struct
from typing import Optional, Dict, Any, List

logger = logging.getLogger("platform.tigerbeetle")

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


def _uuid_to_u128(uid: str) -> int:
    return int(uuid.UUID(uid).hex, 16) if isinstance(uid, str) and len(uid) > 15 else hash(uid) & ((1 << 128) - 1)


class TigerBeetleLedger:
    def __init__(
        self,
        addresses: Optional[str] = None,
        cluster_id: int = 0,
        http_endpoint: Optional[str] = None,
    ):
        self.addresses = addresses or os.getenv("TIGERBEETLE_ADDRESSES", "tigerbeetle:3001")
        self.cluster_id = int(os.getenv("TIGERBEETLE_CLUSTER_ID", str(cluster_id)))
        self.http_endpoint = http_endpoint or os.getenv("TIGERBEETLE_HTTP", "http://tigerbeetle:3001")
        self._http: Optional[Any] = None

    async def connect(self) -> None:
        if _HAS_HTTPX:
            self._http = _httpx.AsyncClient(base_url=self.http_endpoint, timeout=10.0)
            logger.info("TigerBeetle ledger connected to %s (cluster=%d)", self.http_endpoint, self.cluster_id)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    async def create_account(
        self,
        agent_id: str,
        ledger: int = 1,
        code: int = 100,
        flags: int = 0,
    ) -> bool:
        account_id = _uuid_to_u128(agent_id)
        payload = {
            "id": str(account_id),
            "ledger": ledger,
            "code": code,
            "flags": flags,
            "debits_pending": 0,
            "debits_posted": 0,
            "credits_pending": 0,
            "credits_posted": 0,
        }
        return await self._post("/accounts/create", [payload])

    async def create_transfer(
        self,
        debit_account: str,
        credit_account: str,
        amount: int,
        ledger: int = 1,
        code: int = 1,
        transfer_id: Optional[str] = None,
        flags: int = 0,
    ) -> bool:
        tid = transfer_id or str(uuid.uuid4())
        payload = {
            "id": str(_uuid_to_u128(tid)),
            "debit_account_id": str(_uuid_to_u128(debit_account)),
            "credit_account_id": str(_uuid_to_u128(credit_account)),
            "amount": amount,
            "ledger": ledger,
            "code": code,
            "flags": flags,
        }
        return await self._post("/transfers/create", [payload])

    async def create_pending_transfer(
        self,
        debit_account: str,
        credit_account: str,
        amount: int,
        ledger: int = 1,
        code: int = 1,
        timeout_ns: int = 300_000_000_000,
    ) -> Optional[str]:
        tid = str(uuid.uuid4())
        payload = {
            "id": str(_uuid_to_u128(tid)),
            "debit_account_id": str(_uuid_to_u128(debit_account)),
            "credit_account_id": str(_uuid_to_u128(credit_account)),
            "amount": amount,
            "ledger": ledger,
            "code": code,
            "flags": 2,
            "timeout": timeout_ns,
        }
        ok = await self._post("/transfers/create", [payload])
        return tid if ok else None

    async def post_pending_transfer(self, pending_id: str) -> bool:
        payload = {
            "id": str(_uuid_to_u128(str(uuid.uuid4()))),
            "pending_id": str(_uuid_to_u128(pending_id)),
            "flags": 4,
            "amount": 0,
            "debit_account_id": "0",
            "credit_account_id": "0",
            "ledger": 0,
            "code": 0,
        }
        return await self._post("/transfers/create", [payload])

    async def void_pending_transfer(self, pending_id: str) -> bool:
        payload = {
            "id": str(_uuid_to_u128(str(uuid.uuid4()))),
            "pending_id": str(_uuid_to_u128(pending_id)),
            "flags": 8,
            "amount": 0,
            "debit_account_id": "0",
            "credit_account_id": "0",
            "ledger": 0,
            "code": 0,
        }
        return await self._post("/transfers/create", [payload])

    async def get_balance(self, account_id: str) -> Dict[str, int]:
        aid = _uuid_to_u128(account_id)
        try:
            if self._http:
                resp = await self._http.post("/accounts/lookup", json=[str(aid)])
                if resp.status_code < 300:
                    accounts = resp.json()
                    if accounts:
                        a = accounts[0]
                        return {
                            "debits_pending": a.get("debits_pending", 0),
                            "debits_posted": a.get("debits_posted", 0),
                            "credits_pending": a.get("credits_pending", 0),
                            "credits_posted": a.get("credits_posted", 0),
                            "available": a.get("credits_posted", 0) - a.get("debits_posted", 0),
                        }
        except Exception as exc:
            logger.error("TigerBeetle get_balance error: %s", exc)
        return {"debits_pending": 0, "debits_posted": 0, "credits_pending": 0, "credits_posted": 0, "available": 0}

    async def _post(self, path: str, payload: List[Dict[str, Any]]) -> bool:
        if not self._http:
            await self.connect()
        try:
            resp = await self._http.post(path, json=payload)
            if resp.status_code < 300:
                return True
            logger.warning("TigerBeetle %s HTTP %d: %s", path, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("TigerBeetle %s error: %s", path, exc)
        return False
