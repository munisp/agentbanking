from sqlalchemy.orm import Session
from adapters import TigerBeetleAdapter
from repositories import AccountRepository
from utils import (
    generate_account_number,
    create_logger,
    verify_pin,
    AccountStatus,
    AccountType,
    AccountCurrency,
    CurrencyLedgerId,
)
from schemas.v1 import CreateAccountSchema, Context


logger = create_logger(__name__)

_tigerbeetle_adapter = TigerBeetleAdapter()


class AccountService:
    def __init__(self, db: Session):
        self.__db = db
        self.__tigerbeetle_adapter = _tigerbeetle_adapter
        self.__account_repository = AccountRepository(db)

    def create_mint_account(self, context: Context):
        """Create mint accounts for all supported currencies (idempotent)."""

        created_or_existing_accounts = []

        for currency in AccountCurrency:
            ledger_id = int(CurrencyLedgerId.from_currency(currency))

            account = self.__account_repository.get_mint_account_by_currency(
                context.tenant_id, currency
            )

            if not account:
                account = self.__account_repository.create_account(
                    name=f"mint_account_{currency.value.lower()}",
                    keycloak_id=f"mint_account_{context.tenant_id}_{currency.value.lower()}",
                    account_number=generate_account_number(),
                    tenant_id=context.tenant_id,
                    ledger_id=ledger_id,
                    account_type=AccountType.MINT,
                    account_currency=currency,
                )
                self.__db.commit()

            tigerbeetle_account = self.__tigerbeetle_adapter.get_account(id=account.id)
            if not tigerbeetle_account:
                self.__tigerbeetle_adapter.create_account(
                    account.id,
                    is_system_account=True,
                    ledger=ledger_id,
                )

            created_or_existing_accounts.append(account)

        return created_or_existing_accounts

    def create_account(self, payload: CreateAccountSchema, context: Context):
        """Logic to create a new account"""

        account_type = payload.account_type or AccountType.PRIMARY
        account_currency = payload.account_currency or AccountCurrency.NGN
        ledger_id = int(CurrencyLedgerId.from_currency(account_currency))

        # logger.info(
        #     "Creating account for keycloak_id=%s tenant_id=%s type=%s currency=%s ledger_id=%s",
        #     context.keycloak_id,
        #     context.tenant_id,
        #     account_type.value,
        #     account_currency.value,
        #     ledger_id,
        # )

        # existing_accounts = self.__account_repository.get_accounts_by_user(
        #     context.keycloak_id, context.tenant_id
        # )
        # existing_account = next(
        #     (
        #         account
        #         for account in existing_accounts
        #         if account.account_type == account_type
        #         and account.account_currency == account_currency
        #     ),
        #     None,
        # )

        # if existing_account:
        #     logger.info(
        #         "Account already exists for keycloak_id=%s tenant_id=%s type=%s currency=%s. Reusing id=%s",
        #         context.keycloak_id,
        #         context.tenant_id,
        #         account_type.value,
        #         account_currency.value,
        #         existing_account.id,
        #     )

        #     tigerbeetle_account = self.__tigerbeetle_adapter.get_account(
        #         id=existing_account.id
        #     )

        #     if not tigerbeetle_account:
        #         self.__tigerbeetle_adapter.create_account(
        #             id=existing_account.id, ledger=int(existing_account.ledger_id)
        #         )

        #     return existing_account

        # logger.info(
        #     "creating new account for keycloak_id=%s tenant_id=%s type=%s currency=%s ledger_id=%s",
        #     context.keycloak_id,
        #     context.tenant_id,
        #     account_type.value,
        #     account_currency.value,
        #     ledger_id,
        # )

        # Create account entry in the database
        account = self.__account_repository.create_account(
            name=payload.name,
            account_number=payload.account_number or generate_account_number(),
            keycloak_id=context.keycloak_id,
            tenant_id=context.tenant_id,
            ledger_id=ledger_id,
            account_type=account_type,
            account_currency=account_currency,
        )

        self.__db.commit()

        logger.info(f"Account created with ID: {account.id}")

        # Create account in TigerBeetle
        self.__tigerbeetle_adapter.create_account(id=account.id, ledger=ledger_id)

        return account

    def get_accounts(self, context: Context):
        """Logic to get all accounts with balances"""
        accounts = self.__account_repository.get_accounts(context.tenant_id)

        if not accounts:
            return []

        # Fetch all TigerBeetle accounts in a single batch
        account_ids = [account.id for account in accounts]
        tigerbeetle_accounts = self.__tigerbeetle_adapter.get_accounts(account_ids)

        # Create a map of account_id -> tigerbeetle_account for quick lookup
        tb_accounts_map = {tb_acc.id: tb_acc for tb_acc in tigerbeetle_accounts}

        # Enrich accounts with balance information
        enriched_accounts = []
        for account in accounts:
            account_dict = account.to_dict()

            # Add balance if TigerBeetle account exists
            if account.id in tb_accounts_map:
                tb_acc = tb_accounts_map[account.id]
                account_dict["balance"] = tb_acc.credits_posted - tb_acc.debits_posted
            else:
                # Account exists in DB but not in TigerBeetle (shouldn't happen normally)
                logger.warning(f"Account {account.id} not found in TigerBeetle")
                account_dict["balance"] = 0

            enriched_accounts.append(account_dict)

        return enriched_accounts

    def get_accounts_by_user(self, context: Context):
        """Logic to get all accounts for a user with balances"""
        accounts = self.__account_repository.get_accounts_by_user(
            context.keycloak_id, context.tenant_id
        )

        if not accounts:
            return []

        # Fetch all TigerBeetle accounts in a single batch
        account_ids = [account.id for account in accounts]
        tigerbeetle_accounts = self.__tigerbeetle_adapter.get_accounts(account_ids)

        # Create a map of account_id -> tigerbeetle_account for quick lookup
        tb_accounts_map = {tb_acc.id: tb_acc for tb_acc in tigerbeetle_accounts}

        # Enrich accounts with balance information
        enriched_accounts = []
        for account in accounts:
            account_dict = account.to_dict()

            # Add balance if TigerBeetle account exists
            if account.id in tb_accounts_map:
                tb_acc = tb_accounts_map[account.id]
                account_dict["balance"] = tb_acc.credits_posted - tb_acc.debits_posted
            else:
                # Account exists in DB but not in TigerBeetle (shouldn't happen normally)
                logger.warning(f"Account {account.id} not found in TigerBeetle")
                account_dict["balance"] = 0

            enriched_accounts.append(account_dict)

        return enriched_accounts

    def get_account_by_id(self, account_id, context: Context):
        """Logic to get account by ID"""
        account = self.__account_repository.get_by_account_id(
            account_id, context.tenant_id
        )

        if not account:
            raise Exception("Account not found.")
        
        logger.info(f"account found {account}")

        tigerbeetle_account = self.__tigerbeetle_adapter.get_account(id=account_id)

        if not tigerbeetle_account:
            raise Exception("Account not found.")

        return {
            **account.to_dict(),
            **self.__tigerbeetle_adapter.account_to_dict(tigerbeetle_account),
            "balance": tigerbeetle_account.credits_posted
            - tigerbeetle_account.debits_posted,
        }

    def get_account_by_account_number(self, account_number: str, context: Context):
        """Logic to get account by ID"""
        account = self.__account_repository.get_by_account_number(
            account_number, context.tenant_id
        )

        if not account:
            raise Exception("Account not found.")

        tigerbeetle_account = self.__tigerbeetle_adapter.get_account(id=account.id)

        if not tigerbeetle_account:
            raise Exception("Account not found.")

        return {
            **account.to_dict(),
            **self.__tigerbeetle_adapter.account_to_dict(tigerbeetle_account),
            "balance": tigerbeetle_account.credits_posted
            - tigerbeetle_account.debits_posted,
        }

    def get_mint_account(self, context: Context):
        """Logic to get mint account by tenant and ledger ID"""
        mint_accounts = self.__account_repository.get_all_mint_accounts(
            context.tenant_id
        )

        account = next(
            (
                mint_account
                for mint_account in mint_accounts
                if str(mint_account.ledger_id) == str(context.ledger_id)
            ),
            None,
        )

        if not account:
            raise Exception("Account not found.")

        return account

    def get_account_by_keycloak_id(self, keycloak_id: str, context: Context):
        """Logic to get account by keycloak ID"""
        account = self.__account_repository.get_by_keycloak_id(
            keycloak_id, context.tenant_id
        )

        if not account:
            return None

        tigerbeetle_account = self.__tigerbeetle_adapter.get_account(id=account.id)

        if not tigerbeetle_account:
            return None

        return {
            **account.to_dict(),
            **self.__tigerbeetle_adapter.account_to_dict(tigerbeetle_account),
            "balance": tigerbeetle_account.credits_posted
            - tigerbeetle_account.debits_posted,
        }

    def setup_pin(self, pin: str, context: Context):
        """Logic to create user pin."""

        self.__account_repository.setup_pin(pin, context.keycloak_id, context.tenant_id)

        self.__db.commit()

        logger.info("Pin setup success..")

    def verify_pin(self, pin: str, context: Context) -> bool:
        """Logic to create user pin."""

        account = self.__account_repository.get_by_keycloak_id(
            context.keycloak_id, context.tenant_id
        )

        if not account:
            raise Exception("This user has no account.")

        return verify_pin(pin, account.pin)

    def check_account(self, account_id: str, pin: str, context: Context):
        """Logic to create user pin."""

        account = self.__account_repository.get_by_account_id(
            account_id, context.tenant_id
        )

        if not account:
            raise Exception("Invalid account.")

        if account.status != AccountStatus.ACTIVE:
            raise Exception(f"This account is {account.status.value}.")

        is_pin_valid = verify_pin(pin, account.pin)

        if not is_pin_valid:
            raise Exception("Invalid PIN.")

    def update_account(self, account_id, update_data):
        # Logic to update account details
        pass

    def delete_account(self, account_id):
        # Logic to delete an account
        pass
