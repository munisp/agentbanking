"""
Logistics Service
Shipping carrier integration, route optimization, and tracking
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import uuid
import os
import logging
import math
from pydantic import BaseModel

from inventory_service import get_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class CarrierType(str, Enum):
    FEDEX = "fedex"
    UPS = "ups"
    USPS = "usps"
    DHL = "dhl"
    LOCAL_COURIER = "local_courier"

class ServiceLevel(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    TWO_DAY = "two_day"
    SAME_DAY = "same_day"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ShippingRateRequest(BaseModel):
    origin_address: Dict[str, str]
    destination_address: Dict[str, str]
    weight_kg: Decimal
    dimensions_cm: Optional[Dict[str, Decimal]] = None  # length, width, height
    service_level: Optional[ServiceLevel] = None

class ShippingLabel(BaseModel):
    shipment_id: str
    carrier: CarrierType
    service_level: ServiceLevel

class TrackingUpdate(BaseModel):
    shipment_id: str
    status: str
    location: Optional[str] = None
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

class RouteOptimizationRequest(BaseModel):
    warehouse_id: str
    shipments: List[Dict[str, Any]]  # [{"shipment_id": "...", "address": {...}}]
    vehicle_capacity: Optional[int] = 50
    max_stops: Optional[int] = 20

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Logistics Service",
    description="Shipping carrier integration, route optimization, and tracking",
    version="1.0.0"
)

# ============================================================================
# LOGISTICS MANAGER CLASS
# ============================================================================

class LogisticsManager:
    """Logistics operations management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========================================================================
    # SHIPPING RATE CALCULATION
    # ========================================================================
    
    async def get_shipping_rates(
        self,
        request: ShippingRateRequest
    ) -> List[Dict[str, Any]]:
        """Get shipping rates from multiple carriers"""
        
        # Calculate distance (simplified - in production, use proper geocoding)
        distance_km = self._calculate_distance(
            request.origin_address,
            request.destination_address
        )
        
        # Calculate dimensional weight
        if request.dimensions_cm:
            dim_weight = (
                request.dimensions_cm.get('length', 0) *
                request.dimensions_cm.get('width', 0) *
                request.dimensions_cm.get('height', 0)
            ) / 5000  # Standard divisor
            billable_weight = max(float(request.weight_kg), float(dim_weight))
        else:
            billable_weight = float(request.weight_kg)
        
        # Get rates from carriers (simplified - in production, call actual carrier APIs)
        rates = []
        
        # FedEx rates
        rates.append({
            "carrier": CarrierType.FEDEX.value,
            "service_level": ServiceLevel.STANDARD.value,
            "service_name": "FedEx Ground",
            "cost": self._calculate_rate(billable_weight, distance_km, 1.2),
            "estimated_days": 3 + int(distance_km / 500),
            "currency": "USD"
        })
        
        rates.append({
            "carrier": CarrierType.FEDEX.value,
            "service_level": ServiceLevel.EXPRESS.value,
            "service_name": "FedEx Express",
            "cost": self._calculate_rate(billable_weight, distance_km, 2.5),
            "estimated_days": 2,
            "currency": "USD"
        })
        
        rates.append({
            "carrier": CarrierType.FEDEX.value,
            "service_level": ServiceLevel.OVERNIGHT.value,
            "service_name": "FedEx Overnight",
            "cost": self._calculate_rate(billable_weight, distance_km, 4.0),
            "estimated_days": 1,
            "currency": "USD"
        })
        
        # UPS rates
        rates.append({
            "carrier": CarrierType.UPS.value,
            "service_level": ServiceLevel.STANDARD.value,
            "service_name": "UPS Ground",
            "cost": self._calculate_rate(billable_weight, distance_km, 1.15),
            "estimated_days": 3 + int(distance_km / 500),
            "currency": "USD"
        })
        
        rates.append({
            "carrier": CarrierType.UPS.value,
            "service_level": ServiceLevel.EXPRESS.value,
            "service_name": "UPS 2nd Day Air",
            "cost": self._calculate_rate(billable_weight, distance_km, 2.3),
            "estimated_days": 2,
            "currency": "USD"
        })
        
        # USPS rates (usually cheaper for lighter packages)
        if billable_weight < 30:
            rates.append({
                "carrier": CarrierType.USPS.value,
                "service_level": ServiceLevel.STANDARD.value,
                "service_name": "USPS Priority Mail",
                "cost": self._calculate_rate(billable_weight, distance_km, 0.9),
                "estimated_days": 3,
                "currency": "USD"
            })
        
        # Filter by requested service level if specified
        if request.service_level:
            rates = [r for r in rates if r["service_level"] == request.service_level.value]
        
        # Sort by cost
        rates.sort(key=lambda x: x["cost"])
        
        logger.info(f"Shipping rates calculated: {len(rates)} options, distance={distance_km}km")
        
        return rates
    
    def _calculate_distance(
        self,
        origin: Dict[str, str],
        destination: Dict[str, str]
    ) -> float:
        """Calculate distance between addresses (simplified)"""
        
        # In production, use proper geocoding and distance calculation
        # For now, return a random distance based on zip codes
        
        origin_zip = origin.get('zip', '00000')
        dest_zip = destination.get('zip', '00000')
        
        # Simple heuristic based on zip code difference
        try:
            zip_diff = abs(int(origin_zip[:5]) - int(dest_zip[:5]))
            distance_km = min(zip_diff * 10, 5000)  # Max 5000km
        except:
            distance_km = 500  # Default
        
        return distance_km
    
    def _calculate_rate(
        self,
        weight_kg: float,
        distance_km: float,
        rate_multiplier: float
    ) -> float:
        """Calculate shipping rate"""
        
        # Base rate
        base_rate = 5.00
        
        # Weight component
        weight_rate = weight_kg * 0.50
        
        # Distance component
        distance_rate = (distance_km / 100) * 2.00
        
        # Total rate
        total_rate = (base_rate + weight_rate + distance_rate) * rate_multiplier
        
        return round(total_rate, 2)
    
    # ========================================================================
    # SHIPPING LABEL GENERATION
    # ========================================================================
    
    async def generate_shipping_label(
        self,
        data: ShippingLabel
    ) -> Dict[str, Any]:
        """Generate shipping label"""
        
        # Get shipment details
        shipment = self.db.execute(
            """
            SELECT 
                s.id, s.shipment_number, s.order_id,
                s.shipping_address, s.total_weight_kg,
                w.address AS warehouse_address
            FROM shipments s
            JOIN warehouses w ON s.warehouse_id = w.id
            WHERE s.id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(data.shipment_id)}
        ).first()
        
        if not shipment:
            raise ValueError("Shipment not found")
        
        # Generate tracking number (simplified - in production, get from carrier API)
        tracking_number = self._generate_tracking_number(data.carrier)
        
        # Generate label URL (simplified - in production, get from carrier API)
        label_url = f"https://labels.example.com/{tracking_number}.pdf"
        
        # Update shipment with tracking info
        self.db.execute(
            """
            UPDATE shipments
            SET tracking_number = :tracking_number,
                tracking_url = :tracking_url,
                carrier = :carrier,
                service_level = :service_level,
                status = 'picked',
                updated_at = NOW()
            WHERE id = :shipment_id
            """,
            {
                "shipment_id": uuid.UUID(data.shipment_id),
                "tracking_number": tracking_number,
                "tracking_url": f"https://track.example.com/{tracking_number}",
                "carrier": data.carrier.value,
                "service_level": data.service_level.value
            }
        )
        
        self.db.commit()
        
        logger.info(f"Shipping label generated: {tracking_number}")
        
        return {
            "shipment_id": data.shipment_id,
            "shipment_number": shipment.shipment_number,
            "tracking_number": tracking_number,
            "tracking_url": f"https://track.example.com/{tracking_number}",
            "label_url": label_url,
            "carrier": data.carrier.value,
            "service_level": data.service_level.value,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _generate_tracking_number(self, carrier: CarrierType) -> str:
        """Generate tracking number"""
        
        prefix_map = {
            CarrierType.FEDEX: "FDX",
            CarrierType.UPS: "1Z",
            CarrierType.USPS: "9400",
            CarrierType.DHL: "DHL",
            CarrierType.LOCAL_COURIER: "LC"
        }
        
        prefix = prefix_map.get(carrier, "TRK")
        number = uuid.uuid4().hex[:12].upper()
        
        return f"{prefix}{number}"
    
    # ========================================================================
    # TRACKING
    # ========================================================================
    
    async def update_tracking(
        self,
        data: TrackingUpdate
    ) -> Dict[str, Any]:
        """Update shipment tracking"""
        
        # Update shipment status
        self.db.execute(
            """
            UPDATE shipments
            SET status = :status,
                updated_at = NOW()
            WHERE id = :shipment_id
            """,
            {
                "shipment_id": uuid.UUID(data.shipment_id),
                "status": data.status
            }
        )
        
        # In production, store tracking events in a separate table
        
        self.db.commit()
        
        logger.info(f"Tracking updated: {data.shipment_id}, status={data.status}")
        
        return {
            "shipment_id": data.shipment_id,
            "status": data.status,
            "location": data.location,
            "timestamp": (data.timestamp or datetime.utcnow()).isoformat(),
            "notes": data.notes
        }
    
    async def get_tracking_info(
        self,
        shipment_id: str
    ) -> Dict[str, Any]:
        """Get tracking information"""
        
        shipment = self.db.execute(
            """
            SELECT 
                s.id, s.shipment_number, s.tracking_number, s.tracking_url,
                s.carrier, s.service_level, s.status,
                s.ship_date, s.estimated_delivery_date, s.actual_delivery_date,
                s.shipping_address
            FROM shipments s
            WHERE s.id = :shipment_id
            """,
            {"shipment_id": uuid.UUID(shipment_id)}
        ).first()
        
        if not shipment:
            raise ValueError("Shipment not found")
        
        # In production, fetch real-time tracking from carrier API
        tracking_events = self._generate_tracking_events(shipment.status)
        
        return {
            "shipment_id": str(shipment.id),
            "shipment_number": shipment.shipment_number,
            "tracking_number": shipment.tracking_number,
            "tracking_url": shipment.tracking_url,
            "carrier": shipment.carrier,
            "service_level": shipment.service_level,
            "status": shipment.status,
            "ship_date": shipment.ship_date.isoformat() if shipment.ship_date else None,
            "estimated_delivery_date": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else None,
            "actual_delivery_date": shipment.actual_delivery_date.isoformat() if shipment.actual_delivery_date else None,
            "destination": shipment.shipping_address,
            "tracking_events": tracking_events
        }
    
    def _generate_tracking_events(self, status: str) -> List[Dict[str, Any]]:
        """Generate tracking events based on shipment status"""
        
        events = [
            {
                "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "status": "label_created",
                "location": "Origin Facility",
                "description": "Shipping label created"
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(days=2, hours=2)).isoformat(),
                "status": "picked_up",
                "location": "Origin Facility",
                "description": "Package picked up"
            },
            {
                "timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "status": "in_transit",
                "location": "Regional Hub",
                "description": "In transit"
            }
        ]
        
        if status in ['out_for_delivery', 'delivered']:
            events.append({
                "timestamp": datetime.utcnow().isoformat(),
                "status": "out_for_delivery",
                "location": "Local Facility",
                "description": "Out for delivery"
            })
        
        if status == 'delivered':
            events.append({
                "timestamp": datetime.utcnow().isoformat(),
                "status": "delivered",
                "location": "Destination",
                "description": "Delivered"
            })
        
        return events
    
    # ========================================================================
    # ROUTE OPTIMIZATION
    # ========================================================================
    
    async def optimize_delivery_route(
        self,
        request: RouteOptimizationRequest
    ) -> Dict[str, Any]:
        """Optimize delivery route for multiple shipments"""
        
        # Get warehouse location
        warehouse = self.db.execute(
            """
            SELECT id, name, latitude, longitude
            FROM warehouses
            WHERE id = :warehouse_id
            """,
            {"warehouse_id": uuid.UUID(request.warehouse_id)}
        ).first()
        
        if not warehouse:
            raise ValueError("Warehouse not found")
        
        # In production, use proper route optimization algorithm (TSP, VRP)
        # For now, use a simple nearest-neighbor heuristic
        
        optimized_route = self._nearest_neighbor_route(
            (warehouse.latitude, warehouse.longitude),
            request.shipments
        )
        
        # Calculate route metrics
        total_distance = sum(stop['distance_from_previous'] for stop in optimized_route['stops'])
        estimated_time = total_distance / 40  # Assume 40 km/h average speed
        
        logger.info(f"Route optimized: {len(optimized_route['stops'])} stops, {total_distance:.1f}km")
        
        return {
            "warehouse_id": request.warehouse_id,
            "warehouse_name": warehouse.name,
            "total_stops": len(optimized_route['stops']),
            "total_distance_km": round(total_distance, 2),
            "estimated_time_hours": round(estimated_time, 2),
            "route": optimized_route['stops']
        }
    
    def _nearest_neighbor_route(
        self,
        start_location: Tuple[float, float],
        shipments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple nearest neighbor route optimization"""
        
        current_location = start_location
        remaining_shipments = shipments.copy()
        route_stops = []
        
        while remaining_shipments:
            # Find nearest shipment
            nearest = None
            nearest_distance = float('inf')
            
            for shipment in remaining_shipments:
                address = shipment.get('address', {})
                # Simplified - in production, use proper geocoding
                lat = float(address.get('latitude', 0))
                lon = float(address.get('longitude', 0))
                
                if lat == 0 and lon == 0:
                    # Use random location if not provided
                    lat = start_location[0] + (hash(shipment['shipment_id']) % 100) / 1000
                    lon = start_location[1] + (hash(shipment['shipment_id']) % 100) / 1000
                
                distance = self._haversine_distance(
                    current_location[0], current_location[1],
                    lat, lon
                )
                
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest = shipment
                    nearest_location = (lat, lon)
            
            if nearest:
                route_stops.append({
                    "stop_number": len(route_stops) + 1,
                    "shipment_id": nearest['shipment_id'],
                    "address": nearest.get('address', {}),
                    "distance_from_previous": round(nearest_distance, 2),
                    "estimated_arrival": (
                        datetime.utcnow() + 
                        timedelta(hours=len(route_stops) * 0.5)
                    ).isoformat()
                })
                
                remaining_shipments.remove(nearest)
                current_location = nearest_location
        
        return {"stops": route_stops}
    
    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """Calculate distance between two points using Haversine formula"""
        
        R = 6371  # Earth's radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2
        )
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c
        
        return distance

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/shipping/rates", response_model=List[Dict[str, Any]])
async def get_shipping_rates(
    request: ShippingRateRequest,
    db: Session = Depends(get_db)
):
    """Get shipping rates"""
    manager = LogisticsManager(db)
    return await manager.get_shipping_rates(request)

@app.post("/shipping/label", response_model=Dict[str, Any])
async def generate_shipping_label(
    data: ShippingLabel,
    db: Session = Depends(get_db)
):
    """Generate shipping label"""
    manager = LogisticsManager(db)
    return await manager.generate_shipping_label(data)

@app.post("/tracking/update", response_model=Dict[str, Any])
async def update_tracking(
    data: TrackingUpdate,
    db: Session = Depends(get_db)
):
    """Update tracking"""
    manager = LogisticsManager(db)
    return await manager.update_tracking(data)

@app.get("/tracking/{shipment_id}", response_model=Dict[str, Any])
async def get_tracking_info(
    shipment_id: str,
    db: Session = Depends(get_db)
):
    """Get tracking info"""
    manager = LogisticsManager(db)
    return await manager.get_tracking_info(shipment_id)

@app.post("/route/optimize", response_model=Dict[str, Any])
async def optimize_delivery_route(
    request: RouteOptimizationRequest,
    db: Session = Depends(get_db)
):
    """Optimize delivery route"""
    manager = LogisticsManager(db)
    return await manager.optimize_delivery_route(request)

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "logistics-service",
        "version": "1.0.0"
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

