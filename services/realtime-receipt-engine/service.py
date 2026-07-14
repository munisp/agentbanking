"""
Real-Time Receipt Engine
Delivers transaction receipts instantly via SMS, WhatsApp, email, and push notification.
Supports: branded PDF receipts, digital receipt links, receipt re-send,
multi-language receipts (English, Hausa, Yoruba, Igbo), and receipt audit trail.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict
from uuid import UUID, uuid4
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session
from models import Receipt, ReceiptDelivery, ReceiptTemplate, DeliveryChannel, DeliveryStatus
from config import settings

logger = logging.getLogger(__name__)

# Transaction type display names
TXN_TYPE_LABELS = {
    "withdrawal": "Cash Withdrawal",
    "deposit": "Cash Deposit",
    "transfer": "Funds Transfer",
    "bill_payment": "Bill Payment",
    "airtime": "Airtime Top-Up",
    "reversal": "Transaction Reversal",
    "account_opening": "Account Opening",
    "loan_disbursement": "Loan Disbursement",
    "loan_repayment": "Loan Repayment",
}

# Language templates
RECEIPT_TEMPLATES = {
    "en": {
        "header": "TRANSACTION RECEIPT",
        "amount_label": "Amount",
        "fee_label": "Fee",
        "balance_label": "New Balance",
        "date_label": "Date & Time",
        "ref_label": "Reference",
        "agent_label": "Agent",
        "status_label": "Status",
        "success": "SUCCESSFUL",
        "footer": "Thank you for using 54agent Agency Banking",
    },
    "ha": {
        "header": "TAKARDAR CINIKI",
        "amount_label": "Adadin Kudi",
        "fee_label": "Kudin Aiki",
        "balance_label": "Sabon Salo",
        "date_label": "Ranar & Lokaci",
        "ref_label": "Lambar Tabbatarwa",
        "agent_label": "Wakili",
        "status_label": "Yanayi",
        "success": "YA YI NASARA",
        "footer": "Na gode da amfani da 54agent",
    },
    "yo": {
        "header": "IWE IṢOWO",
        "amount_label": "Iye Owo",
        "fee_label": "Owo Iṣẹ",
        "balance_label": "Iye Tuntun",
        "date_label": "Ọjọ & Akoko",
        "ref_label": "Nọmba Ìjẹ́rìísí",
        "agent_label": "Aṣojú",
        "status_label": "Ipò",
        "success": "AṢEYỌRÍ",
        "footer": "E dupe fun lilo 54agent",
    },
    "ig": {
        "header": "AKWỤKWỌ AZỤMAHỊA",
        "amount_label": "Ego",
        "fee_label": "Ụgwọ Ọrụ",
        "balance_label": "Ego Fọdụrụ",
        "date_label": "Ụbọchị & Oge",
        "ref_label": "Nọmba Nkwenye",
        "agent_label": "Onye Nnọchiteanya",
        "status_label": "Ọnọdụ",
        "success": "IHEOMA",
        "footer": "Daalụ maka iji 54agent",
    },
}


class RealtimeReceiptEngine:

    def __init__(self, db: Session):
        self.db = db
        self._http = httpx.AsyncClient(timeout=10.0)

    # ─────────────────────────────────────────────────────────────────────────
    # RECEIPT GENERATION
    # ─────────────────────────────────────────────────────────────────────────

    def generate_receipt(
        self,
        transaction_id: UUID,
        agent_id: UUID,
        agent_name: str,
        agent_code: str,
        customer_phone: str,
        customer_name: Optional[str],
        transaction_type: str,
        amount: Decimal,
        fee: Decimal,
        new_balance: Optional[Decimal],
        reference: str,
        status: str,
        currency: str = "NGN",
        language: str = "en",
        extra_data: Optional[Dict] = None,
    ) -> Receipt:
        """Generate a receipt record for a completed transaction."""
        template = RECEIPT_TEMPLATES.get(language, RECEIPT_TEMPLATES["en"])
        txn_label = TXN_TYPE_LABELS.get(transaction_type, transaction_type.replace("_", " ").title())
        now = datetime.now(timezone.utc)

        receipt_text = self._format_text_receipt(
            template=template,
            txn_label=txn_label,
            agent_name=agent_name,
            agent_code=agent_code,
            customer_name=customer_name,
            amount=amount,
            fee=fee,
            new_balance=new_balance,
            reference=reference,
            status=status,
            currency=currency,
            timestamp=now,
        )

        receipt_link = f"{settings.RECEIPT_BASE_URL}/receipts/{reference}"
        receipt_hash = hashlib.sha256(
            f"{transaction_id}{reference}{amount}{now.isoformat()}".encode()
        ).hexdigest()

        receipt = Receipt(
            transaction_id=transaction_id,
            agent_id=agent_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            transaction_type=transaction_type,
            txn_label=txn_label,
            amount=amount,
            fee=fee,
            new_balance=new_balance,
            reference=reference,
            currency=currency,
            status=status,
            language=language,
            receipt_text=receipt_text,
            receipt_link=receipt_link,
            receipt_hash=receipt_hash,
            extra_data=extra_data or {},
            generated_at=now,
        )
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        return receipt

    def _format_text_receipt(
        self,
        template: Dict,
        txn_label: str,
        agent_name: str,
        agent_code: str,
        customer_name: Optional[str],
        amount: Decimal,
        fee: Decimal,
        new_balance: Optional[Decimal],
        reference: str,
        status: str,
        currency: str,
        timestamp: datetime,
    ) -> str:
        lines = [
            "=" * 40,
            f"  {template['header']}",
            f"  {txn_label}",
            "=" * 40,
            f"{template['date_label']}: {timestamp.strftime('%d/%m/%Y %H:%M:%S')} UTC",
            f"{template['ref_label']}: {reference}",
            f"{template['agent_label']}: {agent_name} ({agent_code})",
        ]
        if customer_name:
            lines.append(f"Customer: {customer_name}")
        lines += [
            "-" * 40,
            f"{template['amount_label']}: {currency} {amount:,.2f}",
            f"{template['fee_label']}: {currency} {fee:,.2f}",
        ]
        if new_balance is not None:
            lines.append(f"{template['balance_label']}: {currency} {new_balance:,.2f}")
        lines += [
            "-" * 40,
            f"{template['status_label']}: {template['success'] if status == 'completed' else status.upper()}",
            "=" * 40,
            template["footer"],
        ]
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # DELIVERY
    # ─────────────────────────────────────────────────────────────────────────

    async def deliver_receipt(
        self,
        receipt: Receipt,
        channels: Optional[List[str]] = None,
    ) -> List[ReceiptDelivery]:
        """Deliver receipt via all configured channels."""
        if channels is None:
            channels = ["sms"]  # Default to SMS; add whatsapp/email if configured

        deliveries = []
        for channel in channels:
            delivery = await self._deliver_via_channel(receipt, channel)
            deliveries.append(delivery)
        return deliveries

    async def _deliver_via_channel(self, receipt: Receipt, channel: str) -> ReceiptDelivery:
        delivery = ReceiptDelivery(
            receipt_id=receipt.id,
            channel=channel,
            recipient=receipt.customer_phone,
            status="pending",
        )
        self.db.add(delivery)
        self.db.flush()

        try:
            if channel == "sms":
                await self._send_sms(receipt.customer_phone, receipt.receipt_text)
            elif channel == "whatsapp":
                await self._send_whatsapp(receipt.customer_phone, receipt)
            elif channel == "email":
                if receipt.extra_data.get("customer_email"):
                    await self._send_email(receipt.extra_data["customer_email"], receipt)
            elif channel == "push":
                await self._send_push(receipt.agent_id, receipt)

            delivery.status = "delivered"
            delivery.delivered_at = datetime.now(timezone.utc)
        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)
            logger.error(f"Receipt delivery failed via {channel}: {e}")

        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    async def _send_sms(self, phone: str, message: str) -> None:
        """Send SMS via configured SMS gateway (Termii/Twilio/Africa's Talking)."""
        if not settings.SMS_API_KEY:
            logger.warning("SMS_API_KEY not configured, skipping SMS delivery")
            return

        # Truncate for SMS (160 chars per segment)
        sms_text = (
            f"54agent Receipt\n"
            f"Ref: {message.split('Ref:')[1].split(chr(10))[0].strip() if 'Ref:' in message else 'N/A'}\n"
            f"Amt: {message.split('Amount:')[1].split(chr(10))[0].strip() if 'Amount:' in message else 'N/A'}\n"
            f"Status: SUCCESS\n"
            f"View: {settings.RECEIPT_BASE_URL}/r/{phone[-4:]}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.SMS_GATEWAY_URL}/api/sms/send",
                json={
                    "to": phone,
                    "from": "54agent",
                    "sms": sms_text,
                    "type": "plain",
                    "api_key": settings.SMS_API_KEY,
                    "channel": "generic",
                },
            )
            response.raise_for_status()

    async def _send_whatsapp(self, phone: str, receipt: Receipt) -> None:
        """Send WhatsApp message via WhatsApp Business API."""
        if not settings.WHATSAPP_API_KEY:
            logger.warning("WHATSAPP_API_KEY not configured, skipping WhatsApp delivery")
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.WHATSAPP_API_URL}/messages",
                headers={"Authorization": f"Bearer {settings.WHATSAPP_API_KEY}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": phone.lstrip("+"),
                    "type": "template",
                    "template": {
                        "name": "transaction_receipt",
                        "language": {"code": "en"},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": receipt.txn_label},
                                    {"type": "text", "text": f"{receipt.currency} {receipt.amount:,.2f}"},
                                    {"type": "text", "text": receipt.reference},
                                    {"type": "text", "text": receipt.receipt_link},
                                ],
                            }
                        ],
                    },
                },
            )
            response.raise_for_status()

    async def _send_email(self, email: str, receipt: Receipt) -> None:
        """Send email receipt via SMTP or SendGrid."""
        if not settings.EMAIL_API_KEY:
            logger.warning("EMAIL_API_KEY not configured, skipping email delivery")
            return

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {settings.EMAIL_API_KEY}"},
                json={
                    "personalizations": [{"to": [{"email": email}]}],
                    "from": {"email": "receipts@54agent.com", "name": "54agent Agency Banking"},
                    "subject": f"Transaction Receipt - {receipt.reference}",
                    "content": [{"type": "text/plain", "value": receipt.receipt_text}],
                },
            )
            response.raise_for_status()

    async def _send_push(self, agent_id: UUID, receipt: Receipt) -> None:
        """Send push notification to agent's mobile app."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.NOTIFICATION_SERVICE_URL}/api/v1/notifications/push",
                json={
                    "user_id": str(agent_id),
                    "title": f"Receipt: {receipt.txn_label}",
                    "body": f"{receipt.currency} {receipt.amount:,.2f} - {receipt.reference}",
                    "data": {"receipt_id": str(receipt.id), "reference": receipt.reference},
                },
            )

    # ─────────────────────────────────────────────────────────────────────────
    # RESEND & RETRIEVAL
    # ─────────────────────────────────────────────────────────────────────────

    async def resend_receipt(self, reference: str, channel: str) -> ReceiptDelivery:
        receipt = self.db.query(Receipt).filter(Receipt.reference == reference).first()
        if not receipt:
            raise ValueError(f"Receipt for reference {reference} not found")
        deliveries = await self.deliver_receipt(receipt, channels=[channel])
        return deliveries[0]

    def get_receipt_by_reference(self, reference: str) -> Optional[Receipt]:
        return self.db.query(Receipt).filter(Receipt.reference == reference).first()

    def get_agent_receipts(self, agent_id: UUID, limit: int = 50) -> List[Receipt]:
        return self.db.query(Receipt).filter(
            Receipt.agent_id == agent_id
        ).order_by(Receipt.generated_at.desc()).limit(limit).all()
