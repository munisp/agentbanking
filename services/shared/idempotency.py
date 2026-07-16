"""
Shared idempotency utilities with Redis primary store and SQLite DB fallback.
Includes background eviction job for expired records.
"""

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 86400
EVICTION_INTERVAL = 3600

_db_lock = threading.Lock()


def _get_db_path(service_name: str) -> str:
    db_dir = os.getenv("IDEMPOTENCY_DB_DIR", "/tmp")
    return os.path.join(db_dir, f"idempotency_{service_name}.db")


def _init_db(service_name: str) -> sqlite3.Connection:
    db_path = _get_db_path(service_name)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS idempotency_records (
            idempotency_key TEXT PRIMARY KEY,
            request_hash TEXT NOT NULL,
            response_data TEXT,
            status TEXT NOT NULL DEFAULT 'processing',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_idem_expires
        ON idempotency_records(expires_at)
    """)
    conn.commit()
    return conn


def request_hash(request_data: Dict[str, Any]) -> str:
    payload = json.dumps(request_data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class IdempotencyStore:
    def __init__(self, service_name: str, redis_client: Optional[Any] = None, key_prefix: str = "idem"):
        self.service_name = service_name
        self.redis = redis_client
        self.key_prefix = key_prefix
        self._db: Optional[sqlite3.Connection] = None
        self._eviction_started = False

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = _init_db(self.service_name)
        return self._db

    def _redis_key(self, idempotency_key: str) -> str:
        return f"{self.key_prefix}:{self.service_name}:{idempotency_key}"

    def check(self, idempotency_key: str, req_hash: str) -> Optional[Dict[str, str]]:
        if self.redis:
            try:
                cached = self.redis.hgetall(self._redis_key(idempotency_key))
                if cached:
                    return cached
            except Exception as exc:
                logger.warning(f"Redis check failed, falling back to DB: {exc}")

        with _db_lock:
            try:
                row = self.db.execute(
                    "SELECT idempotency_key, request_hash, response_data, status FROM idempotency_records "
                    "WHERE idempotency_key = ? AND expires_at > ?",
                    (idempotency_key, datetime.utcnow().isoformat()),
                ).fetchone()
                if row:
                    return {
                        "request_hash": row[1],
                        "response": row[2] or "",
                        "status": row[3],
                    }
            except Exception as exc:
                logger.warning(f"DB idempotency check failed: {exc}")

        return None

    def acquire(self, idempotency_key: str, req_hash: str) -> bool:
        acquired = False
        if self.redis:
            try:
                acquired = bool(
                    self.redis.hsetnx(self._redis_key(idempotency_key), "status", "processing")
                )
                if acquired:
                    self.redis.hset(
                        self._redis_key(idempotency_key),
                        mapping={"request_hash": req_hash},
                    )
                    self.redis.expire(self._redis_key(idempotency_key), IDEMPOTENCY_TTL)
            except Exception as exc:
                logger.warning(f"Redis acquire failed: {exc}")
                acquired = False

        if acquired or not self.redis:
            with _db_lock:
                try:
                    now = datetime.utcnow()
                    self.db.execute(
                        "INSERT OR IGNORE INTO idempotency_records "
                        "(idempotency_key, request_hash, status, created_at, expires_at) "
                        "VALUES (?, ?, 'processing', ?, ?)",
                        (
                            idempotency_key,
                            req_hash,
                            now.isoformat(),
                            (now + timedelta(seconds=IDEMPOTENCY_TTL)).isoformat(),
                        ),
                    )
                    self.db.commit()
                except Exception as exc:
                    logger.warning(f"DB acquire failed: {exc}")

        return acquired

    def complete(self, idempotency_key: str, req_hash: str, response_data: str) -> None:
        if self.redis:
            try:
                self.redis.hset(
                    self._redis_key(idempotency_key),
                    mapping={
                        "status": "completed",
                        "request_hash": req_hash,
                        "response": response_data,
                    },
                )
                self.redis.expire(self._redis_key(idempotency_key), IDEMPOTENCY_TTL)
            except Exception as exc:
                logger.warning(f"Redis complete failed: {exc}")

        with _db_lock:
            try:
                now = datetime.utcnow()
                self.db.execute(
                    "INSERT OR REPLACE INTO idempotency_records "
                    "(idempotency_key, request_hash, response_data, status, created_at, expires_at) "
                    "VALUES (?, ?, ?, 'completed', ?, ?)",
                    (
                        idempotency_key,
                        req_hash,
                        response_data,
                        now.isoformat(),
                        (now + timedelta(seconds=IDEMPOTENCY_TTL)).isoformat(),
                    ),
                )
                self.db.commit()
            except Exception as exc:
                logger.warning(f"DB complete failed: {exc}")

    def evict_expired(self) -> int:
        count = 0
        with _db_lock:
            try:
                cursor = self.db.execute(
                    "DELETE FROM idempotency_records WHERE expires_at < ?",
                    (datetime.utcnow().isoformat(),),
                )
                count = cursor.rowcount
                self.db.commit()
                if count > 0:
                    logger.info(f"Evicted {count} expired idempotency records for {self.service_name}")
            except Exception as exc:
                logger.warning(f"DB eviction failed: {exc}")
        return count

    def start_eviction_job(self) -> None:
        if self._eviction_started:
            return
        self._eviction_started = True

        def _run():
            while True:
                time.sleep(EVICTION_INTERVAL)
                try:
                    self.evict_expired()
                except Exception as exc:
                    logger.warning(f"Eviction job error: {exc}")

        t = threading.Thread(target=_run, daemon=True, name=f"idem-evict-{self.service_name}")
        t.start()
        logger.info(f"Started idempotency eviction job for {self.service_name} (every {EVICTION_INTERVAL}s)")
