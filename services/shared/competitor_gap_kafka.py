"""
Kafka producers and consumers for all 8 competitor-gap services.
Each service gets a dedicated producer class and a consumer class.
"""
import logging
from typing import Any, Callable, Dict

from .kafka_base import BaseKafkaProducer, BaseKafkaConsumer
from .competitor_gap_topics import (
    MULTI_SIM_TOPICS, REVERSAL_TOPICS, WALLET_TOPICS, CBN_TOPICS,
    NFC_QR_TOPICS, RECEIPT_TOPICS, TRAINING_TOPICS, LIQUIDITY_TOPICS,
)

logger = logging.getLogger(__name__)


# ─── A1: Multi-SIM Failover ──────────────────────────────────────────────────

class MultiSimKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("multi-sim-failover")

    def publish_signal_updated(self, terminal_id: str, sim_slot: int, signal_strength: int,
                                network_operator: str, tenant_id: str) -> bool:
        return self.publish(MULTI_SIM_TOPICS.SIGNAL_UPDATED, {
            "terminal_id": terminal_id, "sim_slot": sim_slot,
            "signal_strength": signal_strength, "network_operator": network_operator,
            "tenant_id": tenant_id,
        }, key=terminal_id)

    def publish_failover_triggered(self, terminal_id: str, from_slot: int, to_slot: int,
                                    reason: str, tenant_id: str) -> bool:
        return self.publish(MULTI_SIM_TOPICS.FAILOVER_TRIGGERED, {
            "terminal_id": terminal_id, "from_slot": from_slot,
            "to_slot": to_slot, "reason": reason, "tenant_id": tenant_id,
        }, key=terminal_id)

    def publish_failover_resolved(self, terminal_id: str, active_slot: int,
                                   tenant_id: str) -> bool:
        return self.publish(MULTI_SIM_TOPICS.FAILOVER_RESOLVED, {
            "terminal_id": terminal_id, "active_slot": active_slot, "tenant_id": tenant_id,
        }, key=terminal_id)

    def publish_connectivity_lost(self, terminal_id: str, tenant_id: str) -> bool:
        return self.publish(MULTI_SIM_TOPICS.CONNECTIVITY_LOST, {
            "terminal_id": terminal_id, "tenant_id": tenant_id,
        }, key=terminal_id)

    def publish_connectivity_restored(self, terminal_id: str, active_slot: int,
                                       tenant_id: str) -> bool:
        return self.publish(MULTI_SIM_TOPICS.CONNECTIVITY_RESTORED, {
            "terminal_id": terminal_id, "active_slot": active_slot, "tenant_id": tenant_id,
        }, key=terminal_id)


class MultiSimKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("multi-sim-failover", [
            MULTI_SIM_TOPICS.SIGNAL_UPDATED,
            MULTI_SIM_TOPICS.FAILOVER_TRIGGERED,
            MULTI_SIM_TOPICS.CONNECTIVITY_LOST,
        ], "multi-sim-failover-consumer-group")


# ─── A3: Instant Reversal Engine ─────────────────────────────────────────────

class ReversalKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("instant-reversal-engine")

    def publish_reversal_initiated(self, reversal_id: str, transaction_id: str,
                                    amount: float, agent_id: str, tenant_id: str) -> bool:
        return self.publish(REVERSAL_TOPICS.REVERSAL_INITIATED, {
            "reversal_id": reversal_id, "transaction_id": transaction_id,
            "amount": amount, "agent_id": agent_id, "tenant_id": tenant_id,
        }, key=transaction_id)

    def publish_reversal_completed(self, reversal_id: str, transaction_id: str,
                                    amount: float, agent_id: str, customer_phone: str,
                                    tenant_id: str) -> bool:
        return self.publish(REVERSAL_TOPICS.REVERSAL_COMPLETED, {
            "reversal_id": reversal_id, "transaction_id": transaction_id,
            "amount": amount, "agent_id": agent_id, "customer_phone": customer_phone,
            "tenant_id": tenant_id,
        }, key=transaction_id)

    def publish_reversal_failed(self, reversal_id: str, transaction_id: str,
                                 reason: str, tenant_id: str) -> bool:
        return self.publish(REVERSAL_TOPICS.REVERSAL_FAILED, {
            "reversal_id": reversal_id, "transaction_id": transaction_id,
            "reason": reason, "tenant_id": tenant_id,
        }, key=transaction_id)

    def publish_sla_breach(self, reversal_id: str, transaction_id: str,
                            elapsed_seconds: int, tenant_id: str) -> bool:
        return self.publish(REVERSAL_TOPICS.REVERSAL_SLA_BREACH, {
            "reversal_id": reversal_id, "transaction_id": transaction_id,
            "elapsed_seconds": elapsed_seconds, "tenant_id": tenant_id,
        }, key=reversal_id)

    def publish_double_debit_detected(self, original_txn_id: str, duplicate_txn_id: str,
                                       amount: float, agent_id: str, tenant_id: str) -> bool:
        return self.publish(REVERSAL_TOPICS.DOUBLE_DEBIT_DETECTED, {
            "original_txn_id": original_txn_id, "duplicate_txn_id": duplicate_txn_id,
            "amount": amount, "agent_id": agent_id, "tenant_id": tenant_id,
        }, key=original_txn_id)


class ReversalKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        # Consumes transaction.completed events to detect failed settlements
        super().__init__("instant-reversal-engine", [
            "transaction.completed",
            "transaction.settlement.failed",
            "transaction.timeout",
        ], "instant-reversal-consumer-group")


# ─── B2: Agent Wallet Transparency ───────────────────────────────────────────

class WalletKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("agent-wallet-transparency")

    def publish_balance_updated(self, agent_id: str, new_balance: float,
                                 change_amount: float, entry_type: str, tenant_id: str) -> bool:
        return self.publish(WALLET_TOPICS.BALANCE_UPDATED, {
            "agent_id": agent_id, "new_balance": new_balance,
            "change_amount": change_amount, "entry_type": entry_type, "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_ledger_entry(self, agent_id: str, entry_id: str, amount: float,
                              entry_type: str, description: str, tenant_id: str) -> bool:
        return self.publish(WALLET_TOPICS.LEDGER_ENTRY_CREATED, {
            "agent_id": agent_id, "entry_id": entry_id, "amount": amount,
            "entry_type": entry_type, "description": description, "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_low_balance_alert(self, agent_id: str, current_balance: float,
                                   threshold: float, tenant_id: str) -> bool:
        return self.publish(WALLET_TOPICS.LOW_BALANCE_ALERT, {
            "agent_id": agent_id, "current_balance": current_balance,
            "threshold": threshold, "tenant_id": tenant_id,
        }, key=agent_id)


class WalletKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("agent-wallet-transparency", [
            "transaction.completed",
            "commission.settlement.completed",
            "agent.float.topped_up",
            "loan.disbursed",
            "loan.repayment.made",
        ], "wallet-transparency-consumer-group")


# ─── B3: CBN Reporting Engine ─────────────────────────────────────────────────

class CBNReportingKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("cbn-reporting-engine")

    def publish_report_generated(self, report_id: str, report_type: str,
                                  period: str, tenant_id: str) -> bool:
        return self.publish(CBN_TOPICS.REPORT_GENERATED, {
            "report_id": report_id, "report_type": report_type,
            "period": period, "tenant_id": tenant_id,
        }, key=report_id)

    def publish_sar_filed(self, sar_id: str, agent_id: str, transaction_id: str,
                           amount: float, tenant_id: str) -> bool:
        return self.publish(CBN_TOPICS.SAR_FILED, {
            "sar_id": sar_id, "agent_id": agent_id, "transaction_id": transaction_id,
            "amount": amount, "tenant_id": tenant_id,
        }, key=sar_id)

    def publish_report_due_reminder(self, tenant_id: str, due_date: str,
                                     days_remaining: int) -> bool:
        return self.publish(CBN_TOPICS.REPORT_DUE_REMINDER, {
            "tenant_id": tenant_id, "due_date": due_date, "days_remaining": days_remaining,
        }, key=tenant_id)


class CBNReportingKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("cbn-reporting-engine", [
            "transaction.completed",
            "fraud.incident.detected",
            "agent.training.completed",
            "compliance.violation.detected",
            "customer.complaint.filed",
        ], "cbn-reporting-consumer-group")


# ─── C5: NFC/QR Payments ─────────────────────────────────────────────────────

class NFCQRKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("nfc-qr-payments")

    def publish_qr_generated(self, qr_id: str, agent_id: str, qr_type: str,
                              amount: float, tenant_id: str) -> bool:
        return self.publish(NFC_QR_TOPICS.QR_GENERATED, {
            "qr_id": qr_id, "agent_id": agent_id, "qr_type": qr_type,
            "amount": amount, "tenant_id": tenant_id,
        }, key=qr_id)

    def publish_qr_scanned(self, qr_id: str, customer_id: str, agent_id: str,
                            tenant_id: str) -> bool:
        return self.publish(NFC_QR_TOPICS.QR_SCANNED, {
            "qr_id": qr_id, "customer_id": customer_id,
            "agent_id": agent_id, "tenant_id": tenant_id,
        }, key=qr_id)

    def publish_self_service_complete(self, txn_id: str, qr_id: str, amount: float,
                                       agent_id: str, customer_id: str, tenant_id: str) -> bool:
        return self.publish(NFC_QR_TOPICS.SELF_SERVICE_COMPLETE, {
            "txn_id": txn_id, "qr_id": qr_id, "amount": amount,
            "agent_id": agent_id, "customer_id": customer_id, "tenant_id": tenant_id,
        }, key=txn_id)


class NFCQRKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("nfc-qr-payments", [
            NFC_QR_TOPICS.QR_SCANNED,
            NFC_QR_TOPICS.NFC_TAP_RECEIVED,
        ], "nfc-qr-consumer-group")


# ─── C6: Real-Time Receipt Engine ────────────────────────────────────────────

class ReceiptKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("realtime-receipt-engine")

    def publish_receipt_generated(self, receipt_id: str, transaction_id: str,
                                   agent_id: str, customer_phone: str,
                                   amount: float, tenant_id: str) -> bool:
        return self.publish(RECEIPT_TOPICS.RECEIPT_GENERATED, {
            "receipt_id": receipt_id, "transaction_id": transaction_id,
            "agent_id": agent_id, "customer_phone": customer_phone,
            "amount": amount, "tenant_id": tenant_id,
        }, key=receipt_id)

    def publish_receipt_sent(self, receipt_id: str, channel: str,
                              recipient: str, tenant_id: str) -> bool:
        topic = {
            "sms": RECEIPT_TOPICS.RECEIPT_SENT_SMS,
            "whatsapp": RECEIPT_TOPICS.RECEIPT_SENT_WHATSAPP,
            "email": RECEIPT_TOPICS.RECEIPT_SENT_EMAIL,
        }.get(channel, RECEIPT_TOPICS.RECEIPT_GENERATED)
        return self.publish(topic, {
            "receipt_id": receipt_id, "channel": channel,
            "recipient": recipient, "tenant_id": tenant_id,
        }, key=receipt_id)

    def publish_receipt_failed(self, receipt_id: str, channel: str,
                                error: str, tenant_id: str) -> bool:
        return self.publish(RECEIPT_TOPICS.RECEIPT_FAILED, {
            "receipt_id": receipt_id, "channel": channel,
            "error": error, "tenant_id": tenant_id,
        }, key=receipt_id)


class ReceiptKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        # Consumes all transaction completion events to auto-generate receipts
        super().__init__("realtime-receipt-engine", [
            "transaction.completed",
            NFC_QR_TOPICS.SELF_SERVICE_COMPLETE,
            "payment.bill.completed",
            "payment.airtime.completed",
        ], "receipt-engine-consumer-group")


# ─── D1: Agent Training Academy ──────────────────────────────────────────────

class TrainingKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("agent-training-academy")

    def publish_agent_enrolled(self, agent_id: str, course_id: str,
                                enrollment_id: str, tenant_id: str) -> bool:
        return self.publish(TRAINING_TOPICS.AGENT_ENROLLED, {
            "agent_id": agent_id, "course_id": course_id,
            "enrollment_id": enrollment_id, "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_module_completed(self, agent_id: str, course_id: str,
                                  module_id: str, score: float, tenant_id: str) -> bool:
        return self.publish(TRAINING_TOPICS.MODULE_COMPLETED, {
            "agent_id": agent_id, "course_id": course_id,
            "module_id": module_id, "score": score, "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_certificate_issued(self, agent_id: str, course_id: str,
                                    certificate_id: str, is_cbn_required: bool,
                                    tenant_id: str) -> bool:
        return self.publish(TRAINING_TOPICS.CERTIFICATE_ISSUED, {
            "agent_id": agent_id, "course_id": course_id,
            "certificate_id": certificate_id, "is_cbn_required": is_cbn_required,
            "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_cbn_compliance_met(self, agent_id: str, tenant_id: str) -> bool:
        return self.publish(TRAINING_TOPICS.CBN_COMPLIANCE_MET, {
            "agent_id": agent_id, "tenant_id": tenant_id,
        }, key=agent_id)

    def publish_compliance_overdue(self, agent_id: str, overdue_courses: list,
                                    tenant_id: str) -> bool:
        return self.publish(TRAINING_TOPICS.COMPLIANCE_OVERDUE, {
            "agent_id": agent_id, "overdue_courses": overdue_courses,
            "tenant_id": tenant_id,
        }, key=agent_id)


class TrainingKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("agent-training-academy", [
            "agent.onboarded",
            "agent.scorecard.computed",  # Trigger compliance check on scorecard update
        ], "training-academy-consumer-group")


# ─── D2: Agent Liquidity Network ─────────────────────────────────────────────

class LiquidityKafkaProducer(BaseKafkaProducer):
    def __init__(self):
        super().__init__("agent-liquidity-network")

    def publish_request_created(self, request_id: str, agent_id: str,
                                  amount: float, urgency: str, tenant_id: str) -> bool:
        return self.publish(LIQUIDITY_TOPICS.REQUEST_CREATED, {
            "request_id": request_id, "agent_id": agent_id,
            "amount": amount, "urgency": urgency, "tenant_id": tenant_id,
        }, key=request_id)

    def publish_match_made(self, match_id: str, requester_id: str, provider_id: str,
                            amount: float, tenant_id: str) -> bool:
        return self.publish(LIQUIDITY_TOPICS.MATCH_MADE, {
            "match_id": match_id, "requester_id": requester_id,
            "provider_id": provider_id, "amount": amount, "tenant_id": tenant_id,
        }, key=match_id)

    def publish_transfer_initiated(self, match_id: str, amount: float,
                                    from_agent: str, to_agent: str, tenant_id: str) -> bool:
        return self.publish(LIQUIDITY_TOPICS.TRANSFER_INITIATED, {
            "match_id": match_id, "amount": amount,
            "from_agent": from_agent, "to_agent": to_agent, "tenant_id": tenant_id,
        }, key=match_id)

    def publish_repayment_made(self, match_id: str, amount: float,
                                from_agent: str, to_agent: str, tenant_id: str) -> bool:
        return self.publish(LIQUIDITY_TOPICS.REPAYMENT_MADE, {
            "match_id": match_id, "amount": amount,
            "from_agent": from_agent, "to_agent": to_agent, "tenant_id": tenant_id,
        }, key=match_id)

    def publish_reputation_updated(self, agent_id: str, new_score: float,
                                    reason: str, tenant_id: str) -> bool:
        return self.publish(LIQUIDITY_TOPICS.REPUTATION_UPDATED, {
            "agent_id": agent_id, "new_score": new_score,
            "reason": reason, "tenant_id": tenant_id,
        }, key=agent_id)


class LiquidityKafkaConsumer(BaseKafkaConsumer):
    def __init__(self):
        super().__init__("agent-liquidity-network", [
            LIQUIDITY_TOPICS.REPAYMENT_OVERDUE,
            "agent.wallet.low_balance_alert",  # Trigger liquidity request suggestion
            LIQUIDITY_TOPICS.MATCH_MADE,
        ], "liquidity-network-consumer-group")


# ─── Singleton accessors ──────────────────────────────────────────────────────

_producers: Dict[str, Any] = {}


def get_producer(service: str) -> BaseKafkaProducer:
    if service not in _producers:
        mapping = {
            "multi-sim-failover": MultiSimKafkaProducer,
            "instant-reversal-engine": ReversalKafkaProducer,
            "agent-wallet-transparency": WalletKafkaProducer,
            "cbn-reporting-engine": CBNReportingKafkaProducer,
            "nfc-qr-payments": NFCQRKafkaProducer,
            "realtime-receipt-engine": ReceiptKafkaProducer,
            "agent-training-academy": TrainingKafkaProducer,
            "agent-liquidity-network": LiquidityKafkaProducer,
        }
        cls = mapping.get(service)
        if cls:
            _producers[service] = cls()
    return _producers.get(service)
