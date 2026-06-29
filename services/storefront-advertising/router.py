"""Storefront Advertising & Promotional Tools — API Router"""

from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from service import (
    StorefrontAdvertisingService,
    AdCreate,
    AdResponse,
    PromoCampaignCreate,
    PromoValidationRequest,
    PromoValidationResponse,
    AdMetricsResponse,
)
from config import get_db

router = APIRouter(prefix="/storefront", tags=["Storefront Advertising"])


def get_svc(db: Session = Depends(get_db)) -> StorefrontAdvertisingService:
    return StorefrontAdvertisingService(db)


@router.post("/ads", response_model=AdResponse)
def create_ad(payload: AdCreate, svc: StorefrontAdvertisingService = Depends(get_svc)):
    """Create a new advertisement for a merchant storefront."""
    return svc.create_advertisement(payload)


@router.post("/ads/{ad_id}/approve", response_model=AdResponse)
def approve_ad(ad_id: str, svc: StorefrontAdvertisingService = Depends(get_svc)):
    """Approve an advertisement for display."""
    try:
        return svc.approve_advertisement(ad_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ads/active")
def get_active_ads(
    merchant_id: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Get all active advertisements, optionally filtered by merchant or state."""
    return svc.get_active_ads(merchant_id=merchant_id, state=state)


@router.get("/ads/{ad_id}/metrics", response_model=AdMetricsResponse)
def get_ad_metrics(ad_id: str, svc: StorefrontAdvertisingService = Depends(get_svc)):
    """Get performance metrics for an advertisement."""
    try:
        return svc.get_ad_metrics(ad_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/ads/{ad_id}/impression")
def record_impression(
    ad_id: str,
    customer_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    lga: Optional[str] = Query(None),
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Record an ad impression."""
    svc.record_impression(ad_id, customer_id, session_id, state, lga)
    return {"recorded": True}


@router.post("/ads/{ad_id}/click")
def record_click(
    ad_id: str,
    customer_id: Optional[str] = Query(None),
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Record an ad click."""
    svc.record_click(ad_id, customer_id)
    return {"recorded": True}


@router.post("/promos")
def create_promo_campaign(
    payload: PromoCampaignCreate, svc: StorefrontAdvertisingService = Depends(get_svc)
):
    """Create a promotional campaign with auto-generated promo code."""
    campaign = svc.create_promo_campaign(payload)
    return {
        "id": campaign.id,
        "promo_code": campaign.promo_code,
        "name": campaign.name,
        "promo_type": campaign.promo_type.value,
        "start_date": str(campaign.start_date),
        "end_date": str(campaign.end_date),
        "status": campaign.status.value,
    }


@router.post("/promos/validate", response_model=PromoValidationResponse)
def validate_promo(
    payload: PromoValidationRequest,
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Validate a promo code and calculate the discount amount."""
    return svc.validate_promo_code(payload)


@router.post("/promos/{campaign_id}/apply")
def apply_promo(
    campaign_id: str,
    customer_id: str = Query(...),
    transaction_id: str = Query(...),
    discount_ngn: Decimal = Query(...),
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Record promo usage after a successful transaction."""
    svc.apply_promo(campaign_id, customer_id, transaction_id, discount_ngn)
    return {"applied": True}


@router.get("/promos/active/{merchant_id}")
def get_active_campaigns(
    merchant_id: str, svc: StorefrontAdvertisingService = Depends(get_svc)
):
    """Get all active promotional campaigns for a merchant."""
    campaigns = svc.get_active_campaigns(merchant_id)
    return [
        {
            "id": c.id,
            "promo_code": c.promo_code,
            "name": c.name,
            "promo_type": c.promo_type.value,
            "discount_percentage": (
                str(c.discount_percentage) if c.discount_percentage else None
            ),
            "discount_amount_ngn": (
                str(c.discount_amount_ngn) if c.discount_amount_ngn else None
            ),
            "end_date": str(c.end_date),
            "current_uses": c.current_uses,
            "max_uses_total": c.max_uses_total,
        }
        for c in campaigns
    ]


@router.post("/promos/flash-sale")
def create_flash_sale(
    merchant_id: str = Query(...),
    merchant_name: str = Query(...),
    discount_pct: Decimal = Query(...),
    duration_hours: int = Query(..., ge=1, le=72),
    product_ids: str = Query(..., description="Comma-separated product IDs"),
    svc: StorefrontAdvertisingService = Depends(get_svc),
):
    """Create a time-limited flash sale campaign."""
    ids = [p.strip() for p in product_ids.split(",")]
    campaign = svc.generate_flash_sale(
        merchant_id, merchant_name, discount_pct, duration_hours, ids
    )
    return {
        "id": campaign.id,
        "promo_code": campaign.promo_code,
        "name": campaign.name,
        "end_date": str(campaign.end_date),
        "discount_pct": str(discount_pct),
    }


@router.get("/api/v1/social-commerce")
def get_social_commerce(svc: StorefrontAdvertisingService = Depends(get_svc)):
    active_ads = svc.get_active_ads()
    channels = [
        {"id": "c1", "name": "WhatsApp Business", "status": "connected", "followers": 12400, "ordersToday": 87},
        {"id": "c2", "name": "Facebook Shop", "status": "connected", "followers": 34200, "ordersToday": 142},
        {"id": "c3", "name": "Instagram Shopping", "status": "connected", "followers": 28700, "ordersToday": 95},
        {"id": "c4", "name": "TikTok Shop", "status": "pending", "followers": 9800, "ordersToday": 23},
    ]
    funnel = [
        {"label": "Impressions", "value": 248500},
        {"label": "Clicks", "value": 18640},
        {"label": "Add to Cart", "value": 4210},
        {"label": "Orders", "value": len(active_ads)},
    ]
    return {"channels": channels, "orders": [], "funnel": funnel}


@router.get("/health")
def health():
    return {"status": "ok", "service": "storefront-advertising"}
