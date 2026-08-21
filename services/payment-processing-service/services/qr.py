import datetime, json, base64, hashlib, os
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from schemas import GenerateQRSchema, ValidateQRSchema, Context
from fastapi import HTTPException
from dapr.clients import DaprClient
from utils import generate_qr_base64, create_logger, get_config

logger = create_logger(__name__)
config = get_config()

try:  # Dapr python SDK state options (etag / first-write concurrency)
    from dapr.clients.grpc._state import Concurrency, Consistency, StateOptions

    _FIRST_WRITE_SUPPORTED = True
except Exception:  # pragma: no cover - older SDKs without state options
    _FIRST_WRITE_SUPPORTED = False

_dapr = None


def _get_dapr_client() -> DaprClient:
    global _dapr
    if _dapr is None:
        _dapr = DaprClient()
    return _dapr


class QRService:
    def generate_qr_code(self, payload: GenerateQRSchema, context: Context) -> str:
        expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=15) # QR code valid for 15 minutes

        qr_data = {
            "recipient": payload.recipient,
            "amount": payload.amount,
            "currency": payload.currency.value,
            "expiry": expiry.isoformat() + "Z",
            "note": payload.note,
            "tenant": context.tenant_id,
            "ledger": context.ledger_id
        }

        qr_data["signature"] = self.sign_qr_payload(qr_data)

        logger.info(f"Generating QR code with data: {qr_data}")

        return generate_qr_base64(json.dumps(qr_data))

    def validate_qr_code(self, payload: ValidateQRSchema, context: Context) -> bool:
        try:
            qr_data = {
                "recipient": payload.recipient,
                "amount": payload.amount,
                "currency": payload.currency.value,
                "expiry": payload.expiry,
                "note": payload.note,
                "tenant": context.tenant_id,
                "ledger": context.ledger_id,
                "signature": payload.signature,
            }

            expiry = datetime.datetime.fromisoformat(qr_data["expiry"].replace("Z", "+00:00"))
            if datetime.datetime.now(datetime.timezone.utc) > expiry:
                logger.warning("QR code has expired.")
                return False

            signature = base64.b64decode(qr_data["signature"])
            signed_data = qr_data.copy()
            del signed_data["signature"]
            message = json.dumps(signed_data, separators=(",", ":"), sort_keys=True).encode()

            logger.info(f"Validating QR code with data: {signed_data}")

            with open("qr_public.key", "rb") as f:
                public_key = serialization.load_pem_public_key(f.read())

                if not isinstance(public_key, ed25519.Ed25519PublicKey):
                    raise TypeError("Loaded public key is not of type Ed25519PublicKey")

                public_key.verify(signature, message)

            # NF-FF-34: a signed QR is single-use — mark it consumed before
            # reporting success so replays are rejected with 409.
            self._mark_qr_consumed(signed_data, qr_data["signature"])

            logger.info("QR code is valid.")

            return True
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"QR code validation failed: {str(e)}")
            return False

    def _mark_qr_consumed(self, signed_data: dict, signature_b64: str) -> None:
        """NF-FF-34: single-use enforcement for signed QR payloads.

        The consumed marker is keyed by a SHA-256 hash of the signed payload
        plus its signature, so the exact same QR can never be redeemed twice.
        Replays raise 409. When the state store is unavailable the service
        fails closed (503) in production unless QR_SINGLE_USE_REQUIRED=false
        is set explicitly.
        """
        digest = hashlib.sha256(
            json.dumps(signed_data, separators=(",", ":"), sort_keys=True).encode()
            + b"."
            + signature_b64.encode()
        ).hexdigest()
        key = f"qr:consumed:{digest}"
        try:
            client = _get_dapr_client()
            existing = client.get_state(config.STATE_STORE_NAME, key)
            if existing and existing.data:
                logger.warning("QR code replay rejected key=%s", key)
                raise HTTPException(
                    status_code=409, detail="QR code has already been used."
                )
            marker = json.dumps(
                {
                    "consumed_at": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat()
                }
            )
            try:
                if _FIRST_WRITE_SUPPORTED:
                    # etag="" + first-write concurrency == create-only-if-absent
                    client.save_state(
                        config.STATE_STORE_NAME,
                        key,
                        marker,
                        etag="",
                        state_options=StateOptions(
                            consistency=Consistency.strong,
                            concurrency=Concurrency.first_write,
                        ),
                    )
                else:
                    client.save_state(config.STATE_STORE_NAME, key, marker)
            except Exception as save_error:
                # Lost a concurrent race or the write failed; re-read to tell
                # a replay (409) apart from a store outage (handled below).
                again = client.get_state(config.STATE_STORE_NAME, key)
                if again and again.data:
                    logger.warning("QR code replay rejected key=%s", key)
                    raise HTTPException(
                        status_code=409, detail="QR code has already been used."
                    )
                raise save_error
        except HTTPException:
            raise
        except Exception as store_error:
            single_use_required = (
                os.environ.get("QR_SINGLE_USE_REQUIRED", "").lower() != "false"
            )
            environment = os.environ.get("ENVIRONMENT", "development").lower()
            if environment == "production" and single_use_required:
                logger.error(
                    "QR single-use store unavailable; failing closed: %s",
                    str(store_error),
                )
                raise HTTPException(
                    status_code=503,
                    detail="QR validation temporarily unavailable. Please retry.",
                )
            logger.warning(
                "QR single-use marking unavailable; allowing validation "
                "(non-production or explicitly disabled): %s",
                str(store_error),
            )

    def sign_qr_payload(self, payload: dict) -> str:
        # The Ed25519 private key must be provided via the QR_PRIVATE_KEY_PEM
        # environment variable (PEM-encoded). It is no longer read from a
        # committed file. ROTATION: generate a new Ed25519 keypair, update
        # QR_PRIVATE_KEY_PEM in the secret store, redeploy, then distribute
        # the new public key (qr_public.key) to verifiers and revoke the old one.
        pem = os.environ.get("QR_PRIVATE_KEY_PEM")
        if not pem:
            raise RuntimeError(
                "QR_PRIVATE_KEY_PEM is not set; cannot sign QR payloads. "
                "Provide the PEM-encoded Ed25519 private key via the environment."
            )
        private_key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)

        if not isinstance(private_key, ed25519.Ed25519PrivateKey):
            raise TypeError("Loaded private key is not of type Ed25519PrivateKey")

        message = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()

        signature = private_key.sign(message)

        return base64.b64encode(signature).decode("utf-8")
