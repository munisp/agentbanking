from fastapi import Body
from utils import get_config, PubsubTopics
from .handlers import transaction_initiated_handler, transaction_failed_handler, transaction_success_handler
from schemas import TransactionEventSchema
from utils import create_logger


config = get_config()
logger = create_logger(__name__)


def subscribe(dapr_app):
    @dapr_app.subscribe(
        pubsub=config.DAPR_PUBSUB_NAME,
        topic=PubsubTopics.TRANSACTION_INITIATED.value,
    )
    async def transaction_initiated(event: dict = Body(...)):
        logger.info(f"Received transaction initiated event: {event}")
        await transaction_initiated_handler(TransactionEventSchema(**event["data"]))

    @dapr_app.subscribe(
        pubsub=config.DAPR_PUBSUB_NAME,
        topic=PubsubTopics.TRANSACTION_SUCCESS.value,
    )
    async def transaction_success(event: dict = Body(...)):
        logger.info(f"Received transaction success event: {event}")
        await transaction_success_handler(TransactionEventSchema(**event["data"]))

    @dapr_app.subscribe(
        pubsub=config.DAPR_PUBSUB_NAME,
        topic=PubsubTopics.TRANSACTION_FAILED.value,
    )
    async def transaction_failed(event: dict = Body(...)):
        logger.info(f"Received transaction failed event: {event}")
        await transaction_failed_handler(TransactionEventSchema(**event["data"]))
