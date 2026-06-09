"""
Storefront Advertising & Promotional Tools Service
Enables merchants/agents to create, manage, and track:
- Banner advertisements (storefront header, sidebar, featured)
- Promotional campaigns (discount codes, flash sales, BOGO)
- Product spotlights and featured listings
- Push notification campaigns
- SMS broadcast campaigns
- Social media share cards (auto-generated)
- Loyalty points promotions
- Referral bonus campaigns
- Time-limited offers with countdown timers
- Geographic targeted promotions (by state/LGA)
"""

import os
import json
import hashlib
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Dict, Any
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, DateTime, Date,
    Enum as SAEnum, Text, ForeignKey, Index, func, and_, or_
)
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, HttpUrl, validator
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()


class AdType(str, Enum):
    BANNER = "BANNER"
    FEATURED_PRODUCT = "FEATURED_PRODUCT"
    FLASH_SALE = "FLASH_SALE"
    PUSH_NOTIFICATION = "PUSH_NOTIFICATION"
    SMS_BROADCAST = "SMS_BROADCAST"
    SOCIAL_CARD = "SOCIAL_CARD"
    SPONSORED_LISTING = "SPONSORED_LISTING"
    POPUP = "POPUP"


class PromoType(str, Enum):
    PERCENTAGE_DISCOUNT = "PERCENTAGE_DISCOUNT"
    FIXED_AMOUNT_DISCOUNT = "FIXED_AMOUNT_DISCOUNT"
    BUY_ONE_GET_ONE = "BUY_ONE_GET_ONE"
    FREE_DELIVERY = "FREE_DELIVERY"
    LOYALTY_POINTS_MULTIPLIER = "LOYALTY_POINTS_MULTIPLIER"
    REFERRAL_BONUS = "REFERRAL_BONUS"
    BUNDLE_DEAL = "BUNDLE_DEAL"
    FLASH_SALE = "FLASH_SALE"
    CASHBACK = "CASHBACK"


class AdStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TargetAudience(str, Enum):
    ALL = "ALL"
    NEW_CUSTOMERS = "NEW_CUSTOMERS"
    RETURNING_CUSTOMERS = "RETURNING_CUSTOMERS"
    HIGH_VALUE = "HIGH_VALUE"
    INACTIVE = "INACTIVE"
    BY_LOCATION = "BY_LOCATION"
    BY_AGE_GROUP = "BY_AGE_GROUP"


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class Advertisement(Base):
    __tablename__ = "advertisements"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id = Column(String(100), nullable=False, index=True)
    merchant_name = Column(String(200), nullable=False)
    ad_type = Column(SAEnum(AdType), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    cta_text = Column(String(100), nullable=True)       # Call-to-action text
    cta_url = Column(String(500), nullable=True)        # Call-to-action URL
    target_audience = Column(SAEnum(TargetAudience), default=TargetAudience.ALL)
    target_states = Column(Text, nullable=True)         # JSON array of Nigerian states
    target_lgas = Column(Text, nullable=True)           # JSON array of LGAs
    budget_ngn = Column(Numeric(20, 2), nullable=True)
    cost_per_click_ngn = Column(Numeric(10, 2), nullable=True)
    cost_per_impression_ngn = Column(Numeric(10, 4), nullable=True)
    status = Column(SAEnum(AdStatus), default=AdStatus.DRAFT)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    spend_ngn = Column(Numeric(20, 2), default=Decimal("0"))
    priority = Column(Integer, default=5)               # 1=highest, 10=lowest
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_ad_merchant_status", "merchant_id", "status"),
        Index("ix_ad_dates", "start_date", "end_date"),
    )


class PromoCampaign(Base):
    __tablename__ = "promo_campaigns"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    merchant_id = Column(String(100), nullable=False, index=True)
    merchant_name = Column(String(200), nullable=False)
    promo_type = Column(SAEnum(PromoType), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    promo_code = Column(String(50), nullable=True, unique=True)
    discount_percentage = Column(Numeric(5, 2), nullable=True)
    discount_amount_ngn = Column(Numeric(20, 2), nullable=True)
    cashback_percentage = Column(Numeric(5, 2), nullable=True)
    loyalty_multiplier = Column(Numeric(5, 2), default=Decimal("1.0"))
    referral_bonus_ngn = Column(Numeric(20, 2), nullable=True)
    min_purchase_ngn = Column(Numeric(20, 2), nullable=True)
    max_discount_ngn = Column(Numeric(20, 2), nullable=True)
    applicable_products = Column(Text, nullable=True)   # JSON array of product IDs
    applicable_categories = Column(Text, nullable=True) # JSON array
    max_uses_total = Column(Integer, nullable=True)
    max_uses_per_customer = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    target_audience = Column(SAEnum(TargetAudience), default=TargetAudience.ALL)
    status = Column(SAEnum(AdStatus), default=AdStatus.DRAFT)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_stackable = Column(Boolean, default=False)       # Can be combined with other promos
    terms_conditions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_promo_merchant_status", "merchant_id", "status"),
        Index("ix_promo_code", "promo_code"),
    )


class PromoUsage(Base):
    __tablename__ = "promo_usages"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id = Column(String(36), ForeignKey("promo_campaigns.id"), nullable=False)
    customer_id = Column(String(100), nullable=False)
    transaction_id = Column(String(100), nullable=False)
    discount_applied_ngn = Column(Numeric(20, 2), nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)


class AdImpression(Base):
    __tablename__ = "ad_impressions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ad_id = Column(String(36), ForeignKey("advertisements.id"), nullable=False)
    customer_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    state = Column(String(50), nullable=True)
    lga = Column(String(100), nullable=True)
    clicked = Column(Boolean, default=False)
    converted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────

class AdCreate(BaseModel):
    merchant_id: str
    merchant_name: str
    ad_type: AdType
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    cta_text: Optional[str] = None
    cta_url: Optional[str] = None
    target_audience: TargetAudience = TargetAudience.ALL
    target_states: Optional[List[str]] = None
    target_lgas: Optional[List[str]] = None
    budget_ngn: Optional[Decimal] = None
    cost_per_click_ngn: Optional[Decimal] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    priority: int = Field(5, ge=1, le=10)


class AdResponse(BaseModel):
    id: str
    merchant_id: str
    merchant_name: str
    ad_type: AdType
    title: str
    description: Optional[str]
    image_url: Optional[str]
    cta_text: Optional[str]
    cta_url: Optional[str]
    status: AdStatus
    impressions: int
    clicks: int
    conversions: int
    spend_ngn: Decimal
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PromoCampaignCreate(BaseModel):
    merchant_id: str
    merchant_name: str
    promo_type: PromoType
    name: str
    description: Optional[str] = None
    promo_code: Optional[str] = None
    discount_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_amount_ngn: Optional[Decimal] = None
    cashback_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    loyalty_multiplier: Decimal = Decimal("1.0")
    referral_bonus_ngn: Optional[Decimal] = None
    min_purchase_ngn: Optional[Decimal] = None
    max_discount_ngn: Optional[Decimal] = None
    applicable_products: Optional[List[str]] = None
    applicable_categories: Optional[List[str]] = None
    max_uses_total: Optional[int] = None
    max_uses_per_customer: int = 1
    target_audience: TargetAudience = TargetAudience.ALL
    start_date: datetime
    end_date: datetime
    is_stackable: bool = False
    terms_conditions: Optional[str] = None


class PromoValidationRequest(BaseModel):
    promo_code: str
    customer_id: str
    merchant_id: str
    purchase_amount_ngn: Decimal
    product_ids: Optional[List[str]] = None


class PromoValidationResponse(BaseModel):
    valid: bool
    promo_id: Optional[str]
    promo_type: Optional[str]
    discount_amount_ngn: Decimal
    final_amount_ngn: Decimal
    message: str


class AdMetricsResponse(BaseModel):
    ad_id: str
    title: str
    impressions: int
    clicks: int
    conversions: int
    ctr_pct: float          # Click-through rate
    cvr_pct: float          # Conversion rate
    spend_ngn: Decimal
    cpc_ngn: Optional[Decimal]   # Cost per click
    cpa_ngn: Optional[Decimal]   # Cost per acquisition
    roas: Optional[float]        # Return on ad spend


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────

class StorefrontAdvertisingService:

    def __init__(self, db: Session):
        self.db = db

    def _generate_promo_code(self, merchant_id: str, promo_type: str) -> str:
        base = f"{merchant_id[:4].upper()}{promo_type[:3].upper()}"
        suffix = hashlib.sha256(f"{merchant_id}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:6].upper()
        return f"{base}{suffix}"

    def create_advertisement(self, req: AdCreate) -> Advertisement:
        ad = Advertisement(
            merchant_id=req.merchant_id,
            merchant_name=req.merchant_name,
            ad_type=req.ad_type,
            title=req.title,
            description=req.description,
            image_url=req.image_url,
            cta_text=req.cta_text,
            cta_url=req.cta_url,
            target_audience=req.target_audience,
            target_states=json.dumps(req.target_states or []),
            target_lgas=json.dumps(req.target_lgas or []),
            budget_ngn=req.budget_ngn,
            cost_per_click_ngn=req.cost_per_click_ngn,
            start_date=req.start_date,
            end_date=req.end_date,
            priority=req.priority,
            status=AdStatus.PENDING_APPROVAL,
        )
        self.db.add(ad)
        self.db.commit()
        self.db.refresh(ad)
        logger.info(f"Created advertisement {ad.id} for merchant {req.merchant_id}")
        return ad

    def approve_advertisement(self, ad_id: str) -> Advertisement:
        ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if not ad:
            raise ValueError(f"Advertisement {ad_id} not found")
        ad.status = AdStatus.ACTIVE
        self.db.commit()
        self.db.refresh(ad)
        return ad

    def create_promo_campaign(self, req: PromoCampaignCreate) -> PromoCampaign:
        code = req.promo_code or self._generate_promo_code(req.merchant_id, req.promo_type.value)
        campaign = PromoCampaign(
            merchant_id=req.merchant_id,
            merchant_name=req.merchant_name,
            promo_type=req.promo_type,
            name=req.name,
            description=req.description,
            promo_code=code,
            discount_percentage=req.discount_percentage,
            discount_amount_ngn=req.discount_amount_ngn,
            cashback_percentage=req.cashback_percentage,
            loyalty_multiplier=req.loyalty_multiplier,
            referral_bonus_ngn=req.referral_bonus_ngn,
            min_purchase_ngn=req.min_purchase_ngn,
            max_discount_ngn=req.max_discount_ngn,
            applicable_products=json.dumps(req.applicable_products or []),
            applicable_categories=json.dumps(req.applicable_categories or []),
            max_uses_total=req.max_uses_total,
            max_uses_per_customer=req.max_uses_per_customer,
            target_audience=req.target_audience,
            status=AdStatus.ACTIVE,
            start_date=req.start_date,
            end_date=req.end_date,
            is_stackable=req.is_stackable,
            terms_conditions=req.terms_conditions,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        logger.info(f"Created promo campaign {campaign.id} code={code}")
        return campaign

    def validate_promo_code(self, req: PromoValidationRequest) -> PromoValidationResponse:
        """Validate a promo code and calculate the discount."""
        campaign = (
            self.db.query(PromoCampaign)
            .filter(
                PromoCampaign.promo_code == req.promo_code,
                PromoCampaign.merchant_id == req.merchant_id,
                PromoCampaign.status == AdStatus.ACTIVE,
            )
            .first()
        )

        if not campaign:
            return PromoValidationResponse(
                valid=False, promo_id=None, promo_type=None,
                discount_amount_ngn=Decimal("0"),
                final_amount_ngn=req.purchase_amount_ngn,
                message="Promo code not found or inactive",
            )

        now = datetime.utcnow()
        if now < campaign.start_date or now > campaign.end_date:
            return PromoValidationResponse(
                valid=False, promo_id=campaign.id, promo_type=campaign.promo_type.value,
                discount_amount_ngn=Decimal("0"),
                final_amount_ngn=req.purchase_amount_ngn,
                message="Promo code has expired or not yet started",
            )

        if campaign.max_uses_total and campaign.current_uses >= campaign.max_uses_total:
            return PromoValidationResponse(
                valid=False, promo_id=campaign.id, promo_type=campaign.promo_type.value,
                discount_amount_ngn=Decimal("0"),
                final_amount_ngn=req.purchase_amount_ngn,
                message="Promo code usage limit reached",
            )

        if campaign.min_purchase_ngn and req.purchase_amount_ngn < campaign.min_purchase_ngn:
            return PromoValidationResponse(
                valid=False, promo_id=campaign.id, promo_type=campaign.promo_type.value,
                discount_amount_ngn=Decimal("0"),
                final_amount_ngn=req.purchase_amount_ngn,
                message=f"Minimum purchase of NGN {campaign.min_purchase_ngn} required",
            )

        # Check per-customer usage
        customer_uses = (
            self.db.query(PromoUsage)
            .filter(PromoUsage.campaign_id == campaign.id, PromoUsage.customer_id == req.customer_id)
            .count()
        )
        if customer_uses >= campaign.max_uses_per_customer:
            return PromoValidationResponse(
                valid=False, promo_id=campaign.id, promo_type=campaign.promo_type.value,
                discount_amount_ngn=Decimal("0"),
                final_amount_ngn=req.purchase_amount_ngn,
                message="You have already used this promo code",
            )

        # Calculate discount
        discount = self._calculate_discount(campaign, req.purchase_amount_ngn)
        final_amount = max(req.purchase_amount_ngn - discount, Decimal("0"))

        return PromoValidationResponse(
            valid=True,
            promo_id=campaign.id,
            promo_type=campaign.promo_type.value,
            discount_amount_ngn=discount,
            final_amount_ngn=final_amount,
            message=f"Promo applied: {campaign.name}",
        )

    def _calculate_discount(self, campaign: PromoCampaign, amount: Decimal) -> Decimal:
        if campaign.promo_type == PromoType.PERCENTAGE_DISCOUNT and campaign.discount_percentage:
            discount = (amount * campaign.discount_percentage / 100).quantize(Decimal("0.01"))
            if campaign.max_discount_ngn:
                discount = min(discount, campaign.max_discount_ngn)
            return discount
        if campaign.promo_type == PromoType.FIXED_AMOUNT_DISCOUNT and campaign.discount_amount_ngn:
            return min(campaign.discount_amount_ngn, amount)
        if campaign.promo_type == PromoType.CASHBACK and campaign.cashback_percentage:
            return (amount * campaign.cashback_percentage / 100).quantize(Decimal("0.01"))
        return Decimal("0")

    def apply_promo(self, campaign_id: str, customer_id: str, transaction_id: str, discount_ngn: Decimal):
        """Record promo usage after successful transaction."""
        campaign = self.db.query(PromoCampaign).filter(PromoCampaign.id == campaign_id).first()
        if campaign:
            campaign.current_uses += 1
        usage = PromoUsage(
            campaign_id=campaign_id,
            customer_id=customer_id,
            transaction_id=transaction_id,
            discount_applied_ngn=discount_ngn,
        )
        self.db.add(usage)
        self.db.commit()

    def record_impression(self, ad_id: str, customer_id: Optional[str], session_id: Optional[str],
                          state: Optional[str] = None, lga: Optional[str] = None):
        """Record an ad impression."""
        ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if ad:
            ad.impressions += 1
            if ad.cost_per_impression_ngn:
                ad.spend_ngn += ad.cost_per_impression_ngn
        impression = AdImpression(
            ad_id=ad_id, customer_id=customer_id, session_id=session_id,
            state=state, lga=lga,
        )
        self.db.add(impression)
        self.db.commit()

    def record_click(self, ad_id: str, customer_id: Optional[str] = None):
        """Record an ad click."""
        ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if ad:
            ad.clicks += 1
            if ad.cost_per_click_ngn:
                ad.spend_ngn += ad.cost_per_click_ngn
            # Mark latest impression as clicked
            impression = (
                self.db.query(AdImpression)
                .filter(AdImpression.ad_id == ad_id, AdImpression.customer_id == customer_id)
                .order_by(AdImpression.created_at.desc())
                .first()
            )
            if impression:
                impression.clicked = True
        self.db.commit()

    def get_ad_metrics(self, ad_id: str) -> AdMetricsResponse:
        ad = self.db.query(Advertisement).filter(Advertisement.id == ad_id).first()
        if not ad:
            raise ValueError(f"Advertisement {ad_id} not found")
        ctr = (ad.clicks / ad.impressions * 100) if ad.impressions > 0 else 0.0
        cvr = (ad.conversions / ad.clicks * 100) if ad.clicks > 0 else 0.0
        cpc = (ad.spend_ngn / ad.clicks) if ad.clicks > 0 else None
        cpa = (ad.spend_ngn / ad.conversions) if ad.conversions > 0 else None
        return AdMetricsResponse(
            ad_id=ad.id,
            title=ad.title,
            impressions=ad.impressions,
            clicks=ad.clicks,
            conversions=ad.conversions,
            ctr_pct=round(ctr, 2),
            cvr_pct=round(cvr, 2),
            spend_ngn=ad.spend_ngn,
            cpc_ngn=cpc,
            cpa_ngn=cpa,
            roas=None,
        )

    def get_active_ads(self, merchant_id: Optional[str] = None,
                       state: Optional[str] = None) -> List[Advertisement]:
        """Get all active advertisements, optionally filtered."""
        now = datetime.utcnow()
        q = self.db.query(Advertisement).filter(
            Advertisement.status == AdStatus.ACTIVE,
            or_(Advertisement.start_date == None, Advertisement.start_date <= now),
            or_(Advertisement.end_date == None, Advertisement.end_date >= now),
        )
        if merchant_id:
            q = q.filter(Advertisement.merchant_id == merchant_id)
        return q.order_by(Advertisement.priority).all()

    def get_active_campaigns(self, merchant_id: str) -> List[PromoCampaign]:
        now = datetime.utcnow()
        return (
            self.db.query(PromoCampaign)
            .filter(
                PromoCampaign.merchant_id == merchant_id,
                PromoCampaign.status == AdStatus.ACTIVE,
                PromoCampaign.start_date <= now,
                PromoCampaign.end_date >= now,
            )
            .all()
        )

    def generate_flash_sale(self, merchant_id: str, merchant_name: str,
                             discount_pct: Decimal, duration_hours: int,
                             product_ids: List[str]) -> PromoCampaign:
        """Create a time-limited flash sale campaign."""
        start = datetime.utcnow()
        end = start + timedelta(hours=duration_hours)
        req = PromoCampaignCreate(
            merchant_id=merchant_id,
            merchant_name=merchant_name,
            promo_type=PromoType.FLASH_SALE,
            name=f"Flash Sale {discount_pct}% OFF — {duration_hours}hrs only!",
            description=f"Limited time offer: {discount_pct}% off selected products",
            discount_percentage=discount_pct,
            applicable_products=product_ids,
            start_date=start,
            end_date=end,
            terms_conditions="Valid for selected products only. Cannot be combined with other offers.",
        )
        return self.create_promo_campaign(req)
