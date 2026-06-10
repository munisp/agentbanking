"""APISIX client for API gateway management"""
import logging
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class APISIXConfig:
    def __init__(self, admin_url: str, gateway_url: str, api_key: str):
        self.admin_url = admin_url
        self.gateway_url = gateway_url
        self.api_key = api_key

class Route:
    def __init__(self, id: str, uri: str, name: str, methods: List[str], upstream: Dict[str, Any]):
        self.id = id
        self.uri = uri
        self.name = name
        self.methods = methods
        self.upstream = upstream

class APISIXClient:
    def __init__(self, config: APISIXConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": config.api_key})

    def create_route(self, route: Route) -> None:
        logger.info(f"Creating APISIX route: {route.id}")
        url = f"{self.config.admin_url}/apisix/admin/routes/{route.id}"
        response = self.session.put(url, json=route.__dict__)
        response.raise_for_status()

    def delete_route(self, route_id: str) -> None:
        logger.info(f"Deleting APISIX route: {route_id}")
        url = f"{self.config.admin_url}/apisix/admin/routes/{route_id}"
        response = self.session.delete(url)
        response.raise_for_status()

    def close(self) -> None:
        self.session.close()
