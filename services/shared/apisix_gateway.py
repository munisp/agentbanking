"""
APISIX Gateway Registration for 54Agent Banking Platform

Allows services to self-register their routes with the APISIX API gateway
at startup, including rate-limit, auth, and CORS plugin configurations.

Usage::

    from shared.apisix_gateway import APISIXGateway

    gw = APISIXGateway()
    await gw.register_service(
        service_name="pos-integration",
        upstream_host="pos-integration",
        upstream_port=8000,
        routes=["/v1/pos/*"],
    )
"""

import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("platform.apisix")

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class APISIXGateway:
    def __init__(
        self,
        admin_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.admin_url = admin_url or os.getenv("APISIX_ADMIN_URL", "http://apisix:9180")
        self.api_key = api_key or os.getenv("APISIX_API_KEY", "")
        self._headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["X-API-KEY"] = self.api_key

    async def register_upstream(
        self,
        service_name: str,
        host: str,
        port: int,
        scheme: str = "http",
        health_check_path: str = "/health/live",
    ) -> Optional[str]:
        payload = {
            "name": service_name,
            "type": "roundrobin",
            "nodes": {f"{host}:{port}": 1},
            "scheme": scheme,
            "checks": {
                "active": {
                    "type": "http",
                    "http_path": health_check_path,
                    "healthy": {"interval": 10, "successes": 2},
                    "unhealthy": {"interval": 5, "http_failures": 3},
                }
            },
        }
        return await self._put(f"/apisix/admin/upstreams/{service_name}", payload)

    async def register_route(
        self,
        route_id: str,
        uri: str,
        upstream_id: str,
        methods: Optional[List[str]] = None,
        enable_auth: bool = True,
        rate_limit: int = 100,
        rate_limit_window: int = 60,
    ) -> Optional[str]:
        plugins: Dict[str, Any] = {}
        if enable_auth:
            plugins["openid-connect"] = {
                "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "agent-banking-api"),
                "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET", ""),
                "discovery": os.getenv(
                    "KEYCLOAK_DISCOVERY_URL",
                    "http://keycloak:8080/realms/agent-banking/.well-known/openid-configuration",
                ),
                "bearer_only": True,
                "scope": "openid",
            }
        if rate_limit > 0:
            plugins["limit-count"] = {
                "count": rate_limit,
                "time_window": rate_limit_window,
                "rejected_code": 429,
                "policy": "redis",
                "redis_host": os.getenv("REDIS_HOST", "redis"),
                "redis_port": int(os.getenv("REDIS_PORT", "6379")),
            }
        plugins["cors"] = {
            "allow_origins": os.getenv("ALLOWED_ORIGINS", "http://localhost:5173"),
            "allow_methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
            "allow_headers": "Authorization,Content-Type,X-Request-ID,X-Trace-ID,Idempotency-Key",
            "expose_headers": "X-Request-ID,X-Trace-ID,X-RateLimit-Remaining",
            "max_age": 3600,
            "allow_credential": True,
        }

        payload: Dict[str, Any] = {
            "uri": uri,
            "upstream_id": upstream_id,
            "plugins": plugins,
        }
        if methods:
            payload["methods"] = methods
        return await self._put(f"/apisix/admin/routes/{route_id}", payload)

    async def register_service(
        self,
        service_name: str,
        upstream_host: str,
        upstream_port: int,
        routes: Optional[List[str]] = None,
        enable_auth: bool = True,
        rate_limit: int = 100,
    ) -> bool:
        uid = await self.register_upstream(service_name, upstream_host, upstream_port)
        if not uid:
            return False
        for i, route_uri in enumerate(routes or [f"/v1/{service_name}/*"]):
            route_id = f"{service_name}-{i}"
            await self.register_route(
                route_id=route_id,
                uri=route_uri,
                upstream_id=service_name,
                enable_auth=enable_auth,
                rate_limit=rate_limit,
            )
        logger.info("Registered %s with APISIX (%d routes)", service_name, len(routes or []))
        return True

    async def _put(self, path: str, payload: Dict[str, Any]) -> Optional[str]:
        if not _HAS_HTTPX:
            return None
        try:
            async with _httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    f"{self.admin_url}{path}",
                    json=payload,
                    headers=self._headers,
                )
                if resp.status_code < 300:
                    data = resp.json()
                    return data.get("value", {}).get("id") or data.get("key", path.split("/")[-1])
                logger.warning("APISIX %s HTTP %d: %s", path, resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("APISIX %s error (gateway may not be running): %s", path, exc)
        return None
