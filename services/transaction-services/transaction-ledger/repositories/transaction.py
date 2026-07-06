from sqlalchemy.orm import Session
from sqlalchemy import or_, func, cast, Float
from schemas import TransactionEventSchema, Pagination, Context
from models import Transaction
from adapters import AccountServiceAdapter
from utils.coa_client import CoAClient
from utils import TransactionStatus
import logging

logger = logging.getLogger(__name__)


class TransactionRepository:
    """Transaction repository."""

    def __init__(self, db: Session):
        self.__db = db

    def _ensure_transaction_exists(self, payload: TransactionEventSchema) -> Transaction:
        existing = (
            self.__db.query(Transaction)
            .filter(
                Transaction.tenant_id == payload.tenant_id,
                Transaction.transaction_id == payload.transaction_id,
            )
            .first()
        )

        if existing:
            return existing

        # Create a minimal placeholder transaction
        transaction = Transaction(
            transaction_id=payload.transaction_id,
            payer=payload.payer,
            payee=payload.payee,
            amount=payload.amount,
            currency=payload.currency,
            status=TransactionStatus.PENDING,
            tenant_id=payload.tenant_id,
            ledger_id=payload.ledger_id,
            completed_at=payload.completed_at,
            note=payload.note,
            tag=payload.tag,
        )

        self.__db.add(transaction)
        self.__db.commit()
        self.__db.refresh(transaction)

        logger.info(
            f"Created missing transaction stub for transaction_id={payload.transaction_id}"
        )

        return transaction

    async def initiate_transaction(self, payload: TransactionEventSchema):
        context = Context(
            tenant_id=payload.tenant_id,
        )

        payer_account = AccountServiceAdapter().get_account_by_account_id(
            account_id=payload.payer,
            context=context,
        )

        payee_account = AccountServiceAdapter().get_account_by_account_id(
            account_id=payload.payee,
            context=context,
        )

        # coa_client = CoAClient()
        # lines = [
        #     {
        #         "account_id": ("0" if str(payload.payer) == "MINT_ACCOUNT" else "2000"),
        #         "description": f"Payment sent - {payload.note or ''}",
        #         "debit_amount": int(float(payload.amount)),
        #         "credit_amount": 0,
        #     },
        #     {
        #         "account_id": ("0" if str(payload.payee) == "MINT_ACCOUNT" else "2000"),
        #         "description": f"Payment received - {payload.note or ''}",
        #         "debit_amount": 0,
        #         "credit_amount": int(float(payload.amount)),
        #     },
        # ]
        # try:
        #     await coa_client.create_journal_entry(
        #         tenant_id=payload.tenant_id,
        #         user_id="system",
        #         user_role="bank_admin",
        #         description=payload.note or "Transaction ledger entry",
        #         lines=lines,
        #         reference=payload.transaction_id,
        #         metadata={"ledger_id": payload.ledger_id},
        #     )
        # except Exception as e:
        #     import traceback

        #     logger.error(
        #         f"tenant_id: {payload.tenant_id}, transaction_id: {payload.transaction_id}"
        #     )
        #     logger.error(f"Failed to record accounting entry: {e}")
        #     logger.error(f"Exception type: {type(e).__name__}")
        #     logger.error(f"Full traceback: {traceback.format_exc()}")
        #     logger.error(f"Journal entry data: {lines}")
        #     raise Exception(f"Failed to record accounting entry: {e}")

        transaction = Transaction(
            transaction_id=payload.transaction_id,
            payer=payload.payer,
            payer_account_number=payer_account.get("account", {}).get("account_number"),
            payer_name=payer_account.get("account", {}).get("name"),
            payee=payload.payee,
            payee_account_number=payee_account.get("account", {}).get("account_number"),
            payee_name=payee_account.get("account", {}).get("name"),
            amount=payload.amount,
            status=payload.status,
            currency=payload.currency,
            completed_at=payload.completed_at,
            note=payload.note,
            tag=payload.tag,
            tenant_id=payload.tenant_id,
            ledger_id=payload.ledger_id,
        )

        self.__db.add(transaction)
        self.__db.commit()

    def fetch_account_transactions(
        self, id: str, tenant_id: str, pagination: Pagination
    ):
        offset = (pagination.page - 1) * pagination.limit

        return (
            self.__db.query(Transaction)
            .filter(
                Transaction.tenant_id == tenant_id,
                or_(
                    Transaction.payer == id,
                    Transaction.payee == id,
                ),
            )
            .order_by(Transaction.completed_at.desc())
            .offset(offset)
            .limit(pagination.limit or 10)
            .all()
        )

    def fetch_account_number_transactions(
        self, account_number: str, tenant_id: str, pagination: Pagination
    ):
        offset = (pagination.page - 1) * pagination.limit

        return (
            self.__db.query(Transaction)
            .filter(
                Transaction.tenant_id == tenant_id,
                or_(
                    Transaction.payer_account_number == account_number,
                    Transaction.payee_account_number == account_number,
                ),
            )
            .order_by(Transaction.completed_at.desc())
            .offset(offset)
            .limit(pagination.limit or 10)
            .all()
        )

    def fetch_transactions(self, tenant_id: str, pagination: Pagination):
        offset = (pagination.page - 1) * pagination.limit

        return (
            self.__db.query(Transaction)
            .filter(Transaction.tenant_id == tenant_id)
            .order_by(Transaction.completed_at.desc())
            .offset(offset)
            .limit(pagination.limit or 10)
            .all()
        )

    def fetch_transaction_by_id(self, id: str, tenant_id: str):
        return (
            self.__db.query(Transaction)
            .filter(
                Transaction.tenant_id == tenant_id, Transaction.transaction_id == id
            )
            .first()
        )

    def fetch_transaction_count(self, tenant_id: str) -> int:
        return (
            self.__db.query(Transaction)
            .filter(Transaction.tenant_id == tenant_id)
            .count()
        )

    def fetch_transaction_volume(self, tenant_id: str) -> float:
        result = (
            self.__db.query(func.sum(cast(Transaction.amount, Float)))
            .filter(Transaction.tenant_id == tenant_id)
            .scalar()
        )
        return result or 0.0

    def fetch_transaction_status_counts(self, tenant_id: str) -> dict:
        rows = (
            self.__db.query(Transaction.status, func.count(Transaction.id))
            .filter(Transaction.tenant_id == tenant_id)
            .group_by(Transaction.status)
            .all()
        )
        return {status.value: count for status, count in rows}

    def fetch_transaction_type_counts(self, tenant_id: str) -> dict:
        base_query = self.__db.query(Transaction).filter(
            Transaction.tenant_id == tenant_id
        )
        total = base_query.count()
        deposit = base_query.filter(Transaction.payer == "MINT_ACCOUNT").count()
        withdrawal = base_query.filter(
            Transaction.payer != "MINT_ACCOUNT",
            Transaction.payee == "MINT_ACCOUNT",
        ).count()
        transfer = total - deposit - withdrawal
        return {"deposit": deposit, "withdrawal": withdrawal, "transfer": transfer}

    async def mark_transaction_failed(self, payload: TransactionEventSchema):
        transaction = self._ensure_transaction_exists(payload)
        logger.info(f"Marking transaction failed for transaction_id={payload.transaction_id}, tenant_id={payload.tenant_id}")
        if transaction:
            transaction.status = TransactionStatus.FAILED
            self.__db.commit()

    async def mark_transaction_success(self, payload: TransactionEventSchema):
        transaction = self._ensure_transaction_exists(payload)
        logger.info(f"Marking transaction success for transaction_id={payload.transaction_id}, tenant_id={payload.tenant_id}")
        if transaction:
            transaction.status = TransactionStatus.SUCCESS
            self.__db.commit()
