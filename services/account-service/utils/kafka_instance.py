from utils.kafka_client import KafkaClient
from utils import get_config

config = get_config()

kafka_config = {
    "bootstrap.servers": config.KAFKA_BOOTSTRAP_SERVERS,
    "security.protocol": config.KAFKA_SECURITY_PROTOCOL,
}

if getattr(config, "KAFKA_SASL_MECHANISM", None):
    val = config.KAFKA_SASL_MECHANISM.strip()
    if val:
        kafka_config["sasl.mechanism"] = val
if getattr(config, "KAFKA_SASL_USERNAME", None):
    val = config.KAFKA_SASL_USERNAME.strip()
    if val:
        kafka_config["sasl.username"] = val
if getattr(config, "KAFKA_SASL_PASSWORD", None):
    val = config.KAFKA_SASL_PASSWORD.strip()
    if val:
        kafka_config["sasl.password"] = val

KafkaClientInstance = KafkaClient(kafka_config)
