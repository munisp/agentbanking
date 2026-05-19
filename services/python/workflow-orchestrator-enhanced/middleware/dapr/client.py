"""
Dapr client for service invocation and state management
"""
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class DaprConfig:
    """Dapr configuration"""
    def __init__(self, http_port: int = 3500, grpc_port: int = 50001):
        self.http_port = http_port
        self.grpc_port = grpc_port
        self.base_url = f"http://localhost:{http_port}"


class DaprClient:
    """Dapr client for workflow orchestration"""

    def __init__(self, config: DaprConfig):
        self.config = config
        self.session = requests.Session()

    def invoke_service(
        self, app_id: str, method: str, data: Any
    ) -> Dict[str, Any]:
        """Invoke a service method via Dapr sidecar"""
        logger.info(f"Invoking service via Dapr: {app_id}/{method}")

        url = f"{self.config.base_url}/v1.0/invoke/{app_id}/method/{method}"
        response = self.session.post(url, json=data)
        response.raise_for_status()

        return response.json()

    def save_state(
        self, store_name: str, key: str, value: Any
    ) -> None:
        """Save workflow state to Dapr state store"""
        logger.info(f"Saving state via Dapr: {store_name}/{key}")

        url = f"{self.config.base_url}/v1.0/state/{store_name}"
        payload = [{"key": key, "value": value}]
        response = self.session.post(url, json=payload)
        response.raise_for_status()

    def get_state(
        self, store_name: str, key: str
    ) -> Optional[Any]:
        """Get workflow state from Dapr state store"""
        logger.info(f"Getting state via Dapr: {store_name}/{key}")

        url = f"{self.config.base_url}/v1.0/state/{store_name}/{key}"
        response = self.session.get(url)
        response.raise_for_status()

        return response.json() if response.content else None

    def delete_state(self, store_name: str, key: str) -> None:
        """Delete workflow state from Dapr state store"""
        logger.info(f"Deleting state via Dapr: {store_name}/{key}")

        url = f"{self.config.base_url}/v1.0/state/{store_name}/{key}"
        response = self.session.delete(url)
        response.raise_for_status()

    def publish_event(
        self, pubsub_name: str, topic: str, data: Any
    ) -> None:
        """Publish an event to Dapr pub/sub"""
        logger.info(f"Publishing event via Dapr: {pubsub_name}/{topic}")

        url = f"{self.config.base_url}/v1.0/publish/{pubsub_name}/{topic}"
        response = self.session.post(url, json=data)
        response.raise_for_status()

    def close(self) -> None:
        """Close the Dapr client"""
        self.session.close()
