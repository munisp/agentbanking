from schemas import TransactionEventSchema
from utils import PubsubTopics, get_config, create_logger
from dapr.clients import DaprClient

logger = create_logger(__name__)
config = get_config()

def publish_transaction_event(topic: PubsubTopics, event: TransactionEventSchema):
    with DaprClient() as d:
        d.publish_event(
            pubsub_name=config.DAPR_PUBSUB_NAME,
            topic_name=topic.value,
            data=event.model_dump_json(),
            data_content_type='application/json',
        )

        logger.info("Transaction event published successfully..")
