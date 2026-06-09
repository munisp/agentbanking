"""
Shared idempotency utilities with Redis primary store and PostgreSQL DB fallback.
Includes background eviction job for expired records.
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 86400
EVICTION_INTERVAL = 3600

_db_lock = threading.Lock()


def _get_db_url() -> str:
    return os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/idempotency")


def _init_db() -> psycopg2.extensions.connection:
    db_url = _get_db_url()
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                request_hash TEXT NOT NULL,
                response_data TEXT,
                status TEXT NOT NULL DEFAULT 'processing',
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            )
        """)
        cur.execute("""
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
        self._db: Optional[psycopg2.extensions.connection] = None
        self._eviction_started = False

    @property
    def db(self) -> psycopg2.extensions.connection:
        if self._db is None or self._db.closed:
            self._db = _init_db()
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
                with self.db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(
                        "SELECT idempotency_key, request_hash, response_data, status FROM idempotency_records "
                        "WHERE idempotency_key = %s AND expires_at > %s",
                        (idempotency_key, datetime.utcnow()),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "request_hash": row["request_hash"],
                            "response": row["response_data"] or "",
                            "status": row["status"],
                        }
            except Exception as exc:
                logger.warning(f"DB idempotency check failed: {exc}")
                try:
                    self.db.rollback()
                except Exception:
                    pass

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
                    with self.db.cursor() as cur:
                        cur.execute(
                            "INSERT INTO idempotency_records "
                            "(idempotency_key, request_hash, status, created_at, expires_at) "
                            "VALUES (%s, %s, 'processing', %s, %s) "
                            "ON CONFLICT (idempotency_key) DO NOTHING",
                            (
                                idempotency_key,
                                req_hash,
                                now,
                                now + timedelta(seconds=IDEMPOTENCY_TTL),
                            ),
                        )
                    self.db.commit()
                except Exception as exc:
                    logger.warning(f"DB acquire failed: {exc}")
                    try:
                        self.db.rollback()
                    except Exception:
                        pass

        return acquired

    def complete(self, idempotency_key: str, req_hash: str, response_data: str) -> None:
        if self.redis:
            try:
                self.redis.hset(
                    self._redis_key(idempotency_key),
                    mapping={"response": response_data, "status": "completed"},
                )
            except Exception as exc:
                logger.warning(f"Redis complete failed: {exc}")

        with _db_lock:
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "UPDATE idempotency_records SET response_data = %s, status = 'completed' "
                        "WHERE idempotency_key = %s",
                        (response_data, idempotency_key),
                    )
                self.db.commit()
            except Exception as exc:
                logger.warning(f"DB complete failed: {exc}")
                try:
                    self.db.rollback()
                except Exception:
                    pass

    def _evict_expired(self) -> int:
        with _db_lock:
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "DELETE FROM idempotency_records WHERE expires_at <= %s",
                        (datetime.utcnow(),),
                    )
                    count = cur.rowcount
                self.db.commit()
                return count
            except Exception as exc:
                logger.warning(f"Eviction failed: {exc}")
                try:
                    self.db.rollback()
                except Exception:
                    pass
                return 0

    def start_eviction_loop(self) -> None:
        if self._eviction_started:
            return
        self._eviction_started = True

        def _loop():
            while True:
                time.sleep(EVICTION_INTERVAL)
                evicted = self._evict_expired()
                if evicted:
                    logger.info(f"Evicted {evicted} expired idempotency records")

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
