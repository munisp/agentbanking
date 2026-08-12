import json
import logging
import os
import urllib.error
import urllib.request
from typing import List, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models import Stablecoin, Account, Transaction
from schemas import (
    StablecoinCreate, StablecoinUpdate, AccountCreate, AccountUpdate,
    TransactionCreate, TransactionUpdate, TransactionType, TransactionStatus
)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class ServiceException(HTTPException):
    """Base exception for service layer errors."""
    def __init__(self, detail: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> None:
        super().__init__(status_code=status_code, detail=detail)

class NotFoundException(ServiceException):
    """Raised when a requested resource is not found."""
    def __init__(self, resource_name: str, resource_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} with ID {resource_id} not found."
        )

class IntegrityViolationException(ServiceException):
    """Raised for database integrity errors (e.g., unique constraint violation)."""
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )

class InsufficientBalanceException(ServiceException):
    """Raised when an account has insufficient balance for a transaction."""
    def __init__(self, account_id: int, required_amount: Decimal) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account {account_id} has insufficient balance for transaction of {required_amount}."
        )

class AccountLockedException(ServiceException):
    """Raised when an operation is attempted on a locked account."""
    def __init__(self, account_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account {account_id} is locked and cannot perform this operation."
        )

# --- Stablecoin Service ---

class StablecoinService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_stablecoin(self, stablecoin_in: StablecoinCreate) -> Stablecoin:
        logger.info(f"Creating new stablecoin: {stablecoin_in.symbol}")
        try:
            db_stablecoin = Stablecoin(**stablecoin_in.model_dump())
            self.db.add(db_stablecoin)
            self.db.commit()
            self.db.refresh(db_stablecoin)
            return db_stablecoin
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating stablecoin: {e}")
            raise IntegrityViolationException(detail="Stablecoin with this symbol or contract address already exists.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating stablecoin: {e}")
            raise ServiceException(detail="Could not create stablecoin due to an unexpected error.")

    def get_stablecoin(self, stablecoin_id: int) -> Stablecoin:
        db_stablecoin = self.db.query(Stablecoin).filter(Stablecoin.id == stablecoin_id).first()
        if not db_stablecoin:
            raise NotFoundException("Stablecoin", stablecoin_id)
        return db_stablecoin

    def get_all_stablecoins(self, skip: int = 0, limit: int = 100) -> List[Stablecoin]:
        return self.db.query(Stablecoin).offset(skip).limit(limit).all()

    def update_stablecoin(self, stablecoin_id: int, stablecoin_in: StablecoinUpdate) -> Stablecoin:
        db_stablecoin = self.get_stablecoin(stablecoin_id)
        logger.info(f"Updating stablecoin ID {stablecoin_id}")
        update_data = stablecoin_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_stablecoin, key, value)
        
        try:
            self.db.add(db_stablecoin)
            self.db.commit()
            self.db.refresh(db_stablecoin)
            return db_stablecoin
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating stablecoin: {e}")
            raise ServiceException(detail="Could not update stablecoin due to an unexpected error.")

    def delete_stablecoin(self, stablecoin_id: int) -> None:
        db_stablecoin = self.get_stablecoin(stablecoin_id)
        logger.warning(f"Deleting stablecoin ID {stablecoin_id}")
        self.db.delete(db_stablecoin)
        self.db.commit()

# --- Account Service ---

class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_account(self, account_in: AccountCreate) -> Account:
        logger.info(f"Creating account for user {account_in.user_id} with stablecoin {account_in.stablecoin_id}")
        # Check if stablecoin exists
        if not self.db.query(Stablecoin).filter(Stablecoin.id == account_in.stablecoin_id).first():
            raise NotFoundException("Stablecoin", account_in.stablecoin_id)

        try:
            db_account = Account(**account_in.model_dump())
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating account: {e}")
            raise IntegrityViolationException(detail="Account with this wallet address already exists or user already has an account for this stablecoin.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating account: {e}")
            raise ServiceException(detail="Could not create account due to an unexpected error.")

    def get_account(self, account_id: int) -> Account:
        db_account = self.db.query(Account).filter(Account.id == account_id).first()
        if not db_account:
            raise NotFoundException("Account", account_id)
        return db_account

    def get_all_accounts(self, skip: int = 0, limit: int = 100) -> List[Account]:
        return self.db.query(Account).offset(skip).limit(limit).all()

    def get_accounts_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Account]:
        return self.db.query(Account).filter(Account.user_id == user_id).offset(skip).limit(limit).all()

    def update_account(self, account_id: int, account_in: AccountUpdate) -> Account:
        db_account = self.get_account(account_id)
        logger.info(f"Updating account ID {account_id}")
        update_data = account_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_account, key, value)
        
        try:
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating account: {e}")
            raise ServiceException(detail="Could not update account due to an unexpected error.")

    def delete_account(self, account_id: int) -> None:
        db_account = self.get_account(account_id)
        logger.warning(f"Deleting account ID {account_id}")
        self.db.delete(db_account)
        self.db.commit()

# --- Transaction Service ---

class TransactionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.account_service = AccountService(db)
        # Simulation of on-chain settlement is only allowed when explicitly
        # enabled AND outside production. In production the only way to create
        # a deposit/withdrawal/transfer is via the configured settlement gateway.
        self.simulation_mode = os.getenv("STABLECOIN_SIMULATION_MODE", "false").lower() == "true"
        self.environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "production")).lower()
        self.settlement_gateway_url = os.getenv("STABLECOIN_SETTLEMENT_GATEWAY_URL", "").strip() or None
        if self.simulation_mode and self.environment == "production":
            raise RuntimeError(
                "STABLECOIN_SIMULATION_MODE=true is forbidden in production: "
                "simulated on-chain settlement must never run against live funds"
            )

    def _settle_onchain(self, stablecoin: Stablecoin, transaction_in: TransactionCreate, amount: Decimal) -> dict:
        """Submit the operation to the configured on-chain settlement gateway.

        Returns the gateway-reported settlement (status + tx_hash). Raises
        loudly when the gateway is unavailable — settlement is never fabricated.
        """
        tx_type = transaction_in.transaction_type
        payload = {
            "transaction_type": tx_type.value if hasattr(tx_type, "value") else str(tx_type),
            "account_id": transaction_in.account_id,
            "stablecoin_id": transaction_in.stablecoin_id,
            "contract_address": stablecoin.contract_address,
            "amount": str(amount),
            "destination_address": transaction_in.destination_address,
        }
        request = urllib.request.Request(
            f"{self.settlement_gateway_url.rstrip('/')}/settlements",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            logger.error(f"Settlement gateway call failed: {e}")
            raise ServiceException(
                detail=f"On-chain settlement gateway unavailable: {e}",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        confirmed = (
            bool(data.get("confirmed"))
            or str(data.get("status", "")).upper() == TransactionStatus.COMPLETED.value
        )
        return {
            "status": TransactionStatus.COMPLETED.value if confirmed else TransactionStatus.PENDING.value,
            "tx_hash": data.get("tx_hash"),
        }

    def create_transaction(self, transaction_in: TransactionCreate) -> Transaction:
        logger.info(f"Creating transaction of type {transaction_in.transaction_type} for account {transaction_in.account_id}")
        
        db_account = self.account_service.get_account(transaction_in.account_id)
        
        if db_account.is_locked:
            raise AccountLockedException(db_account.id)

        # Check if stablecoin is active
        db_stablecoin = self.db.query(Stablecoin).filter(Stablecoin.id == transaction_in.stablecoin_id).first()
        if not db_stablecoin or not db_stablecoin.is_active:
            raise ServiceException(detail=f"Stablecoin {transaction_in.stablecoin_id} is not active or does not exist.", status_code=status.HTTP_400_BAD_REQUEST)

        amount = Decimal(str(transaction_in.amount))
        
        if not self.simulation_mode and not self.settlement_gateway_url:
            # Never mark deposits/withdrawals/transfers complete from database
            # writes alone: without a chain settlement path we fail loudly.
            raise ServiceException(
                detail=(
                    "On-chain settlement is not configured "
                    "(STABLECOIN_SETTLEMENT_GATEWAY_URL is unset) and simulation mode "
                    "is disabled. Refusing to record a fabricated settlement."
                ),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            settlement = None
            if not self.simulation_mode:
                settlement = self._settle_onchain(db_stablecoin, transaction_in, amount)

            # 1. Create the transaction record
            db_transaction = Transaction(**transaction_in.model_dump(exclude_none=True))
            if self.simulation_mode:
                db_transaction.status = TransactionStatus.COMPLETED.value
                settled = True
            else:
                db_transaction.status = settlement["status"]
                if settlement.get("tx_hash"):
                    db_transaction.tx_hash = settlement["tx_hash"]
                settled = settlement["status"] == TransactionStatus.COMPLETED.value

            if settled:
                import datetime as _dt
                db_transaction.completed_at = _dt.datetime.utcnow()
            
            # 2. Update account balance only for confirmed settlements
            if settled:
                if transaction_in.transaction_type == TransactionType.DEPOSIT:
                    db_account.balance += float(amount)
                elif transaction_in.transaction_type == TransactionType.WITHDRAWAL or transaction_in.transaction_type == TransactionType.TRANSFER:
                    if db_account.balance < amount:
                        raise InsufficientBalanceException(db_account.id, amount)
                    db_account.balance -= float(amount)
            
            # 3. Commit both changes in a single transaction
            self.db.add(db_transaction)
            self.db.add(db_account)
            self.db.commit()
            self.db.refresh(db_transaction)
            self.db.refresh(db_account)
            
            logger.info(
                f"Transaction {db_transaction.id} recorded with status {db_transaction.status}. "
                f"Balance for account {db_account.id}: {db_account.balance}"
            )
            return db_transaction
            
        except (InsufficientBalanceException, ServiceException):
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error during transaction creation/processing: {e}")
            raise ServiceException(detail="Could not process transaction due to an unexpected error.")

    def get_transaction(self, transaction_id: int) -> Transaction:
        db_transaction = self.db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not db_transaction:
            raise NotFoundException("Transaction", transaction_id)
        return db_transaction

    def get_transactions_by_account(self, account_id: int, skip: int = 0, limit: int = 100) -> List[Transaction]:
        return self.db.query(Transaction).filter(Transaction.account_id == account_id).offset(skip).limit(limit).all()

    def update_transaction_status(self, transaction_id: int, transaction_in: TransactionUpdate) -> Transaction:
        db_transaction = self.get_transaction(transaction_id)
        logger.info(f"Updating status for transaction ID {transaction_id} to {transaction_in.status}")
        
        update_data = transaction_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_transaction, key, value)
        
        try:
            self.db.add(db_transaction)
            self.db.commit()
            self.db.refresh(db_transaction)
            return db_transaction
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating transaction status: {e}")
            raise ServiceException(detail="Could not update transaction status due to an unexpected error.")
