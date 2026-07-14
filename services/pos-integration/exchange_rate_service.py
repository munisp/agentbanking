"""
Live Exchange Rate Service
Multiple API providers with intelligent caching and fallback
"""

import asyncio
import aiohttp
import logging
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class ExchangeRateProvider(str, Enum):
    FIXER = "fixer"
    CURRENCYLAYER = "currencylayer"
    OPENEXCHANGERATES = "openexchangerates"
    EXCHANGERATE_API = "exchangerate_api"
    FALLBACK = "fallback"

class ExchangeRateService:
    """Live exchange rate service with multiple providers and caching"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 3600  # 1 hour cache
        self.providers = {
            ExchangeRateProvider.FIXER: self._get_fixer_rates,
            ExchangeRateProvider.CURRENCYLAYER: self._get_currencylayer_rates,
            ExchangeRateProvider.OPENEXCHANGERATES: self._get_openexchangerates_rates,
            ExchangeRateProvider.EXCHANGERATE_API: self._get_exchangerate_api_rates,
            ExchangeRateProvider.FALLBACK: self._get_fallback_rates
        }
        self.provider_priority = [
            ExchangeRateProvider.FIXER,
            ExchangeRateProvider.CURRENCYLAYER,
            ExchangeRateProvider.OPENEXCHANGERATES,
            ExchangeRateProvider.EXCHANGERATE_API,
            ExchangeRateProvider.FALLBACK
        ]
        
        # Supported currencies
        self.supported_currencies = [
            'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'SEK', 'NZD',
            'MXN', 'SGD', 'HKD', 'NOK', 'TRY', 'RUB', 'INR', 'BRL', 'ZAR', 'KRW'
        ]
    
    async def initialize(self):
        """Initialize the exchange rate service"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379"), 
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Exchange rate service initialized with Redis cache")
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory cache: {e}")
            self.redis_client = None
    
    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """Get exchange rate between two currencies"""
        if from_currency == to_currency:
            return Decimal('1.0')
        
        # Check cache first
        cached_rate = await self._get_cached_rate(from_currency, to_currency)
        if cached_rate:
            return cached_rate
        
        # Try providers in priority order
        for provider in self.provider_priority:
            try:
                rates = await self.providers[provider](from_currency)
                if rates and to_currency in rates:
                    rate = Decimal(str(rates[to_currency]))
                    
                    # Cache the rate
                    await self._cache_rate(from_currency, to_currency, rate)
                    
                    logger.info(f"Got exchange rate {from_currency}/{to_currency} = {rate} from {provider.value}")
                    return rate
                    
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed: {e}")
                continue
        
        logger.error(f"Failed to get exchange rate for {from_currency}/{to_currency}")
        return None
    
    async def get_multiple_rates(self, base_currency: str, target_currencies: List[str]) -> Dict[str, Decimal]:
        """Get multiple exchange rates for a base currency"""
        rates = {}
        
        # Check cache for all rates
        cached_rates = await self._get_multiple_cached_rates(base_currency, target_currencies)
        rates.update(cached_rates)
        
        # Get missing rates
        missing_currencies = [curr for curr in target_currencies if curr not in rates]
        if not missing_currencies:
            return rates
        
        # Try providers for missing rates
        for provider in self.provider_priority:
            try:
                provider_rates = await self.providers[provider](base_currency)
                if provider_rates:
                    for currency in missing_currencies:
                        if currency in provider_rates:
                            rate = Decimal(str(provider_rates[currency]))
                            rates[currency] = rate
                            
                            # Cache individual rate
                            await self._cache_rate(base_currency, currency, rate)
                    
                    # Remove found currencies from missing list
                    missing_currencies = [curr for curr in missing_currencies if curr not in rates]
                    
                    if not missing_currencies:
                        break
                        
            except Exception as e:
                logger.warning(f"Provider {provider.value} failed for multiple rates: {e}")
                continue
        
        return rates
    
    async def convert_amount(self, amount: Decimal, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """Convert amount from one currency to another"""
        if from_currency == to_currency:
            return amount
        
        rate = await self.get_exchange_rate(from_currency, to_currency)
        if rate:
            return amount * rate
        
        return None
    
    async def get_supported_currencies(self) -> List[str]:
        """Get list of supported currencies"""
        return self.supported_currencies.copy()
    
    async def get_rate_history(self, from_currency: str, to_currency: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get historical exchange rates (simplified implementation)"""
        history = []
        
        if self.redis_client:
            try:
                # Get historical data from cache
                for i in range(days):
                    date = datetime.now() - timedelta(days=i)
                    cache_key = f"rate_history:{from_currency}:{to_currency}:{date.strftime('%Y-%m-%d')}"
                    cached_data = await self.redis_client.get(cache_key)
                    
                    if cached_data:
                        history.append(json.loads(cached_data))
                
            except Exception as e:
                logger.error(f"Failed to get rate history: {e}")
        
        # If no historical data, return current rate
        if not history:
            current_rate = await self.get_exchange_rate(from_currency, to_currency)
            if current_rate:
                history.append({
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'rate': float(current_rate),
                    'from_currency': from_currency,
                    'to_currency': to_currency
                })
        
        return history
    
    async def _get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """Get cached exchange rate"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"exchange_rate:{from_currency}:{to_currency}"
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                cached_time = datetime.fromisoformat(data['timestamp'])
                
                # Check if cache is still valid
                if datetime.now() - cached_time < timedelta(seconds=self.cache_ttl):
                    return Decimal(str(data['rate']))
                else:
                    # Remove expired cache
                    await self.redis_client.delete(cache_key)
                    
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None
    
    async def _cache_rate(self, from_currency: str, to_currency: str, rate: Decimal):
        """Cache exchange rate"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"exchange_rate:{from_currency}:{to_currency}"
            cache_data = {
                'rate': float(rate),
                'timestamp': datetime.now().isoformat(),
                'from_currency': from_currency,
                'to_currency': to_currency
            }
            
            await self.redis_client.setex(
                cache_key, 
                self.cache_ttl, 
                json.dumps(cache_data)
            )
            
            # Also cache historical data
            history_key = f"rate_history:{from_currency}:{to_currency}:{datetime.now().strftime('%Y-%m-%d')}"
            await self.redis_client.setex(
                history_key,
                86400 * 30,  # Keep history for 30 days
                json.dumps(cache_data)
            )
            
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
    
    async def _get_multiple_cached_rates(self, base_currency: str, target_currencies: List[str]) -> Dict[str, Decimal]:
        """Get multiple cached rates"""
        rates = {}
        
        if not self.redis_client:
            return rates
        
        try:
            # Build cache keys
            cache_keys = [f"exchange_rate:{base_currency}:{curr}" for curr in target_currencies]
            
            # Get all cached data
            cached_data = await self.redis_client.mget(cache_keys)
            
            for i, data in enumerate(cached_data):
                if data:
                    try:
                        parsed_data = json.loads(data)
                        cached_time = datetime.fromisoformat(parsed_data['timestamp'])
                        
                        # Check if cache is still valid
                        if datetime.now() - cached_time < timedelta(seconds=self.cache_ttl):
                            rates[target_currencies[i]] = Decimal(str(parsed_data['rate']))
                        
                    except Exception as e:
                        logger.warning(f"Error parsing cached rate: {e}")
                        
        except Exception as e:
            logger.warning(f"Multiple cache read error: {e}")
        
        return rates
    
    # Provider implementations
    async def _get_fixer_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get rates from Fixer.io API"""
        api_key = os.getenv("FIXER_API_KEY")
        if not api_key:
            raise ValueError("Fixer API key not configured")
        
        url = f"http://data.fixer.io/api/latest"
        params = {
            'access_key': api_key,
            'base': base_currency,
            'symbols': ','.join(self.supported_currencies)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('rates', {})
                    else:
                        raise ValueError(f"Fixer API error: {data.get('error', {}).get('info', 'Unknown error')}")
                else:
                    raise ValueError(f"Fixer API HTTP error: {response.status}")
    
    async def _get_currencylayer_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get rates from CurrencyLayer API"""
        api_key = os.getenv("CURRENCYLAYER_API_KEY")
        if not api_key:
            raise ValueError("CurrencyLayer API key not configured")
        
        url = "http://api.currencylayer.com/live"
        params = {
            'access_key': api_key,
            'source': base_currency,
            'currencies': ','.join(self.supported_currencies)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        # CurrencyLayer returns rates with source prefix (e.g., USDEUR)
                        quotes = data.get('quotes', {})
                        rates = {}
                        for key, value in quotes.items():
                            if key.startswith(base_currency):
                                target_currency = key[len(base_currency):]
                                rates[target_currency] = value
                        return rates
                    else:
                        raise ValueError(f"CurrencyLayer API error: {data.get('error', {}).get('info', 'Unknown error')}")
                else:
                    raise ValueError(f"CurrencyLayer API HTTP error: {response.status}")
    
    async def _get_openexchangerates_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get rates from OpenExchangeRates API"""
        api_key = os.getenv("OPENEXCHANGERATES_API_KEY")
        if not api_key:
            raise ValueError("OpenExchangeRates API key not configured")
        
        url = "https://openexchangerates.org/api/latest.json"
        params = {
            'app_id': api_key,
            'base': base_currency,
            'symbols': ','.join(self.supported_currencies)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('rates', {})
                else:
                    raise ValueError(f"OpenExchangeRates API HTTP error: {response.status}")
    
    async def _get_exchangerate_api_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get rates from ExchangeRate-API"""
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('rates', {})
                else:
                    raise ValueError(f"ExchangeRate-API HTTP error: {response.status}")
    
    async def _get_fallback_rates(self, base_currency: str) -> Optional[Dict[str, float]]:
        """Get cached fallback exchange rates when all live providers are unavailable.
        Uses the last known rates from Redis cache. If no cached rates exist,
        raises an error rather than returning hardcoded values."""
        logger.warning(f"All live exchange rate providers failed - using cached fallback for {base_currency}")
        if self.redis_client:
            try:
                pattern = f"exchange_rate:{base_currency}:*"
                keys = []
                async for key in self.redis_client.scan_iter(match=pattern):
                    keys.append(key)
                if keys:
                    rates = {}
                    for key in keys:
                        target = key.split(':')[-1]
                        cached_data = await self.redis_client.get(key)
                        if cached_data:
                            data = json.loads(cached_data)
                            rates[target] = data.get('rate', 0)
                    if rates:
                        logger.info(f"Returning {len(rates)} cached fallback rates for {base_currency}")
                        return rates
            except Exception as e:
                logger.error(f"Fallback cache lookup failed: {e}")
        logger.error(f"No cached rates available for {base_currency} - all providers down")
        return None
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of exchange rate service"""
        status = {
            'service': 'exchange_rate_service',
            'status': 'healthy',
            'cache_available': self.redis_client is not None,
            'supported_currencies': len(self.supported_currencies),
            'providers': []
        }
        
        # Test each provider
        for provider in self.provider_priority:
            provider_status = {
                'name': provider.value,
                'available': False,
                'error': None
            }
            
            try:
                # Quick test with USD to EUR
                rates = await self.providers[provider]('USD')
                if rates and 'EUR' in rates:
                    provider_status['available'] = True
            except Exception as e:
                provider_status['error'] = str(e)
            
            status['providers'].append(provider_status)
        
        return status
