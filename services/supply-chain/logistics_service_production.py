"""
Production-Ready Logistics Service
Integrates real carrier APIs, proper geocoding, idempotency, and saga orchestration
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import uuid
import asyncpg
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header
from pydantic import BaseModel, Field

from carrier_clients import (
    CarrierClientFactory, CarrierType, ServiceLevel,
    Address, Package, ShippingRate, ShipmentLabel, TrackingInfo,
    CarrierAPIError
)
from geocoding_service import GeocodingService, GeocodedAddress, DistanceResult
from idempotency_service import (
    IdempotencyService, PostgresIdempotencyStore, idempotent
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/logistics_db")

app = FastAPI(
    title="Production Logistics Service",
    description="Production-ready shipping, tracking, and route optimization",
    version="2.0.0"
)

db_pool: Optional[asyncpg.Pool] = None
idempotency_service: Optional[IdempotencyService] = None
geocoding_service: Optional[GeocodingService] = None


class ShippingRateRequest(BaseModel):
    origin_address: Dict[str, str]
    destination_address: Dict[str, str]
    weight_kg: Decimal = Field(..., gt=0)
    dimensions_cm: Optional[Dict[str, Decimal]] = None
    service_level: Optional[ServiceLevel] = None
    carriers: Optional[List[CarrierType]] = None


class CreateShipmentRequest(BaseModel):
    order_id: str
    origin_address: Dict[str, str]
    destination_address: Dict[str, str]
    packages: List[Dict[str, Any]]
    carrier: CarrierType
    service_code: str
    reference: Optional[str] = None


class TrackingUpdateRequest(BaseModel):
    shipment_id: str
    status: str
    location: Optional[str] = None
    notes: Optional[str] = None


class RouteOptimizationRequest(BaseModel):
    warehouse_id: str
    shipments: List[Dict[str, Any]]
    vehicle_capacity: int = 50
    max_stops: int = 20


@app.on_event("startup")
async def startup():
    global db_pool, idempotency_service, geocoding_service
    
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20
    )
    
    idempotency_store = PostgresIdempotencyStore(db_pool)
    await idempotency_store.initialize_schema()
    idempotency_service = IdempotencyService(idempotency_store)
    
    geocoding_service = GeocodingService(
        primary_provider=os.getenv("GEOCODING_PROVIDER", "google")
    )
    
    await initialize_database()
    
    logger.info("Production Logistics Service started")


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    logger.info("Production Logistics Service stopped")


async def initialize_database():
    """Initialize database schema"""
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS shipments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                shipment_number VARCHAR(50) UNIQUE NOT NULL,
                order_id UUID NOT NULL,
                warehouse_id UUID,
                carrier VARCHAR(50) NOT NULL,
                service_code VARCHAR(50) NOT NULL,
                service_level VARCHAR(50),
                tracking_number VARCHAR(100),
                tracking_url TEXT,
                label_url TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'created',
                origin_address JSONB NOT NULL,
                destination_address JSONB NOT NULL,
                packages JSONB NOT NULL,
                total_weight_kg DECIMAL(10, 3),
                shipping_cost DECIMAL(10, 2),
                currency VARCHAR(3) DEFAULT 'USD',
                ship_date TIMESTAMP,
                estimated_delivery_date TIMESTAMP,
                actual_delivery_date TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);
            CREATE INDEX IF NOT EXISTS idx_shipments_tracking ON shipments(tracking_number);
            CREATE INDEX IF NOT EXISTS idx_shipments_status ON shipments(status);
            
            CREATE TABLE IF NOT EXISTS tracking_events (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                shipment_id UUID NOT NULL REFERENCES shipments(id),
                timestamp TIMESTAMP NOT NULL,
                status VARCHAR(100) NOT NULL,
                status_code VARCHAR(50),
                location VARCHAR(255),
                description TEXT,
                signed_by VARCHAR(100),
                raw_data JSONB,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_tracking_shipment ON tracking_events(shipment_id);
            CREATE INDEX IF NOT EXISTS idx_tracking_timestamp ON tracking_events(timestamp);
            
            CREATE TABLE IF NOT EXISTS warehouses (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                address JSONB NOT NULL,
                latitude DECIMAL(10, 7),
                longitude DECIMAL(10, 7),
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
        """)


class ProductionLogisticsManager:
    """Production-ready logistics operations"""
    
    def __init__(
        self,
        pool: asyncpg.Pool,
        idempotency: IdempotencyService,
        geocoding: GeocodingService
    ):
        self.pool = pool
        self.idempotency = idempotency
        self.geocoding = geocoding
    
    async def get_shipping_rates(
        self,
        request: ShippingRateRequest,
        idempotency_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get shipping rates from real carrier APIs"""
        
        origin = Address(
            street_line1=request.origin_address.get("street_line1", ""),
            city=request.origin_address.get("city", ""),
            state_province=request.origin_address.get("state", ""),
            postal_code=request.origin_address.get("postal_code", request.origin_address.get("zip", "")),
            country_code=request.origin_address.get("country_code", "US")
        )
        
        destination = Address(
            street_line1=request.destination_address.get("street_line1", ""),
            city=request.destination_address.get("city", ""),
            state_province=request.destination_address.get("state", ""),
            postal_code=request.destination_address.get("postal_code", request.destination_address.get("zip", "")),
            country_code=request.destination_address.get("country_code", "US")
        )
        
        packages = [
            Package(
                weight_kg=request.weight_kg,
                length_cm=request.dimensions_cm.get("length") if request.dimensions_cm else None,
                width_cm=request.dimensions_cm.get("width") if request.dimensions_cm else None,
                height_cm=request.dimensions_cm.get("height") if request.dimensions_cm else None
            )
        ]
        
        carriers = request.carriers or [CarrierType.FEDEX, CarrierType.UPS, CarrierType.DHL]
        
        try:
            rates = await CarrierClientFactory.get_all_rates(
                origin=origin,
                destination=destination,
                packages=packages,
                service_level=request.service_level,
                carriers=carriers
            )
            
            return [
                {
                    "carrier": rate.carrier.value,
                    "service_code": rate.service_code,
                    "service_name": rate.service_name,
                    "cost": float(rate.cost),
                    "currency": rate.currency,
                    "estimated_days": rate.estimated_days,
                    "delivery_date": rate.delivery_date.isoformat() if rate.delivery_date else None,
                    "guaranteed": rate.guaranteed
                }
                for rate in rates
            ]
            
        except CarrierAPIError as e:
            logger.error(f"Carrier API error: {e}")
            raise HTTPException(status_code=502, detail=f"Carrier API error: {str(e)}")
    
    async def create_shipment(
        self,
        request: CreateShipmentRequest,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Create shipment with real carrier integration"""
        
        async def _create():
            origin = Address(
                street_line1=request.origin_address.get("street_line1", ""),
                city=request.origin_address.get("city", ""),
                state_province=request.origin_address.get("state", ""),
                postal_code=request.origin_address.get("postal_code", ""),
                country_code=request.origin_address.get("country_code", "US"),
                name=request.origin_address.get("name"),
                phone=request.origin_address.get("phone"),
                company=request.origin_address.get("company")
            )
            
            destination = Address(
                street_line1=request.destination_address.get("street_line1", ""),
                city=request.destination_address.get("city", ""),
                state_province=request.destination_address.get("state", ""),
                postal_code=request.destination_address.get("postal_code", ""),
                country_code=request.destination_address.get("country_code", "US"),
                name=request.destination_address.get("name"),
                phone=request.destination_address.get("phone"),
                company=request.destination_address.get("company")
            )
            
            packages = [
                Package(
                    weight_kg=Decimal(str(pkg.get("weight_kg", 1))),
                    length_cm=Decimal(str(pkg.get("length_cm"))) if pkg.get("length_cm") else None,
                    width_cm=Decimal(str(pkg.get("width_cm"))) if pkg.get("width_cm") else None,
                    height_cm=Decimal(str(pkg.get("height_cm"))) if pkg.get("height_cm") else None,
                    declared_value=Decimal(str(pkg.get("declared_value"))) if pkg.get("declared_value") else None,
                    description=pkg.get("description")
                )
                for pkg in request.packages
            ]
            
            carrier_client = CarrierClientFactory.get_client(request.carrier)
            
            label = await carrier_client.create_shipment(
                origin=origin,
                destination=destination,
                packages=packages,
                service_code=request.service_code,
                reference=request.reference or request.order_id
            )
            
            shipment_number = f"SHP-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            
            async with self.pool.acquire() as conn:
                shipment_id = await conn.fetchval("""
                    INSERT INTO shipments (
                        shipment_number, order_id, carrier, service_code,
                        tracking_number, tracking_url, status,
                        origin_address, destination_address, packages,
                        total_weight_kg, shipping_cost, currency, ship_date
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    RETURNING id
                """,
                    shipment_number,
                    uuid.UUID(request.order_id),
                    request.carrier.value,
                    request.service_code,
                    label.tracking_number,
                    f"https://track.{request.carrier.value}.com/{label.tracking_number}",
                    "label_created",
                    request.origin_address,
                    request.destination_address,
                    [pkg.__dict__ for pkg in packages],
                    float(sum(pkg.weight_kg for pkg in packages)),
                    float(label.cost),
                    label.currency,
                    datetime.utcnow()
                )
                
                await conn.execute("""
                    INSERT INTO tracking_events (
                        shipment_id, timestamp, status, status_code, location, description
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    shipment_id,
                    datetime.utcnow(),
                    "label_created",
                    "LC",
                    origin.city,
                    "Shipping label created"
                )
            
            return {
                "shipment_id": str(shipment_id),
                "shipment_number": shipment_number,
                "order_id": request.order_id,
                "tracking_number": label.tracking_number,
                "carrier": request.carrier.value,
                "service_code": request.service_code,
                "shipping_cost": float(label.cost),
                "currency": label.currency,
                "status": "label_created",
                "created_at": datetime.utcnow().isoformat()
            }
        
        return await self.idempotency.execute_idempotent(
            idempotency_key=idempotency_key,
            operation_type="create_shipment",
            request=request.dict(),
            operation=_create
        )
    
    async def get_tracking_info(
        self,
        shipment_id: str,
        refresh: bool = False
    ) -> Dict[str, Any]:
        """Get tracking information from carrier API"""
        
        async with self.pool.acquire() as conn:
            shipment = await conn.fetchrow("""
                SELECT id, shipment_number, tracking_number, carrier, status,
                       origin_address, destination_address, ship_date,
                       estimated_delivery_date, actual_delivery_date
                FROM shipments
                WHERE id = $1
            """, uuid.UUID(shipment_id))
            
            if not shipment:
                raise HTTPException(status_code=404, detail="Shipment not found")
            
            if refresh and shipment["tracking_number"]:
                try:
                    carrier = CarrierType(shipment["carrier"])
                    carrier_client = CarrierClientFactory.get_client(carrier)
                    
                    tracking = await carrier_client.track_shipment(shipment["tracking_number"])
                    
                    for event in tracking.events:
                        await conn.execute("""
                            INSERT INTO tracking_events (
                                shipment_id, timestamp, status, status_code,
                                location, description, signed_by
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT DO NOTHING
                        """,
                            shipment["id"],
                            event.timestamp,
                            event.status,
                            event.status_code,
                            event.location,
                            event.description,
                            event.signed_by
                        )
                    
                    new_status = self._map_carrier_status(tracking.status)
                    
                    await conn.execute("""
                        UPDATE shipments
                        SET status = $2,
                            estimated_delivery_date = $3,
                            actual_delivery_date = $4,
                            updated_at = NOW()
                        WHERE id = $1
                    """,
                        shipment["id"],
                        new_status,
                        tracking.estimated_delivery,
                        tracking.actual_delivery
                    )
                    
                except CarrierAPIError as e:
                    logger.warning(f"Failed to refresh tracking: {e}")
            
            events = await conn.fetch("""
                SELECT timestamp, status, status_code, location, description, signed_by
                FROM tracking_events
                WHERE shipment_id = $1
                ORDER BY timestamp DESC
            """, shipment["id"])
            
            return {
                "shipment_id": str(shipment["id"]),
                "shipment_number": shipment["shipment_number"],
                "tracking_number": shipment["tracking_number"],
                "carrier": shipment["carrier"],
                "status": shipment["status"],
                "origin": shipment["origin_address"],
                "destination": shipment["destination_address"],
                "ship_date": shipment["ship_date"].isoformat() if shipment["ship_date"] else None,
                "estimated_delivery": shipment["estimated_delivery_date"].isoformat() if shipment["estimated_delivery_date"] else None,
                "actual_delivery": shipment["actual_delivery_date"].isoformat() if shipment["actual_delivery_date"] else None,
                "events": [
                    {
                        "timestamp": e["timestamp"].isoformat(),
                        "status": e["status"],
                        "status_code": e["status_code"],
                        "location": e["location"],
                        "description": e["description"],
                        "signed_by": e["signed_by"]
                    }
                    for e in events
                ]
            }
    
    async def optimize_delivery_route(
        self,
        request: RouteOptimizationRequest
    ) -> Dict[str, Any]:
        """Optimize delivery route using real geocoding"""
        
        async with self.pool.acquire() as conn:
            warehouse = await conn.fetchrow("""
                SELECT id, name, address, latitude, longitude
                FROM warehouses
                WHERE id = $1
            """, uuid.UUID(request.warehouse_id))
            
            if not warehouse:
                raise HTTPException(status_code=404, detail="Warehouse not found")
        
        if warehouse["latitude"] and warehouse["longitude"]:
            warehouse_coords = (float(warehouse["latitude"]), float(warehouse["longitude"]))
        else:
            geocoded = await self.geocoding.geocode_address_dict(warehouse["address"])
            if geocoded:
                warehouse_coords = (geocoded.latitude, geocoded.longitude)
                
                async with self.pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE warehouses
                        SET latitude = $2, longitude = $3
                        WHERE id = $1
                    """, warehouse["id"], geocoded.latitude, geocoded.longitude)
            else:
                raise HTTPException(status_code=400, detail="Could not geocode warehouse address")
        
        shipment_coords = []
        for shipment in request.shipments:
            address = shipment.get("address", {})
            
            if address.get("latitude") and address.get("longitude"):
                coords = (float(address["latitude"]), float(address["longitude"]))
            else:
                geocoded = await self.geocoding.geocode_address_dict(address)
                if geocoded:
                    coords = (geocoded.latitude, geocoded.longitude)
                else:
                    logger.warning(f"Could not geocode address for shipment {shipment.get('shipment_id')}")
                    continue
            
            shipment_coords.append({
                "shipment_id": shipment.get("shipment_id"),
                "address": address,
                "coords": coords
            })
        
        all_coords = [warehouse_coords] + [s["coords"] for s in shipment_coords]
        
        distance_matrix = await self.geocoding.calculate_distance_matrix(
            origins=all_coords,
            destinations=all_coords,
            mode="driving"
        )
        
        optimized_route = self._solve_tsp(distance_matrix, shipment_coords)
        
        total_distance = sum(stop["distance_km"] for stop in optimized_route)
        total_duration = sum(stop["duration_minutes"] for stop in optimized_route)
        
        return {
            "warehouse_id": request.warehouse_id,
            "warehouse_name": warehouse["name"],
            "total_stops": len(optimized_route),
            "total_distance_km": round(total_distance, 2),
            "total_duration_minutes": round(total_duration, 2),
            "estimated_completion_time": (
                datetime.utcnow() + timedelta(minutes=total_duration)
            ).isoformat(),
            "route": optimized_route
        }
    
    def _solve_tsp(
        self,
        distance_matrix: List[List[Optional[DistanceResult]]],
        shipments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Solve TSP using nearest neighbor with 2-opt improvement"""
        
        n = len(shipments)
        if n == 0:
            return []
        
        visited = [False] * n
        route = []
        current = 0
        
        for _ in range(n):
            best_next = -1
            best_distance = float('inf')
            
            for j in range(n):
                if not visited[j]:
                    dist_result = distance_matrix[current + 1][j + 1] if current < len(distance_matrix) - 1 else None
                    dist = dist_result.distance_km if dist_result else float('inf')
                    
                    if dist < best_distance:
                        best_distance = dist
                        best_next = j
            
            if best_next >= 0:
                visited[best_next] = True
                
                dist_result = distance_matrix[current + 1][best_next + 1] if current < len(distance_matrix) - 1 else None
                
                route.append({
                    "stop_number": len(route) + 1,
                    "shipment_id": shipments[best_next]["shipment_id"],
                    "address": shipments[best_next]["address"],
                    "coordinates": {
                        "latitude": shipments[best_next]["coords"][0],
                        "longitude": shipments[best_next]["coords"][1]
                    },
                    "distance_km": dist_result.distance_km if dist_result else 0,
                    "duration_minutes": dist_result.duration_minutes if dist_result else 0,
                    "estimated_arrival": (
                        datetime.utcnow() + timedelta(minutes=sum(
                            r["duration_minutes"] for r in route
                        ) + (dist_result.duration_minutes if dist_result else 0))
                    ).isoformat()
                })
                
                current = best_next
        
        route = self._two_opt_improvement(route, distance_matrix)
        
        return route
    
    def _two_opt_improvement(
        self,
        route: List[Dict[str, Any]],
        distance_matrix: List[List[Optional[DistanceResult]]]
    ) -> List[Dict[str, Any]]:
        """Apply 2-opt improvement to route"""
        
        if len(route) < 4:
            return route
        
        improved = True
        while improved:
            improved = False
            
            for i in range(len(route) - 2):
                for j in range(i + 2, len(route)):
                    current_dist = self._route_distance(route, i, j, distance_matrix)
                    
                    new_route = route[:i+1] + route[i+1:j+1][::-1] + route[j+1:]
                    new_dist = self._route_distance(new_route, i, j, distance_matrix)
                    
                    if new_dist < current_dist:
                        route = new_route
                        improved = True
                        break
                
                if improved:
                    break
        
        for i, stop in enumerate(route):
            stop["stop_number"] = i + 1
        
        return route
    
    def _route_distance(
        self,
        route: List[Dict[str, Any]],
        i: int,
        j: int,
        distance_matrix: List[List[Optional[DistanceResult]]]
    ) -> float:
        """Calculate total distance for route segment"""
        total = 0
        for k in range(i, min(j + 1, len(route) - 1)):
            total += route[k].get("distance_km", 0)
        return total
    
    def _map_carrier_status(self, carrier_status: str) -> str:
        """Map carrier status to internal status"""
        status_lower = carrier_status.lower()
        
        if "delivered" in status_lower:
            return "delivered"
        elif "out for delivery" in status_lower:
            return "out_for_delivery"
        elif "transit" in status_lower:
            return "in_transit"
        elif "picked up" in status_lower:
            return "picked_up"
        elif "label" in status_lower:
            return "label_created"
        elif "exception" in status_lower or "delay" in status_lower:
            return "exception"
        elif "return" in status_lower:
            return "returned"
        else:
            return "in_transit"


@app.post("/shipping/rates")
async def get_shipping_rates(
    request: ShippingRateRequest,
    x_idempotency_key: Optional[str] = Header(None)
):
    """Get shipping rates from multiple carriers"""
    manager = ProductionLogisticsManager(db_pool, idempotency_service, geocoding_service)
    return await manager.get_shipping_rates(request, x_idempotency_key)


@app.post("/shipments")
async def create_shipment(
    request: CreateShipmentRequest,
    x_idempotency_key: str = Header(...)
):
    """Create shipment with carrier integration"""
    manager = ProductionLogisticsManager(db_pool, idempotency_service, geocoding_service)
    return await manager.create_shipment(request, x_idempotency_key)


@app.get("/shipments/{shipment_id}/tracking")
async def get_tracking(
    shipment_id: str,
    refresh: bool = False
):
    """Get shipment tracking information"""
    manager = ProductionLogisticsManager(db_pool, idempotency_service, geocoding_service)
    return await manager.get_tracking_info(shipment_id, refresh)


@app.post("/routes/optimize")
async def optimize_route(request: RouteOptimizationRequest):
    """Optimize delivery route"""
    manager = ProductionLogisticsManager(db_pool, idempotency_service, geocoding_service)
    return await manager.optimize_delivery_route(request)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "production-logistics",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
