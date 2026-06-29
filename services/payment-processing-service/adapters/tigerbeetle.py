import logging
import tigerbeetle as tb
from utils import create_logger, get_config

logging.basicConfig(level=logging.DEBUG)

logger = create_logger(__name__)

config = get_config()

tb.configure_logging(debug=True)


class TigerBeetleAdapter:
    def __init__(self):
        self._cluster_id = int(config.TB_CLUSTER_ID)
        self._address = config.TB_ADDRESS

    def transfer(self, payer: int, payee: int, amount: int, ledger: int = 1):
        # Generate transaction ID
        id = tb.id()

        with tb.ClientSync(
            cluster_id=self._cluster_id, replica_addresses=self._address
        ) as client:
            transfer_errors = client.create_transfers(
                [
                    tb.Transfer(
                        id=id,
                        debit_account_id=payer,
                        credit_account_id=payee,
                        amount=amount,
                        code=1,
                        ledger=ledger,
                    ),
                ]
            )
            logger.info(f"TigerBeetle transfer_errors errors: {transfer_errors}")

            if len(transfer_errors) > 0:
                error_codes = [
                    str(getattr(error, "result", "")) for error in transfer_errors
                ]

                if any("EXCEEDS_CREDITS" in code for code in error_codes):
                    raise TigerBeetleBusinessError(
                        "Insufficient balance for transfer.",
                        error_code="EXCEEDS_CREDITS",
                    )

                raise Exception(f"TigerBeetle transfer failed: {transfer_errors}")

        return id


class TigerBeetleBusinessError(Exception):
    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code

    def get_account(self, id: int):
        with tb.ClientSync(
            cluster_id=self._cluster_id, replica_addresses=self._address
        ) as client:
            accounts = client.lookup_accounts([id])

            logger.info(f"TigerBeetle get_account result: {accounts}")

            if len(accounts) == 0:
                return None

            return accounts[0]

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
