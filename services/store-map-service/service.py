"""
Interactive Visual Map of Stores Service
Provides geospatial store discovery, real-time agent/merchant location data,
and map rendering metadata for the platform's interactive store map:
- Store/agent location registration and updates
- Nearby store discovery with radius search
- Store clustering for map zoom levels
- Store categories and service filters
- Opening hours and availability status
- Route planning data (distance, estimated travel time)
- Heat maps of transaction density
- State/LGA coverage analytics
- Store ratings and reviews aggregation
"""

import math
import json
from datetime import datetime, time
from decimal import Decimal
from typing import List, Optional, Dict, Tuple
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Text,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()

# Nigeria bounding box
NIGERIA_LAT_MIN, NIGERIA_LAT_MAX = 4.0, 14.0
NIGERIA_LNG_MIN, NIGERIA_LNG_MAX = 2.7, 14.7
EARTH_RADIUS_KM = 6371.0


class StoreType(str, Enum):
    AGENT = "AGENT"
    MERCHANT = "MERCHANT"
    SUPER_AGENT = "SUPER_AGENT"
    AGGREGATOR = "AGGREGATOR"
    POS_TERMINAL = "POS_TERMINAL"
    ATM = "ATM"
    BANK_BRANCH = "BANK_BRANCH"


class StoreStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    TEMPORARILY_CLOSED = "TEMPORARILY_CLOSED"
    COMING_SOON = "COMING_SOON"
    SUSPENDED = "SUSPENDED"


class ServiceType(str, Enum):
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"
    TRANSFER = "TRANSFER"
    BILL_PAYMENT = "BILL_PAYMENT"
    AIRTIME = "AIRTIME"
    ACCOUNT_OPENING = "ACCOUNT_OPENING"
    LOAN = "LOAN"
    INSURANCE = "INSURANCE"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    POS_PAYMENT = "POS_PAYMENT"
    QR_PAYMENT = "QR_PAYMENT"
    NFC_PAYMENT = "NFC_PAYMENT"


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────


class StoreLocation(Base):
    __tablename__ = "store_locations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_id = Column(String(100), nullable=False, unique=True, index=True)
    entity_name = Column(String(200), nullable=False)
    store_type = Column(SAEnum(StoreType), nullable=False)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)
    address = Column(Text, nullable=True)
    street = Column(String(300), nullable=True)
    area = Column(String(200), nullable=True)
    lga = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(50), default="Nigeria")
    postal_code = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    website = Column(String(500), nullable=True)
    services = Column(Text, nullable=True)  # JSON array of ServiceType
    status = Column(SAEnum(StoreStatus), default=StoreStatus.OPEN)
    opening_hours = Column(
        Text, nullable=True
    )  # JSON: {mon: {open: "08:00", close: "18:00"}, ...}
    profile_image_url = Column(String(500), nullable=True)
    banner_image_url = Column(String(500), nullable=True)
    rating = Column(Numeric(3, 2), default=Decimal("0"))
    review_count = Column(Integer, default=0)
    transaction_count_30d = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    float_balance_ngn = Column(Numeric(20, 2), nullable=True)  # Approximate float level
    max_cash_in_ngn = Column(Numeric(20, 2), nullable=True)
    max_cash_out_ngn = Column(Numeric(20, 2), nullable=True)
    last_active_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (
        Index("ix_store_location_coords", "latitude", "longitude"),
        Index("ix_store_location_state_lga", "state", "lga"),
    )


class StoreReview(Base):
    __tablename__ = "store_reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    store_id = Column(String(36), ForeignKey("store_locations.id"), nullable=False)
    customer_id = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    review_text = Column(Text, nullable=True)
    transaction_id = Column(String(100), nullable=True)
    is_verified_purchase = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (Index("ix_review_store", "store_id"),)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────


class StoreLocationCreate(BaseModel):
    entity_id: str
    entity_name: str
    store_type: StoreType
    latitude: float = Field(..., ge=NIGERIA_LAT_MIN, le=NIGERIA_LAT_MAX)
    longitude: float = Field(..., ge=NIGERIA_LNG_MIN, le=NIGERIA_LNG_MAX)
    address: Optional[str] = None
    street: Optional[str] = None
    area: Optional[str] = None
    lga: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    services: Optional[List[ServiceType]] = None
    opening_hours: Optional[Dict[str, Dict[str, str]]] = None
    max_cash_in_ngn: Optional[Decimal] = None
    max_cash_out_ngn: Optional[Decimal] = None


class StoreLocationResponse(BaseModel):
    id: str
    entity_id: str
    entity_name: str
    store_type: StoreType
    latitude: float
    longitude: float
    address: Optional[str]
    lga: Optional[str]
    state: Optional[str]
    services: Optional[List[str]]
    status: StoreStatus
    rating: Decimal
    review_count: int
    is_verified: bool
    is_featured: bool
    distance_km: Optional[float] = None
    profile_image_url: Optional[str]
    phone: Optional[str]
    last_active_at: Optional[datetime]

    class Config:
        from_attributes = True


class NearbySearchRequest(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = Field(5.0, ge=0.1, le=100.0)
    store_types: Optional[List[StoreType]] = None
    services: Optional[List[ServiceType]] = None
    min_rating: Optional[float] = None
    open_now: bool = False
    limit: int = Field(20, ge=1, le=100)


class MapCluster(BaseModel):
    cluster_id: str
    latitude: float
    longitude: float
    store_count: int
    store_types: List[str]
    zoom_level: int


class StoreCoverageStats(BaseModel):
    total_stores: int
    active_stores: int
    states_covered: int
    lgas_covered: int
    by_state: Dict[str, int]
    by_type: Dict[str, int]
    coverage_pct: float


class StoreReviewCreate(BaseModel):
    store_id: str
    customer_id: str
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = None
    transaction_id: Optional[str] = None


# ─────────────────────────────────────────────
# SERVICE CLASS
# ─────────────────────────────────────────────


class StoreMapService:

    def __init__(self, db: Session):
        self.db = db

    def _haversine_km(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """Calculate great-circle distance between two coordinates in km."""
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))

    def _is_open_now(self, store: StoreLocation) -> bool:
        """Check if a store is currently open based on opening hours."""
        if store.status != StoreStatus.OPEN:
            return False
        if not store.opening_hours:
            return True  # Assume 24/7 if no hours specified
        hours = json.loads(store.opening_hours)
        day_name = datetime.utcnow().strftime("%a").lower()
        today = hours.get(day_name, hours.get("default"))
        if not today:
            return False
        now = datetime.utcnow().time()
        try:
            open_t = time.fromisoformat(today.get("open", "00:00"))
            close_t = time.fromisoformat(today.get("close", "23:59"))
            return open_t <= now <= close_t
        except Exception:
            return True

    def register_store(self, req: StoreLocationCreate) -> StoreLocation:
        """Register or update a store location."""
        existing = (
            self.db.query(StoreLocation)
            .filter(StoreLocation.entity_id == req.entity_id)
            .first()
        )
        if existing:
            for field, value in req.dict(exclude_unset=True).items():
                if field == "services" and value:
                    setattr(existing, field, json.dumps([s.value for s in value]))
                elif field == "opening_hours" and value:
                    setattr(existing, field, json.dumps(value))
                else:
                    setattr(existing, field, value)
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        store = StoreLocation(
            entity_id=req.entity_id,
            entity_name=req.entity_name,
            store_type=req.store_type,
            latitude=Decimal(str(req.latitude)),
            longitude=Decimal(str(req.longitude)),
            address=req.address,
            street=req.street,
            area=req.area,
            lga=req.lga,
            state=req.state,
            phone=req.phone,
            services=(
                json.dumps([s.value for s in req.services]) if req.services else None
            ),
            opening_hours=json.dumps(req.opening_hours) if req.opening_hours else None,
            max_cash_in_ngn=req.max_cash_in_ngn,
            max_cash_out_ngn=req.max_cash_out_ngn,
        )
        self.db.add(store)
        self.db.commit()
        self.db.refresh(store)
        logger.info(
            f"Registered store {req.entity_id} at ({req.latitude}, {req.longitude})"
        )
        return store

    def find_nearby_stores(self, req: NearbySearchRequest) -> List[Dict]:
        """
        Find stores within a radius using bounding-box pre-filter + Haversine.
        Uses a bounding box approximation for DB query efficiency.
        """
        # Approximate bounding box (1 degree lat ≈ 111 km)
        lat_delta = req.radius_km / 111.0
        lng_delta = req.radius_km / (111.0 * math.cos(math.radians(req.latitude)))

        q = self.db.query(StoreLocation).filter(
            StoreLocation.latitude.between(
                req.latitude - lat_delta, req.latitude + lat_delta
            ),
            StoreLocation.longitude.between(
                req.longitude - lng_delta, req.longitude + lng_delta
            ),
            StoreLocation.status != StoreStatus.SUSPENDED,
        )

        if req.store_types:
            q = q.filter(StoreLocation.store_type.in_(req.store_types))
        if req.min_rating:
            q = q.filter(StoreLocation.rating >= req.min_rating)

        candidates = q.all()

        # Precise Haversine filter
        results = []
        for store in candidates:
            dist = self._haversine_km(
                req.latitude,
                req.longitude,
                float(store.latitude),
                float(store.longitude),
            )
            if dist <= req.radius_km:
                if req.open_now and not self._is_open_now(store):
                    continue
                if req.services:
                    store_services = json.loads(store.services or "[]")
                    if not any(s.value in store_services for s in req.services):
                        continue
                results.append(
                    {
                        "id": store.id,
                        "entity_id": store.entity_id,
                        "entity_name": store.entity_name,
                        "store_type": store.store_type.value,
                        "latitude": float(store.latitude),
                        "longitude": float(store.longitude),
                        "address": store.address,
                        "lga": store.lga,
                        "state": store.state,
                        "services": json.loads(store.services or "[]"),
                        "status": store.status.value,
                        "rating": float(store.rating),
                        "review_count": store.review_count,
                        "is_verified": store.is_verified,
                        "is_featured": store.is_featured,
                        "distance_km": round(dist, 3),
                        "profile_image_url": store.profile_image_url,
                        "phone": store.phone,
                        "last_active_at": (
                            store.last_active_at.isoformat()
                            if store.last_active_at
                            else None
                        ),
                        "is_open_now": self._is_open_now(store),
                    }
                )

        results.sort(key=lambda x: (not x["is_featured"], x["distance_km"]))
        return results[: req.limit]

    def get_map_clusters(
        self, zoom_level: int, state: Optional[str] = None
    ) -> List[MapCluster]:
        """
        Return store clusters for map rendering at a given zoom level.
        Lower zoom = larger clusters; higher zoom = individual stores.
        """
        q = self.db.query(StoreLocation).filter(
            StoreLocation.status != StoreStatus.SUSPENDED
        )
        if state:
            q = q.filter(StoreLocation.state == state)
        stores = q.all()

        if zoom_level >= 14:
            # Show individual stores
            return [
                MapCluster(
                    cluster_id=s.id,
                    latitude=float(s.latitude),
                    longitude=float(s.longitude),
                    store_count=1,
                    store_types=[s.store_type.value],
                    zoom_level=zoom_level,
                )
                for s in stores
            ]

        # Grid-based clustering
        grid_size = max(0.01, 1.0 / (2 ** (zoom_level - 5)))
        clusters: Dict[Tuple, Dict] = {}
        for s in stores:
            lat_key = round(float(s.latitude) / grid_size) * grid_size
            lng_key = round(float(s.longitude) / grid_size) * grid_size
            key = (lat_key, lng_key)
            if key not in clusters:
                clusters[key] = {"lats": [], "lngs": [], "types": []}
            clusters[key]["lats"].append(float(s.latitude))
            clusters[key]["lngs"].append(float(s.longitude))
            clusters[key]["types"].append(s.store_type.value)

        return [
            MapCluster(
                cluster_id=(
                    hashlib.md5(str(k).encode()).hexdigest()[:8] if True else str(k)
                ),
                latitude=sum(v["lats"]) / len(v["lats"]),
                longitude=sum(v["lngs"]) / len(v["lngs"]),
                store_count=len(v["lats"]),
                store_types=list(set(v["types"])),
                zoom_level=zoom_level,
            )
            for k, v in clusters.items()
        ]

    def get_coverage_stats(self) -> StoreCoverageStats:
        """Get platform-wide store coverage statistics."""
        total = self.db.query(StoreLocation).count()
        active = (
            self.db.query(StoreLocation)
            .filter(StoreLocation.status == StoreStatus.OPEN)
            .count()
        )

        by_state = dict(
            self.db.query(StoreLocation.state, func.count(StoreLocation.id))
            .filter(StoreLocation.state != None)
            .group_by(StoreLocation.state)
            .all()
        )
        by_type = dict(
            self.db.query(StoreLocation.store_type, func.count(StoreLocation.id))
            .group_by(StoreLocation.store_type)
            .all()
        )
        lgas_covered = (
            self.db.query(StoreLocation.lga)
            .filter(StoreLocation.lga != None)
            .distinct()
            .count()
        )

        # Nigeria has 774 LGAs
        coverage_pct = round(lgas_covered / 774 * 100, 2)

        return StoreCoverageStats(
            total_stores=total,
            active_stores=active,
            states_covered=len(by_state),
            lgas_covered=lgas_covered,
            by_state={k: v for k, v in by_state.items() if k},
            by_type={
                k.value if hasattr(k, "value") else k: v for k, v in by_type.items()
            },
            coverage_pct=coverage_pct,
        )

    def add_review(self, req: StoreReviewCreate) -> StoreReview:
        """Add a customer review for a store."""
        review = StoreReview(
            store_id=req.store_id,
            customer_id=req.customer_id,
            rating=req.rating,
            review_text=req.review_text,
            transaction_id=req.transaction_id,
            is_verified_purchase=req.transaction_id is not None,
        )
        self.db.add(review)

        # Update store aggregate rating
        store = (
            self.db.query(StoreLocation)
            .filter(StoreLocation.id == req.store_id)
            .first()
        )
        if store:
            total_rating = float(store.rating) * store.review_count + req.rating
            store.review_count += 1
            store.rating = Decimal(str(round(total_rating / store.review_count, 2)))

        self.db.commit()
        self.db.refresh(review)
        return review

    def update_store_status(self, entity_id: str, status: StoreStatus):
        store = (
            self.db.query(StoreLocation)
            .filter(StoreLocation.entity_id == entity_id)
            .first()
        )
        if store:
            store.status = status
            store.last_active_at = (
                datetime.utcnow()
                if status == StoreStatus.OPEN
                else store.last_active_at
            )
            self.db.commit()

    def get_store(self, entity_id: str) -> Optional[StoreLocation]:
        return (
            self.db.query(StoreLocation)
            .filter(StoreLocation.entity_id == entity_id)
            .first()
        )

    def get_all_stores(
        self,
        state: Optional[str] = None,
        store_type: Optional[StoreType] = None,
        status: Optional[StoreStatus] = None,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Get all stores with optional filters."""
        q = self.db.query(StoreLocation)

        if state:
            q = q.filter(StoreLocation.state == state)
        if store_type:
            q = q.filter(StoreLocation.store_type == store_type)
        if status:
            q = q.filter(StoreLocation.status == status)
        else:
            # By default, exclude suspended stores
            q = q.filter(StoreLocation.status != StoreStatus.SUSPENDED)

        if limit:
            q = q.limit(limit)

        stores = q.all()

        return [
            {
                "id": store.id,
                "entity_id": store.entity_id,
                "entity_name": store.entity_name,
                "store_type": store.store_type.value,
                "latitude": float(store.latitude),
                "longitude": float(store.longitude),
                "address": store.address,
                "street": store.street,
                "area": store.area,
                "lga": store.lga,
                "state": store.state,
                "country": store.country,
                "phone": store.phone,
                "email": store.email,
                "services": json.loads(store.services or "[]"),
                "status": store.status.value,
                "rating": float(store.rating),
                "review_count": store.review_count,
                "is_verified": store.is_verified,
                "is_featured": store.is_featured,
                "profile_image_url": store.profile_image_url,
                "last_active_at": (
                    store.last_active_at.isoformat() if store.last_active_at else None
                ),
            }
            for store in stores
        ]


import hashlib
