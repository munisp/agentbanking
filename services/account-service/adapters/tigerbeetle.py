import logging
import tigerbeetle as tb
from decimal import Decimal
from utils import create_logger, get_config

logging.basicConfig(level=logging.DEBUG)

logger = create_logger(__name__)

config = get_config()

tb.configure_logging(debug=False)


class TigerBeetleAdapter:
    def __init__(self):
        self._cluster_id = int(Decimal(config.TB_CLUSTER_ID))
        self._address = config.TB_ADDRESS
        self._client = tb.ClientSync(
            cluster_id=self._cluster_id,
            replica_addresses=self._address
        )
        logger.info(f"TigerBeetle cluster_id resolved to: {self._cluster_id}")

    def get_account(self, id: int):
        accounts = self._client.lookup_accounts([id])
        if len(accounts) == 0:
            return None
        return accounts[0]

    def get_accounts(self, ids: list[int]):
        if not ids:
            return []
        return self._client.lookup_accounts(ids)

    def create_account(self, id: int, is_system_account: bool = False, ledger: int = 1):
        flags = tb.AccountFlags.NONE
        if not is_system_account:
            flags = tb.AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS
        flags = flags | tb.AccountFlags.HISTORY

        account_errors = self._client.create_accounts([
            tb.Account(
                id=id,
                debits_pending=0,
                debits_posted=0,
                credits_pending=0,
                credits_posted=0,
                user_data_128=0,
                user_data_64=0,
                user_data_32=0,
                ledger=ledger,
                code=1,
                timestamp=0,
                flags=flags,
            )
        ])

        if len(account_errors) > 0:
            raise Exception(f"TigerBeetle account creation failed: {account_errors}")

    def account_to_dict(self, acc: tb.Account):
        return {
            "id": acc.id,
            "debits_pending": acc.debits_pending,
            "debits_posted": acc.debits_posted,
            "credits_pending": acc.credits_pending,
            "credits_posted": acc.credits_posted,
            "user_data_128": acc.user_data_128,
            "user_data_64": acc.user_data_64,
            "user_data_32": acc.user_data_32,
            "ledger": acc.ledger,
            "code": acc.code,
            "flags": int(acc.flags),  # Enum -> number
            "timestamp": acc.timestamp,
        }
