import os

from utils.kafka_client import KafkaClient


def _get_env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


bootstrap_servers = _get_env("KAFKA_BOOTSTRAP_SERVERS", "")
security_protocol = _get_env("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")

kafka_config = {
    "bootstrap.servers": bootstrap_servers,
    "security.protocol": security_protocol,
}

sasl_mechanism = _get_env("KAFKA_SASL_MECHANISM")
if sasl_mechanism:
    kafka_config["sasl.mechanism"] = sasl_mechanism

sasl_username = _get_env("KAFKA_SASL_USERNAME")
if sasl_username:
    kafka_config["sasl.username"] = sasl_username

sasl_password = _get_env("KAFKA_SASL_PASSWORD")
if sasl_password:
    kafka_config["sasl.password"] = sasl_password

KafkaClientInstance = KafkaClient(kafka_config)
