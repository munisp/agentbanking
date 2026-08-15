import datetime, json, base64, os
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from schemas import GenerateQRSchema, ValidateQRSchema, Context
from utils import generate_qr_base64, create_logger

logger = create_logger(__name__)

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

            logger.info("QR code is valid.")

            return True
        except Exception as e:
            logger.error(f"QR code validation failed: {str(e)}")
            return False
    
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
