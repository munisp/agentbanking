"""
Production-Ready Geocoding Service
Provides address geocoding and distance calculation using real APIs
Supports Google Maps, Mapbox, and OpenStreetMap (Nominatim)
"""

import os
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
import math
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


@dataclass
class GeocodedAddress:
    latitude: float
    longitude: float
    formatted_address: str
    street_number: Optional[str] = None
    street_name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    confidence: float = 1.0


@dataclass
class DistanceResult:
    distance_km: float
    duration_minutes: float
    route_polyline: Optional[str] = None


class GeocodingProvider(ABC):
    """Abstract base class for geocoding providers"""
    
    @abstractmethod
    async def geocode(self, address: str) -> Optional[GeocodedAddress]:
        """Convert address to coordinates"""
        pass
    
    @abstractmethod
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[GeocodedAddress]:
        """Convert coordinates to address"""
        pass
    
    @abstractmethod
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[DistanceResult]:
        """Calculate distance and duration between two points"""
        pass
    
    @abstractmethod
    async def calculate_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = "driving"
    ) -> List[List[Optional[DistanceResult]]]:
        """Calculate distance matrix between multiple origins and destinations"""
        pass


class GoogleMapsProvider(GeocodingProvider):
    """Google Maps Geocoding and Distance Matrix API"""
    
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_MAPS_API_KEY not set, Google Maps provider will not work")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def geocode(self, address: str) -> Optional[GeocodedAddress]:
        """Geocode address using Google Maps"""
        if not self.api_key:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GEOCODE_URL,
                params={
                    "address": address,
                    "key": self.api_key
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Google geocode failed: {response.text}")
                return None
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                return None
            
            result = data["results"][0]
            location = result["geometry"]["location"]
            
            components = {}
            for component in result.get("address_components", []):
                for comp_type in component.get("types", []):
                    components[comp_type] = component.get("long_name")
                    if comp_type == "country":
                        components["country_code"] = component.get("short_name")
            
            return GeocodedAddress(
                latitude=location["lat"],
                longitude=location["lng"],
                formatted_address=result.get("formatted_address", ""),
                street_number=components.get("street_number"),
                street_name=components.get("route"),
                city=components.get("locality") or components.get("administrative_area_level_2"),
                state=components.get("administrative_area_level_1"),
                postal_code=components.get("postal_code"),
                country=components.get("country"),
                country_code=components.get("country_code"),
                confidence=self._get_confidence(result.get("geometry", {}).get("location_type", ""))
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[GeocodedAddress]:
        """Reverse geocode coordinates using Google Maps"""
        if not self.api_key:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GEOCODE_URL,
                params={
                    "latlng": f"{lat},{lon}",
                    "key": self.api_key
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                return None
            
            result = data["results"][0]
            
            components = {}
            for component in result.get("address_components", []):
                for comp_type in component.get("types", []):
                    components[comp_type] = component.get("long_name")
                    if comp_type == "country":
                        components["country_code"] = component.get("short_name")
            
            return GeocodedAddress(
                latitude=lat,
                longitude=lon,
                formatted_address=result.get("formatted_address", ""),
                street_number=components.get("street_number"),
                street_name=components.get("route"),
                city=components.get("locality") or components.get("administrative_area_level_2"),
                state=components.get("administrative_area_level_1"),
                postal_code=components.get("postal_code"),
                country=components.get("country"),
                country_code=components.get("country_code")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[DistanceResult]:
        """Calculate distance using Google Maps Directions API"""
        if not self.api_key:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.DIRECTIONS_URL,
                params={
                    "origin": f"{origin[0]},{origin[1]}",
                    "destination": f"{destination[0]},{destination[1]}",
                    "mode": mode,
                    "key": self.api_key
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("routes"):
                return None
            
            route = data["routes"][0]
            leg = route["legs"][0]
            
            return DistanceResult(
                distance_km=leg["distance"]["value"] / 1000,
                duration_minutes=leg["duration"]["value"] / 60,
                route_polyline=route.get("overview_polyline", {}).get("points")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def calculate_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = "driving"
    ) -> List[List[Optional[DistanceResult]]]:
        """Calculate distance matrix using Google Maps Distance Matrix API"""
        if not self.api_key:
            return [[None] * len(destinations) for _ in origins]
        
        origins_str = "|".join(f"{lat},{lon}" for lat, lon in origins)
        destinations_str = "|".join(f"{lat},{lon}" for lat, lon in destinations)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.DISTANCE_URL,
                params={
                    "origins": origins_str,
                    "destinations": destinations_str,
                    "mode": mode,
                    "key": self.api_key
                }
            )
            
            if response.status_code != 200:
                return [[None] * len(destinations) for _ in origins]
            
            data = response.json()
            
            if data.get("status") != "OK":
                return [[None] * len(destinations) for _ in origins]
            
            matrix = []
            for row in data.get("rows", []):
                row_results = []
                for element in row.get("elements", []):
                    if element.get("status") == "OK":
                        row_results.append(DistanceResult(
                            distance_km=element["distance"]["value"] / 1000,
                            duration_minutes=element["duration"]["value"] / 60
                        ))
                    else:
                        row_results.append(None)
                matrix.append(row_results)
            
            return matrix
    
    def _get_confidence(self, location_type: str) -> float:
        """Convert Google location type to confidence score"""
        confidence_map = {
            "ROOFTOP": 1.0,
            "RANGE_INTERPOLATED": 0.8,
            "GEOMETRIC_CENTER": 0.6,
            "APPROXIMATE": 0.4
        }
        return confidence_map.get(location_type, 0.5)


class MapboxProvider(GeocodingProvider):
    """Mapbox Geocoding and Directions API"""
    
    GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    DIRECTIONS_URL = "https://api.mapbox.com/directions/v5/mapbox"
    MATRIX_URL = "https://api.mapbox.com/directions-matrix/v1/mapbox"
    
    def __init__(self):
        self.access_token = os.getenv("MAPBOX_ACCESS_TOKEN")
        if not self.access_token:
            logger.warning("MAPBOX_ACCESS_TOKEN not set, Mapbox provider will not work")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def geocode(self, address: str) -> Optional[GeocodedAddress]:
        """Geocode address using Mapbox"""
        if not self.access_token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GEOCODE_URL}/{address}.json",
                params={
                    "access_token": self.access_token,
                    "limit": 1
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if not data.get("features"):
                return None
            
            feature = data["features"][0]
            coords = feature["geometry"]["coordinates"]
            
            context = {}
            for ctx in feature.get("context", []):
                ctx_id = ctx.get("id", "").split(".")[0]
                context[ctx_id] = ctx.get("text")
                if ctx_id == "country":
                    context["country_code"] = ctx.get("short_code", "").upper()
            
            return GeocodedAddress(
                latitude=coords[1],
                longitude=coords[0],
                formatted_address=feature.get("place_name", ""),
                street_number=feature.get("address"),
                street_name=feature.get("text"),
                city=context.get("place") or context.get("locality"),
                state=context.get("region"),
                postal_code=context.get("postcode"),
                country=context.get("country"),
                country_code=context.get("country_code"),
                confidence=feature.get("relevance", 0.5)
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[GeocodedAddress]:
        """Reverse geocode coordinates using Mapbox"""
        if not self.access_token:
            return None
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GEOCODE_URL}/{lon},{lat}.json",
                params={
                    "access_token": self.access_token,
                    "limit": 1
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if not data.get("features"):
                return None
            
            feature = data["features"][0]
            
            context = {}
            for ctx in feature.get("context", []):
                ctx_id = ctx.get("id", "").split(".")[0]
                context[ctx_id] = ctx.get("text")
                if ctx_id == "country":
                    context["country_code"] = ctx.get("short_code", "").upper()
            
            return GeocodedAddress(
                latitude=lat,
                longitude=lon,
                formatted_address=feature.get("place_name", ""),
                street_number=feature.get("address"),
                street_name=feature.get("text"),
                city=context.get("place") or context.get("locality"),
                state=context.get("region"),
                postal_code=context.get("postcode"),
                country=context.get("country"),
                country_code=context.get("country_code")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[DistanceResult]:
        """Calculate distance using Mapbox Directions API"""
        if not self.access_token:
            return None
        
        profile = self._get_profile(mode)
        coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.DIRECTIONS_URL}/{profile}/{coords}",
                params={
                    "access_token": self.access_token,
                    "geometries": "polyline"
                }
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if not data.get("routes"):
                return None
            
            route = data["routes"][0]
            
            return DistanceResult(
                distance_km=route["distance"] / 1000,
                duration_minutes=route["duration"] / 60,
                route_polyline=route.get("geometry")
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def calculate_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = "driving"
    ) -> List[List[Optional[DistanceResult]]]:
        """Calculate distance matrix using Mapbox Matrix API"""
        if not self.access_token:
            return [[None] * len(destinations) for _ in origins]
        
        profile = self._get_profile(mode)
        
        all_coords = origins + destinations
        coords_str = ";".join(f"{lon},{lat}" for lat, lon in all_coords)
        
        sources = ";".join(str(i) for i in range(len(origins)))
        destinations_idx = ";".join(str(i) for i in range(len(origins), len(all_coords)))
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.MATRIX_URL}/{profile}/{coords_str}",
                params={
                    "access_token": self.access_token,
                    "sources": sources,
                    "destinations": destinations_idx,
                    "annotations": "distance,duration"
                }
            )
            
            if response.status_code != 200:
                return [[None] * len(destinations) for _ in origins]
            
            data = response.json()
            
            distances = data.get("distances", [])
            durations = data.get("durations", [])
            
            matrix = []
            for i, (dist_row, dur_row) in enumerate(zip(distances, durations)):
                row_results = []
                for j, (dist, dur) in enumerate(zip(dist_row, dur_row)):
                    if dist is not None and dur is not None:
                        row_results.append(DistanceResult(
                            distance_km=dist / 1000,
                            duration_minutes=dur / 60
                        ))
                    else:
                        row_results.append(None)
                matrix.append(row_results)
            
            return matrix
    
    def _get_profile(self, mode: str) -> str:
        """Convert mode to Mapbox profile"""
        profile_map = {
            "driving": "driving",
            "walking": "walking",
            "cycling": "cycling",
            "transit": "driving-traffic"
        }
        return profile_map.get(mode, "driving")


class NominatimProvider(GeocodingProvider):
    """OpenStreetMap Nominatim Geocoding (free, rate-limited)"""
    
    GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
    REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
    
    def __init__(self):
        self.user_agent = os.getenv("NOMINATIM_USER_AGENT", "AgentBankingPlatform/1.0")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def geocode(self, address: str) -> Optional[GeocodedAddress]:
        """Geocode address using Nominatim"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.GEOCODE_URL,
                params={
                    "q": address,
                    "format": "json",
                    "addressdetails": 1,
                    "limit": 1
                },
                headers={"User-Agent": self.user_agent}
            )
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            if not data:
                return None
            
            result = data[0]
            addr = result.get("address", {})
            
            return GeocodedAddress(
                latitude=float(result["lat"]),
                longitude=float(result["lon"]),
                formatted_address=result.get("display_name", ""),
                street_number=addr.get("house_number"),
                street_name=addr.get("road"),
                city=addr.get("city") or addr.get("town") or addr.get("village"),
                state=addr.get("state"),
                postal_code=addr.get("postcode"),
                country=addr.get("country"),
                country_code=addr.get("country_code", "").upper(),
                confidence=float(result.get("importance", 0.5))
            )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[GeocodedAddress]:
        """Reverse geocode coordinates using Nominatim"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.REVERSE_URL,
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "addressdetails": 1
                },
                headers={"User-Agent": self.user_agent}
            )
            
            if response.status_code != 200:
                return None
            
            result = response.json()
            
            if result.get("error"):
                return None
            
            addr = result.get("address", {})
            
            return GeocodedAddress(
                latitude=lat,
                longitude=lon,
                formatted_address=result.get("display_name", ""),
                street_number=addr.get("house_number"),
                street_name=addr.get("road"),
                city=addr.get("city") or addr.get("town") or addr.get("village"),
                state=addr.get("state"),
                postal_code=addr.get("postcode"),
                country=addr.get("country"),
                country_code=addr.get("country_code", "").upper()
            )
    
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[DistanceResult]:
        """Calculate distance using Haversine formula (Nominatim doesn't provide routing)"""
        distance_km = self._haversine_distance(origin[0], origin[1], destination[0], destination[1])
        
        speed_map = {
            "driving": 50,
            "walking": 5,
            "cycling": 15
        }
        speed = speed_map.get(mode, 50)
        duration_minutes = (distance_km / speed) * 60
        
        return DistanceResult(
            distance_km=distance_km,
            duration_minutes=duration_minutes
        )
    
    async def calculate_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = "driving"
    ) -> List[List[Optional[DistanceResult]]]:
        """Calculate distance matrix using Haversine formula"""
        matrix = []
        for origin in origins:
            row = []
            for destination in destinations:
                result = await self.calculate_distance(origin, destination, mode)
                row.append(result)
            matrix.append(row)
        return matrix
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        R = 6371
        
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
        
        return round(distance, 2)


class GeocodingService:
    """Unified geocoding service with fallback providers"""
    
    def __init__(self, primary_provider: str = "google"):
        self.providers: Dict[str, GeocodingProvider] = {}
        self.primary_provider = primary_provider
        
        if os.getenv("GOOGLE_MAPS_API_KEY"):
            self.providers["google"] = GoogleMapsProvider()
        
        if os.getenv("MAPBOX_ACCESS_TOKEN"):
            self.providers["mapbox"] = MapboxProvider()
        
        self.providers["nominatim"] = NominatimProvider()
        
        if primary_provider not in self.providers:
            available = list(self.providers.keys())
            self.primary_provider = available[0] if available else "nominatim"
            logger.warning(f"Primary provider {primary_provider} not available, using {self.primary_provider}")
    
    async def geocode(self, address: str) -> Optional[GeocodedAddress]:
        """Geocode address with fallback"""
        providers_to_try = [self.primary_provider] + [
            p for p in self.providers.keys() if p != self.primary_provider
        ]
        
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if provider:
                try:
                    result = await provider.geocode(address)
                    if result:
                        logger.info(f"Geocoded '{address}' using {provider_name}")
                        return result
                except Exception as e:
                    logger.warning(f"Geocoding failed with {provider_name}: {e}")
        
        return None
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[GeocodedAddress]:
        """Reverse geocode with fallback"""
        providers_to_try = [self.primary_provider] + [
            p for p in self.providers.keys() if p != self.primary_provider
        ]
        
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if provider:
                try:
                    result = await provider.reverse_geocode(lat, lon)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Reverse geocoding failed with {provider_name}: {e}")
        
        return None
    
    async def calculate_distance(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str = "driving"
    ) -> Optional[DistanceResult]:
        """Calculate distance with fallback"""
        providers_to_try = [self.primary_provider] + [
            p for p in self.providers.keys() if p != self.primary_provider
        ]
        
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if provider:
                try:
                    result = await provider.calculate_distance(origin, destination, mode)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Distance calculation failed with {provider_name}: {e}")
        
        return None
    
    async def calculate_distance_matrix(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        mode: str = "driving"
    ) -> List[List[Optional[DistanceResult]]]:
        """Calculate distance matrix with fallback"""
        providers_to_try = [self.primary_provider] + [
            p for p in self.providers.keys() if p != self.primary_provider
        ]
        
        for provider_name in providers_to_try:
            provider = self.providers.get(provider_name)
            if provider:
                try:
                    result = await provider.calculate_distance_matrix(origins, destinations, mode)
                    if result and any(any(r is not None for r in row) for row in result):
                        return result
                except Exception as e:
                    logger.warning(f"Distance matrix calculation failed with {provider_name}: {e}")
        
        return [[None] * len(destinations) for _ in origins]
    
    async def geocode_address_dict(self, address: Dict[str, str]) -> Optional[GeocodedAddress]:
        """Geocode from address dictionary"""
        address_parts = []
        
        if address.get("street_line1"):
            address_parts.append(address["street_line1"])
        if address.get("street_line2"):
            address_parts.append(address["street_line2"])
        if address.get("city"):
            address_parts.append(address["city"])
        if address.get("state") or address.get("state_province"):
            address_parts.append(address.get("state") or address.get("state_province"))
        if address.get("postal_code") or address.get("zip"):
            address_parts.append(address.get("postal_code") or address.get("zip"))
        if address.get("country") or address.get("country_code"):
            address_parts.append(address.get("country") or address.get("country_code"))
        
        if not address_parts:
            return None
        
        return await self.geocode(", ".join(address_parts))


geocoding_service = GeocodingService()
