"""
Auto-Generated Shareable Links Service
Generates, tracks, and manages shareable links for:
- Agent shops/storefronts
- Individual products
- Promotional campaigns
- Agent referral links
- Business cards (digital)

Features:
- Unique short URLs (e.g., 54link.ng/s/ABC123)
- QR code generation for each link
- Click/scan analytics
- UTM parameter injection
- Link expiry management
- Social media preview cards (Open Graph)
- WhatsApp/Telegram share integration
- Deep links for mobile app
"""

import os
import json
import hashlib
import logging
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import uuid4
from enum import Enum

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum as SAEnum, Index, func
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
Base = declarative_base()


class LinkType(str, Enum):
    SHOP = "SHOP"
    PRODUCT = "PRODUCT"
    CAMPAIGN = "CAMPAIGN"
    REFERRAL = "REFERRAL"
    BUSINESS_CARD = "BUSINESS_CARD"
    PAYMENT = "PAYMENT"


class LinkStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class ShareableLink(Base):
    __tablename__ = "shareable_links"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id = Column(String(100), nullable=False, index=True)   # merchant/agent ID
    link_type = Column(SAEnum(LinkType), nullable=False)
    status = Column(SAEnum(LinkStatus), default=LinkStatus.ACTIVE)
    short_code = Column(String(20), nullable=False, unique=True)
    short_url = Column(String(200), nullable=False)
    destination_url = Column(String(500), nullable=False)
    title = Column(String(300), nullable=True)
    description = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    # UTM parameters
    utm_source = Column(String(100), nullable=True)
    utm_medium = Column(String(100), nullable=True)
    utm_campaign = Column(String(100), nullable=True)
    # Analytics
    total_clicks = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    whatsapp_shares = Column(Integer, default=0)
    telegram_shares = Column(Integer, default=0)
    # QR code
    qr_code_base64 = Column(Text, nullable=True)
    # Expiry
    expires_at = Column(DateTime, nullable=True)
    # Metadata
    reference_id = Column(String(100), nullable=True)   # product_id, shop_id, etc.
    metadata = Column(Text, nullable=True)              # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_link_short_code", "short_code"),
        Index("ix_link_owner", "owner_id"),
    )


class LinkClick(Base):
    __tablename__ = "link_clicks"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    link_id = Column(String(36), nullable=False, index=True)
    short_code = Column(String(20), nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    referrer = Column(String(500), nullable=True)
    channel = Column(String(50), nullable=True)   # whatsapp, telegram, direct, etc.
    country = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)
    clicked_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────

class CreateLinkRequest(BaseModel):
    owner_id: str
    link_type: LinkType
    destination_url: str
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    reference_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    expires_in_days: Optional[int] = None
    metadata: Optional[Dict] = None


class CreateShopLinkRequest(BaseModel):
    owner_id: str
    shop_name: str
    shop_description: Optional[str] = None
    shop_logo_url: Optional[str] = None
    location: Optional[str] = None


class CreateProductLinkRequest(BaseModel):
    owner_id: str
    product_id: str
    product_name: str
    product_description: Optional[str] = None
    product_image_url: Optional[str] = None
    price_ngn: Optional[float] = None


class ShareableLinkResponse(BaseModel):
    id: str
    short_code: str
    short_url: str
    destination_url: str
    link_type: str
    title: Optional[str]
    description: Optional[str]
    qr_code_base64: Optional[str]
    whatsapp_share_url: str
    telegram_share_url: str
    total_clicks: int
    created_at: str
    expires_at: Optional[str]


class LinkAnalyticsResponse(BaseModel):
    link_id: str
    short_code: str
    total_clicks: int
    unique_clicks: int
    whatsapp_shares: int
    telegram_shares: int
    clicks_by_day: List[Dict]
    clicks_by_channel: Dict[str, int]
    clicks_by_device: Dict[str, int]


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────

class ShareableLinksService:

    BASE_URL = os.environ.get("PLATFORM_BASE_URL", "https://54link.ng")
    SHORT_URL_BASE = os.environ.get("SHORT_URL_BASE", "https://54link.ng/s")

    def __init__(self, db: Session):
        self.db = db

    def _generate_short_code(self, owner_id: str, reference: str) -> str:
        """Generate a unique 8-character alphanumeric short code."""
        seed = f"{owner_id}{reference}{datetime.utcnow().isoformat()}"
        hash_val = hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
        # Ensure uniqueness
        while self.db.query(ShareableLink).filter(ShareableLink.short_code == hash_val).first():
            seed += "x"
            hash_val = hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
        return hash_val

    def _generate_qr_code(self, url: str) -> str:
        """Generate a QR code for a URL and return as base64 PNG."""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logger.warning(f"QR code generation failed: {e}")
            return ""

    def _build_whatsapp_share_url(self, short_url: str, title: Optional[str]) -> str:
        text = f"{title or 'Check this out'}: {short_url}"
        import urllib.parse
        return f"https://wa.me/?text={urllib.parse.quote(text)}"

    def _build_telegram_share_url(self, short_url: str, title: Optional[str]) -> str:
        import urllib.parse
        text = title or "Check this out"
        return f"https://t.me/share/url?url={urllib.parse.quote(short_url)}&text={urllib.parse.quote(text)}"

    def _to_response(self, link: ShareableLink) -> ShareableLinkResponse:
        return ShareableLinkResponse(
            id=link.id,
            short_code=link.short_code,
            short_url=link.short_url,
            destination_url=link.destination_url,
            link_type=link.link_type.value,
            title=link.title,
            description=link.description,
            qr_code_base64=link.qr_code_base64,
            whatsapp_share_url=self._build_whatsapp_share_url(link.short_url, link.title),
            telegram_share_url=self._build_telegram_share_url(link.short_url, link.title),
            total_clicks=link.total_clicks,
            created_at=str(link.created_at),
            expires_at=str(link.expires_at) if link.expires_at else None,
        )

    def create_link(self, req: CreateLinkRequest) -> ShareableLinkResponse:
        """Create a shareable link with QR code."""
        short_code = self._generate_short_code(req.owner_id, req.destination_url)
        short_url = f"{self.SHORT_URL_BASE}/{short_code}"

        # Build destination URL with UTM params
        dest_url = req.destination_url
        utm_params = []
        if req.utm_source:
            utm_params.append(f"utm_source={req.utm_source}")
        if req.utm_medium:
            utm_params.append(f"utm_medium={req.utm_medium}")
        if req.utm_campaign:
            utm_params.append(f"utm_campaign={req.utm_campaign}")
        if utm_params:
            separator = "&" if "?" in dest_url else "?"
            dest_url = f"{dest_url}{separator}{'&'.join(utm_params)}"

        qr_b64 = self._generate_qr_code(short_url)
        expires_at = None
        if req.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=req.expires_in_days)

        link = ShareableLink(
            owner_id=req.owner_id,
            link_type=req.link_type,
            short_code=short_code,
            short_url=short_url,
            destination_url=dest_url,
            title=req.title,
            description=req.description,
            image_url=req.image_url,
            utm_source=req.utm_source,
            utm_medium=req.utm_medium,
            utm_campaign=req.utm_campaign,
            reference_id=req.reference_id,
            qr_code_base64=qr_b64,
            expires_at=expires_at,
            metadata=json.dumps(req.metadata) if req.metadata else None,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        logger.info(f"Created shareable link {short_code} for owner {req.owner_id}")
        return self._to_response(link)

    def create_shop_link(self, req: CreateShopLinkRequest) -> ShareableLinkResponse:
        """Create a shareable link for an agent/merchant shop."""
        slug = req.shop_name.lower().replace(" ", "-").replace("/", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        destination = f"{self.BASE_URL}/shop/{req.owner_id}/{slug}"
        return self.create_link(CreateLinkRequest(
            owner_id=req.owner_id,
            link_type=LinkType.SHOP,
            destination_url=destination,
            title=req.shop_name,
            description=req.shop_description or f"Shop at {req.shop_name} on 54link",
            image_url=req.shop_logo_url,
            utm_source="share",
            utm_medium="shop_link",
        ))

    def create_product_link(self, req: CreateProductLinkRequest) -> ShareableLinkResponse:
        """Create a shareable link for a specific product."""
        destination = f"{self.BASE_URL}/product/{req.product_id}"
        title = req.product_name
        if req.price_ngn:
            title += f" — ₦{req.price_ngn:,.0f}"
        return self.create_link(CreateLinkRequest(
            owner_id=req.owner_id,
            link_type=LinkType.PRODUCT,
            destination_url=destination,
            title=title,
            description=req.product_description,
            image_url=req.product_image_url,
            reference_id=req.product_id,
            utm_source="share",
            utm_medium="product_link",
        ))

    def create_referral_link(self, agent_id: str, campaign: Optional[str] = None) -> ShareableLinkResponse:
        """Create an agent referral link for new customer acquisition."""
        destination = f"{self.BASE_URL}/join?ref={agent_id}"
        return self.create_link(CreateLinkRequest(
            owner_id=agent_id,
            link_type=LinkType.REFERRAL,
            destination_url=destination,
            title="Join 54link — Nigeria's #1 Agency Banking Platform",
            description="Sign up through my referral link and get started today!",
            utm_source="agent_referral",
            utm_medium="referral",
            utm_campaign=campaign or "agent_referral_2025",
        ))

    def resolve_link(self, short_code: str, ip_address: Optional[str] = None,
                     user_agent: Optional[str] = None, channel: Optional[str] = None) -> Optional[str]:
        """Resolve a short code to its destination URL and record the click."""
        link = self.db.query(ShareableLink).filter(ShareableLink.short_code == short_code).first()
        if not link:
            return None
        if link.status == LinkStatus.DISABLED:
            return None
        if link.expires_at and link.expires_at < datetime.utcnow():
            link.status = LinkStatus.EXPIRED
            self.db.commit()
            return None

        # Record click
        click = LinkClick(
            link_id=link.id,
            short_code=short_code,
            ip_address=ip_address,
            user_agent=user_agent,
            channel=channel or "direct",
        )
        self.db.add(click)

        # Update counters
        link.total_clicks += 1
        if channel == "whatsapp":
            link.whatsapp_shares += 1
        elif channel == "telegram":
            link.telegram_shares += 1

        # Unique clicks (simple IP-based)
        if ip_address:
            existing = (
                self.db.query(LinkClick)
                .filter(LinkClick.link_id == link.id, LinkClick.ip_address == ip_address)
                .count()
            )
            if existing == 1:  # This is the first click from this IP
                link.unique_clicks += 1
        else:
            link.unique_clicks += 1

        self.db.commit()
        return link.destination_url

    def get_link_analytics(self, link_id: str) -> LinkAnalyticsResponse:
        """Get detailed analytics for a shareable link."""
        link = self.db.query(ShareableLink).filter(ShareableLink.id == link_id).first()
        if not link:
            raise ValueError(f"Link {link_id} not found")

        # Clicks by day (last 30 days)
        from sqlalchemy import func, cast, Date as SADate
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_clicks = (
            self.db.query(
                func.date(LinkClick.clicked_at).label("day"),
                func.count(LinkClick.id).label("count"),
            )
            .filter(LinkClick.link_id == link_id, LinkClick.clicked_at >= thirty_days_ago)
            .group_by(func.date(LinkClick.clicked_at))
            .order_by(func.date(LinkClick.clicked_at))
            .all()
        )

        # Clicks by channel
        channel_clicks = (
            self.db.query(LinkClick.channel, func.count(LinkClick.id).label("count"))
            .filter(LinkClick.link_id == link_id)
            .group_by(LinkClick.channel)
            .all()
        )

        # Clicks by device
        device_clicks = (
            self.db.query(LinkClick.device_type, func.count(LinkClick.id).label("count"))
            .filter(LinkClick.link_id == link_id)
            .group_by(LinkClick.device_type)
            .all()
        )

        return LinkAnalyticsResponse(
            link_id=link.id,
            short_code=link.short_code,
            total_clicks=link.total_clicks,
            unique_clicks=link.unique_clicks,
            whatsapp_shares=link.whatsapp_shares,
            telegram_shares=link.telegram_shares,
            clicks_by_day=[{"day": str(r.day), "count": r.count} for r in daily_clicks],
            clicks_by_channel={r.channel or "direct": r.count for r in channel_clicks},
            clicks_by_device={r.device_type or "unknown": r.count for r in device_clicks},
        )

    def get_owner_links(self, owner_id: str, link_type: Optional[LinkType] = None) -> List[ShareableLinkResponse]:
        """Get all shareable links for an owner."""
        q = self.db.query(ShareableLink).filter(ShareableLink.owner_id == owner_id)
        if link_type:
            q = q.filter(ShareableLink.link_type == link_type)
        links = q.order_by(ShareableLink.created_at.desc()).all()
        return [self._to_response(link) for link in links]

    def disable_link(self, link_id: str, owner_id: str) -> bool:
        """Disable a shareable link."""
        link = self.db.query(ShareableLink).filter(
            ShareableLink.id == link_id, ShareableLink.owner_id == owner_id
        ).first()
        if not link:
            return False
        link.status = LinkStatus.DISABLED
        self.db.commit()
        return True
