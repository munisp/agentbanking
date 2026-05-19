"""
Unified Payment Corridor Router
Routes transactions to the appropriate payment corridor based on source/destination

Supported Corridors:
- PAPSS: Pan-African (intra-Africa)
- Mojaloop: Open-source instant payments (Africa, Asia)
- CIPS: China Cross-Border Interbank Payment System
- UPI: India Unified Payments Interface
- PIX: Brazil Instant Payment System
"""

import logging
import os
from typing import Dict, Any, Optional, List
from decimal import Decimal
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PaymentCorridor(Enum):
    """Available payment corridors"""
    PAPSS = "PAPSS"
    MOJALOOP = "MOJALOOP"
    CIPS = "CIPS"
    UPI = "UPI"
    PIX = "PIX"
    SWIFT = "SWIFT"  # Fallback for unsupported routes


@dataclass
class CorridorRoute:
    """Defines a payment route"""
    corridor: PaymentCorridor
    source_countries: List[str]
    destination_countries: List[str]
    source_currencies: List[str]
    destination_currencies: List[str]
    priority: int = 1  # Lower is higher priority
    max_amount: Optional[Decimal] = None
    min_amount: Optional[Decimal] = None
    settlement_time_hours: int = 24


class CorridorRouter:
    """
    Routes payments to the appropriate corridor based on:
    - Source and destination countries
    - Currencies involved
    - Amount limits
    - Corridor availability
    """
    
    # Country to region mapping
    AFRICAN_COUNTRIES = [
        "NG", "KE", "GH", "ZA", "EG", "TZ", "UG", "RW", "ET", "SN",
        "CI", "CM", "DZ", "MA", "TN", "AO", "MZ", "ZM", "ZW", "BW",
        "NA", "MW", "MG", "MU", "SC", "DJ", "ER", "SS", "SD", "LY",
        "ML", "BF", "NE", "TD", "CF", "CG", "CD", "GA", "GQ", "ST",
        "BJ", "TG", "GN", "SL", "LR", "GM", "GW", "CV", "MR", "SO"
    ]
    
    SOUTH_AMERICAN_COUNTRIES = [
        "BR", "AR", "CL", "CO", "PE", "VE", "EC", "BO", "PY", "UY",
        "GY", "SR", "GF"
    ]
    
    ASIAN_COUNTRIES = [
        "IN", "CN", "JP", "KR", "SG", "MY", "TH", "VN", "PH", "ID",
        "BD", "PK", "LK", "NP", "MM", "KH", "LA"
    ]
    
    # Define corridor routes
    ROUTES: List[CorridorRoute] = [
        # PAPSS: Intra-African payments
        CorridorRoute(
            corridor=PaymentCorridor.PAPSS,
            source_countries=AFRICAN_COUNTRIES,
            destination_countries=AFRICAN_COUNTRIES,
            source_currencies=["NGN", "KES", "GHS", "ZAR", "EGP", "TZS", "UGX", "XOF", "XAF"],
            destination_currencies=["NGN", "KES", "GHS", "ZAR", "EGP", "TZS", "UGX", "XOF", "XAF"],
            priority=1,
            max_amount=Decimal("1000000"),
            settlement_time_hours=2
        ),
        
        # Mojaloop: Africa to Africa (alternative to PAPSS)
        CorridorRoute(
            corridor=PaymentCorridor.MOJALOOP,
            source_countries=AFRICAN_COUNTRIES,
            destination_countries=AFRICAN_COUNTRIES,
            source_currencies=["KES", "TZS", "UGX", "RWF", "GHS", "ZMW"],
            destination_currencies=["KES", "TZS", "UGX", "RWF", "GHS", "ZMW"],
            priority=2,
            max_amount=Decimal("500000"),
            settlement_time_hours=1
        ),
        
        # UPI: India payments
        CorridorRoute(
            corridor=PaymentCorridor.UPI,
            source_countries=["IN"] + AFRICAN_COUNTRIES,  # Africa to India
            destination_countries=["IN"],
            source_currencies=["INR", "NGN", "KES", "GHS", "ZAR"],
            destination_currencies=["INR"],
            priority=1,
            max_amount=Decimal("100000"),  # 1 lakh INR
            settlement_time_hours=1
        ),
        
        # PIX: Brazil payments
        CorridorRoute(
            corridor=PaymentCorridor.PIX,
            source_countries=AFRICAN_COUNTRIES + SOUTH_AMERICAN_COUNTRIES,
            destination_countries=["BR"],
            source_currencies=["BRL", "NGN", "ZAR", "USD"],
            destination_currencies=["BRL"],
            priority=1,
            max_amount=Decimal("1000000"),
            settlement_time_hours=1
        ),
        
        # CIPS: China payments
        CorridorRoute(
            corridor=PaymentCorridor.CIPS,
            source_countries=AFRICAN_COUNTRIES + ASIAN_COUNTRIES,
            destination_countries=["CN"],
            source_currencies=["CNY", "NGN", "ZAR", "KES", "USD"],
            destination_currencies=["CNY"],
            priority=1,
            max_amount=Decimal("5000000"),
            settlement_time_hours=4
        ),
    ]
    
    def __init__(self):
        """Initialize corridor router with clients"""
        self._clients = {}
        self._initialized = False
        logger.info("Corridor router initialized")
    
    async def initialize(self) -> None:
        """Initialize all corridor clients"""
        if self._initialized:
            return
        
        try:
            # Import and initialize clients lazily
            from .mojaloop.client import MojaloopClient
            from .upi.client import UPIClient
            from .pix.client import PixClient
            
            # Initialize Mojaloop
            self._clients[PaymentCorridor.MOJALOOP] = MojaloopClient(
                hub_url=os.getenv("MOJALOOP_HUB_URL", "https://mojaloop.example.com"),
                fsp_id=os.getenv("MOJALOOP_FSP_ID", "remittance-fsp"),
                signing_key=os.getenv("MOJALOOP_SIGNING_KEY")
            )
            
            # Initialize UPI
            self._clients[PaymentCorridor.UPI] = UPIClient(
                psp_url=os.getenv("UPI_PSP_URL", "https://upi.example.com"),
                merchant_id=os.getenv("UPI_MERCHANT_ID", "MERCHANT001"),
                merchant_key=os.getenv("UPI_MERCHANT_KEY", ""),
                merchant_vpa=os.getenv("UPI_MERCHANT_VPA", "merchant@bank")
            )
            
            # Initialize PIX
            self._clients[PaymentCorridor.PIX] = PixClient(
                api_url=os.getenv("PIX_API_URL", "https://pix.example.com"),
                client_id=os.getenv("PIX_CLIENT_ID", ""),
                client_secret=os.getenv("PIX_CLIENT_SECRET", ""),
                pix_key=os.getenv("PIX_KEY", "")
            )
            
            # PAPSS and CIPS use TigerBeetle services
            # They are initialized separately in the payment corridors module
            
            self._initialized = True
            logger.info("All corridor clients initialized")
            
        except ImportError as e:
            logger.warning(f"Some corridor clients not available: {e}")
        except Exception as e:
            logger.error(f"Error initializing corridor clients: {e}")
    
    async def close(self) -> None:
        """Close all corridor clients"""
        for client in self._clients.values():
            if hasattr(client, 'close'):
                await client.close()
    
    def select_corridor(
        self,
        source_country: str,
        destination_country: str,
        source_currency: str,
        destination_currency: str,
        amount: Decimal
    ) -> Optional[CorridorRoute]:
        """
        Select the best corridor for a payment
        
        Args:
            source_country: ISO country code of sender
            destination_country: ISO country code of receiver
            source_currency: Source currency code
            destination_currency: Destination currency code
            amount: Payment amount
            
        Returns:
            Best matching corridor route or None
        """
        matching_routes = []
        
        for route in self.ROUTES:
            # Check country match
            if source_country not in route.source_countries:
                continue
            if destination_country not in route.destination_countries:
                continue
            
            # Check currency match
            if source_currency not in route.source_currencies:
                continue
            if destination_currency not in route.destination_currencies:
                continue
            
            # Check amount limits
            if route.max_amount and amount > route.max_amount:
                continue
            if route.min_amount and amount < route.min_amount:
                continue
            
            matching_routes.append(route)
        
        if not matching_routes:
            logger.warning(
                f"No corridor found for {source_country}/{source_currency} -> "
                f"{destination_country}/{destination_currency}"
            )
            return None
        
        # Sort by priority and return best match
        matching_routes.sort(key=lambda r: r.priority)
        selected = matching_routes[0]
        
        logger.info(
            f"Selected corridor {selected.corridor.value} for "
            f"{source_country} -> {destination_country}"
        )
        
        return selected
    
    async def route_payment(
        self,
        source_country: str,
        destination_country: str,
        source_currency: str,
        destination_currency: str,
        amount: Decimal,
        sender_id: str,
        receiver_id: str,
        note: str = "",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Route a payment through the appropriate corridor
        
        Args:
            source_country: Sender's country
            destination_country: Receiver's country
            source_currency: Source currency
            destination_currency: Destination currency
            amount: Payment amount
            sender_id: Sender identifier (phone, VPA, PIX key, etc.)
            receiver_id: Receiver identifier
            note: Payment note/description
            idempotency_key: Optional idempotency key
            
        Returns:
            Payment result
        """
        await self.initialize()
        
        # Select corridor
        route = self.select_corridor(
            source_country, destination_country,
            source_currency, destination_currency,
            amount
        )
        
        if not route:
            return {
                "success": False,
                "error": "No suitable payment corridor found",
                "source": f"{source_country}/{source_currency}",
                "destination": f"{destination_country}/{destination_currency}"
            }
        
        # Route to appropriate corridor
        try:
            if route.corridor == PaymentCorridor.MOJALOOP:
                return await self._route_mojaloop(
                    sender_id, receiver_id, amount, source_currency, note
                )
            elif route.corridor == PaymentCorridor.UPI:
                return await self._route_upi(
                    receiver_id, amount, note
                )
            elif route.corridor == PaymentCorridor.PIX:
                return await self._route_pix(
                    receiver_id, amount, note
                )
            elif route.corridor == PaymentCorridor.PAPSS:
                return await self._route_papss(
                    sender_id, receiver_id, amount, source_currency, note
                )
            elif route.corridor == PaymentCorridor.CIPS:
                return await self._route_cips(
                    sender_id, receiver_id, amount, note
                )
            else:
                return {
                    "success": False,
                    "error": f"Corridor {route.corridor.value} not implemented"
                }
                
        except Exception as e:
            logger.error(f"Payment routing failed: {e}")
            return {
                "success": False,
                "corridor": route.corridor.value,
                "error": str(e)
            }
    
    async def _route_mojaloop(
        self,
        sender_msisdn: str,
        receiver_msisdn: str,
        amount: Decimal,
        currency: str,
        note: str
    ) -> Dict[str, Any]:
        """Route payment through Mojaloop"""
        client = self._clients.get(PaymentCorridor.MOJALOOP)
        if not client:
            return {"success": False, "error": "Mojaloop client not initialized"}
        
        result = await client.send_money(
            sender_msisdn=sender_msisdn,
            receiver_msisdn=receiver_msisdn,
            amount=amount,
            currency=currency,
            note=note
        )
        
        result["corridor"] = "MOJALOOP"
        return result
    
    async def _route_upi(
        self,
        receiver_vpa: str,
        amount: Decimal,
        note: str
    ) -> Dict[str, Any]:
        """Route payment through UPI"""
        client = self._clients.get(PaymentCorridor.UPI)
        if not client:
            return {"success": False, "error": "UPI client not initialized"}
        
        result = await client.send_money(
            receiver_vpa=receiver_vpa,
            amount=amount,
            note=note
        )
        
        result["corridor"] = "UPI"
        return result
    
    async def _route_pix(
        self,
        receiver_key: str,
        amount: Decimal,
        description: str
    ) -> Dict[str, Any]:
        """Route payment through PIX"""
        client = self._clients.get(PaymentCorridor.PIX)
        if not client:
            return {"success": False, "error": "PIX client not initialized"}
        
        result = await client.send_money(
            receiver_key=receiver_key,
            amount=amount,
            description=description
        )
        
        result["corridor"] = "PIX"
        return result
    
    async def _route_papss(
        self,
        sender_account: str,
        receiver_account: str,
        amount: Decimal,
        currency: str,
        note: str
    ) -> Dict[str, Any]:
        """Route payment through PAPSS"""
        # Import PAPSS service
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from payment_corridors.papss_tigerbeetle_service import PapssTigerbeetleService
            
            papss = PapssTigerbeetleService()
            
            # For mobile money transfers
            if receiver_account.startswith("+") or receiver_account.isdigit():
                result = await papss.process_mobile_money_transfer(
                    from_account_id=int(sender_account) if sender_account.isdigit() else hash(sender_account),
                    mobile_number=receiver_account,
                    amount=amount,
                    currency=currency
                )
            else:
                # Regular account transfer
                result = await papss.process_transfer(
                    from_account_id=int(sender_account) if sender_account.isdigit() else hash(sender_account),
                    to_account_id=int(receiver_account) if receiver_account.isdigit() else hash(receiver_account),
                    amount=amount,
                    currency=currency
                )
            
            result["corridor"] = "PAPSS"
            return result
            
        except Exception as e:
            logger.error(f"PAPSS routing failed: {e}")
            return {"success": False, "corridor": "PAPSS", "error": str(e)}
    
    async def _route_cips(
        self,
        sender_account: str,
        receiver_account: str,
        amount: Decimal,
        note: str
    ) -> Dict[str, Any]:
        """Route payment through CIPS"""
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from payment_corridors.cips_tigerbeetle_service import CipsTigerbeetleService
            
            cips = CipsTigerbeetleService()
            
            result = await cips.process_transfer(
                from_account_id=int(sender_account) if sender_account.isdigit() else hash(sender_account),
                to_account_id=int(receiver_account) if receiver_account.isdigit() else hash(receiver_account),
                amount=amount
            )
            
            result["corridor"] = "CIPS"
            return result
            
        except Exception as e:
            logger.error(f"CIPS routing failed: {e}")
            return {"success": False, "corridor": "CIPS", "error": str(e)}
    
    def get_available_corridors(
        self,
        source_country: str,
        destination_country: str
    ) -> List[Dict[str, Any]]:
        """
        Get all available corridors for a country pair
        
        Args:
            source_country: Source country code
            destination_country: Destination country code
            
        Returns:
            List of available corridors with details
        """
        available = []
        
        for route in self.ROUTES:
            if source_country in route.source_countries and \
               destination_country in route.destination_countries:
                available.append({
                    "corridor": route.corridor.value,
                    "source_currencies": route.source_currencies,
                    "destination_currencies": route.destination_currencies,
                    "max_amount": float(route.max_amount) if route.max_amount else None,
                    "min_amount": float(route.min_amount) if route.min_amount else None,
                    "settlement_time_hours": route.settlement_time_hours,
                    "priority": route.priority
                })
        
        return sorted(available, key=lambda x: x["priority"])
    
    def get_corridor_status(self) -> Dict[str, Any]:
        """Get status of all corridors"""
        return {
            "initialized": self._initialized,
            "corridors": {
                corridor.value: {
                    "available": corridor in self._clients or corridor in [
                        PaymentCorridor.PAPSS, PaymentCorridor.CIPS
                    ],
                    "client_initialized": corridor in self._clients
                }
                for corridor in PaymentCorridor
            },
            "total_routes": len(self.ROUTES),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
_router_instance: Optional[CorridorRouter] = None


def get_router() -> CorridorRouter:
    """Get corridor router singleton"""
    global _router_instance
    if _router_instance is None:
        _router_instance = CorridorRouter()
    return _router_instance
