"""
Agent Embedded Finance — Kafka Producer
Publishes loan lifecycle and BNPL events to Kafka.
"""
import json
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from confluent_kafka import Producer, KafkaException

from .topics import (
    FinanceTopics,
    LoanDisbursedEvent,
    LoanRepaidEvent,
    CreditLimitUpdatedEvent,
)

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka-broker-1:9092,kafka-broker-2:9092,kafka-broker-3:9092")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
KAFKA_SASL_MECHANISM    = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-512")
KAFKA_SASL_USERNAME     = os.getenv("KAFKA_SASL_USERNAME", "finance-service")
KAFKA_SASL_PASSWORD     = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_SSL_CA_LOCATION   = os.getenv("KAFKA_SSL_CA_LOCATION", "/certs/ca.crt")


def _build_producer_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "acks": "all",
        "enable.idempotence": True,
        "max.in.flight.requests.per.connection": 5,
        "retries": 2147483647,
        "retry.backoff.ms": 500,
        "compression.type": "snappy",
        "linger.ms": 5,
        "batch.size": 65536,
        "client.id": "agent-finance-producer",
    }
    if KAFKA_SECURITY_PROTOCOL != "PLAINTEXT":
        cfg.update({
            "security.protocol": KAFKA_SECURITY_PROTOCOL,
            "sasl.mechanism": KAFKA_SASL_MECHANISM,
            "sasl.username": KAFKA_SASL_USERNAME,
            "sasl.password": KAFKA_SASL_PASSWORD,
        })
        if "SSL" in KAFKA_SECURITY_PROTOCOL:
            cfg["ssl.ca.location"] = KAFKA_SSL_CA_LOCATION
    return cfg


class FinanceKafkaProducer:
    """Kafka producer for Agent Embedded Finance events."""

    def __init__(self):
        self._producer: Optional[Producer] = None
        self._sent = 0
        self._failed = 0

    def _get_producer(self) -> Producer:
        if self._producer is None:
            self._producer = Producer(_build_producer_config())
            logger.info("FinanceKafkaProducer initialized")
        return self._producer

    def _delivery_callback(self, err, msg):
        if err:
            self._failed += 1
            logger.error("Kafka delivery failed | topic=%s error=%s", msg.topic(), err)
        else:
            self._sent += 1

    def _publish(self, topic: str, payload: Dict[str, Any], key: Optional[str] = None) -> bool:
        try:
            p = self._get_producer()
            p.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=json.dumps(payload).encode("utf-8"),
                headers={
                    "content-type": "application/json",
                    "source-service": "agent-embedded-finance",
                    "event-time": datetime.utcnow().isoformat(),
                },
                callback=self._delivery_callback,
            )
            p.poll(0)
            return True
        except KafkaException as e:
            logger.error("Kafka publish error | topic=%s error=%s", topic, e)
            return False

    def publish_loan_application_submitted(self, agent_id: str, tenant_id: str,
                                            application_id: str, product_type: str,
                                            requested_amount: float) -> bool:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": FinanceTopics.LOAN_APPLICATION_SUBMITTED,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "product_type": product_type,
            "requested_amount": requested_amount,
            "submitted_at": datetime.utcnow().isoformat(),
            "source_service": "agent-embedded-finance",
        }
        return self._publish(FinanceTopics.LOAN_APPLICATION_SUBMITTED, payload, key=agent_id)

    def publish_loan_approved(self, agent_id: str, tenant_id: str,
                               application_id: str, approved_amount: float,
                               interest_rate: float, tenure_days: int) -> bool:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": FinanceTopics.LOAN_APPROVED,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "approved_amount": approved_amount,
            "interest_rate": interest_rate,
            "tenure_days": tenure_days,
            "approved_at": datetime.utcnow().isoformat(),
            "source_service": "agent-embedded-finance",
        }
        return self._publish(FinanceTopics.LOAN_APPROVED, payload, key=agent_id)

    def publish_loan_rejected(self, agent_id: str, tenant_id: str,
                               application_id: str, rejection_reason: str) -> bool:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": FinanceTopics.LOAN_REJECTED,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "application_id": application_id,
            "rejection_reason": rejection_reason,
            "rejected_at": datetime.utcnow().isoformat(),
            "source_service": "agent-embedded-finance",
        }
        return self._publish(FinanceTopics.LOAN_REJECTED, payload, key=agent_id)

    def publish_loan_disbursed(self, event: LoanDisbursedEvent) -> bool:
        return self._publish(FinanceTopics.LOAN_DISBURSED, event.to_dict(), key=event.agent_id)

    def publish_loan_repaid(self, event: LoanRepaidEvent) -> bool:
        topic = FinanceTopics.LOAN_SETTLED if event.is_settled else FinanceTopics.LOAN_REPAID
        return self._publish(topic, event.to_dict(), key=event.agent_id)

    def publish_loan_overdue(self, agent_id: str, tenant_id: str, loan_id: str,
                              days_overdue: int, outstanding_balance: float) -> bool:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": FinanceTopics.LOAN_OVERDUE,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "loan_id": loan_id,
            "days_overdue": days_overdue,
            "outstanding_balance": outstanding_balance,
            "flagged_at": datetime.utcnow().isoformat(),
            "source_service": "agent-embedded-finance",
        }
        return self._publish(FinanceTopics.LOAN_OVERDUE, payload, key=agent_id)

    def publish_bnpl_order_created(self, agent_id: str, tenant_id: str,
                                    order_id: str, merchant_name: str,
                                    total_amount: float, installments: int) -> bool:
        payload = {
            "event_id": str(uuid.uuid4()),
            "event_type": FinanceTopics.BNPL_ORDER_CREATED,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "order_id": order_id,
            "merchant_name": merchant_name,
            "total_amount": total_amount,
            "installments": installments,
            "created_at": datetime.utcnow().isoformat(),
            "source_service": "agent-embedded-finance",
        }
        return self._publish(FinanceTopics.BNPL_ORDER_CREATED, payload, key=agent_id)

    def publish_credit_limit_updated(self, event: CreditLimitUpdatedEvent) -> bool:
        return self._publish(FinanceTopics.CREDIT_LIMIT_UPDATED, event.to_dict(), key=event.agent_id)

    def flush(self, timeout: float = 10.0):
        if self._producer:
            self._producer.flush(timeout=timeout)

    def stats(self) -> Dict[str, int]:
        return {"sent": self._sent, "failed": self._failed}


_producer_instance: Optional[FinanceKafkaProducer] = None


def get_finance_kafka_producer() -> FinanceKafkaProducer:
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = FinanceKafkaProducer()
    return _producer_instance
