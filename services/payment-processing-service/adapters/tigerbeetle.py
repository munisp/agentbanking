import logging
import uuid
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

    @staticmethod
    def derive_transfer_id(idempotency_key: str, step: str = "") -> int:
        """Deterministic TigerBeetle transfer id derived from an idempotency key.

        Retrying the same logical operation (same idempotency key + step)
        always yields the same transfer id, so TigerBeetle itself rejects
        duplicate postings instead of double-moving funds.
        """
        return uuid.uuid5(
            uuid.NAMESPACE_URL, f"54agent:transfer:{idempotency_key}:{step}"
        ).int

    def transfer(
        self,
        payer: int,
        payee: int,
        amount: int,
        ledger: int = 1,
        transfer_id: int | uuid.UUID | str | None = None,
    ):
        # NF-FF-14: use a caller-supplied deterministic id when provided so that
        # ledger-level dedupe works; otherwise fall back to a fresh random id.
        if transfer_id is None:
            id = tb.id()
        elif isinstance(transfer_id, uuid.UUID):
            id = transfer_id.int
        elif isinstance(transfer_id, str):
            id = uuid.UUID(transfer_id).int
        else:
            id = int(transfer_id)

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

    @property
    def supports_linked_transfers(self) -> bool:
        """True when the TigerBeetle client library supports linked (atomic) transfers."""
        transfer_flags = getattr(tb, "TransferFlags", None)
        return transfer_flags is not None and hasattr(transfer_flags, "linked")

    def transfer_linked(self, legs: list, transfer_ids: list | None = None):
        """Create multiple transfers as an atomic linked chain (all-or-nothing).

        NF-FF-12: cross-currency movements use this so the debit and credit
        legs can never drift apart. `legs` is a list of dicts with keys
        payer/payee/amount/ledger. Returns the list of transfer ids.
        Raises TigerBeetleBusinessError for insufficient funds.
        """
        if not self.supports_linked_transfers:
            raise NotImplementedError(
                "TigerBeetle client does not support linked transfers"
            )

        ids = []
        transfers = []
        last_index = len(legs) - 1
        for index, leg in enumerate(legs):
            transfer_id = (
                transfer_ids[index] if transfer_ids is not None else None
            )
            if transfer_id is None:
                leg_id = tb.id()
            elif isinstance(transfer_id, uuid.UUID):
                leg_id = transfer_id.int
            elif isinstance(transfer_id, str):
                leg_id = uuid.UUID(transfer_id).int
            else:
                leg_id = int(transfer_id)
            ids.append(leg_id)
            transfers.append(
                tb.Transfer(
                    id=leg_id,
                    debit_account_id=leg["payer"],
                    credit_account_id=leg["payee"],
                    amount=leg["amount"],
                    code=1,
                    ledger=leg["ledger"],
                    # all but the last transfer carry the linked flag, chaining
                    # the batch into a single atomic commit
                    flags=(
                        tb.TransferFlags.linked if index < last_index else tb.TransferFlags(0)
                    ),
                )
            )

        with tb.ClientSync(
            cluster_id=self._cluster_id, replica_addresses=self._address
        ) as client:
            transfer_errors = client.create_transfers(transfers)
            logger.info(f"TigerBeetle linked transfer errors: {transfer_errors}")

            if len(transfer_errors) > 0:
                # linked chain: when any leg fails, NONE of the legs commit
                error_codes = [
                    str(getattr(error, "result", "")) for error in transfer_errors
                ]
                if any("EXCEEDS_CREDITS" in code for code in error_codes):
                    raise TigerBeetleBusinessError(
                        "Insufficient balance for linked transfer.",
                        error_code="EXCEEDS_CREDITS",
                    )
                raise Exception(
                    f"TigerBeetle linked transfer failed: {transfer_errors}"
                )

        return ids

    def get_account(self, id: int):
        with tb.ClientSync(
            cluster_id=self._cluster_id, replica_addresses=self._address
        ) as client:
            accounts = client.lookup_accounts([id])

            logger.info(f"TigerBeetle get_account result: {accounts}")

            if len(accounts) == 0:
                return None

            return accounts[0]

    def account_to_dict(self, acc: "tb.Account"):
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


class TigerBeetleBusinessError(Exception):
    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code
