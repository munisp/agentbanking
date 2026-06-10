"""Auto-Generated Shareable Links — API Router"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .service import (
    ShareableLinksService, CreateLinkRequest, CreateShopLinkRequest,
    CreateProductLinkRequest, LinkType, ShareableLinkResponse
)
from .config import get_db

router = APIRouter(prefix="/links", tags=["Shareable Links"])


def get_svc(db: Session = Depends(get_db)) -> ShareableLinksService:
    return ShareableLinksService(db)


@router.post("/create", response_model=ShareableLinkResponse)
def create_link(payload: CreateLinkRequest, svc: ShareableLinksService = Depends(get_svc)):
    """Create a custom shareable link with QR code."""
    return svc.create_link(payload)


@router.post("/shop", response_model=ShareableLinkResponse)
def create_shop_link(payload: CreateShopLinkRequest, svc: ShareableLinksService = Depends(get_svc)):
    """Generate a shareable link for an agent/merchant shop storefront."""
    return svc.create_shop_link(payload)


@router.post("/product", response_model=ShareableLinkResponse)
def create_product_link(payload: CreateProductLinkRequest, svc: ShareableLinksService = Depends(get_svc)):
    """Generate a shareable link for a specific product."""
    return svc.create_product_link(payload)


@router.post("/referral/{agent_id}", response_model=ShareableLinkResponse)
def create_referral_link(
    agent_id: str,
    campaign: Optional[str] = Query(None),
    svc: ShareableLinksService = Depends(get_svc)
):
    """Generate an agent referral link for new customer acquisition."""
    return svc.create_referral_link(agent_id, campaign)


@router.get("/resolve/{short_code}")
def resolve_link(
    short_code: str,
    request: Request,
    channel: Optional[str] = Query(None),
    svc: ShareableLinksService = Depends(get_svc)
):
    """Resolve a short code to its destination URL (records click analytics)."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    destination = svc.resolve_link(short_code, ip_address=ip, user_agent=ua, channel=channel)
    if not destination:
        raise HTTPException(status_code=404, detail="Link not found or expired")
    return {"destination_url": destination, "short_code": short_code}


@router.get("/redirect/{short_code}")
def redirect_link(
    short_code: str,
    request: Request,
    channel: Optional[str] = Query(None),
    svc: ShareableLinksService = Depends(get_svc)
):
    """HTTP redirect endpoint — resolves short code and redirects browser."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    destination = svc.resolve_link(short_code, ip_address=ip, user_agent=ua, channel=channel)
    if not destination:
        raise HTTPException(status_code=404, detail="Link not found or expired")
    return RedirectResponse(url=destination, status_code=302)


@router.get("/owner/{owner_id}")
def get_owner_links(
    owner_id: str,
    link_type: Optional[str] = Query(None),
    svc: ShareableLinksService = Depends(get_svc)
):
    """Get all shareable links for an owner (merchant/agent)."""
    lt = LinkType(link_type) if link_type else None
    return svc.get_owner_links(owner_id, lt)


@router.get("/analytics/{link_id}")
def get_link_analytics(link_id: str, svc: ShareableLinksService = Depends(get_svc)):
    """Get detailed click analytics for a shareable link."""
    try:
        return svc.get_link_analytics(link_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{link_id}")
def disable_link(
    link_id: str,
    owner_id: str = Query(...),
    svc: ShareableLinksService = Depends(get_svc)
):
    """Disable a shareable link."""
    success = svc.disable_link(link_id, owner_id)
    if not success:
        raise HTTPException(status_code=404, detail="Link not found or access denied")
    return {"disabled": True, "link_id": link_id}


@router.get("/health")
def health():
    return {"status": "ok", "service": "shareable-links"}
