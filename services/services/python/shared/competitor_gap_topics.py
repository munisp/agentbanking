"""
Shared Kafka topic registry for all 8 competitor-gap services.
All topics follow the pattern: {domain}.{entity}.{event}
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MultiSimTopics:
    SIGNAL_UPDATED       = "terminal.sim.signal_updated"
    FAILOVER_TRIGGERED   = "terminal.sim.failover_triggered"
    FAILOVER_RESOLVED    = "terminal.sim.failover_resolved"
    CONNECTIVITY_LOST    = "terminal.sim.connectivity_lost"
    CONNECTIVITY_RESTORED = "terminal.sim.connectivity_restored"


@dataclass(frozen=True)
class ReversalTopics:
    REVERSAL_INITIATED   = "transaction.reversal.initiated"
    REVERSAL_COMPLETED   = "transaction.reversal.completed"
    REVERSAL_FAILED      = "transaction.reversal.failed"
    REVERSAL_SLA_BREACH  = "transaction.reversal.sla_breach"
    DOUBLE_DEBIT_DETECTED = "transaction.reversal.double_debit_detected"


@dataclass(frozen=True)
class WalletTopics:
    BALANCE_UPDATED      = "agent.wallet.balance_updated"
    LEDGER_ENTRY_CREATED = "agent.wallet.ledger_entry_created"
    STATEMENT_GENERATED  = "agent.wallet.statement_generated"
    LOW_BALANCE_ALERT    = "agent.wallet.low_balance_alert"
    FLOAT_THRESHOLD_HIT  = "agent.wallet.float_threshold_hit"


@dataclass(frozen=True)
class CBNReportingTopics:
    REPORT_GENERATED     = "compliance.cbn.report_generated"
    REPORT_SUBMITTED     = "compliance.cbn.report_submitted"
    SAR_FILED            = "compliance.cbn.sar_filed"
    REPORT_DUE_REMINDER  = "compliance.cbn.report_due_reminder"
    FRAUD_CASE_REPORTED  = "compliance.cbn.fraud_case_reported"


@dataclass(frozen=True)
class NFCQRTopics:
    QR_GENERATED         = "payment.qr.generated"
    QR_SCANNED           = "payment.qr.scanned"
    NFC_TAP_RECEIVED     = "payment.nfc.tap_received"
    SELF_SERVICE_TXN     = "payment.self_service.transaction_initiated"
    SELF_SERVICE_COMPLETE = "payment.self_service.transaction_completed"


@dataclass(frozen=True)
class ReceiptTopics:
    RECEIPT_GENERATED    = "receipt.generated"
    RECEIPT_SENT_SMS     = "receipt.delivered.sms"
    RECEIPT_SENT_WHATSAPP = "receipt.delivered.whatsapp"
    RECEIPT_SENT_EMAIL   = "receipt.delivered.email"
    RECEIPT_FAILED       = "receipt.delivery_failed"
    RECEIPT_RESENT       = "receipt.resent"


@dataclass(frozen=True)
class TrainingTopics:
    AGENT_ENROLLED       = "training.agent.enrolled"
    MODULE_COMPLETED     = "training.module.completed"
    QUIZ_PASSED          = "training.quiz.passed"
    QUIZ_FAILED          = "training.quiz.failed"
    CERTIFICATE_ISSUED   = "training.certificate.issued"
    CBN_COMPLIANCE_MET   = "training.compliance.cbn_requirements_met"
    COMPLIANCE_OVERDUE   = "training.compliance.overdue"


@dataclass(frozen=True)
class LiquidityTopics:
    REQUEST_CREATED      = "liquidity.request.created"
    OFFER_CREATED        = "liquidity.offer.created"
    MATCH_MADE           = "liquidity.match.made"
    TRANSFER_INITIATED   = "liquidity.transfer.initiated"
    REPAYMENT_MADE       = "liquidity.repayment.made"
    REPAYMENT_OVERDUE    = "liquidity.repayment.overdue"
    REPUTATION_UPDATED   = "liquidity.reputation.updated"


# Singleton instances
MULTI_SIM_TOPICS    = MultiSimTopics()
REVERSAL_TOPICS     = ReversalTopics()
WALLET_TOPICS       = WalletTopics()
CBN_TOPICS          = CBNReportingTopics()
NFC_QR_TOPICS       = NFCQRTopics()
RECEIPT_TOPICS      = ReceiptTopics()
TRAINING_TOPICS     = TrainingTopics()
LIQUIDITY_TOPICS    = LiquidityTopics()

# All topics for Kafka admin topic creation
ALL_COMPETITOR_GAP_TOPICS = [
    # Multi-SIM
    MULTI_SIM_TOPICS.SIGNAL_UPDATED, MULTI_SIM_TOPICS.FAILOVER_TRIGGERED,
    MULTI_SIM_TOPICS.FAILOVER_RESOLVED, MULTI_SIM_TOPICS.CONNECTIVITY_LOST,
    MULTI_SIM_TOPICS.CONNECTIVITY_RESTORED,
    # Reversal
    REVERSAL_TOPICS.REVERSAL_INITIATED, REVERSAL_TOPICS.REVERSAL_COMPLETED,
    REVERSAL_TOPICS.REVERSAL_FAILED, REVERSAL_TOPICS.REVERSAL_SLA_BREACH,
    REVERSAL_TOPICS.DOUBLE_DEBIT_DETECTED,
    # Wallet
    WALLET_TOPICS.BALANCE_UPDATED, WALLET_TOPICS.LEDGER_ENTRY_CREATED,
    WALLET_TOPICS.STATEMENT_GENERATED, WALLET_TOPICS.LOW_BALANCE_ALERT,
    WALLET_TOPICS.FLOAT_THRESHOLD_HIT,
    # CBN
    CBN_TOPICS.REPORT_GENERATED, CBN_TOPICS.REPORT_SUBMITTED,
    CBN_TOPICS.SAR_FILED, CBN_TOPICS.REPORT_DUE_REMINDER,
    CBN_TOPICS.FRAUD_CASE_REPORTED,
    # NFC/QR
    NFC_QR_TOPICS.QR_GENERATED, NFC_QR_TOPICS.QR_SCANNED,
    NFC_QR_TOPICS.NFC_TAP_RECEIVED, NFC_QR_TOPICS.SELF_SERVICE_TXN,
    NFC_QR_TOPICS.SELF_SERVICE_COMPLETE,
    # Receipt
    RECEIPT_TOPICS.RECEIPT_GENERATED, RECEIPT_TOPICS.RECEIPT_SENT_SMS,
    RECEIPT_TOPICS.RECEIPT_SENT_WHATSAPP, RECEIPT_TOPICS.RECEIPT_SENT_EMAIL,
    RECEIPT_TOPICS.RECEIPT_FAILED, RECEIPT_TOPICS.RECEIPT_RESENT,
    # Training
    TRAINING_TOPICS.AGENT_ENROLLED, TRAINING_TOPICS.MODULE_COMPLETED,
    TRAINING_TOPICS.QUIZ_PASSED, TRAINING_TOPICS.QUIZ_FAILED,
    TRAINING_TOPICS.CERTIFICATE_ISSUED, TRAINING_TOPICS.CBN_COMPLIANCE_MET,
    TRAINING_TOPICS.COMPLIANCE_OVERDUE,
    # Liquidity
    LIQUIDITY_TOPICS.REQUEST_CREATED, LIQUIDITY_TOPICS.OFFER_CREATED,
    LIQUIDITY_TOPICS.MATCH_MADE, LIQUIDITY_TOPICS.TRANSFER_INITIATED,
    LIQUIDITY_TOPICS.REPAYMENT_MADE, LIQUIDITY_TOPICS.REPAYMENT_OVERDUE,
    LIQUIDITY_TOPICS.REPUTATION_UPDATED,
]
