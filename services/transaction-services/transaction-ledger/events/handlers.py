from schemas import TransactionEventSchema
from repositories import TransactionRepository
from database import get_session


async def transaction_initiated_handler(payload: TransactionEventSchema):
    session = next(get_session())
    try:
        transaction_repository = TransactionRepository(session)
        await transaction_repository.initiate_transaction(payload)
    finally:
        session.close()


async def transaction_failed_handler(payload: TransactionEventSchema):
    session = next(get_session())
    try:
        transaction_repository = TransactionRepository(session)
        await transaction_repository.mark_transaction_failed(payload)
    finally:
        session.close()


async def transaction_success_handler(payload: TransactionEventSchema):
    session = next(get_session())
    try:
        transaction_repository = TransactionRepository(session)
        await transaction_repository.mark_transaction_success(payload)
    finally:
        session.close()
