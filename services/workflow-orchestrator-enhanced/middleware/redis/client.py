"""Redis client for caching and distributed locking"""
import logging
import json
from typing import Any, Optional
import redis

logger = logging.getLogger(__name__)

class RedisConfig:
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.db = db
        self.password = password

class RedisClient:
    def __init__(self, config: RedisConfig):
        self.config = config
        self.client = redis.Redis(
            host=config.host,
            port=config.port,
            db=config.db,
            password=config.password,
            decode_responses=True
        )

    def cache_workflow_state(self, workflow_id: str, state: dict, ttl: int = 3600) -> None:
        logger.info(f"Caching workflow state: {workflow_id}")
        key = f"workflow:{workflow_id}:state"
        self.client.setex(key, ttl, json.dumps(state))

    def get_workflow_state(self, workflow_id: str) -> Optional[dict]:
        logger.info(f"Getting workflow state from cache: {workflow_id}")
        key = f"workflow:{workflow_id}:state"
        data = self.client.get(key)
        return json.loads(data) if data else None

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        logger.info(f"Acquiring distributed lock: {lock_name}")
        return self.client.set(f"lock:{lock_name}", "1", nx=True, ex=timeout)

    def release_lock(self, lock_name: str) -> None:
        logger.info(f"Releasing distributed lock: {lock_name}")
        self.client.delete(f"lock:{lock_name}")

    def close(self) -> None:
        self.client.close()
