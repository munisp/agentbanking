import os
from .kafka_client import KafkaClient

def get_kafka_config():
    config = {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "security.protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        "client.id": os.getenv("KAFKA_CLIENT_ID", "savings-service"),
        "acks": os.getenv("KAFKA_ACKS", "all"),
    }
    
    # Only add SASL config if values are provided
    sasl_mechanism = os.getenv("KAFKA_SASL_MECHANISMS", "").strip()
    sasl_username = os.getenv("KAFKA_SASL_USERNAME", "").strip()
    sasl_password = os.getenv("KAFKA_SASL_PASSWORD", "").strip()
    
    if sasl_mechanism:
        config["sasl.mechanisms"] = sasl_mechanism
    if sasl_username:
        config["sasl.username"] = sasl_username
    if sasl_password:
        config["sasl.password"] = sasl_password
    
    return config

kafka_client = KafkaClient(get_kafka_config())
