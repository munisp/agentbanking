from sqlalchemy.orm import Session
from repositories import TransactionRepository
from schemas import Context, Pagination


class TransactionService:
    def __init__(self, db: Session):
        self.__transaction_repository = TransactionRepository(db)

    def fetch_account_transactions(
        self, id: str, context: Context, pagination: Pagination
    ):
        return self.__transaction_repository.fetch_account_transactions(
            id, context.tenant_id, pagination
        )

    def fetch_account_number_transactions(
        self, account_number: str, context: Context, pagination: Pagination
    ):
        return self.__transaction_repository.fetch_account_number_transactions(
            account_number, context.tenant_id, pagination
        )

    def fetch_transactions(self, context: Context, pagination: Pagination):
        return self.__transaction_repository.fetch_transactions(
            context.tenant_id, pagination
        )

    def fetch_transaction_by_id(self, id: str, context: Context):
        return self.__transaction_repository.fetch_transaction_by_id(
            id, context.tenant_id
        )

    def fetch_transaction_metrics(self, context: Context):
        return {
            "total_count": self.__transaction_repository.fetch_transaction_count(
                context.tenant_id
            ),
            "total_volume": self.__transaction_repository.fetch_transaction_volume(
                context.tenant_id
            ),
            "status_breakdown": self.__transaction_repository.fetch_transaction_status_counts(
                context.tenant_id
            ),
            "type_breakdown": self.__transaction_repository.fetch_transaction_type_counts(
                context.tenant_id
            ),
        }
