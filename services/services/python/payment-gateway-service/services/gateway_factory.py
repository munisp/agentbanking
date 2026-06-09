"""
Payment Gateway Factory

Factory class for creating and managing payment gateway instances.
Handles dynamic gateway selection based on various criteria.
"""

from typing import Dict, Optional, List
from decimal import Decimal
import logging

from .base_gateway import BasePaymentGateway, PaymentGatewayError
from .gateways.paystack_gateway import PaystackGateway
from .gateways.flutterwave_gateway import FlutterwaveGateway
from .gateways.interswitch_gateway import InterswitchGateway
from .gateways.stripe_gateway import StripeGateway
from .gateways.paypal_gateway import PayPalGateway
from .gateways.remita_gateway import RemitaGateway
from .gateways.paga_gateway import PagaGateway
from .gateways.opay_gateway import OpayGateway
from .gateways.kuda_gateway import KudaGateway
from .gateways.chipper_cash_gateway import ChipperCashGateway
from .gateways.nibss_gateway import NIBSSGateway
from .gateways.gtpay_gateway import GTPay Gateway
from .gateways.ecobank_gateway import EcobankGateway

logger = logging.getLogger(__name__)


class GatewayFactory:
    """
    Factory for creating and managing payment gateway instances.
    
    Supports automatic gateway selection based on:
    - Currency support
    - Transaction amount
    - Country/region
    - Gateway availability
    - Priority/cost
    """
    
    # Gateway class registry
    GATEWAY_REGISTRY = {
        "paystack": PaystackGateway,
        "flutterwave": FlutterwaveGateway,
        "interswitch": InterswitchGateway,
        "stripe": StripeGateway,
        "paypal": PayPalGateway,
        "remita": RemitaGateway,
        "paga": PagaGateway,
        "opay": OpayGateway,
        "kuda": KudaGateway,
        "chipper_cash": ChipperCashGateway,
        "nibss": NIBSSGateway,
        "gtpay": GTPay,
        "ecobank": EcobankGateway,
    }
    
    def __init__(self, gateway_configs: Dict[str, Dict]):
        """
        Initialize the gateway factory.
        
        Args:
            gateway_configs: Dictionary of gateway configurations
                            {gateway_name: {config_dict}}
        """
        self.gateway_configs = gateway_configs
        self._gateway_instances: Dict[str, BasePaymentGateway] = {}
        self._gateway_health: Dict[str, bool] = {}
        
    def get_gateway(self, gateway_name: str) -> BasePaymentGateway:
        """
        Get a gateway instance by name.
        
        Args:
            gateway_name: Name of the gateway
            
        Returns:
            Gateway instance
            
        Raises:
            PaymentGatewayError: If gateway not found or initialization fails
        """
        gateway_name = gateway_name.lower()
        
        # Return cached instance if available
        if gateway_name in self._gateway_instances:
            return self._gateway_instances[gateway_name]
        
        # Check if gateway is registered
        if gateway_name not in self.GATEWAY_REGISTRY:
            raise PaymentGatewayError(
                f"Gateway '{gateway_name}' not found",
                gateway_name=gateway_name,
                error_code="GATEWAY_NOT_FOUND"
            )
        
        # Get gateway configuration
        config = self.gateway_configs.get(gateway_name)
        if not config:
            raise PaymentGatewayError(
                f"Configuration not found for gateway '{gateway_name}'",
                gateway_name=gateway_name,
                error_code="GATEWAY_NOT_CONFIGURED"
            )
        
        # Check if gateway is active
        if not config.get("is_active", False):
            raise PaymentGatewayError(
                f"Gateway '{gateway_name}' is not active",
                gateway_name=gateway_name,
                error_code="GATEWAY_INACTIVE"
            )
        
        # Create gateway instance
        try:
            gateway_class = self.GATEWAY_REGISTRY[gateway_name]
            gateway = gateway_class(config)
            gateway.validate_config()
            
            # Cache instance
            self._gateway_instances[gateway_name] = gateway
            self._gateway_health[gateway_name] = True
            
            logger.info(f"Initialized gateway: {gateway_name}")
            return gateway
            
        except Exception as e:
            logger.error(f"Failed to initialize gateway {gateway_name}: {str(e)}")
            raise PaymentGatewayError(
                f"Failed to initialize gateway '{gateway_name}': {str(e)}",
                gateway_name=gateway_name,
                error_code="GATEWAY_INIT_FAILED"
            )
    
    async def select_gateway(
        self,
        currency: str,
        amount: Optional[Decimal] = None,
        country: Optional[str] = None,
        preferred_gateway: Optional[str] = None
    ) -> BasePaymentGateway:
        """
        Automatically select the best gateway based on criteria.
        
        Args:
            currency: Currency code
            amount: Transaction amount (optional)
            country: Country code (optional)
            preferred_gateway: Preferred gateway name (optional)
            
        Returns:
            Selected gateway instance
            
        Raises:
            PaymentGatewayError: If no suitable gateway found
        """
        # If preferred gateway specified, try to use it
        if preferred_gateway:
            try:
                gateway = self.get_gateway(preferred_gateway)
                if await self._is_gateway_suitable(gateway, currency, amount, country):
                    return gateway
                logger.warning(
                    f"Preferred gateway {preferred_gateway} not suitable, "
                    f"falling back to auto-selection"
                )
            except PaymentGatewayError as e:
                logger.warning(f"Preferred gateway {preferred_gateway} unavailable: {e}")
        
        # Find all suitable gateways
        suitable_gateways = []
        for gateway_name, config in self.gateway_configs.items():
            if not config.get("is_active", False):
                continue
            
            try:
                gateway = self.get_gateway(gateway_name)
                if await self._is_gateway_suitable(gateway, currency, amount, country):
                    priority = config.get("priority", 100)
                    suitable_gateways.append((priority, gateway_name, gateway))
            except Exception as e:
                logger.warning(f"Gateway {gateway_name} check failed: {e}")
                continue
        
        if not suitable_gateways:
            raise PaymentGatewayError(
                f"No suitable gateway found for currency {currency}",
                gateway_name="auto",
                error_code="NO_GATEWAY_AVAILABLE"
            )
        
        # Sort by priority (lower number = higher priority)
        suitable_gateways.sort(key=lambda x: x[0])
        
        selected_gateway = suitable_gateways[0][2]
        logger.info(
            f"Auto-selected gateway: {suitable_gateways[0][1]} "
            f"for currency {currency}"
        )
        
        return selected_gateway
    
    async def _is_gateway_suitable(
        self,
        gateway: BasePaymentGateway,
        currency: str,
        amount: Optional[Decimal],
        country: Optional[str]
    ) -> bool:
        """
        Check if a gateway is suitable for the given criteria.
        
        Args:
            gateway: Gateway instance
            currency: Currency code
            amount: Transaction amount
            country: Country code
            
        Returns:
            True if gateway is suitable
        """
        try:
            # Check health
            if not await gateway.health_check():
                return False
            
            # Check currency support
            supported_currencies = await gateway.get_supported_currencies()
            if currency not in supported_currencies:
                return False
            
            # Check amount limits (if configured)
            config = self.gateway_configs.get(gateway.gateway_name.lower(), {})
            if amount:
                min_amount = config.get("min_transaction_amount")
                max_amount = config.get("max_transaction_amount")
                
                if min_amount and amount < min_amount:
                    return False
                if max_amount and amount > max_amount:
                    return False
            
            # Check country support (if configured)
            if country:
                supported_countries = config.get("supported_countries", [])
                if supported_countries and country not in supported_countries:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking gateway suitability: {e}")
            return False
    
    async def get_all_active_gateways(self) -> List[str]:
        """
        Get list of all active gateway names.
        
        Returns:
            List of active gateway names
        """
        active_gateways = []
        for gateway_name, config in self.gateway_configs.items():
            if config.get("is_active", False):
                active_gateways.append(gateway_name)
        return active_gateways
    
    async def check_gateway_health(self, gateway_name: str) -> bool:
        """
        Check health of a specific gateway.
        
        Args:
            gateway_name: Gateway name
            
        Returns:
            True if gateway is healthy
        """
        try:
            gateway = self.get_gateway(gateway_name)
            is_healthy = await gateway.health_check()
            self._gateway_health[gateway_name] = is_healthy
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed for {gateway_name}: {e}")
            self._gateway_health[gateway_name] = False
            return False
    
    async def check_all_gateways_health(self) -> Dict[str, bool]:
        """
        Check health of all active gateways.
        
        Returns:
            Dictionary mapping gateway names to health status
        """
        health_status = {}
        for gateway_name in await self.get_all_active_gateways():
            health_status[gateway_name] = await self.check_gateway_health(gateway_name)
        return health_status
    
    def get_gateway_config(self, gateway_name: str) -> Dict:
        """
        Get configuration for a specific gateway.
        
        Args:
            gateway_name: Gateway name
            
        Returns:
            Gateway configuration dictionary
        """
        return self.gateway_configs.get(gateway_name.lower(), {})
    
    def update_gateway_config(self, gateway_name: str, config: Dict):
        """
        Update configuration for a specific gateway.
        
        Args:
            gateway_name: Gateway name
            config: New configuration dictionary
        """
        gateway_name = gateway_name.lower()
        self.gateway_configs[gateway_name] = config
        
        # Clear cached instance to force re-initialization
        if gateway_name in self._gateway_instances:
            del self._gateway_instances[gateway_name]
        
        logger.info(f"Updated configuration for gateway: {gateway_name}")
    
    async def get_supported_currencies_all(self) -> Dict[str, List[str]]:
        """
        Get supported currencies for all active gateways.
        
        Returns:
            Dictionary mapping gateway names to currency lists
        """
        all_currencies = {}
        for gateway_name in await self.get_all_active_gateways():
            try:
                gateway = self.get_gateway(gateway_name)
                currencies = await gateway.get_supported_currencies()
                all_currencies[gateway_name] = currencies
            except Exception as e:
                logger.error(f"Failed to get currencies for {gateway_name}: {e}")
                all_currencies[gateway_name] = []
        return all_currencies
    
    async def get_best_exchange_rate(
        self,
        source_currency: str,
        destination_currency: str
    ) -> tuple[str, Decimal]:
        """
        Get the best exchange rate across all gateways.
        
        Args:
            source_currency: Source currency code
            destination_currency: Destination currency code
            
        Returns:
            Tuple of (gateway_name, exchange_rate)
            
        Raises:
            PaymentGatewayError: If no gateway supports the currency pair
        """
        rates = []
        
        for gateway_name in await self.get_all_active_gateways():
            try:
                gateway = self.get_gateway(gateway_name)
                rate = await gateway.get_exchange_rate(source_currency, destination_currency)
                rates.append((gateway_name, rate))
            except Exception as e:
                logger.debug(f"Gateway {gateway_name} doesn't support rate: {e}")
                continue
        
        if not rates:
            raise PaymentGatewayError(
                f"No gateway supports exchange rate for {source_currency}/{destination_currency}",
                gateway_name="auto",
                error_code="EXCHANGE_RATE_NOT_AVAILABLE"
            )
        
        # Return the best rate (highest value)
        best_rate = max(rates, key=lambda x: x[1])
        logger.info(
            f"Best exchange rate for {source_currency}/{destination_currency}: "
            f"{best_rate[1]} from {best_rate[0]}"
        )
        
        return best_rate
    
    def clear_cache(self):
        """Clear all cached gateway instances."""
        self._gateway_instances.clear()
        self._gateway_health.clear()
        logger.info("Cleared gateway cache")
