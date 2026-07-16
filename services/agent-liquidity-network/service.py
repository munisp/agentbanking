"""
Agent-to-Agent Liquidity Network
Enables agents to lend/borrow float from each other within a trusted network,
reducing dependency on bank branches for float top-up.
Features: P2P float requests, automated matching, tiered interest rates,
reputation scoring, settlement via TigerBeetle, and network analytics.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple
from uuid import UUID, uuid4
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from models import (
    LiquidityRequest, LiquidityOffer, LiquidityMatch, LiquidityRepayment,
    AgentLiquidityProfile, NetworkTransaction, RequestStatus, MatchStatus
)
from config import settings

logger = logging.getLogger(__name__)

# Network parameters
MIN_FLOAT_REQUEST = Decimal("5000.00")     # NGN 5,000 minimum
MAX_FLOAT_REQUEST = Decimal("500000.00")   # NGN 500,000 maximum
DEFAULT_INTEREST_RATE = Decimal("0.005")   # 0.5% per day
MAX_LOAN_DURATION_DAYS = 7
MATCHING_FEE_RATE = Decimal("0.001")       # 0.1% platform fee


class AgentLiquidityNetworkService:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # LIQUIDITY PROFILE
    # ─────────────────────────────────────────────────────────────────────────

    def get_or_create_profile(self, agent_id: UUID, agent_name: str, agent_code: str) -> AgentLiquidityProfile:
        profile = self.db.query(AgentLiquidityProfile).filter(
            AgentLiquidityProfile.agent_id == agent_id
        ).first()
        if not profile:
            profile = AgentLiquidityProfile(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_code=agent_code,
                reputation_score=Decimal("100.00"),
                total_lent=Decimal("0"),
                total_borrowed=Decimal("0"),
                successful_repayments=0,
                late_repayments=0,
                defaults=0,
                is_lender_eligible=True,
                is_borrower_eligible=True,
                max_lend_amount=Decimal("100000.00"),
                max_borrow_amount=Decimal("50000.00"),
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_lender_eligibility(self, agent_id: UUID, max_lend_amount: Decimal) -> AgentLiquidityProfile:
        profile = self._get_profile(agent_id)
        profile.is_lender_eligible = True
        profile.max_lend_amount = max_lend_amount
        self.db.commit()
        self.db.refresh(profile)
        return profile

    # ─────────────────────────────────────────────────────────────────────────
    # FLOAT REQUESTS
    # ─────────────────────────────────────────────────────────────────────────

    def create_float_request(
        self,
        borrower_id: UUID,
        amount: Decimal,
        duration_hours: int,
        max_interest_rate: Optional[Decimal] = None,
        purpose: Optional[str] = None,
    ) -> LiquidityRequest:
        """Agent requests float from the network."""
        if amount < MIN_FLOAT_REQUEST:
            raise ValueError(f"Minimum float request is NGN {MIN_FLOAT_REQUEST:,.2f}")
        if amount > MAX_FLOAT_REQUEST:
            raise ValueError(f"Maximum float request is NGN {MAX_FLOAT_REQUEST:,.2f}")
        if duration_hours > MAX_LOAN_DURATION_DAYS * 24:
            raise ValueError(f"Maximum loan duration is {MAX_LOAN_DURATION_DAYS} days")

        profile = self._get_profile(borrower_id)
        if not profile.is_borrower_eligible:
            raise ValueError("Agent is not eligible to borrow. Check reputation score.")

        # Check for existing active requests
        active = self.db.query(LiquidityRequest).filter(
            and_(
                LiquidityRequest.borrower_id == borrower_id,
                LiquidityRequest.status.in_(["pending", "matched", "active"]),
            )
        ).count()
        if active >= 2:
            raise ValueError("Maximum of 2 active float requests allowed")

        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)  # Request expires in 2 hours if unmatched
        repayment_due = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        request = LiquidityRequest(
            borrower_id=borrower_id,
            amount=amount,
            duration_hours=duration_hours,
            max_interest_rate=max_interest_rate or DEFAULT_INTEREST_RATE,
            purpose=purpose,
            status="pending",
            expires_at=expires_at,
            repayment_due_at=repayment_due,
        )
        self.db.add(request)
        self.db.flush()

        # Attempt auto-matching
        match = self._auto_match(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def create_float_offer(
        self,
        lender_id: UUID,
        amount: Decimal,
        interest_rate: Decimal,
        min_duration_hours: int = 1,
        max_duration_hours: int = 168,
    ) -> LiquidityOffer:
        """Agent offers float to the network."""
        profile = self._get_profile(lender_id)
        if not profile.is_lender_eligible:
            raise ValueError("Agent is not eligible to lend")
        if amount > profile.max_lend_amount:
            raise ValueError(f"Amount exceeds your maximum lending limit of NGN {profile.max_lend_amount:,.2f}")

        offer = LiquidityOffer(
            lender_id=lender_id,
            amount=amount,
            available_amount=amount,
            interest_rate=interest_rate,
            min_duration_hours=min_duration_hours,
            max_duration_hours=max_duration_hours,
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        self.db.add(offer)
        self.db.flush()

        # Try to match with pending requests
        self._match_offer_to_requests(offer)
        self.db.commit()
        self.db.refresh(offer)
        return offer

    # ─────────────────────────────────────────────────────────────────────────
    # MATCHING ENGINE
    # ─────────────────────────────────────────────────────────────────────────

    def _auto_match(self, request: LiquidityRequest) -> Optional[LiquidityMatch]:
        """Find the best available offer for a request."""
        offers = self.db.query(LiquidityOffer).filter(
            and_(
                LiquidityOffer.status == "active",
                LiquidityOffer.available_amount >= request.amount,
                LiquidityOffer.interest_rate <= request.max_interest_rate,
                LiquidityOffer.min_duration_hours <= request.duration_hours,
                LiquidityOffer.max_duration_hours >= request.duration_hours,
                LiquidityOffer.lender_id != request.borrower_id,
                LiquidityOffer.expires_at > datetime.now(timezone.utc),
            )
        ).order_by(LiquidityOffer.interest_rate.asc()).first()

        if not offers:
            return None

        return self._create_match(request, offers)

    def _match_offer_to_requests(self, offer: LiquidityOffer) -> List[LiquidityMatch]:
        """Match a new offer against pending requests."""
        requests = self.db.query(LiquidityRequest).filter(
            and_(
                LiquidityRequest.status == "pending",
                LiquidityRequest.amount <= offer.available_amount,
                LiquidityRequest.max_interest_rate >= offer.interest_rate,
                LiquidityRequest.duration_hours >= offer.min_duration_hours,
                LiquidityRequest.duration_hours <= offer.max_duration_hours,
                LiquidityRequest.borrower_id != offer.lender_id,
                LiquidityRequest.expires_at > datetime.now(timezone.utc),
            )
        ).order_by(LiquidityRequest.amount.desc()).all()

        matches = []
        for req in requests:
            if offer.available_amount < req.amount:
                break
            match = self._create_match(req, offer)
            if match:
                matches.append(match)
        return matches

    def _create_match(self, request: LiquidityRequest, offer: LiquidityOffer) -> LiquidityMatch:
        """Create a match between a request and an offer."""
        interest_amount = request.amount * offer.interest_rate * Decimal(str(request.duration_hours / 24))
        platform_fee = request.amount * MATCHING_FEE_RATE
        total_repayable = request.amount + interest_amount + platform_fee

        match = LiquidityMatch(
            request_id=request.id,
            offer_id=offer.id,
            borrower_id=request.borrower_id,
            lender_id=offer.lender_id,
            matched_amount=request.amount,
            interest_rate=offer.interest_rate,
            interest_amount=interest_amount,
            platform_fee=platform_fee,
            total_repayable=total_repayable,
            status="pending_disbursement",
            matched_at=datetime.now(timezone.utc),
            repayment_due_at=request.repayment_due_at,
        )
        self.db.add(match)

        # Update request and offer status
        request.status = "matched"
        request.matched_offer_id = offer.id
        offer.available_amount -= request.amount
        if offer.available_amount <= 0:
            offer.status = "exhausted"

        self.db.flush()
        logger.info(f"Matched request {request.id} with offer {offer.id} for NGN {request.amount:,.2f}")
        return match

    # ─────────────────────────────────────────────────────────────────────────
    # DISBURSEMENT & REPAYMENT
    # ─────────────────────────────────────────────────────────────────────────

    def confirm_disbursement(self, match_id: UUID, tigerbeetle_transfer_id: str) -> LiquidityMatch:
        """Confirm that float has been disbursed to borrower."""
        match = self._get_match(match_id)
        if match.status != "pending_disbursement":
            raise ValueError(f"Match is in status {match.status}, expected pending_disbursement")

        match.status = "active"
        match.disbursed_at = datetime.now(timezone.utc)
        match.tigerbeetle_transfer_id = tigerbeetle_transfer_id

        # Update request status
        request = self.db.query(LiquidityRequest).filter(LiquidityRequest.id == match.request_id).first()
        if request:
            request.status = "active"

        # Update lender profile
        lender_profile = self._get_profile(match.lender_id)
        lender_profile.total_lent += match.matched_amount

        self.db.commit()
        self.db.refresh(match)
        return match

    def process_repayment(
        self,
        match_id: UUID,
        amount_paid: Decimal,
        payment_reference: str,
    ) -> Tuple[LiquidityRepayment, LiquidityMatch]:
        """Process a repayment from borrower to lender."""
        match = self._get_match(match_id)
        if match.status not in ("active", "overdue"):
            raise ValueError(f"Cannot repay match in status {match.status}")

        repayment = LiquidityRepayment(
            match_id=match_id,
            borrower_id=match.borrower_id,
            lender_id=match.lender_id,
            amount_paid=amount_paid,
            payment_reference=payment_reference,
            paid_at=datetime.now(timezone.utc),
            is_late=(datetime.now(timezone.utc) > match.repayment_due_at),
        )
        self.db.add(repayment)

        # Check if fully repaid
        total_paid = (self.db.query(func.sum(LiquidityRepayment.amount_paid))
                      .filter(LiquidityRepayment.match_id == match_id).scalar() or Decimal("0"))
        total_paid += amount_paid

        if total_paid >= match.total_repayable:
            match.status = "repaid"
            match.repaid_at = datetime.now(timezone.utc)
            # Update request status
            request = self.db.query(LiquidityRequest).filter(LiquidityRequest.id == match.request_id).first()
            if request:
                request.status = "repaid"
            # Update reputation scores
            self._update_reputation_on_repayment(match, repayment.is_late)

        self.db.commit()
        self.db.refresh(repayment)
        self.db.refresh(match)
        return repayment, match

    def _update_reputation_on_repayment(self, match: LiquidityMatch, is_late: bool) -> None:
        borrower_profile = self._get_profile(match.borrower_id)
        if is_late:
            borrower_profile.late_repayments += 1
            borrower_profile.reputation_score = max(
                Decimal("0"), borrower_profile.reputation_score - Decimal("5")
            )
        else:
            borrower_profile.successful_repayments += 1
            borrower_profile.reputation_score = min(
                Decimal("200"), borrower_profile.reputation_score + Decimal("2")
            )
        # Suspend borrowing if reputation drops below 50
        if borrower_profile.reputation_score < Decimal("50"):
            borrower_profile.is_borrower_eligible = False

    # ─────────────────────────────────────────────────────────────────────────
    # QUERIES & ANALYTICS
    # ─────────────────────────────────────────────────────────────────────────

    def get_active_requests(self, limit: int = 50) -> List[LiquidityRequest]:
        return self.db.query(LiquidityRequest).filter(
            and_(
                LiquidityRequest.status == "pending",
                LiquidityRequest.expires_at > datetime.now(timezone.utc),
            )
        ).order_by(LiquidityRequest.amount.desc()).limit(limit).all()

    def get_agent_network_summary(self, agent_id: UUID) -> Dict:
        profile = self._get_profile(agent_id)
        active_loans = self.db.query(LiquidityMatch).filter(
            and_(LiquidityMatch.borrower_id == agent_id, LiquidityMatch.status == "active")
        ).all()
        active_lendings = self.db.query(LiquidityMatch).filter(
            and_(LiquidityMatch.lender_id == agent_id, LiquidityMatch.status == "active")
        ).all()
        return {
            "agent_id": str(agent_id),
            "reputation_score": float(profile.reputation_score),
            "is_lender_eligible": profile.is_lender_eligible,
            "is_borrower_eligible": profile.is_borrower_eligible,
            "max_lend_amount": float(profile.max_lend_amount),
            "max_borrow_amount": float(profile.max_borrow_amount),
            "total_lent": float(profile.total_lent),
            "total_borrowed": float(profile.total_borrowed),
            "successful_repayments": profile.successful_repayments,
            "late_repayments": profile.late_repayments,
            "active_loans_count": len(active_loans),
            "active_loans_amount": float(sum(m.matched_amount for m in active_loans)),
            "active_lendings_count": len(active_lendings),
            "active_lendings_amount": float(sum(m.matched_amount for m in active_lendings)),
        }

    def _get_profile(self, agent_id: UUID) -> AgentLiquidityProfile:
        profile = self.db.query(AgentLiquidityProfile).filter(
            AgentLiquidityProfile.agent_id == agent_id
        ).first()
        if not profile:
            raise ValueError(f"Liquidity profile for agent {agent_id} not found. Please register first.")
        return profile

    def _get_match(self, match_id: UUID) -> LiquidityMatch:
        match = self.db.query(LiquidityMatch).filter(LiquidityMatch.id == match_id).first()
        if not match:
            raise ValueError(f"Match {match_id} not found")
        return match
