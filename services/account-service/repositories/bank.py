from sqlalchemy.orm import Session
from models import Bank
from schemas.v1 import CreateBankSchema, Context

class BankRepository:
    """Bank repository."""

    def __init__(self, db: Session):
        self.__db = db

    def create_bank(
            self,
            payload: CreateBankSchema,
            context: Context,
    ) -> Bank:
        existing = self.__db.query(Bank).filter(Bank.tenant_id == context.tenant_id).first()
        if existing:
            return existing

        bank = Bank(
            name=payload.name,
            logo=payload.logo,
            tenant_id=context.tenant_id,
            ledger_id=context.ledger_id
        )
        self.__db.add(bank)
        return bank
    
    def get_banks(self, context: Context):
        return self.__db.query(Bank).filter(Bank.ledger_id == context.ledger_id).order_by(Bank.created_at).all()
    