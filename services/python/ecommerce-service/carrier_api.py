"""
Carrier API Module
Real carrier API integration replacing production tracking events
"""

import asyncio
import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import httpx

from service_config import get_config, ServiceEndpoints
from circuit_breaker import ResilientHttpClient, circuit_breaker_registry

logger = logging.getLogger(__name__)


class ShipmentStatus(str, Enum):
    """Shipment status"""
    PENDING = "pending"
    LABEL_CREATED = "label_created"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED_DELIVERY = "failed_delivery"
    RETURNED = "returned"
    CANCELLED = "cancelled"


@dataclass
class TrackingEvent:
    """Tracking event from carrier"""
    timestamp: datetime
    status: ShipmentStatus
    location: str
    description: str
    carrier_code: str
    raw_status: str


@dataclass
class ShipmentRate:
    """Shipping rate quote"""
    carrier: str
    service_type: str
    service_name: str
    rate: float
    currency: str
    estimated_days: int
    guaranteed: bool


@dataclass
class ShipmentLabel:
    """Shipping label"""
    tracking_number: str
    carrier: str
    label_url: str
    label_format: str
    rate: float
    currency: str


@dataclass
class Address:
    """Shipping address"""
    name: str
    company: Optional[str]
    street1: str
    street2: Optional[str]
    city: str
    state: str
    postal_code: str
    country: str
    phone: str
    email: Optional[str]


@dataclass
class Package:
    """Package dimensions and weight"""
    weight: float  # kg
    length: float  # cm
    width: float   # cm
    height: float  # cm
    weight_unit: str = "kg"
    dimension_unit: str = "cm"


class CarrierAPI(ABC):
    """Abstract base class for carrier APIs"""
    
    @abstractmethod
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> List[ShipmentRate]:
        """Get shipping rates"""
        pass
    
    @abstractmethod
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_type: str
    ) -> ShipmentLabel:
        """Create shipment and get label"""
        pass
    
    @abstractmethod
    async def track_shipment(self, tracking_number: str) -> List[TrackingEvent]:
        """Get tracking events for shipment"""
        pass
    
    @abstractmethod
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel shipment"""
        pass


class FedExAPI(CarrierAPI):
    """FedEx API integration"""
    
    def __init__(self, api_key: str, api_secret: str, account_number: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_number = account_number
        self.config = get_config()
        self.base_url = self.config.endpoints.fedex_api
        self._client = ResilientHttpClient(
            service_name="fedex",
            base_url=self.base_url,
            timeout=30.0,
            failure_threshold=5,
            recovery_timeout=60
        )
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
    
    async def _get_token(self) -> str:
        """Get OAuth token"""
        if self._token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.api_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self._token = data["access_token"]
            # Token typically valid for 1 hour, refresh at 50 minutes
            from datetime import timedelta
            self._token_expires = datetime.utcnow() + timedelta(minutes=50)
            
            return self._token
    
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> List[ShipmentRate]:
        """Get FedEx shipping rates"""
        token = await self._get_token()
        
        request_body = {
            "accountNumber": {"value": self.account_number},
            "requestedShipment": {
                "shipper": self._format_address(origin),
                "recipient": self._format_address(destination),
                "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                "requestedPackageLineItems": [
                    {
                        "weight": {"units": "KG", "value": pkg.weight},
                        "dimensions": {
                            "length": int(pkg.length),
                            "width": int(pkg.width),
                            "height": int(pkg.height),
                            "units": "CM"
                        }
                    }
                    for pkg in packages
                ]
            }
        }
        
        try:
            response = await self._client.post(
                "/rate/v1/rates/quotes",
                headers={"Authorization": f"Bearer {token}"},
                json=request_body
            )
            
            data = response.json()
            rates = []
            
            for rate_reply in data.get("output", {}).get("rateReplyDetails", []):
                for rate_detail in rate_reply.get("ratedShipmentDetails", []):
                    rates.append(ShipmentRate(
                        carrier="fedex",
                        service_type=rate_reply.get("serviceType", ""),
                        service_name=rate_reply.get("serviceName", ""),
                        rate=float(rate_detail.get("totalNetCharge", 0)),
                        currency=rate_detail.get("currency", "USD"),
                        estimated_days=rate_reply.get("commit", {}).get("transitDays", 0),
                        guaranteed=rate_reply.get("commit", {}).get("guaranteedDelivery", False)
                    ))
            
            return rates
        except Exception as e:
            logger.error(f"FedEx rate request failed: {e}")
            return []
    
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_type: str
    ) -> ShipmentLabel:
        """Create FedEx shipment"""
        token = await self._get_token()
        
        request_body = {
            "accountNumber": {"value": self.account_number},
            "labelResponseOptions": "URL_ONLY",
            "requestedShipment": {
                "shipper": self._format_address(origin),
                "recipients": [self._format_address(destination)],
                "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                "serviceType": service_type,
                "packagingType": "YOUR_PACKAGING",
                "labelSpecification": {
                    "labelFormatType": "COMMON2D",
                    "imageType": "PDF",
                    "labelStockType": "PAPER_4X6"
                },
                "requestedPackageLineItems": [
                    {
                        "weight": {"units": "KG", "value": pkg.weight},
                        "dimensions": {
                            "length": int(pkg.length),
                            "width": int(pkg.width),
                            "height": int(pkg.height),
                            "units": "CM"
                        }
                    }
                    for pkg in packages
                ]
            }
        }
        
        response = await self._client.post(
            "/ship/v1/shipments",
            headers={"Authorization": f"Bearer {token}"},
            json=request_body
        )
        
        data = response.json()
        output = data.get("output", {})
        transaction = output.get("transactionShipments", [{}])[0]
        piece = transaction.get("pieceResponses", [{}])[0]
        
        return ShipmentLabel(
            tracking_number=transaction.get("masterTrackingNumber", ""),
            carrier="fedex",
            label_url=piece.get("packageDocuments", [{}])[0].get("url", ""),
            label_format="PDF",
            rate=float(transaction.get("completedShipmentDetail", {}).get("shipmentRating", {}).get("actualRateType", {}).get("totalNetCharge", 0)),
            currency="USD"
        )
    
    async def track_shipment(self, tracking_number: str) -> List[TrackingEvent]:
        """Track FedEx shipment"""
        token = await self._get_token()
        
        request_body = {
            "trackingInfo": [
                {"trackingNumberInfo": {"trackingNumber": tracking_number}}
            ],
            "includeDetailedScans": True
        }
        
        try:
            response = await self._client.post(
                "/track/v1/trackingnumbers",
                headers={"Authorization": f"Bearer {token}"},
                json=request_body
            )
            
            data = response.json()
            events = []
            
            for result in data.get("output", {}).get("completeTrackResults", []):
                for track_result in result.get("trackResults", []):
                    for scan in track_result.get("scanEvents", []):
                        events.append(TrackingEvent(
                            timestamp=datetime.fromisoformat(scan.get("date", "").replace("Z", "+00:00")),
                            status=self._map_status(scan.get("derivedStatus", "")),
                            location=f"{scan.get('scanLocation', {}).get('city', '')}, {scan.get('scanLocation', {}).get('countryCode', '')}",
                            description=scan.get("eventDescription", ""),
                            carrier_code="fedex",
                            raw_status=scan.get("derivedStatus", "")
                        ))
            
            return sorted(events, key=lambda e: e.timestamp, reverse=True)
        except Exception as e:
            logger.error(f"FedEx tracking failed: {e}")
            return []
    
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel FedEx shipment"""
        token = await self._get_token()
        
        try:
            response = await self._client.put(
                "/ship/v1/shipments/cancel",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "accountNumber": {"value": self.account_number},
                    "trackingNumber": tracking_number
                }
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FedEx cancellation failed: {e}")
            return False
    
    def _format_address(self, addr: Address) -> Dict[str, Any]:
        """Format address for FedEx API"""
        return {
            "contact": {
                "personName": addr.name,
                "companyName": addr.company or "",
                "phoneNumber": addr.phone,
                "emailAddress": addr.email or ""
            },
            "address": {
                "streetLines": [addr.street1, addr.street2] if addr.street2 else [addr.street1],
                "city": addr.city,
                "stateOrProvinceCode": addr.state,
                "postalCode": addr.postal_code,
                "countryCode": addr.country
            }
        }
    
    def _map_status(self, fedex_status: str) -> ShipmentStatus:
        """Map FedEx status to standard status"""
        status_map = {
            "PU": ShipmentStatus.PICKED_UP,
            "IT": ShipmentStatus.IN_TRANSIT,
            "OD": ShipmentStatus.OUT_FOR_DELIVERY,
            "DL": ShipmentStatus.DELIVERED,
            "DE": ShipmentStatus.FAILED_DELIVERY,
            "RS": ShipmentStatus.RETURNED
        }
        return status_map.get(fedex_status, ShipmentStatus.IN_TRANSIT)


class GIGLogisticsAPI(CarrierAPI):
    """GIG Logistics API integration (Nigerian carrier)"""
    
    def __init__(self, api_key: str, merchant_id: str):
        self.api_key = api_key
        self.merchant_id = merchant_id
        self.config = get_config()
        self.base_url = self.config.endpoints.gig_logistics_api
        self._client = ResilientHttpClient(
            service_name="gig-logistics",
            base_url=self.base_url,
            timeout=30.0,
            failure_threshold=5,
            recovery_timeout=60
        )
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Merchant-ID": self.merchant_id,
            "Content-Type": "application/json"
        }
    
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> List[ShipmentRate]:
        """Get GIG Logistics shipping rates"""
        total_weight = sum(pkg.weight for pkg in packages)
        
        request_body = {
            "origin": {
                "city": origin.city,
                "state": origin.state,
                "country": origin.country
            },
            "destination": {
                "city": destination.city,
                "state": destination.state,
                "country": destination.country
            },
            "weight": total_weight,
            "shipmentType": "REGULAR"
        }
        
        try:
            response = await self._client.post(
                "/api/v1/rates",
                headers=self._get_headers(),
                json=request_body
            )
            
            data = response.json()
            rates = []
            
            for rate in data.get("rates", []):
                rates.append(ShipmentRate(
                    carrier="gig_logistics",
                    service_type=rate.get("serviceCode", ""),
                    service_name=rate.get("serviceName", ""),
                    rate=float(rate.get("amount", 0)),
                    currency="NGN",
                    estimated_days=rate.get("estimatedDays", 0),
                    guaranteed=rate.get("guaranteed", False)
                ))
            
            return rates
        except Exception as e:
            logger.error(f"GIG Logistics rate request failed: {e}")
            return []
    
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_type: str
    ) -> ShipmentLabel:
        """Create GIG Logistics shipment"""
        total_weight = sum(pkg.weight for pkg in packages)
        
        request_body = {
            "sender": {
                "name": origin.name,
                "phone": origin.phone,
                "email": origin.email,
                "address": origin.street1,
                "city": origin.city,
                "state": origin.state
            },
            "receiver": {
                "name": destination.name,
                "phone": destination.phone,
                "email": destination.email,
                "address": destination.street1,
                "city": destination.city,
                "state": destination.state
            },
            "weight": total_weight,
            "serviceType": service_type,
            "paymentMethod": "PREPAID",
            "items": [
                {
                    "description": "Package",
                    "quantity": 1,
                    "weight": pkg.weight
                }
                for pkg in packages
            ]
        }
        
        response = await self._client.post(
            "/api/v1/shipments",
            headers=self._get_headers(),
            json=request_body
        )
        
        data = response.json()
        
        return ShipmentLabel(
            tracking_number=data.get("trackingNumber", ""),
            carrier="gig_logistics",
            label_url=data.get("labelUrl", ""),
            label_format="PDF",
            rate=float(data.get("amount", 0)),
            currency="NGN"
        )
    
    async def track_shipment(self, tracking_number: str) -> List[TrackingEvent]:
        """Track GIG Logistics shipment"""
        try:
            response = await self._client.get(
                f"/api/v1/tracking/{tracking_number}",
                headers=self._get_headers()
            )
            
            data = response.json()
            events = []
            
            for event in data.get("events", []):
                events.append(TrackingEvent(
                    timestamp=datetime.fromisoformat(event.get("timestamp", "")),
                    status=self._map_status(event.get("status", "")),
                    location=event.get("location", ""),
                    description=event.get("description", ""),
                    carrier_code="gig_logistics",
                    raw_status=event.get("status", "")
                ))
            
            return sorted(events, key=lambda e: e.timestamp, reverse=True)
        except Exception as e:
            logger.error(f"GIG Logistics tracking failed: {e}")
            return []
    
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel GIG Logistics shipment"""
        try:
            response = await self._client.delete(
                f"/api/v1/shipments/{tracking_number}",
                headers=self._get_headers()
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"GIG Logistics cancellation failed: {e}")
            return False
    
    def _map_status(self, gig_status: str) -> ShipmentStatus:
        """Map GIG status to standard status"""
        status_map = {
            "CREATED": ShipmentStatus.LABEL_CREATED,
            "PICKED_UP": ShipmentStatus.PICKED_UP,
            "IN_TRANSIT": ShipmentStatus.IN_TRANSIT,
            "OUT_FOR_DELIVERY": ShipmentStatus.OUT_FOR_DELIVERY,
            "DELIVERED": ShipmentStatus.DELIVERED,
            "FAILED": ShipmentStatus.FAILED_DELIVERY,
            "RETURNED": ShipmentStatus.RETURNED,
            "CANCELLED": ShipmentStatus.CANCELLED
        }
        return status_map.get(gig_status, ShipmentStatus.IN_TRANSIT)


class CarrierAggregator:
    """
    Aggregates multiple carrier APIs for unified shipping operations
    """
    
    def __init__(self):
        self.carriers: Dict[str, CarrierAPI] = {}
        self._initialized = False
    
    def register_carrier(self, name: str, carrier: CarrierAPI):
        """Register a carrier API"""
        self.carriers[name] = carrier
        logger.info(f"Registered carrier: {name}")
    
    async def get_all_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> List[ShipmentRate]:
        """Get rates from all carriers"""
        all_rates = []
        
        tasks = [
            carrier.get_rates(origin, destination, packages)
            for carrier in self.carriers.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_rates.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Carrier rate request failed: {result}")
        
        # Sort by rate
        return sorted(all_rates, key=lambda r: r.rate)
    
    async def get_cheapest_rate(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> Optional[ShipmentRate]:
        """Get cheapest rate across all carriers"""
        rates = await self.get_all_rates(origin, destination, packages)
        return rates[0] if rates else None
    
    async def get_fastest_rate(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package]
    ) -> Optional[ShipmentRate]:
        """Get fastest rate across all carriers"""
        rates = await self.get_all_rates(origin, destination, packages)
        if not rates:
            return None
        return min(rates, key=lambda r: r.estimated_days)
    
    async def create_shipment(
        self,
        carrier_name: str,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_type: str
    ) -> ShipmentLabel:
        """Create shipment with specific carrier"""
        if carrier_name not in self.carriers:
            raise ValueError(f"Unknown carrier: {carrier_name}")
        
        return await self.carriers[carrier_name].create_shipment(
            origin, destination, packages, service_type
        )
    
    async def track_shipment(
        self,
        carrier_name: str,
        tracking_number: str
    ) -> List[TrackingEvent]:
        """Track shipment with specific carrier"""
        if carrier_name not in self.carriers:
            raise ValueError(f"Unknown carrier: {carrier_name}")
        
        return await self.carriers[carrier_name].track_shipment(tracking_number)
    
    async def cancel_shipment(
        self,
        carrier_name: str,
        tracking_number: str
    ) -> bool:
        """Cancel shipment with specific carrier"""
        if carrier_name not in self.carriers:
            raise ValueError(f"Unknown carrier: {carrier_name}")
        
        return await self.carriers[carrier_name].cancel_shipment(tracking_number)


# Factory function to create configured aggregator
def create_carrier_aggregator() -> CarrierAggregator:
    """Create carrier aggregator with configured carriers"""
    import os
    
    aggregator = CarrierAggregator()
    
    # Register FedEx if configured
    fedex_key = os.getenv("FEDEX_API_KEY")
    fedex_secret = os.getenv("FEDEX_API_SECRET")
    fedex_account = os.getenv("FEDEX_ACCOUNT_NUMBER")
    
    if fedex_key and fedex_secret and fedex_account:
        aggregator.register_carrier(
            "fedex",
            FedExAPI(fedex_key, fedex_secret, fedex_account)
        )
    
    # Register GIG Logistics if configured
    gig_key = os.getenv("GIG_LOGISTICS_API_KEY")
    gig_merchant = os.getenv("GIG_LOGISTICS_MERCHANT_ID")
    
    if gig_key and gig_merchant:
        aggregator.register_carrier(
            "gig_logistics",
            GIGLogisticsAPI(gig_key, gig_merchant)
        )
    
    return aggregator
