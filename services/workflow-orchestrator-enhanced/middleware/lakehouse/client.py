"""Lakehouse client for analytics data storage"""
import logging
import requests
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class LakehouseConfig:
    def __init__(self, api_url: str, s3_bucket: str, api_key: str):
        self.api_url = api_url
        self.s3_bucket = s3_bucket
        self.api_key = api_key

class WorkflowEvent:
    def __init__(self, event_id: str, event_type: str, timestamp: datetime, workflow_id: str, workflow_type: str, status: str, tenant_id: str, user_id: str, entity_id: str, duration: float, step_count: int, metadata: Dict[str, Any]):
        self.event_id = event_id
        self.event_type = event_type
        self.timestamp = timestamp
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.status = status
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.entity_id = entity_id
        self.duration = duration
        self.step_count = step_count
        self.metadata = metadata

class LakehouseClient:
    def __init__(self, config: LakehouseConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.api_key}"})

    def stream_workflow_event(self, event: WorkflowEvent) -> None:
        logger.info(f"Streaming workflow event to Lakehouse: {event.workflow_id}")
        url = f"{self.config.api_url}/api/v1/events"
        response = self.session.post(url, json=event.__dict__)
        response.raise_for_status()

    def batch_stream_events(self, events: List[WorkflowEvent]) -> None:
        logger.info(f"Batch streaming {len(events)} events to Lakehouse")
        url = f"{self.config.api_url}/api/v1/events/batch"
        response = self.session.post(url, json={"events": [e.__dict__ for e in events]})
        response.raise_for_status()

    def close(self) -> None:
        self.session.close()
