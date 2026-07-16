"""
Production-Ready Carrier Integration Clients
Provides abstraction layer for real carrier APIs (FedEx, UPS, DHL, USPS)
"""

import os
import logging
import hashlib
import hmac
import base64
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


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


@dataclass
class Address:
    street_line1: str
    city: str
    state_province: str
    postal_code: str
    country_code: str
    street_line2: Optional[str] = None
    company: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_residential: bool = True


@dataclass
class Package:
    weight_kg: Decimal
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    declared_value: Optional[Decimal] = None
    currency: str = "USD"
    description: Optional[str] = None


@dataclass
class ShippingRate:
    carrier: CarrierType
    service_code: str
    service_name: str
    cost: Decimal
    currency: str
    estimated_days: int
    delivery_date: Optional[datetime] = None
    guaranteed: bool = False


@dataclass
class ShipmentLabel:
    tracking_number: str
    label_data: bytes
    label_format: str
    carrier: CarrierType
    service_code: str
    cost: Decimal
    currency: str


@dataclass
class TrackingEvent:
    timestamp: datetime
    status: str
    status_code: str
    location: str
    description: str
    signed_by: Optional[str] = None


@dataclass
class TrackingInfo:
    tracking_number: str
    carrier: CarrierType
    status: str
    estimated_delivery: Optional[datetime]
    actual_delivery: Optional[datetime]
    events: List[TrackingEvent]
    origin: Optional[Address] = None
    destination: Optional[Address] = None


class CarrierAPIError(Exception):
    """Base exception for carrier API errors"""
    def __init__(self, carrier: str, message: str, code: Optional[str] = None):
        self.carrier = carrier
        self.code = code
        super().__init__(f"{carrier}: {message}")


class CarrierClient(ABC):
    """Abstract base class for carrier API clients"""
    
    @abstractmethod
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_level: Optional[ServiceLevel] = None
    ) -> List[ShippingRate]:
        """Get shipping rates from carrier"""
        pass
    
    @abstractmethod
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_code: str,
        reference: Optional[str] = None
    ) -> ShipmentLabel:
        """Create shipment and get label"""
        pass
    
    @abstractmethod
    async def track_shipment(self, tracking_number: str) -> TrackingInfo:
        """Get tracking information"""
        pass
    
    @abstractmethod
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel a shipment"""
        pass
    
    @abstractmethod
    async def validate_address(self, address: Address) -> Dict[str, Any]:
        """Validate and standardize address"""
        pass


class FedExClient(CarrierClient):
    """FedEx API Client using REST API"""
    
    BASE_URL = "https://apis.fedex.com"
    SANDBOX_URL = "https://apis-sandbox.fedex.com"
    
    SERVICE_MAP = {
        ServiceLevel.STANDARD: ["FEDEX_GROUND", "FEDEX_HOME_DELIVERY"],
        ServiceLevel.EXPRESS: ["FEDEX_EXPRESS_SAVER", "FEDEX_2_DAY"],
        ServiceLevel.OVERNIGHT: ["PRIORITY_OVERNIGHT", "STANDARD_OVERNIGHT"],
        ServiceLevel.TWO_DAY: ["FEDEX_2_DAY", "FEDEX_2_DAY_AM"],
        ServiceLevel.SAME_DAY: ["SAME_DAY", "SAME_DAY_CITY"]
    }
    
    def __init__(self):
        self.client_id = os.getenv("FEDEX_CLIENT_ID")
        self.client_secret = os.getenv("FEDEX_CLIENT_SECRET")
        self.account_number = os.getenv("FEDEX_ACCOUNT_NUMBER")
        self.sandbox = os.getenv("FEDEX_SANDBOX", "true").lower() == "true"
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
        self._access_token = None
        self._token_expires = None
    
    async def _get_access_token(self) -> str:
        """Get OAuth access token"""
        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._access_token
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("FedEx", f"Authentication failed: {response.text}")
            
            data = response.json()
            self._access_token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(seconds=data["expires_in"] - 60)
            return self._access_token
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_level: Optional[ServiceLevel] = None
    ) -> List[ShippingRate]:
        """Get FedEx shipping rates"""
        token = await self._get_access_token()
        
        request_body = {
            "accountNumber": {"value": self.account_number},
            "requestedShipment": {
                "shipper": self._format_address(origin),
                "recipient": self._format_address(destination),
                "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                "rateRequestType": ["ACCOUNT", "LIST"],
                "requestedPackageLineItems": [
                    self._format_package(pkg) for pkg in packages
                ]
            }
        }
        
        if service_level and service_level in self.SERVICE_MAP:
            request_body["requestedShipment"]["serviceType"] = self.SERVICE_MAP[service_level][0]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rate/v1/rates/quotes",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-locale": "en_US"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("FedEx", f"Rate request failed: {response.text}")
            
            data = response.json()
            rates = []
            
            for rate_detail in data.get("output", {}).get("rateReplyDetails", []):
                service_type = rate_detail.get("serviceType", "")
                service_name = rate_detail.get("serviceName", service_type)
                
                for rate in rate_detail.get("ratedShipmentDetails", []):
                    total_charge = rate.get("totalNetCharge", 0)
                    currency = rate.get("currency", "USD")
                    
                    delivery_date = None
                    if "deliveryTimestamp" in rate_detail:
                        delivery_date = datetime.fromisoformat(
                            rate_detail["deliveryTimestamp"].replace("Z", "+00:00")
                        )
                    
                    transit_days = rate_detail.get("commit", {}).get("transitDays", {}).get("value", 5)
                    
                    rates.append(ShippingRate(
                        carrier=CarrierType.FEDEX,
                        service_code=service_type,
                        service_name=service_name,
                        cost=Decimal(str(total_charge)),
                        currency=currency,
                        estimated_days=transit_days,
                        delivery_date=delivery_date,
                        guaranteed="GUARANTEED" in service_type.upper()
                    ))
            
            return rates
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_code: str,
        reference: Optional[str] = None
    ) -> ShipmentLabel:
        """Create FedEx shipment and get label"""
        token = await self._get_access_token()
        
        request_body = {
            "labelResponseOptions": "LABEL",
            "requestedShipment": {
                "shipper": self._format_address(origin),
                "recipients": [self._format_address(destination)],
                "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
                "serviceType": service_code,
                "packagingType": "YOUR_PACKAGING",
                "shippingChargesPayment": {
                    "paymentType": "SENDER",
                    "payor": {
                        "responsibleParty": {
                            "accountNumber": {"value": self.account_number}
                        }
                    }
                },
                "labelSpecification": {
                    "labelFormatType": "COMMON2D",
                    "imageType": "PDF",
                    "labelStockType": "PAPER_4X6"
                },
                "requestedPackageLineItems": [
                    self._format_package(pkg) for pkg in packages
                ]
            },
            "accountNumber": {"value": self.account_number}
        }
        
        if reference:
            request_body["requestedShipment"]["shipmentSpecialServices"] = {
                "specialServiceTypes": ["RETURN_SHIPMENT"],
                "returnShipmentDetail": {
                    "returnType": "PRINT_RETURN_LABEL"
                }
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/ship/v1/shipments",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-locale": "en_US"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("FedEx", f"Shipment creation failed: {response.text}")
            
            data = response.json()
            output = data.get("output", {})
            transaction = output.get("transactionShipments", [{}])[0]
            piece = transaction.get("pieceResponses", [{}])[0]
            
            tracking_number = piece.get("trackingNumber", "")
            label_data = base64.b64decode(piece.get("packageDocuments", [{}])[0].get("encodedLabel", ""))
            
            shipment_rating = transaction.get("shipmentRating", {})
            total_charge = shipment_rating.get("totalNetCharge", 0)
            
            return ShipmentLabel(
                tracking_number=tracking_number,
                label_data=label_data,
                label_format="PDF",
                carrier=CarrierType.FEDEX,
                service_code=service_code,
                cost=Decimal(str(total_charge)),
                currency="USD"
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def track_shipment(self, tracking_number: str) -> TrackingInfo:
        """Track FedEx shipment"""
        token = await self._get_access_token()
        
        request_body = {
            "includeDetailedScans": True,
            "trackingInfo": [
                {"trackingNumberInfo": {"trackingNumber": tracking_number}}
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/track/v1/trackingnumbers",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-locale": "en_US"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("FedEx", f"Tracking request failed: {response.text}")
            
            data = response.json()
            track_results = data.get("output", {}).get("completeTrackResults", [{}])[0]
            track_result = track_results.get("trackResults", [{}])[0]
            
            latest_status = track_result.get("latestStatusDetail", {})
            status = latest_status.get("statusByLocale", "Unknown")
            
            events = []
            for scan in track_result.get("scanEvents", []):
                event_time = datetime.fromisoformat(
                    scan.get("date", "").replace("Z", "+00:00")
                ) if scan.get("date") else datetime.utcnow()
                
                location_parts = []
                scan_location = scan.get("scanLocation", {})
                if scan_location.get("city"):
                    location_parts.append(scan_location["city"])
                if scan_location.get("stateOrProvinceCode"):
                    location_parts.append(scan_location["stateOrProvinceCode"])
                if scan_location.get("countryCode"):
                    location_parts.append(scan_location["countryCode"])
                
                events.append(TrackingEvent(
                    timestamp=event_time,
                    status=scan.get("eventType", ""),
                    status_code=scan.get("derivedStatusCode", ""),
                    location=", ".join(location_parts) if location_parts else "Unknown",
                    description=scan.get("eventDescription", ""),
                    signed_by=scan.get("signedForByName")
                ))
            
            estimated_delivery = None
            if track_result.get("estimatedDeliveryTimeWindow"):
                window = track_result["estimatedDeliveryTimeWindow"]
                if window.get("window", {}).get("ends"):
                    estimated_delivery = datetime.fromisoformat(
                        window["window"]["ends"].replace("Z", "+00:00")
                    )
            
            actual_delivery = None
            if latest_status.get("code") == "DL":
                actual_delivery = events[0].timestamp if events else None
            
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=CarrierType.FEDEX,
                status=status,
                estimated_delivery=estimated_delivery,
                actual_delivery=actual_delivery,
                events=events
            )
    
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel FedEx shipment"""
        token = await self._get_access_token()
        
        request_body = {
            "accountNumber": {"value": self.account_number},
            "trackingNumber": tracking_number
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/ship/v1/shipments/cancel",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            return response.status_code == 200
    
    async def validate_address(self, address: Address) -> Dict[str, Any]:
        """Validate address using FedEx Address Validation API"""
        token = await self._get_access_token()
        
        request_body = {
            "addressesToValidate": [{
                "address": {
                    "streetLines": [address.street_line1],
                    "city": address.city,
                    "stateOrProvinceCode": address.state_province,
                    "postalCode": address.postal_code,
                    "countryCode": address.country_code
                }
            }]
        }
        
        if address.street_line2:
            request_body["addressesToValidate"][0]["address"]["streetLines"].append(address.street_line2)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/address/v1/addresses/resolve",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                return {"valid": False, "error": response.text}
            
            data = response.json()
            result = data.get("output", {}).get("resolvedAddresses", [{}])[0]
            
            return {
                "valid": result.get("classification") != "UNKNOWN",
                "residential": result.get("classification") == "RESIDENTIAL",
                "standardized_address": result.get("streetLinesToken", []),
                "city": result.get("city"),
                "state": result.get("stateOrProvinceCode"),
                "postal_code": result.get("postalCode"),
                "country": result.get("countryCode")
            }
    
    def _format_address(self, address: Address) -> Dict[str, Any]:
        """Format address for FedEx API"""
        result = {
            "address": {
                "streetLines": [address.street_line1],
                "city": address.city,
                "stateOrProvinceCode": address.state_province,
                "postalCode": address.postal_code,
                "countryCode": address.country_code,
                "residential": address.is_residential
            }
        }
        
        if address.street_line2:
            result["address"]["streetLines"].append(address.street_line2)
        
        if address.name:
            result["contact"] = {"personName": address.name}
        if address.phone:
            result["contact"] = result.get("contact", {})
            result["contact"]["phoneNumber"] = address.phone
        if address.email:
            result["contact"] = result.get("contact", {})
            result["contact"]["emailAddress"] = address.email
        if address.company:
            result["contact"] = result.get("contact", {})
            result["contact"]["companyName"] = address.company
        
        return result
    
    def _format_package(self, package: Package) -> Dict[str, Any]:
        """Format package for FedEx API"""
        result = {
            "weight": {
                "units": "KG",
                "value": float(package.weight_kg)
            }
        }
        
        if package.length_cm and package.width_cm and package.height_cm:
            result["dimensions"] = {
                "length": int(package.length_cm),
                "width": int(package.width_cm),
                "height": int(package.height_cm),
                "units": "CM"
            }
        
        if package.declared_value:
            result["declaredValue"] = {
                "amount": float(package.declared_value),
                "currency": package.currency
            }
        
        return result


class UPSClient(CarrierClient):
    """UPS API Client using REST API"""
    
    BASE_URL = "https://onlinetools.ups.com/api"
    SANDBOX_URL = "https://wwwcie.ups.com/api"
    
    SERVICE_MAP = {
        ServiceLevel.STANDARD: ["03"],  # UPS Ground
        ServiceLevel.EXPRESS: ["02"],   # UPS 2nd Day Air
        ServiceLevel.OVERNIGHT: ["01"], # UPS Next Day Air
        ServiceLevel.TWO_DAY: ["02"],   # UPS 2nd Day Air
        ServiceLevel.SAME_DAY: ["14"]   # UPS Next Day Air Early
    }
    
    def __init__(self):
        self.client_id = os.getenv("UPS_CLIENT_ID")
        self.client_secret = os.getenv("UPS_CLIENT_SECRET")
        self.account_number = os.getenv("UPS_ACCOUNT_NUMBER")
        self.sandbox = os.getenv("UPS_SANDBOX", "true").lower() == "true"
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
        self._access_token = None
        self._token_expires = None
    
    async def _get_access_token(self) -> str:
        """Get OAuth access token"""
        if self._access_token and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._access_token
        
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/security/v1/oauth/token",
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("UPS", f"Authentication failed: {response.text}")
            
            data = response.json()
            self._access_token = data["access_token"]
            self._token_expires = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600) - 60)
            return self._access_token
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_level: Optional[ServiceLevel] = None
    ) -> List[ShippingRate]:
        """Get UPS shipping rates"""
        token = await self._get_access_token()
        
        request_body = {
            "RateRequest": {
                "Request": {
                    "RequestOption": "Shop" if not service_level else "Rate"
                },
                "Shipment": {
                    "Shipper": self._format_address(origin, include_account=True),
                    "ShipTo": self._format_address(destination),
                    "ShipFrom": self._format_address(origin),
                    "Package": [self._format_package(pkg) for pkg in packages]
                }
            }
        }
        
        if service_level and service_level in self.SERVICE_MAP:
            request_body["RateRequest"]["Shipment"]["Service"] = {
                "Code": self.SERVICE_MAP[service_level][0]
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rating/v1/Shop",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "transId": str(datetime.utcnow().timestamp()),
                    "transactionSrc": "AgentBanking"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("UPS", f"Rate request failed: {response.text}")
            
            data = response.json()
            rates = []
            
            rated_shipments = data.get("RateResponse", {}).get("RatedShipment", [])
            if not isinstance(rated_shipments, list):
                rated_shipments = [rated_shipments]
            
            service_names = {
                "01": "UPS Next Day Air",
                "02": "UPS 2nd Day Air",
                "03": "UPS Ground",
                "12": "UPS 3 Day Select",
                "13": "UPS Next Day Air Saver",
                "14": "UPS Next Day Air Early",
                "59": "UPS 2nd Day Air A.M."
            }
            
            for rated in rated_shipments:
                service_code = rated.get("Service", {}).get("Code", "")
                total_charges = rated.get("TotalCharges", {})
                
                rates.append(ShippingRate(
                    carrier=CarrierType.UPS,
                    service_code=service_code,
                    service_name=service_names.get(service_code, f"UPS Service {service_code}"),
                    cost=Decimal(total_charges.get("MonetaryValue", "0")),
                    currency=total_charges.get("CurrencyCode", "USD"),
                    estimated_days=int(rated.get("GuaranteedDelivery", {}).get("BusinessDaysInTransit", 5)),
                    guaranteed=rated.get("GuaranteedDelivery") is not None
                ))
            
            return rates
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_code: str,
        reference: Optional[str] = None
    ) -> ShipmentLabel:
        """Create UPS shipment and get label"""
        token = await self._get_access_token()
        
        request_body = {
            "ShipmentRequest": {
                "Request": {"RequestOption": "validate"},
                "Shipment": {
                    "Description": "Shipment",
                    "Shipper": self._format_address(origin, include_account=True),
                    "ShipTo": self._format_address(destination),
                    "ShipFrom": self._format_address(origin),
                    "PaymentInformation": {
                        "ShipmentCharge": {
                            "Type": "01",
                            "BillShipper": {
                                "AccountNumber": self.account_number
                            }
                        }
                    },
                    "Service": {"Code": service_code},
                    "Package": [self._format_package(pkg) for pkg in packages]
                },
                "LabelSpecification": {
                    "LabelImageFormat": {"Code": "PDF"},
                    "LabelStockSize": {"Height": "6", "Width": "4"}
                }
            }
        }
        
        if reference:
            request_body["ShipmentRequest"]["Shipment"]["ReferenceNumber"] = {
                "Value": reference
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/shipments/v1/ship",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "transId": str(datetime.utcnow().timestamp()),
                    "transactionSrc": "AgentBanking"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("UPS", f"Shipment creation failed: {response.text}")
            
            data = response.json()
            shipment_results = data.get("ShipmentResponse", {}).get("ShipmentResults", {})
            
            tracking_number = shipment_results.get("ShipmentIdentificationNumber", "")
            package_results = shipment_results.get("PackageResults", {})
            
            label_data = b""
            if package_results.get("ShippingLabel", {}).get("GraphicImage"):
                label_data = base64.b64decode(package_results["ShippingLabel"]["GraphicImage"])
            
            total_charges = shipment_results.get("ShipmentCharges", {}).get("TotalCharges", {})
            
            return ShipmentLabel(
                tracking_number=tracking_number,
                label_data=label_data,
                label_format="PDF",
                carrier=CarrierType.UPS,
                service_code=service_code,
                cost=Decimal(total_charges.get("MonetaryValue", "0")),
                currency=total_charges.get("CurrencyCode", "USD")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def track_shipment(self, tracking_number: str) -> TrackingInfo:
        """Track UPS shipment"""
        token = await self._get_access_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/track/v1/details/{tracking_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "transId": str(datetime.utcnow().timestamp()),
                    "transactionSrc": "AgentBanking"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("UPS", f"Tracking request failed: {response.text}")
            
            data = response.json()
            track_response = data.get("trackResponse", {})
            shipment = track_response.get("shipment", [{}])[0]
            package = shipment.get("package", [{}])[0]
            
            current_status = package.get("currentStatus", {})
            status = current_status.get("description", "Unknown")
            
            events = []
            for activity in package.get("activity", []):
                location = activity.get("location", {}).get("address", {})
                location_str = ", ".join(filter(None, [
                    location.get("city"),
                    location.get("stateProvince"),
                    location.get("country")
                ]))
                
                event_date = activity.get("date", "")
                event_time = activity.get("time", "")
                timestamp = datetime.utcnow()
                if event_date:
                    try:
                        timestamp = datetime.strptime(f"{event_date} {event_time}", "%Y%m%d %H%M%S")
                    except ValueError:
                        pass
                
                events.append(TrackingEvent(
                    timestamp=timestamp,
                    status=activity.get("status", {}).get("type", ""),
                    status_code=activity.get("status", {}).get("code", ""),
                    location=location_str or "Unknown",
                    description=activity.get("status", {}).get("description", ""),
                    signed_by=package.get("deliveryInformation", {}).get("receivedBy")
                ))
            
            delivery_date = package.get("deliveryDate", [{}])[0] if package.get("deliveryDate") else {}
            estimated_delivery = None
            if delivery_date.get("date"):
                try:
                    estimated_delivery = datetime.strptime(delivery_date["date"], "%Y%m%d")
                except ValueError:
                    pass
            
            actual_delivery = None
            if current_status.get("code") == "011":
                actual_delivery = events[0].timestamp if events else None
            
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=CarrierType.UPS,
                status=status,
                estimated_delivery=estimated_delivery,
                actual_delivery=actual_delivery,
                events=events
            )
    
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel UPS shipment"""
        token = await self._get_access_token()
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/shipments/v1/void/cancel/{tracking_number}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "transId": str(datetime.utcnow().timestamp()),
                    "transactionSrc": "AgentBanking"
                }
            )
            
            return response.status_code == 200
    
    async def validate_address(self, address: Address) -> Dict[str, Any]:
        """Validate address using UPS Address Validation API"""
        token = await self._get_access_token()
        
        request_body = {
            "XAVRequest": {
                "AddressKeyFormat": {
                    "AddressLine": [address.street_line1],
                    "PoliticalDivision2": address.city,
                    "PoliticalDivision1": address.state_province,
                    "PostcodePrimaryLow": address.postal_code,
                    "CountryCode": address.country_code
                }
            }
        }
        
        if address.street_line2:
            request_body["XAVRequest"]["AddressKeyFormat"]["AddressLine"].append(address.street_line2)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/addressvalidation/v1/1",
                json=request_body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                return {"valid": False, "error": response.text}
            
            data = response.json()
            xav_response = data.get("XAVResponse", {})
            
            valid_indicator = xav_response.get("ValidAddressIndicator") is not None
            candidate = xav_response.get("Candidate", [{}])[0] if xav_response.get("Candidate") else {}
            address_key = candidate.get("AddressKeyFormat", {})
            
            return {
                "valid": valid_indicator,
                "residential": xav_response.get("AddressClassification", {}).get("Code") == "1",
                "standardized_address": address_key.get("AddressLine", []),
                "city": address_key.get("PoliticalDivision2"),
                "state": address_key.get("PoliticalDivision1"),
                "postal_code": address_key.get("PostcodePrimaryLow"),
                "country": address_key.get("CountryCode")
            }
    
    def _format_address(self, address: Address, include_account: bool = False) -> Dict[str, Any]:
        """Format address for UPS API"""
        result = {
            "Address": {
                "AddressLine": [address.street_line1],
                "City": address.city,
                "StateProvinceCode": address.state_province,
                "PostalCode": address.postal_code,
                "CountryCode": address.country_code
            }
        }
        
        if address.street_line2:
            result["Address"]["AddressLine"].append(address.street_line2)
        
        if address.name:
            result["Name"] = address.name
        if address.phone:
            result["Phone"] = {"Number": address.phone}
        if address.email:
            result["EMailAddress"] = address.email
        if address.company:
            result["AttentionName"] = address.company
        
        if include_account:
            result["ShipperNumber"] = self.account_number
        
        return result
    
    def _format_package(self, package: Package) -> Dict[str, Any]:
        """Format package for UPS API"""
        result = {
            "PackagingType": {"Code": "02"},
            "PackageWeight": {
                "UnitOfMeasurement": {"Code": "KGS"},
                "Weight": str(float(package.weight_kg))
            }
        }
        
        if package.length_cm and package.width_cm and package.height_cm:
            result["Dimensions"] = {
                "UnitOfMeasurement": {"Code": "CM"},
                "Length": str(int(package.length_cm)),
                "Width": str(int(package.width_cm)),
                "Height": str(int(package.height_cm))
            }
        
        if package.declared_value:
            result["PackageServiceOptions"] = {
                "DeclaredValue": {
                    "CurrencyCode": package.currency,
                    "MonetaryValue": str(float(package.declared_value))
                }
            }
        
        return result


class DHLClient(CarrierClient):
    """DHL Express API Client"""
    
    BASE_URL = "https://express.api.dhl.com/mydhlapi"
    SANDBOX_URL = "https://express.api.dhl.com/mydhlapi/test"
    
    SERVICE_MAP = {
        ServiceLevel.STANDARD: ["N"],   # DHL Express Domestic
        ServiceLevel.EXPRESS: ["P"],    # DHL Express Worldwide
        ServiceLevel.OVERNIGHT: ["T"],  # DHL Express 9:00
        ServiceLevel.TWO_DAY: ["Y"],    # DHL Express 12:00
        ServiceLevel.SAME_DAY: ["0"]    # DHL Same Day
    }
    
    def __init__(self):
        self.api_key = os.getenv("DHL_API_KEY")
        self.api_secret = os.getenv("DHL_API_SECRET")
        self.account_number = os.getenv("DHL_ACCOUNT_NUMBER")
        self.sandbox = os.getenv("DHL_SANDBOX", "true").lower() == "true"
        self.base_url = self.SANDBOX_URL if self.sandbox else self.BASE_URL
    
    def _get_auth_header(self) -> str:
        """Get Basic auth header"""
        credentials = base64.b64encode(
            f"{self.api_key}:{self.api_secret}".encode()
        ).decode()
        return f"Basic {credentials}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_level: Optional[ServiceLevel] = None
    ) -> List[ShippingRate]:
        """Get DHL shipping rates"""
        params = {
            "accountNumber": self.account_number,
            "originCountryCode": origin.country_code,
            "originPostalCode": origin.postal_code,
            "originCityName": origin.city,
            "destinationCountryCode": destination.country_code,
            "destinationPostalCode": destination.postal_code,
            "destinationCityName": destination.city,
            "weight": float(sum(pkg.weight_kg for pkg in packages)),
            "length": float(max((pkg.length_cm or 0) for pkg in packages)),
            "width": float(max((pkg.width_cm or 0) for pkg in packages)),
            "height": float(max((pkg.height_cm or 0) for pkg in packages)),
            "plannedShippingDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "isCustomsDeclarable": "false",
            "unitOfMeasurement": "metric"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rates",
                params=params,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("DHL", f"Rate request failed: {response.text}")
            
            data = response.json()
            rates = []
            
            for product in data.get("products", []):
                product_code = product.get("productCode", "")
                
                if service_level and service_level in self.SERVICE_MAP:
                    if product_code not in self.SERVICE_MAP[service_level]:
                        continue
                
                total_price = product.get("totalPrice", [{}])[0]
                delivery_date = None
                if product.get("deliveryCapabilities", {}).get("estimatedDeliveryDateAndTime"):
                    delivery_date = datetime.fromisoformat(
                        product["deliveryCapabilities"]["estimatedDeliveryDateAndTime"].replace("Z", "+00:00")
                    )
                
                rates.append(ShippingRate(
                    carrier=CarrierType.DHL,
                    service_code=product_code,
                    service_name=product.get("productName", f"DHL {product_code}"),
                    cost=Decimal(str(total_price.get("price", 0))),
                    currency=total_price.get("priceCurrency", "USD"),
                    estimated_days=product.get("deliveryCapabilities", {}).get("totalTransitDays", 5),
                    delivery_date=delivery_date
                ))
            
            return rates
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def create_shipment(
        self,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_code: str,
        reference: Optional[str] = None
    ) -> ShipmentLabel:
        """Create DHL shipment and get label"""
        request_body = {
            "plannedShippingDateAndTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S GMT+00:00"),
            "pickup": {"isRequested": False},
            "productCode": service_code,
            "accounts": [{"typeCode": "shipper", "number": self.account_number}],
            "customerDetails": {
                "shipperDetails": self._format_address(origin),
                "receiverDetails": self._format_address(destination)
            },
            "content": {
                "packages": [self._format_package(pkg, i) for i, pkg in enumerate(packages)],
                "isCustomsDeclarable": False,
                "description": "Commercial goods",
                "incoterm": "DAP",
                "unitOfMeasurement": "metric"
            },
            "outputImageProperties": {
                "imageOptions": [{"typeCode": "label", "templateName": "ECOM26_84_001"}],
                "splitTransportAndWaybillDocLabels": True
            }
        }
        
        if reference:
            request_body["customerReferences"] = [{"value": reference, "typeCode": "CU"}]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/shipments",
                json=request_body,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code not in [200, 201]:
                raise CarrierAPIError("DHL", f"Shipment creation failed: {response.text}")
            
            data = response.json()
            
            tracking_number = data.get("shipmentTrackingNumber", "")
            label_data = b""
            
            for doc in data.get("documents", []):
                if doc.get("typeCode") == "label":
                    label_data = base64.b64decode(doc.get("content", ""))
                    break
            
            total_price = data.get("shipmentCharges", [{}])[0]
            
            return ShipmentLabel(
                tracking_number=tracking_number,
                label_data=label_data,
                label_format="PDF",
                carrier=CarrierType.DHL,
                service_code=service_code,
                cost=Decimal(str(total_price.get("price", 0))),
                currency=total_price.get("priceCurrency", "USD")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def track_shipment(self, tracking_number: str) -> TrackingInfo:
        """Track DHL shipment"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/shipments/{tracking_number}/tracking",
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise CarrierAPIError("DHL", f"Tracking request failed: {response.text}")
            
            data = response.json()
            shipments = data.get("shipments", [{}])
            shipment = shipments[0] if shipments else {}
            
            status = shipment.get("status", {}).get("status", "Unknown")
            
            events = []
            for event in shipment.get("events", []):
                event_time = datetime.fromisoformat(
                    event.get("timestamp", "").replace("Z", "+00:00")
                ) if event.get("timestamp") else datetime.utcnow()
                
                location = event.get("location", {}).get("address", {})
                location_str = ", ".join(filter(None, [
                    location.get("addressLocality"),
                    location.get("countryCode")
                ]))
                
                events.append(TrackingEvent(
                    timestamp=event_time,
                    status=event.get("statusCode", ""),
                    status_code=event.get("statusCode", ""),
                    location=location_str or "Unknown",
                    description=event.get("description", ""),
                    signed_by=shipment.get("receiverDetails", {}).get("signedBy")
                ))
            
            estimated_delivery = None
            if shipment.get("estimatedDeliveryDate"):
                estimated_delivery = datetime.fromisoformat(
                    shipment["estimatedDeliveryDate"].replace("Z", "+00:00")
                )
            
            actual_delivery = None
            if status == "delivered":
                actual_delivery = events[0].timestamp if events else None
            
            return TrackingInfo(
                tracking_number=tracking_number,
                carrier=CarrierType.DHL,
                status=status,
                estimated_delivery=estimated_delivery,
                actual_delivery=actual_delivery,
                events=events
            )
    
    async def cancel_shipment(self, tracking_number: str) -> bool:
        """Cancel DHL shipment"""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/shipments/{tracking_number}",
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json"
                }
            )
            
            return response.status_code in [200, 204]
    
    async def validate_address(self, address: Address) -> Dict[str, Any]:
        """Validate address using DHL Address Validation"""
        params = {
            "countryCode": address.country_code,
            "postalCode": address.postal_code,
            "cityName": address.city
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/address-validate",
                params=params,
                headers={
                    "Authorization": self._get_auth_header(),
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                return {"valid": False, "error": response.text}
            
            data = response.json()
            
            return {
                "valid": len(data.get("address", [])) > 0,
                "suggestions": data.get("address", [])
            }
    
    def _format_address(self, address: Address) -> Dict[str, Any]:
        """Format address for DHL API"""
        result = {
            "postalAddress": {
                "postalCode": address.postal_code,
                "cityName": address.city,
                "countryCode": address.country_code,
                "addressLine1": address.street_line1
            },
            "contactInformation": {}
        }
        
        if address.state_province:
            result["postalAddress"]["provinceCode"] = address.state_province
        if address.street_line2:
            result["postalAddress"]["addressLine2"] = address.street_line2
        if address.name:
            result["contactInformation"]["fullName"] = address.name
        if address.phone:
            result["contactInformation"]["phone"] = address.phone
        if address.email:
            result["contactInformation"]["email"] = address.email
        if address.company:
            result["contactInformation"]["companyName"] = address.company
        
        return result
    
    def _format_package(self, package: Package, index: int = 0) -> Dict[str, Any]:
        """Format package for DHL API"""
        result = {
            "weight": float(package.weight_kg),
            "dimensions": {
                "length": int(package.length_cm or 10),
                "width": int(package.width_cm or 10),
                "height": int(package.height_cm or 10)
            }
        }
        
        if package.description:
            result["description"] = package.description
        
        return result


class CarrierClientFactory:
    """Factory for creating carrier clients"""
    
    _clients: Dict[CarrierType, CarrierClient] = {}
    
    @classmethod
    def get_client(cls, carrier: CarrierType) -> CarrierClient:
        """Get or create carrier client"""
        if carrier not in cls._clients:
            if carrier == CarrierType.FEDEX:
                cls._clients[carrier] = FedExClient()
            elif carrier == CarrierType.UPS:
                cls._clients[carrier] = UPSClient()
            elif carrier == CarrierType.DHL:
                cls._clients[carrier] = DHLClient()
            else:
                raise ValueError(f"Unsupported carrier: {carrier}")
        
        return cls._clients[carrier]
    
    @classmethod
    async def get_all_rates(
        cls,
        origin: Address,
        destination: Address,
        packages: List[Package],
        service_level: Optional[ServiceLevel] = None,
        carriers: Optional[List[CarrierType]] = None
    ) -> List[ShippingRate]:
        """Get rates from all carriers concurrently"""
        if carriers is None:
            carriers = [CarrierType.FEDEX, CarrierType.UPS, CarrierType.DHL]
        
        tasks = []
        for carrier in carriers:
            try:
                client = cls.get_client(carrier)
                tasks.append(client.get_rates(origin, destination, packages, service_level))
            except ValueError:
                continue
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_rates = []
        for result in results:
            if isinstance(result, list):
                all_rates.extend(result)
            elif isinstance(result, Exception):
                logger.warning(f"Failed to get rates: {result}")
        
        all_rates.sort(key=lambda x: x.cost)
        return all_rates
