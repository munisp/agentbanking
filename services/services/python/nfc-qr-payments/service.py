"""
NFC/QR Self-Service Payments Service
Enables customers to initiate transactions themselves via NFC tap or QR scan
at agent locations — reducing agent workload and enabling 24/7 self-service.
Supports: QR code generation, NFC token validation, payment initiation,
dynamic QR for specific amounts, and static QR for agent identification.
"""
import hashlib
import hmac
import json
import logging
import qrcode
import base64
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import (
    QRCode, NFCToken, SelfServiceTransaction,
    QRType, QRStatus, TransactionStatus
)
from config import settings

logger = logging.getLogger(__name__)

QR_EXPIRY_STATIC_DAYS = 365       # Static agent QR valid for 1 year
QR_EXPIRY_DYNAMIC_MINUTES = 10    # Dynamic payment QR valid for 10 minutes
NFC_TOKEN_EXPIRY_MINUTES = 5      # NFC token valid for 5 minutes
MAX_QR_AMOUNT = Decimal("500000") # Max NGN 500K per QR transaction
HMAC_SECRET = settings.QR_HMAC_SECRET


class NFCQRPaymentsService:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # QR CODE GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    def generate_static_agent_qr(
        self,
        agent_id: UUID,
        agent_name: str,
        agent_code: str,
        bank_code: str,
        account_number: str,
    ) -> QRCode:
        """Generate a static QR code for an agent's location — printed on signage."""
        payload = {
            "type": "static_agent",
            "agent_id": str(agent_id),
            "agent_code": agent_code,
            "agent_name": agent_name,
            "bank_code": bank_code,
            "account_number": account_number,
            "version": "1.0",
        }
        qr_data = self._sign_payload(payload)
        qr_image_b64 = self._generate_qr_image(qr_data)
        expires_at = datetime.now(timezone.utc) + timedelta(days=QR_EXPIRY_STATIC_DAYS)

        qr = QRCode(
            agent_id=agent_id,
            qr_type="static",
            payload=payload,
            qr_data=qr_data,
            qr_image_base64=qr_image_b64,
            status="active",
            expires_at=expires_at,
        )
        self.db.add(qr)
        self.db.commit()
        self.db.refresh(qr)
        logger.info(f"Static QR generated for agent {agent_id}")
        return qr

    def generate_dynamic_payment_qr(
        self,
        agent_id: UUID,
        amount: Decimal,
        transaction_type: str,
        description: str,
        customer_phone: Optional[str] = None,
        reference: Optional[str] = None,
    ) -> QRCode:
        """Generate a dynamic QR for a specific payment amount — expires in 10 minutes."""
        if amount > MAX_QR_AMOUNT:
            raise ValueError(f"Amount exceeds maximum QR limit of NGN {MAX_QR_AMOUNT:,.2f}")

        ref = reference or f"QR-{uuid4().hex[:12].upper()}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=QR_EXPIRY_DYNAMIC_MINUTES)

        payload = {
            "type": "dynamic_payment",
            "agent_id": str(agent_id),
            "amount": str(amount),
            "currency": "NGN",
            "transaction_type": transaction_type,
            "description": description,
            "reference": ref,
            "customer_phone": customer_phone,
            "expires_at": expires_at.isoformat(),
            "version": "1.0",
        }
        qr_data = self._sign_payload(payload)
        qr_image_b64 = self._generate_qr_image(qr_data)

        qr = QRCode(
            agent_id=agent_id,
            qr_type="dynamic",
            amount=amount,
            transaction_type=transaction_type,
            reference=ref,
            payload=payload,
            qr_data=qr_data,
            qr_image_base64=qr_image_b64,
            status="active",
            expires_at=expires_at,
            customer_phone=customer_phone,
        )
        self.db.add(qr)
        self.db.commit()
        self.db.refresh(qr)
        return qr

    def _generate_qr_image(self, data: str) -> str:
        """Generate QR code image and return as base64 string."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _sign_payload(self, payload: Dict) -> str:
        """Sign payload with HMAC-SHA256 for tamper detection."""
        payload_str = json.dumps(payload, sort_keys=True)
        sig = hmac.new(
            HMAC_SECRET.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        signed = {"data": payload, "sig": sig}
        return json.dumps(signed)

    def _verify_signature(self, qr_data: str) -> Optional[Dict]:
        """Verify QR payload signature. Returns payload if valid, None if tampered."""
        try:
            signed = json.loads(qr_data)
            payload = signed.get("data", {})
            claimed_sig = signed.get("sig", "")
            payload_str = json.dumps(payload, sort_keys=True)
            expected_sig = hmac.new(
                HMAC_SECRET.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(claimed_sig, expected_sig):
                return payload
            return None
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # QR SCANNING & PAYMENT INITIATION
    # ─────────────────────────────────────────────────────────────────────────

    def scan_and_initiate(
        self,
        qr_data: str,
        customer_phone: str,
        customer_bvn: Optional[str] = None,
        override_amount: Optional[Decimal] = None,
    ) -> SelfServiceTransaction:
        """Process a scanned QR code and initiate the payment."""
        # Verify signature
        payload = self._verify_signature(qr_data)
        if not payload:
            raise ValueError("Invalid or tampered QR code")

        # Check expiry for dynamic QR
        if payload.get("type") == "dynamic_payment":
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                raise ValueError("QR code has expired")

        # Find QR record
        qr = self.db.query(QRCode).filter(
            QRCode.agent_id == UUID(payload["agent_id"]),
            QRCode.status == "active",
        ).order_by(QRCode.created_at.desc()).first()

        if qr and qr.expires_at and datetime.now(timezone.utc) > qr.expires_at:
            qr.status = "expired"
            self.db.commit()
            raise ValueError("QR code has expired")

        # Determine amount
        if payload.get("type") == "dynamic_payment":
            amount = Decimal(payload["amount"])
        elif override_amount:
            amount = override_amount
        else:
            raise ValueError("Amount required for static QR transactions")

        # Create self-service transaction
        txn = SelfServiceTransaction(
            agent_id=UUID(payload["agent_id"]),
            customer_phone=customer_phone,
            customer_bvn=customer_bvn,
            amount=amount,
            currency="NGN",
            transaction_type=payload.get("transaction_type", "payment"),
            description=payload.get("description", "QR Payment"),
            reference=payload.get("reference", f"QR-{uuid4().hex[:12].upper()}"),
            channel="qr",
            status="pending",
            qr_payload=payload,
        )
        self.db.add(txn)

        # Mark dynamic QR as used
        if qr and payload.get("type") == "dynamic_payment":
            qr.status = "used"

        self.db.commit()
        self.db.refresh(txn)
        logger.info(f"QR payment initiated: {txn.id} amount={amount} agent={payload['agent_id']}")
        return txn

    # ─────────────────────────────────────────────────────────────────────────
    # NFC TOKEN MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def issue_nfc_token(
        self,
        agent_id: UUID,
        amount: Decimal,
        transaction_type: str,
        customer_phone: str,
    ) -> NFCToken:
        """Issue a short-lived NFC token for tap-to-pay at agent terminal."""
        token_value = uuid4().hex.upper()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=NFC_TOKEN_EXPIRY_MINUTES)

        token = NFCToken(
            agent_id=agent_id,
            token_value=token_value,
            amount=amount,
            transaction_type=transaction_type,
            customer_phone=customer_phone,
            expires_at=expires_at,
            status="active",
        )
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def validate_nfc_token(
        self,
        token_value: str,
        agent_id: UUID,
    ) -> SelfServiceTransaction:
        """Validate an NFC token tap and initiate the transaction."""
        token = self.db.query(NFCToken).filter(
            and_(
                NFCToken.token_value == token_value,
                NFCToken.agent_id == agent_id,
                NFCToken.status == "active",
            )
        ).first()

        if not token:
            raise ValueError("Invalid NFC token")

        if datetime.now(timezone.utc) > token.expires_at:
            token.status = "expired"
            self.db.commit()
            raise ValueError("NFC token has expired")

        # Create transaction
        txn = SelfServiceTransaction(
            agent_id=agent_id,
            customer_phone=token.customer_phone,
            amount=token.amount,
            currency="NGN",
            transaction_type=token.transaction_type,
            description=f"NFC {token.transaction_type}",
            reference=f"NFC-{uuid4().hex[:12].upper()}",
            channel="nfc",
            status="pending",
        )
        self.db.add(txn)

        # Consume token
        token.status = "used"
        token.used_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(txn)
        return txn

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSACTION COMPLETION
    # ─────────────────────────────────────────────────────────────────────────

    def complete_transaction(
        self,
        transaction_id: UUID,
        gateway_reference: str,
        success: bool,
        failure_reason: Optional[str] = None,
    ) -> SelfServiceTransaction:
        txn = self.db.query(SelfServiceTransaction).filter(
            SelfServiceTransaction.id == transaction_id
        ).first()
        if not txn:
            raise ValueError(f"Transaction {transaction_id} not found")

        txn.status = "completed" if success else "failed"
        txn.gateway_reference = gateway_reference
        txn.failure_reason = failure_reason
        txn.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(txn)
        return txn

    def get_agent_qr_codes(self, agent_id: UUID) -> List[QRCode]:
        return self.db.query(QRCode).filter(
            and_(QRCode.agent_id == agent_id, QRCode.status == "active")
        ).order_by(QRCode.created_at.desc()).all()

    def get_agent_transactions(self, agent_id: UUID, limit: int = 50) -> List[SelfServiceTransaction]:
        return self.db.query(SelfServiceTransaction).filter(
            SelfServiceTransaction.agent_id == agent_id
        ).order_by(SelfServiceTransaction.created_at.desc()).limit(limit).all()
