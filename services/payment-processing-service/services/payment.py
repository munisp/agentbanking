from utils import (
    create_logger,
    PubsubTopics,
    CurrencyEnum,
    CurrencyLedgerId,
    TransactionStatus,
)
from utils.coa_client import CoAClient
from adapters import (
    TigerBeetleAdapter,
    AccountServiceAdapter,
    LoanServiceAdapter,
    LpoServiceAdapter,
    InsuranceServiceAdapter,
    SupplyChainServiceAdapter,
    AuditServiceAdapter,
    ExchangeRateServiceAdapter,
    FraudEngineAdapter,
    CommissionServiceAdapter,
    ComplianceServiceAdapter,
    LoyaltyServiceAdapter,
    NetworkOpsAdapter,
)
from schemas import (
    InitiatePaymentSchema,
    InitiateDepositSchema,
    InitiateDepositWithAccountNumberSchema,
    TransactionEventSchema,
    InitiateLoanPaymentSchema,
    InitiateLPOPaymentSchema,
    Context,
    InitiateSystemPayoutSchema,
    InitiateInsurancePremiumPaymentSchema,
    SupplyChainFinancingPaymentSchema,
    AuditEventSchema,
)
from events import publish_transaction_event
from datetime import datetime, timezone
from typing import Any, Optional
import uuid
from adapters import payment_rails_connector_adapter
from schemas.payment import ExternalTransferSchema, ExternalDebitSchema

logger = create_logger(__name__)

_tigerbeetle_adapter = TigerBeetleAdapter()


class PaymentService:
    def __init__(self):
        self.__tigerbeetle_adapter = _tigerbeetle_adapter
        self.__loan_service_adapter = LoanServiceAdapter()
        self.__lpo_service_adapter = LpoServiceAdapter()
        self.__insurance_service_adapter = InsuranceServiceAdapter()
        self.__account_service_adapter = AccountServiceAdapter()
        self.__supply_chain_service_adapter = SupplyChainServiceAdapter()
        self.__exchange_rate_service_adapter = ExchangeRateServiceAdapter()
        self.__fraud_engine_adapter = FraudEngineAdapter()
        self.__coa_client = CoAClient()
        self.__commission_service_adapter = CommissionServiceAdapter()
        self.__compliance_adapter = ComplianceServiceAdapter()
        self.__loyalty_adapter = LoyaltyServiceAdapter()
        self.__network_ops_adapter = NetworkOpsAdapter()

    @staticmethod
    def _to_minor_units(amount: float) -> int:
        return int(round(float(amount)))

    @staticmethod
    def _to_major_units(minor_units: int) -> float:
        return float(minor_units) / 100.0

    def _get_account_currency(self, account_id: int, context: Context) -> str:
        account = self.__account_service_adapter.get_account_by_id(
            str(account_id), context
        )
        account_data = account.get("account") if isinstance(account, dict) else None
        currency = (account_data or {}).get("account_currency")
        if not currency:
            raise Exception(f"Unable to determine currency for account {account_id}")
        return str(currency).upper()

    def _get_account_balance_minor_units(
        self, account_id: int, context: Context
    ) -> int:
        account = self.__account_service_adapter.get_account_by_id(
            str(account_id), context
        )
        account_data = account.get("account") if isinstance(account, dict) else None

        credits_posted = int((account_data or {}).get("credits_posted", 0))
        debits_posted = int((account_data or {}).get("debits_posted", 0))

        return credits_posted - debits_posted

    def _get_currency_context(self, currency: str, base_context: Context) -> Context:
        return Context(
            tenant_id=base_context.tenant_id,
            keycloak_id=base_context.keycloak_id,
            ledger_id=str(CurrencyLedgerId.from_currency(currency)),
            mint_account_id=base_context.mint_account_id,
        )

    def _get_mint_account_for_currency(
        self, currency: str, base_context: Context
    ) -> int:
        currency_context = self._get_currency_context(currency, base_context)

        mint_account = self.__account_service_adapter.get_mint_account_by_ledger(
            currency_context
        )
        mint_account_id = (mint_account or {}).get("id")
        if mint_account_id is None:
            raise Exception(f"Mint account not found for currency {currency}")
        return int(mint_account_id)

    def _get_mint_account_for_ledger(
        self, ledger_id: int, base_context: Context
    ) -> int:
        ledger_context = Context(
            tenant_id=base_context.tenant_id,
            keycloak_id=base_context.keycloak_id,
            ledger_id=str(ledger_id),
            mint_account_id=base_context.mint_account_id,
        )

        mint_account = self.__account_service_adapter.get_mint_account_by_ledger(
            ledger_context
        )
        mint_account_id = (mint_account or {}).get("id")
        if mint_account_id is None:
            raise Exception(f"Mint account not found for ledger {ledger_id}")
        return int(mint_account_id)

    @staticmethod
    def _to_uuid_string(value: Any, prefix: str) -> str:
        raw_value = str(value or "").strip()
        if not raw_value:
            return str(uuid.uuid4())

        try:
            return str(uuid.UUID(raw_value))
        except Exception:
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"54agent:{prefix}:{raw_value}"))

    def _run_fraud_precheck(
        self,
        *,
        transaction_ref: str,
        transaction_type: str,
        amount: float,
        currency: str,
        context: Context,
        source_account: Optional[str] = None,
        destination_account: Optional[str] = None,
        agent_identifier: Optional[str] = None,
        customer_identifier: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        fraud_payload = {
            "transaction_id": self._to_uuid_string(transaction_ref, "transaction_ref"),
            "transaction_ref": transaction_ref,
            "transaction_type": transaction_type,
            "amount": float(amount),
            "currency": str(currency or "NGN").upper(),
            "agent_id": self._to_uuid_string(
                agent_identifier or context.keycloak_id,
                "agent",
            ),
            "customer_id": (
                self._to_uuid_string(customer_identifier, "customer")
                if customer_identifier
                else None
            ),
            "source_account": source_account,
            "destination_account": destination_account,
            "ip_address": None,
            "device_fingerprint": None,
            "latitude": None,
            "longitude": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        fraud_result = self.__fraud_engine_adapter.score_transaction(
            fraud_payload, context
        )

        decision = str((fraud_result or {}).get("decision") or "").lower()
        score = float((fraud_result or {}).get("score") or 0.0)

        logger.info(
            "Fraud pre-check completed transaction_ref=%s decision=%s score=%.3f",
            transaction_ref,
            decision,
            score,
        )

        if decision == "block":
            # Notify compliance before raising so the fraud record is captured
            self.__compliance_adapter.notify_fraud(
                fraud_type="UNAUTHORIZED_TRANSFER",
                amount_attempted=float(amount),
                channel=str(metadata.get("channel", "UNKNOWN")) if metadata else "UNKNOWN",
                incident_date=datetime.now(timezone.utc).isoformat(),
                victim_account=str(destination_account or ""),
                perpetrator_info=f"agent={agent_identifier or context.keycloak_id} score={score:.3f}",
            )
            raise Exception(f"Transaction blocked by fraud engine (score={score:.3f})")

        if decision == "review":
            raise Exception(
                f"Transaction flagged for manual fraud review (score={score:.3f})"
            )

    def _notify_compliance(
        self,
        *,
        transaction_id: str,
        transaction_type: str,
        amount_ngn: float,
        agent_id: str,
        customer_name: str = "",
        customer_bvn: str | None = None,
        customer_account: str = "",
    ) -> None:
        try:
            self.__compliance_adapter.notify_transaction(
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                amount_ngn=amount_ngn,
                currency="NGN",
                agent_id=agent_id,
                customer_name=customer_name,
                customer_bvn=customer_bvn,
                customer_account=customer_account,
                transaction_date=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.warning("Compliance notification failed transaction_id=%s error=%s", transaction_id, str(e))

    def _notify_loyalty(
        self,
        *,
        transaction_id: str,
        transaction_type: str,
        amount_ngn: float,
        agent_id: str,
    ) -> None:
        try:
            self.__loyalty_adapter.process_transaction(
                user_id=agent_id,
                reference_id=transaction_id,
                amount_ngn=amount_ngn,
                transaction_type=transaction_type,
            )
        except Exception as e:
            logger.warning("Loyalty notification failed transaction_id=%s error=%s", transaction_id, str(e))

    def _notify_network_ops(
        self,
        *,
        transaction_type: str,
        status: str,
        channel: str = "app",
        medium: str = "internal",
        amount_ngn: Optional[float] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        try:
            self.__network_ops_adapter.register_transaction(
                tx_type=transaction_type,
                channel=channel,
                medium=medium,
                status=status,
                amount=amount_ngn,
                agent_id=agent_id,
            )
        except Exception as e:
            logger.warning(
                "Network ops notification failed transaction_type=%s status=%s error=%s",
                transaction_type, status, str(e),
            )

    def _resolve_external_party_account_id(
        self, id_type: str, id_value: str, context: Context
    ) -> int:
        normalized_id_type = str(id_type or "").upper()
        normalized_id_value = str(id_value or "").strip()

        if not normalized_id_value:
            raise Exception("Invalid external party id value")

        def _extract_account_id(resp: dict | None) -> int | None:
            account_data = (resp or {}).get("account") if isinstance(resp, dict) else {}
            account_id = (account_data or {}).get("id")
            return int(account_id) if account_id is not None else None

        if normalized_id_type in {"ACCOUNT_ID", "ACCOUNT_NUMBER"}:
            account = self.__account_service_adapter.get_account_by_account_number(
                normalized_id_value, context
            )
            account_id = _extract_account_id(account)
            if account_id is None:
                raise Exception(
                    f"Unable to resolve account for external party {id_type}:{id_value}"
                )
            return account_id

        if normalized_id_value.isdigit():
            account = self.__account_service_adapter.get_account_by_id(
                normalized_id_value, context
            )
            account_id = _extract_account_id(account)
            if account_id is not None:
                return account_id

        raise Exception(f"Unsupported external party id type for debit: {id_type}")

    def initiate_deposit(self, payload: InitiateDepositSchema, context: Context) -> str:
        """Initiate a deposit."""

        logger.info("Initiating deposit payer=%s payee=%s", context.mint_account_id, payload.recipient)

        commission = self.__commission_service_adapter.calculate_commission(
            agent_id=context.keycloak_id,
            transaction_type="deposit",
            amount=float(payload.amount),
            currency="NGN",
            transaction_ref=f"deposit:{context.tenant_id}:{context.mint_account_id}:{payload.recipient}:{payload.amount}",
            context=context,
            metadata={"recipient": str(payload.recipient), "note": payload.note},
        )
        amount_minor = int(commission["net_amount_minor"])

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=int(context.mint_account_id),
                payee=payload.recipient,
                amount=amount_minor,
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Deposit transfer created transaction_id=%s", transaction_id)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(payload.recipient),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(payload.recipient),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_network_ops(
                transaction_type="cash_in",
                status="success",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Deposit failed error=%s", str(e))
            self._notify_network_ops(
                transaction_type="cash_in",
                status="failed",
                amount_ngn=float(payload.amount) if payload.amount else None,
                agent_id=context.keycloak_id,
            )
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_INITIATED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount_minor),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=payload.note,
                        payee=str(payload.recipient),
                        payer="MINT_ACCOUNT",
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_deposit_with_account_number(
        self, payload: InitiateDepositWithAccountNumberSchema, context: Context
    ) -> str:
        """Initiate a deposit using recipient account number."""

        account_response = self.__account_service_adapter.get_account_by_account_number(
            payload.recipient_account_number, context
        )

        recipient_account_id: int = account_response.get("account").get("id")

        if recipient_account_id is None:
            raise Exception("Failed to retrieve recipient account.")

        logger.info(
            "Initiating deposit payer=%s payee_account_number=%s payee_account=%s",
            context.mint_account_id,
            payload.recipient_account_number,
            recipient_account_id,
        )

        commission = self.__commission_service_adapter.calculate_commission(
            agent_id=context.keycloak_id,
            transaction_type="deposit",
            amount=float(payload.amount),
            currency="NGN",
            transaction_ref=f"deposit:{context.tenant_id}:{context.mint_account_id}:{recipient_account_id}:{payload.amount}",
            context=context,
            metadata={
                "recipient_account_number": payload.recipient_account_number,
                "note": payload.note,
            },
        )
        amount_minor = int(commission["net_amount_minor"])

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=int(context.mint_account_id),
                payee=recipient_account_id,
                amount=amount_minor,
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Deposit transfer created transaction_id=%s", transaction_id)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(recipient_account_id),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(recipient_account_id),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
                customer_account=payload.recipient_account_number,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_network_ops(
                transaction_type="cash_in",
                status="success",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Deposit with account number failed error=%s", str(e))
            self._notify_network_ops(
                transaction_type="cash_in",
                status="failed",
                amount_ngn=float(payload.amount) if payload.amount else None,
                agent_id=context.keycloak_id,
            )
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_INITIATED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount_minor),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=payload.note,
                        payee=str(recipient_account_id),
                        payer="MINT_ACCOUNT",
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_system_payout(
        self, payload: InitiateSystemPayoutSchema, context: Context
    ) -> str:
        """
        Initiate a system payout.
        For a system payout, the recepient is the keycloak id.
        """

        logger.info("Initiating system payout payer=%s payee_keycloak=%s", context.mint_account_id, payload.recipient)

        account_response = self.__account_service_adapter.get_account_by_keycloak_id(
            payload.recipient, context
        )

        account_id: int = account_response.get("account").get("id")

        if account_id is None:
            raise Exception("Failed to retrieve account.")

        logger.info("System payout resolved payee_account=%s", account_id)

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=int(context.mint_account_id),
                payee=account_id,
                amount=int(payload.amount),
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("System payout transfer created transaction_id=%s", transaction_id)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(payload.amount),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(account_id),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(payload.amount),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(account_id),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="cash_out",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="cash_out",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("System payout failed error=%s", str(e))
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_INITIATED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(payload.amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=payload.note,
                        payee=str(account_id),
                        payer="MINT_ACCOUNT",
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_transfer(
        self, payload: InitiatePaymentSchema, context: Context
    ) -> str:
        """Initiate a transfer."""

        is_outbound = bool(payload.payee_bank_code)

        # Validate Account
        payee_context = Context(
            tenant_id=payload.payee_tenant_id or context.tenant_id,
            keycloak_id=context.keycloak_id,
            ledger_id=context.ledger_id,
            mint_account_id=context.mint_account_id,
        )

        payer_account_data: dict = {}
        if isinstance(payload.payer, str):
            payer_account = (
                self.__account_service_adapter.get_account_by_account_number(
                    payload.payer, context
                )
            )
            payer_account_data = (
                payer_account.get("account") if isinstance(payer_account, dict) else {}
            )
            payer_account_id = payer_account_data.get("id")
        else:
            payer_account_id = payload.payer
            payer_account = self.__account_service_adapter.get_account_by_id(
                str(payload.payer), context
            )
            payer_account_data = (
                payer_account.get("account") if isinstance(payer_account, dict) else {}
            )

        if payer_account_id is None:
            raise Exception("Unable to resolve payer account")

        if is_outbound:
            payee_account_id = int(context.mint_account_id)
            payee_account_data: dict = {}
        else:
            if isinstance(payload.payee, str):
                payee_account = (
                    self.__account_service_adapter.get_account_by_account_number(
                        payload.payee, payee_context
                    )
                )
                payee_account_data = (
                    payee_account.get("account")
                    if isinstance(payee_account, dict)
                    else {}
                )
                payee_account_id = payee_account_data.get("id")
            else:
                payee_account_id = payload.payee
                payee_account = self.__account_service_adapter.get_account_by_id(
                    str(payload.payee), payee_context
                )
                payee_account_data = (
                    payee_account.get("account")
                    if isinstance(payee_account, dict)
                    else {}
                )

            if payee_account_id is None:
                raise Exception("Unable to resolve payee account")

        logger.info("Payer Account ID: %s", payer_account_id)
        logger.info("Payee Account ID: %s", payee_account_id)

        fraud_currency = str(
            (payer_account_data or {}).get("account_currency") or ""
        ).upper() or self._get_account_currency(int(payer_account_id), context)
        fraud_reference = f"transfer:{payer_account_id}:{payee_account_id}:{datetime.now(timezone.utc).timestamp()}"

        commission = self.__commission_service_adapter.calculate_commission(
            agent_id=context.keycloak_id,
            transaction_type="transfer",
            amount=float(payload.amount),
            currency=fraud_currency,
            transaction_ref=fraud_reference,
            context=context,
            metadata={
                "is_outbound": is_outbound,
                "payee_bank_code": payload.payee_bank_code,
                "payee_tenant_id": payload.payee_tenant_id,
            },
        )
        net_amount_minor = int(commission["net_amount_minor"])

        self._run_fraud_precheck(
            transaction_ref=fraud_reference,
            transaction_type="transfer",
            amount=float(payload.amount),
            currency=fraud_currency,
            context=context,
            source_account=str(payer_account_id),
            destination_account=str(payee_account_id),
            agent_identifier=context.keycloak_id,
            customer_identifier=(payer_account_data or {}).get("keycloak_id"),
            metadata={
                "is_outbound": is_outbound,
                "payee_bank_code": payload.payee_bank_code,
                "payee_tenant_id": payload.payee_tenant_id,
            },
        )

        self.__account_service_adapter.check_account(
            str(payer_account_id), payload.pin, context
        )

        if not is_outbound:
            payer_currency = self._get_account_currency(int(payer_account_id), context)
            payee_currency = self._get_account_currency(
                int(payee_account_id), payee_context
            )

            if payer_currency != payee_currency:
                logger.info(
                    "Processing cross-currency transfer payer_currency=%s payee_currency=%s amount=%s",
                    payer_currency,
                    payee_currency,
                    payload.amount,
                )

                payer_mint_account_id = self._get_mint_account_for_currency(
                    payer_currency, context
                )
                payee_mint_account_id = self._get_mint_account_for_currency(
                    payee_currency, payee_context
                )

                debit_minor_amount = net_amount_minor
                if debit_minor_amount <= 0:
                    raise Exception("Transfer amount must be greater than zero")

                fx_rate_data = self.__exchange_rate_service_adapter.get_exchange_rate(
                    payer_currency,
                    payee_currency,
                    context,
                )
                fx_rate = float((fx_rate_data or {}).get("rate"))
                if fx_rate <= 0:
                    raise Exception(
                        f"Invalid exchange rate for {payer_currency}/{payee_currency}"
                    )

                credit_minor_amount = int(round(debit_minor_amount * fx_rate))
                if credit_minor_amount <= 0:
                    raise Exception("Converted amount must be greater than zero")

                payer_balance_minor_amount = self._get_account_balance_minor_units(
                    int(payer_account_id),
                    context,
                )
                if payer_balance_minor_amount < debit_minor_amount:
                    raise Exception(
                        f"Insufficient funds in payer account for {payer_currency} transfer"
                    )

                payee_currency_context = self._get_currency_context(
                    payee_currency,
                    payee_context,
                )
                payee_mint_balance_minor_amount = self._get_account_balance_minor_units(
                    int(payee_mint_account_id),
                    payee_currency_context,
                )
                if payee_mint_balance_minor_amount < credit_minor_amount:
                    raise Exception(
                        f"Insufficient mint liquidity for {payee_currency} conversion: "
                        f"available={self._to_major_units(payee_mint_balance_minor_amount)} "
                        f"required={self._to_major_units(credit_minor_amount)}"
                    )

                debit_reference = self.__tigerbeetle_adapter.transfer(
                    payer=int(payer_account_id),
                    payee=int(payer_mint_account_id),
                    amount=int(debit_minor_amount),
                    ledger=int(CurrencyLedgerId.from_currency(payer_currency)),
                )

                try:
                    credit_reference = self.__tigerbeetle_adapter.transfer(
                        payer=int(payee_mint_account_id),
                        payee=int(payee_account_id),
                        amount=int(credit_minor_amount),
                        ledger=int(CurrencyLedgerId.from_currency(payee_currency)),
                    )
                except Exception as credit_error:
                    logger.error(
                        "Cross-currency credit leg failed, attempting rollback debit_reference=%s error=%s",
                        str(debit_reference),
                        str(credit_error),
                    )
                    try:
                        rollback_reference = self.__tigerbeetle_adapter.transfer(
                            payer=int(payer_mint_account_id),
                            payee=int(payer_account_id),
                            amount=int(debit_minor_amount),
                            ledger=int(CurrencyLedgerId.from_currency(payer_currency)),
                        )
                        logger.info(
                            "Cross-currency rollback completed rollback_reference=%s",
                            str(rollback_reference),
                        )
                    except Exception as rollback_error:
                        logger.critical(
                            "UNRECOVERABLE cross_currency_rollback_failed debit_reference=%s "
                            "rollback_error=%s original_credit_error=%s "
                            "ACTION=manual_ops_recovery_required",
                            str(debit_reference),
                            str(rollback_error),
                            str(credit_error),
                        )
                        raise Exception(
                            f"Debit unrecoverable: rollback failed after credit failure "
                            f"(debit_reference={debit_reference}). Manual ops recovery required."
                        ) from rollback_error

                    publish_transaction_event(
                        PubsubTopics.TRANSACTION_INITIATED,
                        TransactionEventSchema(
                            transaction_id=str(debit_reference),
                            amount=str(debit_minor_amount),
                            completed_at=datetime.now(timezone.utc),
                            currency=CurrencyEnum[payer_currency],
                            note=payload.note,
                            payee=str(payee_account_id),
                            payer=str(payer_account_id),
                            status=TransactionStatus.FAILED,
                            tag="cross_currency",
                            tenant_id=context.tenant_id,
                            ledger_id=context.ledger_id,
                        ),
                    )

                    raise Exception(
                        f"Cross-currency transfer failed during credit leg: {str(credit_error)}"
                    )

                reference = f"{debit_reference}:{credit_reference}"

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_INITIATED,
                    TransactionEventSchema(
                        transaction_id=str(reference),
                        amount=str(credit_minor_amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum[payee_currency],
                        note=payload.note,
                        payee=str(payee_account_id),
                        payer=str(payer_account_id),
                        status=TransactionStatus.INITIATED,
                        tag="cross_currency",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_SUCCESS,
                    TransactionEventSchema(
                        transaction_id=str(reference),
                        amount=str(credit_minor_amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum[payee_currency],
                        note=payload.note,
                        payee=str(payee_account_id),
                        payer=str(payer_account_id),
                        status=TransactionStatus.SUCCESS,
                        tag="cross_currency",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )

                AuditServiceAdapter().create_audit(
                    payload=AuditEventSchema(
                        actor_id=context.keycloak_id,
                        tenant_id=context.tenant_id,
                        event_type="TRANSFER",
                        event_data={
                            "transaction_id": str(reference),
                            "debit_transaction_id": str(debit_reference),
                            "credit_transaction_id": str(credit_reference),
                            "payer": str(payer_account_id),
                            "payee": str(payee_account_id),
                            "gross_amount": str(payload.amount),
                            "commission_amount": str(
                                commission.get("commission_amount", 0)
                            ),
                            "debit_amount": str(debit_minor_amount),
                            "debit_currency": payer_currency,
                            "credit_amount": str(credit_minor_amount),
                            "credit_currency": payee_currency,
                            "exchange_rate": str(fx_rate),
                        },
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    ),
                    context=context,
                )

                return str(reference)

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=int(payer_account_id),
                payee=int(payee_account_id),
                amount=net_amount_minor,
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Transfer created transaction_id=%s", transaction_id)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(net_amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(payee_account_id),
                    payer=str(payer_account_id),
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(net_amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum.NGN,
                    note=payload.note,
                    payee=str(payee_account_id),
                    payer=str(payer_account_id),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="transfer",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
                customer_account=str(payer_account_id),
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="transfer",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_network_ops(
                transaction_type="transfer",
                status="success",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Transfer failed payer=%s payee=%s error=%s", payer_account_id, payee_account_id, str(e))
            self._notify_network_ops(
                transaction_type="transfer",
                status="failed",
                amount_ngn=float(payload.amount) if payload.amount else None,
                agent_id=context.keycloak_id,
            )
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(net_amount_minor),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=payload.note,
                        payee=str(payee_account_id),
                        payer=str(payer_account_id),
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def process_external_credit(
        self, payload: ExternalTransferSchema, context: Context
    ) -> str:
        """Process an external credit by crediting payee account from mint account."""

        normalized_payee = str(payload.party.idValue or "").strip()
        if not normalized_payee:
            raise Exception("Invalid payee")

        payee_account_id: int | None = None
        payee_account_data: dict = {}

        # Try account-number lookup first (more common)
        try:
            payee_account = (
                self.__account_service_adapter.get_account_by_account_number(
                    normalized_payee,
                    context,
                )
            )
            payee_account_data = (
                payee_account.get("account") if isinstance(payee_account, dict) else {}
            )
            payee_account_id = payee_account_data.get("id")
        except Exception as e:
            logger.info(
                "Account-number lookup failed for payee %s, will try numeric ID: %s",
                normalized_payee,
                str(e),
            )

        # Fall back to numeric ID lookup if account-number failed
        if payee_account_id is None and normalized_payee.isdigit():
            payee_account = self.__account_service_adapter.get_account_by_id(
                normalized_payee,
                context,
            )
            payee_account_data = (
                payee_account.get("account") if isinstance(payee_account, dict) else {}
            )
            payee_account_id = payee_account_data.get("id")

        if payee_account_id is None:
            raise Exception(f"Unable to resolve payee account for {normalized_payee}")

        logger.info("Resolved payee account_id=%s for identifier=%s", payee_account_id, normalized_payee)
        logger.info("Running fraud pre-check for external credit transaction for payee_account_id=%s", payee_account_id)
        self._run_fraud_precheck(
            transaction_ref=str(payload.transactionId),
            transaction_type="external_credit",
            amount=float(payload.amount.amount),
            currency=str(payload.amount.currency),
            context=context,
            source_account="mint_account",
            destination_account=str(payee_account_id),
            agent_identifier=context.keycloak_id,
            customer_identifier=(payee_account_data or {}).get("keycloak_id"),
            metadata={
                "external_party_id_type": payload.party.idType,
                "external_party_id_value": payload.party.idValue,
                "metadata": payload.metadata or {},
            },
        )

        if self._to_minor_units(payload.amount.amount) <= 0:
            raise Exception("Transfer amount must be greater than zero")

        payee_currency = str(payee_account_data.get("account_currency") or "").upper()
        if not payee_currency:
            payee_currency = self._get_account_currency(int(payee_account_id), context)

        payload_currency = str(payload.amount.currency).upper()
        if payload_currency != payee_currency:
            logger.warning(
                "External credit payload currency (%s) differs from payee account currency (%s); using payee account currency ledger",
                payload_currency,
                payee_currency,
            )

        commission = self.__commission_service_adapter.calculate_commission(
            agent_id=context.keycloak_id,
            transaction_type="deposit",
            amount=float(payload.amount.amount),
            currency=payee_currency,
            transaction_ref=str(payload.transactionId),
            context=context,
            metadata={
                "external_party_id_type": payload.party.idType,
                "external_party_id_value": payload.party.idValue,
                "metadata": payload.metadata or {},
            },
        )
        amount_minor = int(commission["net_amount_minor"])

        transfer_ledger_id = int(CurrencyLedgerId.from_currency(payee_currency))

        payee_tb_ledger = (payee_account_data or {}).get("ledger")
        if payee_tb_ledger is not None:
            payee_tb_ledger = int(payee_tb_ledger)
            if payee_tb_ledger != transfer_ledger_id:
                logger.warning(
                    "Payee account ledger (%s) differs from currency-derived ledger (%s) for payee=%s; using payee ledger",
                    str(payee_tb_ledger),
                    str(transfer_ledger_id),
                    normalized_payee,
                )
                transfer_ledger_id = payee_tb_ledger

        # Resolve mint account using finalized transfer ledger
        mint_account_id = self._get_mint_account_for_ledger(transfer_ledger_id, context)

        transaction_id = None
        try:
            reference = self.__tigerbeetle_adapter.transfer(
                payer=int(mint_account_id),
                payee=int(payee_account_id),
                amount=amount_minor,
                ledger=transfer_ledger_id,
            )
            transaction_id = str(reference)

            logger.info(
                "External credit processed mint=%s payee=%s amount_minor=%s currency=%s ledger=%s reference=%s",
                str(mint_account_id),
                str(payee_account_id),
                str(amount_minor),
                payee_currency,
                str(transfer_ledger_id),
                transaction_id,
            )

            logger.info("External credit transaction completed successfully for payee_account_id=%s", payee_account_id)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum[payee_currency] if payee_currency in CurrencyEnum.__members__ else CurrencyEnum.NGN,
                    note=str(payload.metadata or ""),
                    payee=str(payee_account_id),
                    payer="MINT_ACCOUNT",
                    status=TransactionStatus.SUCCESS,
                    tag="external_credit",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="cash_in",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_network_ops(
                transaction_type="cash_in",
                status="success",
                channel="pos",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("External credit failed payee=%s error=%s", normalized_payee, str(e))
            self._notify_network_ops(
                transaction_type="cash_in",
                status="failed",
                channel="pos",
                amount_ngn=float(payload.amount.amount) if payload.amount else None,
                agent_id=context.keycloak_id,
            )
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount_minor),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum[payee_currency] if payee_currency in CurrencyEnum.__members__ else CurrencyEnum.NGN,
                        note=str(payload.metadata or ""),
                        payee=str(payee_account_id),
                        payer="MINT_ACCOUNT",
                        status=TransactionStatus.FAILED,
                        tag="external_credit",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def process_external_debit(
        self, payload: ExternalDebitSchema, context: Context
    ) -> str:
        """Process a debit by debiting payer account into mint account."""

        normalized_payer = str(payload.payer or "").strip()
        logger.info("Processing external debit for payer identifier: %s", normalized_payer)
        if not normalized_payer:
            raise Exception("Invalid payer")

        payer_account_id: int | None = None
        payer_account_data: dict = {}

        # Try account-number lookup first (more common)
        try:
            payer_account = (
                self.__account_service_adapter.get_account_by_account_number(
                    normalized_payer,
                    context,
                )
            )
            payer_account_data = (
                payer_account.get("account") if isinstance(payer_account, dict) else {}
            )
            payer_account_id = payer_account_data.get("id")
            logger.info("Account number lookup successful for payer %s, account_id=%s", normalized_payer, payer_account_id)
        except Exception as e:
            logger.info(
                "Account-number lookup failed for %s, will try numeric ID: %s",
                normalized_payer,
                str(e),
            )

        # Fall back to numeric ID lookup if account-number failed
        if payer_account_id is None and normalized_payer.isdigit():
            payer_account = self.__account_service_adapter.get_account_by_id(
                normalized_payer,
                context,
            )
            payer_account_data = (
                payer_account.get("account") if isinstance(payer_account, dict) else {}
            )
            payer_account_id = payer_account_data.get("id")

        if payer_account_id is None:
            raise Exception(f"Unable to resolve payer account for {normalized_payer}")

        logger.info("Resolved payer account_id=%s for identifier %s", payer_account_id, normalized_payer)
        logger.info("Fraud pre-check for external debit transaction_ref=%s payer_account=%s amount=%s currency=%s",
            str(payload.transactionId),
            str(payer_account_id),
            str(payload.amount.amount),
            str(payload.amount.currency),
        )

        self._run_fraud_precheck(
            transaction_ref=str(payload.transactionId),
            transaction_type="external_debit",
            amount=float(payload.amount.amount),
            currency=str(payload.amount.currency),
            context=context,
            source_account=str(payer_account_id),
            destination_account="mint_account",
            agent_identifier=context.keycloak_id,
            customer_identifier=(payer_account_data or {}).get("keycloak_id"),
            metadata={
                "metadata": payload.metadata or {},
            },
        )

        commission = self.__commission_service_adapter.calculate_commission(
            agent_id=context.keycloak_id,
            transaction_type="withdrawal",
            amount=float(payload.amount.amount),
            currency=str(payload.amount.currency),
            transaction_ref=str(payload.transactionId),
            context=context,
            metadata={"metadata": payload.metadata or {}},
        )
        amount_minor = int(commission["net_amount_minor"])
        if amount_minor <= 0:
            raise Exception("Transfer amount must be greater than zero")

        # Resolve mint account for the transfer currency
        mint_account_id = self._get_mint_account_for_currency(
            payload.amount.currency, context
        )

        logger.info("Resolved mint account_id=%s for currency %s", mint_account_id, str(payload.amount.currency))

        debit_currency = str(payload.amount.currency).upper()
        transaction_id = None
       
        try:
            reference = self.__tigerbeetle_adapter.transfer(
                payer=int(payer_account_id),
                payee=int(mint_account_id),
                amount=amount_minor,
                ledger=int(context.ledger_id),
            )
            transaction_id = str(reference)
           
            logger.info(
                "External debit processed payer=%s mint=%s amount_minor=%s currency=%s reference=%s",
                str(payer_account_id),
                str(mint_account_id),
                str(amount_minor),
                debit_currency,
                transaction_id,
            )

            

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount_minor),
                    completed_at=datetime.now(timezone.utc),
                    currency=CurrencyEnum[debit_currency] if debit_currency in CurrencyEnum.__members__ else CurrencyEnum.NGN,
                    note=str(payload.metadata or ""),
                    payee="MINT_ACCOUNT",
                    payer=str(payer_account_id),
                    status=TransactionStatus.SUCCESS,
                    tag="external_debit",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="cash_out",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="cash_out",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_network_ops(
                transaction_type="cash_out",
                status="success",
                channel="pos",
                amount_ngn=float(payload.amount.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("External debit failed payer=%s error=%s", normalized_payer, str(e))
            self._notify_network_ops(
                transaction_type="cash_out",
                status="failed",
                channel="pos",
                amount_ngn=float(payload.amount.amount) if payload.amount else None,
                agent_id=context.keycloak_id,
            )
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount_minor),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum[debit_currency] if debit_currency in CurrencyEnum.__members__ else CurrencyEnum.NGN,
                        note=str(payload.metadata or ""),
                        payee="MINT_ACCOUNT",
                        payer=str(payer_account_id),
                        status=TransactionStatus.FAILED,
                        tag="external_debit",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_loan_payment(
        self, payload: InitiateLoanPaymentSchema, context: Context
    ) -> str:
        """Initiate a loan payment."""

        # Validate Loan

        loan_details = self.__loan_service_adapter.get_loan_details(
            loan_id=payload.loan_id, tenant_id=context.tenant_id
        )

        if not loan_details:
            raise ValueError("Invalid loan")

        if loan_details.get("status") == "completed":
            raise ValueError("Loan payment is already completed")

        if loan_details.get("status") != "disbursed":
            raise ValueError("You can only make payments on disbursed loans")

        # Validate Account

        self.__account_service_adapter.check_account(
            str(payload.payer), payload.pin, context
        )

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=payload.payer,
                payee=int(context.mint_account_id),
                amount=int(payload.amount),
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Loan payment transfer created transaction_id=%s", transaction_id)

            completed_at = datetime.now(timezone.utc)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(payload.amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note="LOAN_PAYMENT",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            result = self.__loan_service_adapter.record_payment(
                transaction_id=transaction_id,
                loan_id=payload.loan_id,
                amount=int(payload.amount),
                payment_date=completed_at.isoformat().replace("+00:00", "Z"),
                payment_method="TRANSFER",
                tenant_id=context.tenant_id,
            )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(payload.amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note="LOAN_PAYMENT",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            recorded_amount = result.get("amount", 0)

            if recorded_amount < int(payload.amount):
                refund_amount = int(payload.amount) - recorded_amount

                refund_id = self.__tigerbeetle_adapter.transfer(
                    payer=int(context.mint_account_id),
                    payee=payload.payer,
                    amount=refund_amount,
                    ledger=int(context.ledger_id),
                )

                logger.info("Loan payment refund transaction_id=%s", str(refund_id))

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_SUCCESS,
                    TransactionEventSchema(
                        transaction_id=str(refund_id),
                        amount=str(refund_amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note="LOAN_PAYMENT_REFUND",
                        payee=str(payload.payer),
                        payer="MINT_ACCOUNT",
                        status=TransactionStatus.SUCCESS,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(payload.amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note="LOAN_PAYMENT",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="loan_payment",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="loan_payment",
                amount_ngn=float(payload.amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Loan payment failed loan_id=%s error=%s", payload.loan_id, str(e))
            if transaction_id:
                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(payload.amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note="LOAN_PAYMENT",
                        payee="MINT_ACCOUNT",
                        payer=str(payload.payer),
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_lpo_payment(
        self, payload: InitiateLPOPaymentSchema, context: Context
    ) -> str:
        """Initiate an lpo payment."""

        # Validate LPO

        lpo_details = self.__lpo_service_adapter.get_lpo_details(
            lpo_id=payload.lpo_id, tenant_id=context.tenant_id
        )

        logger.info("LPO Details: %s", lpo_details)

        amount: float = lpo_details.get("total_repayment", 0)

        logger.info("LPO Amount: %s", amount)

        if not lpo_details:
            raise ValueError("Invalid LPO")

        if lpo_details.get("status") == "completed":
            raise ValueError("LPO payment is already completed")

        if lpo_details.get("status") != "disbursed":
            raise ValueError("You can only make payments on disbursed LPOs")

        # Validate Account

        self.__account_service_adapter.check_account(
            str(payload.payer), payload.pin, context
        )

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=payload.payer,
                payee=int(context.mint_account_id),
                amount=int(amount),
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("LPO payment transfer created transaction_id=%s", transaction_id)

            completed_at = datetime.now(timezone.utc)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"LPO_PAYMENT/{lpo_details.get('issuing_organization')}/{payload.lpo_id}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            result = self.__lpo_service_adapter.record_payment(
                transaction_id=transaction_id,
                lpo_id=payload.lpo_id,
                amount=int(amount),
                payment_date=completed_at.isoformat(),
                payment_method="TRANSFER",
                tenant_id=context.tenant_id,
            )

            if result.get("status") != "success":
                raise ValueError("LPO payment recording failed")

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"LPO_PAYMENT/{lpo_details.get('issuing_organization')}/{payload.lpo_id}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="lpo_payment",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="lpo_payment",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("LPO payment failed lpo_id=%s error=%s", payload.lpo_id, str(e))
            if transaction_id:
                try:
                    self.__tigerbeetle_adapter.transfer(
                        payer=int(context.mint_account_id),
                        payee=payload.payer,
                        amount=int(amount),
                        ledger=int(context.ledger_id),
                    )
                except Exception as refund_error:
                    logger.error("LPO payment refund failed transaction_id=%s error=%s", transaction_id, str(refund_error))

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=f"LPO_PAYMENT/{lpo_details.get('issuing_organization')}/{payload.lpo_id}",
                        payee="MINT_ACCOUNT",
                        payer=str(payload.payer),
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def initiate_insurance_premium_payment(
        self, payload: InitiateInsurancePremiumPaymentSchema, context: Context
    ) -> str:
        """Initiate an insurance premium payment."""

        policy_details = self.__insurance_service_adapter.get_insurance_policy_details(
            policy_id=payload.insurance_policy_id, context=context
        )

        logger.info("Insurance Policy Details: %s", policy_details)

        if not policy_details:
            raise ValueError("Invalid Insurance Policy")

        if policy_details.get("status") != "active":
            raise ValueError(
                "You can only make premium payments on active Insurance Policies"
            )

        amount = policy_details.get("premium_amount")

        if not amount:
            raise ValueError("Invalid amount")

        logger.info("Insurance premium amount=%s", amount)

        # Validate Account

        self.__account_service_adapter.check_account(
            str(payload.payer), payload.pin, context
        )

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=payload.payer,
                payee=int(context.mint_account_id),
                amount=int(amount),
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Insurance premium transfer created transaction_id=%s", transaction_id)

            completed_at = datetime.now(timezone.utc)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"INSURANCE_PREMIUM_PAYMENT/{policy_details.get('policy_id')}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            result = self.__insurance_service_adapter.record_payment(
                transaction_id=transaction_id,
                policy_id=payload.insurance_policy_id,
                amount=int(amount),
                payment_date=completed_at.isoformat(),
                payment_method="TRANSFER",
                context=context,
            )

            if result.get("status") != "success":
                raise ValueError("Insurance premium payment recording failed")

            publish_transaction_event(
                PubsubTopics.TRANSACTION_SUCCESS,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"INSURANCE_PREMIUM_PAYMENT/{policy_details.get('policy_id')}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="insurance_premium",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="insurance_premium",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Insurance premium payment failed policy_id=%s error=%s", payload.insurance_policy_id, str(e))
            if transaction_id:
                try:
                    refund_id = self.__tigerbeetle_adapter.transfer(
                        payer=int(context.mint_account_id),
                        payee=payload.payer,
                        amount=int(amount),
                        ledger=int(context.ledger_id),
                    )
                    publish_transaction_event(
                        PubsubTopics.TRANSACTION_FAILED,
                        TransactionEventSchema(
                            transaction_id=str(refund_id),
                            amount=str(amount),
                            completed_at=datetime.now(timezone.utc),
                            currency=CurrencyEnum.NGN,
                            note=f"REFUND/INSURANCE_PREMIUM_PAYMENT/{policy_details.get('policy_id')}",
                            payer="MINT_ACCOUNT",
                            payee=str(payload.payer),
                            status=TransactionStatus.FAILED,
                            tag="",
                            tenant_id=context.tenant_id,
                            ledger_id=context.ledger_id,
                        ),
                    )
                except Exception as refund_error:
                    logger.error("Insurance premium refund failed transaction_id=%s error=%s", transaction_id, str(refund_error))

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_FAILED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=f"INSURANCE_PREMIUM_PAYMENT/{policy_details.get('policy_id')}",
                        payee="MINT_ACCOUNT",
                        payer=str(payload.payer),
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def supply_chain_financing_payment(
        self, payload: SupplyChainFinancingPaymentSchema, context: Context
    ) -> str:
        """Initiate an supply chain financing payment."""

        # Validate Financing

        financing_details = self.__supply_chain_service_adapter.get_financing_details(
            financing_id=payload.financing_id, context=context
        )

        logger.info("Financing Details: %s", financing_details)

        if not financing_details:
            raise ValueError("Invalid Financing")

        if financing_details.get("status") != "disbursed":
            raise ValueError("You can only make payments on disbursed financings")

        amount = financing_details.get("repayment_amount")

        if not amount:
            raise ValueError("Invalid amount")

        logger.info("Supply chain financing repayment amount=%s", amount)

        # Validate Account

        self.__account_service_adapter.check_account(
            str(payload.payer), payload.pin, context
        )

        transaction_id = None
        try:
            id = self.__tigerbeetle_adapter.transfer(
                payer=payload.payer,
                payee=int(context.mint_account_id),
                amount=int(amount),
                ledger=int(context.ledger_id),
            )
            transaction_id = str(id)
            logger.info("Supply chain financing transfer created transaction_id=%s", transaction_id)

            completed_at = datetime.now(timezone.utc)

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"SUPPLY_CHAIN_FINANCING_REPAYMENT/{financing_details.get('financing_id')}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.INITIATED,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )

            result = self.__supply_chain_service_adapter.record_payment(
                transaction_id=transaction_id,
                financing_id=payload.financing_id,
                amount=int(amount),
                payment_date=completed_at.isoformat(),
                payment_method="TRANSFER",
                context=context,
            )

            if result.get("status") != "success":
                raise ValueError("Financing repayment recording failed")

            publish_transaction_event(
                PubsubTopics.TRANSACTION_INITIATED,
                TransactionEventSchema(
                    transaction_id=transaction_id,
                    amount=str(amount),
                    completed_at=completed_at,
                    currency=CurrencyEnum.NGN,
                    note=f"SUPPLY_CHAIN_FINANCING_REPAYMENT/{financing_details.get('financing_id')}",
                    payee="MINT_ACCOUNT",
                    payer=str(payload.payer),
                    status=TransactionStatus.SUCCESS,
                    tag="",
                    tenant_id=context.tenant_id,
                    ledger_id=context.ledger_id,
                ),
            )
            self._notify_compliance(
                transaction_id=transaction_id,
                transaction_type="supply_chain",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )
            self._notify_loyalty(
                transaction_id=transaction_id,
                transaction_type="supply_chain",
                amount_ngn=float(amount),
                agent_id=context.keycloak_id,
            )

            return transaction_id

        except Exception as e:
            logger.error("Supply chain financing payment failed financing_id=%s error=%s", payload.financing_id, str(e))
            if transaction_id:
                try:
                    refund_id = self.__tigerbeetle_adapter.transfer(
                        payer=int(context.mint_account_id),
                        payee=payload.payer,
                        amount=int(amount),
                        ledger=int(context.ledger_id),
                    )
                    publish_transaction_event(
                        PubsubTopics.TRANSACTION_INITIATED,
                        TransactionEventSchema(
                            transaction_id=str(refund_id),
                            amount=str(amount),
                            completed_at=datetime.now(timezone.utc),
                            currency=CurrencyEnum.NGN,
                            note=f"REFUND/SUPPLY_CHAIN_FINANCING_REPAYMENT/{financing_details.get('financing_id')}",
                            payer="MINT_ACCOUNT",
                            payee=str(payload.payer),
                            status=TransactionStatus.SUCCESS,
                            tag="",
                            tenant_id=context.tenant_id,
                            ledger_id=context.ledger_id,
                        ),
                    )
                except Exception as refund_error:
                    logger.error("Supply chain financing refund failed transaction_id=%s error=%s", transaction_id, str(refund_error))

                publish_transaction_event(
                    PubsubTopics.TRANSACTION_INITIATED,
                    TransactionEventSchema(
                        transaction_id=transaction_id,
                        amount=str(amount),
                        completed_at=datetime.now(timezone.utc),
                        currency=CurrencyEnum.NGN,
                        note=f"SUPPLY_CHAIN_FINANCING_REPAYMENT/{financing_details.get('financing_id')}",
                        payee="MINT_ACCOUNT",
                        payer=str(payload.payer),
                        status=TransactionStatus.FAILED,
                        tag="",
                        tenant_id=context.tenant_id,
                        ledger_id=context.ledger_id,
                    ),
                )
            raise

    def notify_external_systems(
        self, reference: str, payload: InitiatePaymentSchema, context: Context
    ):
        """Notify agents external systems about the transaction."""

        is_outbound = bool(payload.payee_bank_code)

        if not is_outbound:
            return

        amount_currency = "NGN"
        if payload.note:
            note = payload.note
        else:
            note = "Transfer"

        outbound_payload = {
            "transactionId": reference,
            "payer": {
                "idType": "MSISDN",
                "idValue": str(payload.payer),
            },
            "payee": {
                "idType": "MSISDN",
                "idValue": str(payload.payee),
            },
            "destination": str(payload.payee_bank_code or payload.payee_tenant_id),
            "amount": {
                "currency": amount_currency,
                "amount": payload.amount,
            },
            "note": note,
            "pin": payload.pin,
            "debit_in_payment_processing": False,
            "metadata": {
                "source_tenant_id": context.tenant_id,
                "payee_tenant_id": payload.payee_tenant_id,
                "payee_bank_code": payload.payee_bank_code,
                "flow": "outbound",
            },
        }

        payment_rails_connector_adapter.initiate_outbound_transfer(outbound_payload)
