from sqlalchemy.orm import Session
from adapters import TigerBeetleAdapter
from repositories import BankRepository
from utils import create_logger
from schemas.v1 import CreateBankSchema, Context

logger = create_logger(__name__)

class BankService:
    def __init__(self, db: Session):
        self.__db = db
        self.__bank_repository = BankRepository(db)

    def create_bank(self, payload: CreateBankSchema, context: Context):
        """Logic to create a new bank"""

        # Create bank entry in the database
        bank = self.__bank_repository.create_bank(
            payload=payload,
            context=context
        )

        self.__db.commit()

        logger.info(f"Bank created with code: {bank.code}")

        return bank
    
    def get_banks(self, context: Context):
        """Logic to get banks"""

        banks = self.__bank_repository.get_banks(context)
        
        return banks
