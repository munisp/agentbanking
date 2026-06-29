import json

from utils import get_config, create_logger, PubsubTopics, NotificationCategory, NotificationType
from dapr.clients import DaprClient
from typing import Optional

from urllib.parse import urlencode

# Setup config
config = get_config()

logger = create_logger(__name__)

class NotificationServiceAdapter():
    """Notification service adapter."""

    def __init__(self):
        self._dapr_client = None

    @property
    def dapr_client(self):
        """Lazy initialization of Dapr client"""
        if self._dapr_client is None:
            self._dapr_client = DaprClient()
        return self._dapr_client

    def create_subscriber(self, keycloak_id: str, email: str, first_name: Optional[str] = None, last_name: Optional[str] = None, phone: Optional[str] = None):
        """Create notification subscriber."""

        event_payload = json.dumps({
            "subscriberId": "54agent_" + keycloak_id,
            "traits": {
                "firstName": first_name,
                "lastName": last_name,
                "email": email,
                "phone": phone            
            }
        })

        logger.info(f"event_payload: {event_payload}")

        self.dapr_client.publish_event(pubsub_name=config.DAPR_PUBSUB_NAME, topic_name=PubsubTopics.CORE_54agent_NEW_SUBSCRIBER.value, data=event_payload, data_content_type="application/json")

        logger.info("Event published successfully.")

    
notification_service_adapter = NotificationServiceAdapter()