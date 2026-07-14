from sqlalchemy.orm import Session
from models import Account
from typing import Optional
from utils import encrypt_pin, AccountType, AccountCurrency


class AccountRepository:
    """Account repository."""

    def __init__(self, db: Session):
        self.__db = db

    def create_account(
        self,
        keycloak_id: str,
        tenant_id: str,
        ledger_id: str,
        account_number: str,
        name: str,
        id: Optional[int] = None,
        account_type: AccountType = AccountType.PRIMARY,
        account_currency: AccountCurrency = AccountCurrency.NGN,
    ) -> Account:
        account = Account(
            id=id,
            keycloak_id=keycloak_id,
            tenant_id=tenant_id,
            ledger_id=ledger_id,
            account_number=account_number,
            name=name,
            balance="0",
            account_type=account_type,
            account_currency=account_currency,
        )
        self.__db.add(account)
        return account

    def setup_pin(self, pin: str, keycloak_id: str, tenant_id: str):
        accounts = (
            self.__db.query(Account)
            .filter(Account.keycloak_id == keycloak_id, Account.tenant_id == tenant_id)
            .all()
        )

        if not accounts:
            raise Exception("Account not found")

        encrypted_pin = encrypt_pin(pin)
        for account in accounts:
            account.pin = encrypted_pin
            self.__db.add(account)

        return accounts[0]

    def get_mint_account(self, tenant_id: str):
        """Get the first mint account for a tenant (default currency)."""
        return (
            self.__db.query(Account)
            .filter(
                Account.tenant_id == tenant_id, Account.account_type == AccountType.MINT
            )
            .first()
        )

    def get_mint_account_by_currency(self, tenant_id: str, currency: AccountCurrency):
        """Get the mint account for a specific currency."""
        return (
            self.__db.query(Account)
            .filter(
                Account.tenant_id == tenant_id,
                Account.account_type == AccountType.MINT,
                Account.account_currency == currency,
            )
            .first()
        )

    def get_all_mint_accounts(self, tenant_id: str):
        """Get all mint accounts for a tenant (one per currency)."""
        return (
            self.__db.query(Account)
            .filter(
                Account.tenant_id == tenant_id,
                Account.account_type == AccountType.MINT,
            )
            .order_by(Account.created_at)
            .all()
        )

    def get_accounts(self, tenant_id: str):
        return (
            self.__db.query(Account)
            .filter(Account.tenant_id == tenant_id)
            .order_by(Account.created_at)
            .all()
        )

    def get_accounts_by_user(self, keycloak_id: str, tenant_id: str):
        """Get all accounts for a specific user (all account types)"""
        return (
            self.__db.query(Account)
            .filter(
                Account.keycloak_id == keycloak_id,
                Account.tenant_id == tenant_id,
            )
            .order_by(Account.created_at)
            .all()
        )

    def get_accounts_by_keycloak_id(self, keycloak_id: str, tenant_id: str):
        return (
            self.__db.query(Account)
            .filter(
                Account.keycloak_id == keycloak_id,
                Account.tenant_id == tenant_id,
                Account.account_type == AccountType.PRIMARY,
            )
            .all()
        )

    def get_by_account_id(self, account_id: str, tenant_id: str):
        return (
            self.__db.query(Account)
            .filter(Account.id == account_id, Account.tenant_id == tenant_id)
            .first()
        )

    def get_by_account_number(self, account_number: str, tenant_id: str):
        return (
            self.__db.query(Account)
            .filter(
                Account.account_number == account_number, Account.tenant_id == tenant_id
            )
            .first()
        )

    def get_by_keycloak_id(self, keycloak_id: str, tenant_id: str):
        return (
            self.__db.query(Account)
            .filter(
                Account.keycloak_id == keycloak_id,
                Account.tenant_id == tenant_id,
                Account.account_type == AccountType.PRIMARY,
            )
            .first()
        )
