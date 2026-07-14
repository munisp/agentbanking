from fastapi import Body
from utils import get_config, PubsubTopics
from .handlers import audit_received_handler
from schemas import AuditEventSchema

config = get_config()

def subscribe(dapr_app):
    @dapr_app.subscribe(
        pubsub=config.DAPR_PUBSUB_NAME,
        topic=PubsubTopics.NEW_AUDIT_LOG,
    )
    def new_audit(event: dict = Body(...)):
        audit_received_handler(AuditEventSchema(**event["data"]))