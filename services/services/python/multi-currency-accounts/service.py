from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

import models
import schemas

# --- Custom Exceptions ---

class ServiceError(Exception):
    """Base class for service-layer exceptions."""
    pass

class AccountNotFound(ServiceError):
    """Raised when an Account is not found."""
    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(f"Account with ID {account_id} not found.")

class CurrencyBalanceNotFound(ServiceError):
    """Raised when a CurrencyBalance is not found."""
    def __init__(self, account_id: int, currency_code: str) -> None:
        self.account_id = account_id
        self.currency_code = currency_code
        super().__init__(f"Currency balance for account {account_id} and currency {currency_code} not found.")

class CurrencyBalanceAlreadyExists(ServiceError):
    """Raised when trying to create a balance that already exists for the account/currency pair."""
    def __init__(self, account_id: int, currency_code: str) -> None:
        self.account_id = account_id
        self.currency_code = currency_code
        super().__init__(f"Currency balance for account {account_id} and currency {currency_code} already exists.")

# --- Service Layer ---

class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_account(self, account_data: schemas.AccountCreate) -> models.Account:
        """Creates a new account and its initial currency balances."""
        try:
            db_account = models.Account(
                user_id=account_data.user_id,
                account_name=account_data.account_name
            )
            self.db.add(db_account)
            self.db.flush() # Flush to get the account ID for balances

            for balance_data in account_data.initial_balances:
                db_balance = models.CurrencyBalance(
                    account_id=db_account.id,
                    currency_code=balance_data.currency_code,
                    balance=balance_data.balance
                )
                self.db.add(db_balance)
            
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except IntegrityError as e:
            self.db.rollback()
            # This would typically catch a unique constraint violation on user_id/account_name if one existed
            raise ServiceError(f"Database integrity error during account creation: {e}")
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during account creation: {e}")

    def get_account(self, account_id: int) -> models.Account:
        """Retrieves a single account by ID."""
        db_account = self.db.query(models.Account).filter(models.Account.id == account_id).first()
        if not db_account:
            raise AccountNotFound(account_id)
        return db_account

    def get_all_accounts(self, user_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[models.Account]:
        """Retrieves a list of accounts, optionally filtered by user_id."""
        query = self.db.query(models.Account)
        if user_id is not None:
            query = query.filter(models.Account.user_id == user_id)
        return query.offset(skip).limit(limit).all()

    def update_account(self, account_id: int, account_data: schemas.AccountUpdate) -> models.Account:
        """Updates an existing account's details."""
        db_account = self.get_account(account_id)
        
        update_data = account_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_account, key, value)
        
        try:
            self.db.commit()
            self.db.refresh(db_account)
            return db_account
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during account update: {e}")

    def delete_account(self, account_id: int) -> None:
        """Deletes an account and all its associated currency balances."""
        db_account = self.get_account(account_id)
        
        try:
            self.db.delete(db_account)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during account deletion: {e}")

    def get_currency_balance(self, account_id: int, currency_code: str) -> models.CurrencyBalance:
        """Retrieves a single currency balance for an account."""
        db_balance = self.db.query(models.CurrencyBalance).filter(
            models.CurrencyBalance.account_id == account_id,
            models.CurrencyBalance.currency_code == currency_code
        ).first()
        if not db_balance:
            raise CurrencyBalanceNotFound(account_id, currency_code)
        return db_balance

    def update_currency_balance(self, account_id: int, currency_code: str, balance_data: schemas.CurrencyBalanceUpdate) -> models.CurrencyBalance:
        """Updates the balance for a specific currency in an account."""
        db_balance = self.db.query(models.CurrencyBalance).filter(
            models.CurrencyBalance.account_id == account_id,
            models.CurrencyBalance.currency_code == currency_code
        ).first()

        if not db_balance:
            # If balance doesn't exist, create it (upsert-like behavior for convenience)
            try:
                db_balance = models.CurrencyBalance(
                    account_id=account_id,
                    currency_code=currency_code,
                    balance=balance_data.balance
                )
                self.db.add(db_balance)
                self.db.commit()
                self.db.refresh(db_balance)
                return db_balance
            except IntegrityError:
                self.db.rollback()
                # Should not happen if account_id is valid, but good to catch
                raise AccountNotFound(account_id)
            except Exception as e:
                self.db.rollback()
                raise ServiceError(f"An unexpected error occurred during currency balance creation: {e}")
        
        # If balance exists, update it
        db_balance.balance = balance_data.balance
        
        try:
            self.db.commit()
            self.db.refresh(db_balance)
            return db_balance
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during currency balance update: {e}")

    def create_currency_balance(self, account_id: int, balance_data: schemas.CurrencyBalanceCreate) -> models.CurrencyBalance:
        """Creates a new currency balance for an existing account."""
        # Check if account exists
        self.get_account(account_id) 
        
        # Check if balance already exists
        existing_balance = self.db.query(models.CurrencyBalance).filter(
            models.CurrencyBalance.account_id == account_id,
            models.CurrencyBalance.currency_code == balance_data.currency_code
        ).first()
        
        if existing_balance:
            raise CurrencyBalanceAlreadyExists(account_id, balance_data.currency_code)

        db_balance = models.CurrencyBalance(
            account_id=account_id,
            currency_code=balance_data.currency_code,
            balance=balance_data.balance
        )
        
        try:
            self.db.add(db_balance)
            self.db.commit()
            self.db.refresh(db_balance)
            return db_balance
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during currency balance creation: {e}")

    def delete_currency_balance(self, account_id: int, currency_code: str) -> None:
        """Deletes a specific currency balance from an account."""
        db_balance = self.get_currency_balance(account_id, currency_code)
        
        try:
            self.db.delete(db_balance)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise ServiceError(f"An unexpected error occurred during currency balance deletion: {e}")