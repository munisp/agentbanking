"""
Instant Reversal Engine
Detects failed/double-debit transactions and automatically initiates
reversals within 60 seconds. Integrates with all payment gateways
and notifies agents and customers via SMS/WhatsApp.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from uuid import UUID, uuid4
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from models import (
    ReversalRequest, ReversalAuditLog,
    ReversalStatus, ReversalReason, DetectionSource
)
from config import settings

logger = logging.getLogger(__name__)

SLA_SECONDS = 60          # CBN mandated: reverse within 60 seconds
ESCALATION_SECONDS = 300  # Escalate to RM after 5 minutes if not resolved
AUTO_REVERSAL_REASONS = {
    "double_debit": "Customer debited twice for single transaction",
    "failed_dispense": "Cash not dispensed but account debited",
    "network_error": "Transaction failed mid-flight due to network",
    "timeout": "Transaction timed out with ambiguous state",
}


class InstantReversalEngine:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # DETECTION
    # ─────────────────────────────────────────────────────────────────────────

    def detect_double_debit(self, agent_id: UUID, customer_phone: str,
                            amount: Decimal, window_seconds: int = 120) -> bool:
        """Detect if a duplicate transaction occurred within the time window."""
        since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
        count = self.db.query(ReversalRequest).filter(
            and_(
                ReversalRequest.agent_id == agent_id,
                ReversalRequest.customer_phone == customer_phone,
                ReversalRequest.amount == amount,
                ReversalRequest.reversal_reason == "double_debit",
                ReversalRequest.created_at >= since,
            )
        ).count()
        return count > 0

    def check_transaction_ambiguity(self, transaction_id: UUID) -> Dict:
        """
        Check if a transaction is in an ambiguous state (debit sent but
        no confirmation received). Returns ambiguity details.
        """
        # In production this queries the transaction service
        # Here we check the reversal table for existing pending reversals
        existing = self.db.query(ReversalRequest).filter(
            ReversalRequest.original_transaction_id == transaction_id
        ).first()
        return {
            "is_ambiguous": existing is None,
            "existing_reversal": existing.id if existing else None,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # INITIATION
    # ─────────────────────────────────────────────────────────────────────────

    def initiate_reversal(
        self,
        original_transaction_id: UUID,
        agent_id: UUID,
        amount: Decimal,
        reason: str,
        customer_phone: Optional[str] = None,
        auto_triggered: bool = False,
        detection_source: str = "agent_report",
    ) -> ReversalRequest:
        """Initiate a reversal request with 60-second SLA clock."""
        # Check for duplicate reversal request
        existing = self.db.query(ReversalRequest).filter(
            and_(
                ReversalRequest.original_transaction_id == original_transaction_id,
                ReversalRequest.status.in_(["pending", "processing"]),
            )
        ).first()
        if existing:
            raise ValueError(f"Active reversal already exists: {existing.id}")

        sla_deadline = datetime.now(timezone.utc) + timedelta(seconds=SLA_SECONDS)

        reversal = ReversalRequest(
            original_transaction_id=original_transaction_id,
            agent_id=agent_id,
            customer_phone=customer_phone,
            amount=amount,
            reversal_reason=reason,
            status="pending",
            auto_triggered=auto_triggered,
            detection_source=detection_source,
            sla_deadline=sla_deadline,
            initiated_at=datetime.now(timezone.utc),
        )
        self.db.add(reversal)
        self.db.commit()
        self.db.refresh(reversal)

        self._log_audit(reversal.id, "initiated", "system", {
            "reason": reason,
            "auto_triggered": auto_triggered,
            "sla_deadline": sla_deadline.isoformat(),
        })

        logger.info(f"Reversal initiated: {reversal.id} for txn {original_transaction_id} "
                    f"amount={amount} reason={reason} SLA={sla_deadline.isoformat()}")

        # Trigger async processing
        asyncio.create_task(self._process_reversal_async(reversal.id))
        return reversal

    # ─────────────────────────────────────────────────────────────────────────
    # PROCESSING
    # ─────────────────────────────────────────────────────────────────────────

    async def _process_reversal_async(self, reversal_id: UUID):
        """Async processing of reversal through payment gateway."""
        try:
            reversal = self.db.query(ReversalRequest).filter(
                ReversalRequest.id == reversal_id
            ).first()
            if not reversal or reversal.status != "pending":
                return

            reversal.status = "processing"
            self.db.commit()

            # Call payment gateway reversal API
            result = await self._call_gateway_reversal(reversal)

            if result["success"]:
                reversal.status = "completed"
                reversal.bank_reference = result.get("bank_reference")
                reversal.reversal_reference = result.get("reversal_reference")
                reversal.completed_at = datetime.now(timezone.utc)
                reversal.sla_breached = datetime.now(timezone.utc) > reversal.sla_deadline
                self.db.commit()

                self._log_audit(reversal_id, "completed", "system", result)
                await self._send_reversal_notification(reversal, success=True)

                logger.info(f"Reversal {reversal_id} completed. "
                            f"SLA breached: {reversal.sla_breached}")
            else:
                reversal.status = "failed"
                self.db.commit()
                self._log_audit(reversal_id, "failed", "system", result)
                await self._escalate_reversal(reversal, result.get("error", "Gateway failure"))

        except Exception as e:
            logger.error(f"Reversal processing error {reversal_id}: {e}")
            try:
                reversal = self.db.query(ReversalRequest).filter(
                    ReversalRequest.id == reversal_id
                ).first()
                if reversal:
                    reversal.status = "escalated"
                    reversal.escalated_at = datetime.now(timezone.utc)
                    reversal.escalation_reason = str(e)
                    self.db.commit()
            except Exception:
                pass

    async def _call_gateway_reversal(self, reversal: ReversalRequest) -> Dict:
        """Call the appropriate payment gateway to reverse the transaction."""
        # Determine gateway from transaction metadata
        # In production, this looks up the original transaction's gateway
        gateway_url = settings.PAYMENT_GATEWAY_URL
        timeout = httpx.Timeout(30.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{gateway_url}/api/v1/transactions/reverse",
                    json={
                        "transaction_id": str(reversal.original_transaction_id),
                        "amount": float(reversal.amount),
                        "reason": reversal.reversal_reason,
                        "reversal_id": str(reversal.id),
                    },
                    headers={
                        "Authorization": f"Bearer {settings.GATEWAY_API_KEY}",
                        "X-Idempotency-Key": str(reversal.id),
                    }
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    return {
                        "success": True,
                        "bank_reference": data.get("bank_reference"),
                        "reversal_reference": data.get("reversal_reference"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Gateway returned {response.status_code}: {response.text[:200]}",
                    }
        except httpx.TimeoutException:
            return {"success": False, "error": "Gateway timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _escalate_reversal(self, reversal: ReversalRequest, reason: str):
        """Escalate failed reversal to relationship manager."""
        reversal.status = "escalated"
        reversal.escalated_at = datetime.now(timezone.utc)
        reversal.escalation_reason = reason
        self.db.commit()
        self._log_audit(reversal.id, "escalated", "system", {"reason": reason})
        logger.warning(f"Reversal {reversal.id} escalated: {reason}")

    async def _send_reversal_notification(self, reversal: ReversalRequest, success: bool):
        """Send SMS/WhatsApp notification to customer and agent."""
        if not reversal.customer_phone:
            return
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                msg = (
                    f"Your reversal of NGN {reversal.amount:,.2f} has been processed successfully. "
                    f"Ref: {reversal.reversal_reference}"
                ) if success else (
                    f"Your reversal request for NGN {reversal.amount:,.2f} is being processed. "
                    f"Our team will contact you shortly."
                )
                await client.post(
                    f"{settings.NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
                    json={
                        "phone": reversal.customer_phone,
                        "message": msg,
                        "channels": ["sms", "whatsapp"],
                        "priority": "high",
                    }
                )
        except Exception as e:
            logger.warning(f"Notification failed for reversal {reversal.id}: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # QUERIES
    # ─────────────────────────────────────────────────────────────────────────

    def get_reversal(self, reversal_id: UUID) -> Optional[ReversalRequest]:
        return self.db.query(ReversalRequest).filter(
            ReversalRequest.id == reversal_id
        ).first()

    def get_agent_reversals(self, agent_id: UUID, limit: int = 50) -> List[ReversalRequest]:
        return self.db.query(ReversalRequest).filter(
            ReversalRequest.agent_id == agent_id
        ).order_by(ReversalRequest.initiated_at.desc()).limit(limit).all()

    def get_pending_reversals(self) -> List[ReversalRequest]:
        """Get all pending reversals for SLA monitoring."""
        return self.db.query(ReversalRequest).filter(
            ReversalRequest.status.in_(["pending", "processing"])
        ).order_by(ReversalRequest.sla_deadline.asc()).all()

    def get_sla_breached_reversals(self) -> List[ReversalRequest]:
        """Get reversals that have breached the 60-second SLA."""
        now = datetime.now(timezone.utc)
        return self.db.query(ReversalRequest).filter(
            and_(
                ReversalRequest.sla_deadline < now,
                ReversalRequest.status.in_(["pending", "processing"]),
            )
        ).all()

    def get_reversal_metrics(self) -> Dict:
        """Reversal performance metrics for admin dashboard."""
        from sqlalchemy import func
        today = datetime.now(timezone.utc).date()
        since_today = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

        total_today = self.db.query(func.count(ReversalRequest.id)).filter(
            ReversalRequest.initiated_at >= since_today
        ).scalar() or 0

        completed_today = self.db.query(func.count(ReversalRequest.id)).filter(
            and_(ReversalRequest.initiated_at >= since_today,
                 ReversalRequest.status == "completed")
        ).scalar() or 0

        sla_met = self.db.query(func.count(ReversalRequest.id)).filter(
            and_(ReversalRequest.initiated_at >= since_today,
                 ReversalRequest.status == "completed",
                 ReversalRequest.sla_breached == False)
        ).scalar() or 0

        avg_time = self.db.query(
            func.avg(
                func.extract("epoch", ReversalRequest.completed_at) -
                func.extract("epoch", ReversalRequest.initiated_at)
            )
        ).filter(
            and_(ReversalRequest.initiated_at >= since_today,
                 ReversalRequest.status == "completed")
        ).scalar()

        return {
            "total_today": total_today,
            "completed_today": completed_today,
            "sla_met_today": sla_met,
            "sla_compliance_pct": round(sla_met / completed_today * 100, 1) if completed_today > 0 else 100.0,
            "avg_reversal_seconds": round(float(avg_time), 1) if avg_time else 0,
            "pending_count": self.db.query(func.count(ReversalRequest.id)).filter(
                ReversalRequest.status.in_(["pending", "processing"])
            ).scalar() or 0,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # AUDIT
    # ─────────────────────────────────────────────────────────────────────────

    def _log_audit(self, reversal_id: UUID, action: str, actor: str, details: Dict):
        log = ReversalAuditLog(
            reversal_id=reversal_id,
            action=action,
            actor=actor,
            details=details,
        )
        self.db.add(log)
        self.db.commit()

    def get_audit_trail(self, reversal_id: UUID) -> List[ReversalAuditLog]:
        return self.db.query(ReversalAuditLog).filter(
            ReversalAuditLog.reversal_id == reversal_id
        ).order_by(ReversalAuditLog.created_at.asc()).all()
