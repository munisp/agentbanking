"""
KYB Screening Services - Real Implementations
Provides actual integrations for sanctions, adverse media, and PEP screening.
Calls real HTTP APIs for OFAC, UN, EU sanctions lists with retry and fallback.

FAIL-CLOSED CONTRACT: when a screening provider is unreachable or not
configured, these services raise ScreeningUnavailableError instead of
returning an empty (clean-looking) result or fabricating hits from
keywords. Callers must treat ScreeningUnavailableError as
"screening_unavailable" and force manual review.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import httpx
import re

logger = logging.getLogger(__name__)

SCREENING_TIMEOUT = float(os.getenv("SCREENING_TIMEOUT_SECONDS", "10"))
SCREENING_MAX_RETRIES = int(os.getenv("SCREENING_MAX_RETRIES", "3"))


class ScreeningUnavailableError(Exception):
    """Raised when a screening provider cannot actually perform screening.
    Callers must force manual review; never treat as a clean pass."""
    pass


async def _http_get_with_retry(url: str, params: dict = None, headers: dict = None, max_retries: int = SCREENING_MAX_RETRIES) -> Optional[dict]:
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, headers=headers, timeout=SCREENING_TIMEOUT)
                if resp.status_code < 400:
                    return resp.json()
                logger.warning(f"Screening API {url} returned {resp.status_code} (attempt {attempt + 1})")
        except Exception as e:
            logger.warning(f"Screening API {url} failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return None


class SanctionsScreeningService:
    """
    Sanctions screening service calling real OFAC, UN, EU APIs.
    Raises ScreeningUnavailableError when a provider cannot be reached —
    never fabricates hits from country or name keywords.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.cache = {}
        self.cache_ttl = 3600

        self.ofac_endpoint = os.getenv(
            "OFAC_API_URL",
            self.config.get("ofac_endpoint", "https://sanctionslist.ofac.treas.gov/api/v1"),
        )
        self.ofac_api_key = os.getenv("OFAC_API_KEY", self.config.get("ofac_api_key", ""))
        self.un_endpoint = os.getenv(
            "UN_SANCTIONS_API_URL",
            self.config.get("un_endpoint", "https://scsanctions.un.org/api"),
        )
        self.eu_endpoint = os.getenv(
            "EU_SANCTIONS_API_URL",
            self.config.get("eu_endpoint", "https://webgate.ec.europa.eu/fsd/fsf/api"),
        )
        
    async def screen_entity(self, name: str, country: str, entity_type: str) -> List[Dict[str, Any]]:
        """
        Screen entity against multiple sanctions lists
        
        Args:
            name: Entity name to screen
            country: Country of entity
            entity_type: 'business' or 'individual'
            
        Returns:
            List of sanctions matches
            
        Raises:
            ScreeningUnavailableError: if any sanctions list provider could
                not actually be queried. Callers must force manual review.
        """
        # Check cache first
        cache_key = self._get_cache_key(name, country, entity_type)
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return cached_data
        
        hits = []
        
        try:
            # Screen against multiple lists in parallel
            tasks = [
                self._screen_ofac(name, country, entity_type),
                self._screen_un(name, country, entity_type),
                self._screen_eu(name, country, entity_type)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results; track provider failures
            failures = []
            for result in results:
                if isinstance(result, list):
                    hits.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Screening error: {result}")
                    failures.append(result)
            
            # Fail closed: an unscreened list must never look like a clean
            # pass feeding an auto-APPROVED decision.
            if failures:
                raise ScreeningUnavailableError(
                    f"Sanctions screening incomplete: {len(failures)} provider(s) "
                    f"unavailable (first error: {failures[0]}); manual review required"
                )
            
            # Cache results (only real, complete screening results)
            self.cache[cache_key] = (hits, datetime.now())
            
            return hits
            
        except ScreeningUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Sanctions screening failed: {e}")
            raise ScreeningUnavailableError(
                f"Sanctions screening failed: {e}; manual review required"
            ) from e
    
    async def _screen_ofac(self, name: str, country: str, entity_type: str) -> List[Dict[str, Any]]:
        """Screen against OFAC SDN list via real API (raises when unavailable)"""
        hits = []

        headers = {}
        if self.ofac_api_key:
            headers["Authorization"] = f"Bearer {self.ofac_api_key}"

        api_result = await _http_get_with_retry(
            f"{self.ofac_endpoint}/search",
            params={"name": name, "country": country, "type": entity_type},
            headers=headers,
        )

        if api_result is None:
            raise ScreeningUnavailableError("OFAC API unreachable after retries")

        for entry in api_result.get("results") or []:
            hits.append({
                "list_name": "OFAC SDN",
                "match_strength": entry.get("score", 0.0),
                "entity_name": name,
                "list_entry": entry.get("matched_name", ""),
                "country": country,
                "reason": entry.get("program", "OFAC match"),
                "list_url": "https://sanctionslist.ofac.treas.gov/",
                "screened_at": datetime.utcnow().isoformat(),
            })

        return hits
    
    async def _screen_un(self, name: str, country: str, entity_type: str) -> List[Dict[str, Any]]:
        """Screen against UN Consolidated List via real API (raises when unavailable)"""
        hits = []

        api_result = await _http_get_with_retry(
            f"{self.un_endpoint}/search",
            params={"name": name, "country": country},
        )

        if api_result is None:
            raise ScreeningUnavailableError("UN sanctions API unreachable after retries")

        for entry in api_result.get("results") or []:
            hits.append({
                "list_name": "UN Consolidated List",
                "match_strength": entry.get("score", 0.0),
                "entity_name": name,
                "list_entry": entry.get("matched_name", ""),
                "country": country,
                "reason": entry.get("regime", "UN Security Council sanctions"),
                "list_url": "https://www.un.org/securitycouncil/sanctions/",
                "screened_at": datetime.utcnow().isoformat(),
            })

        return hits
    
    async def _screen_eu(self, name: str, country: str, entity_type: str) -> List[Dict[str, Any]]:
        """Screen against EU Consolidated List via real API (raises when unavailable)"""
        hits = []

        api_result = await _http_get_with_retry(
            f"{self.eu_endpoint}/search",
            params={"searchKey": name, "country": country},
        )

        if api_result is None:
            raise ScreeningUnavailableError("EU sanctions API unreachable after retries")

        for entry in api_result.get("results") or []:
            hits.append({
                "list_name": "EU Consolidated List",
                "match_strength": entry.get("score", 0.0),
                "entity_name": name,
                "list_entry": entry.get("matched_name", ""),
                "country": country,
                "reason": entry.get("regulation", "EU restrictive measures"),
                "list_url": "https://www.sanctionsmap.eu/",
                "screened_at": datetime.utcnow().isoformat(),
            })

        return hits
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for matching"""
        return re.sub(r'[^a-z0-9\s]', '', name.lower().strip())
    
    def _calculate_fuzzy_match(self, name1: str, name2: str) -> float:
        """Calculate fuzzy match score between two names"""
        # Simple Levenshtein-based similarity
        from difflib import SequenceMatcher
        return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
    
    def _get_cache_key(self, name: str, country: str, entity_type: str) -> str:
        """Generate cache key"""
        key_str = f"{name}:{country}:{entity_type}"
        return hashlib.sha256(key_str.encode()).hexdigest()


class AdverseMediaScreeningService:
    """
    Adverse media screening via a real news provider (NewsAPI-compatible).
    Raises ScreeningUnavailableError when no provider is configured or the
    provider is unreachable — never fabricates news articles.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.news_api_key = os.getenv("NEWS_API_KEY", self.config.get('news_api_key', ''))
        self.news_api_url = os.getenv(
            "NEWS_API_URL",
            self.config.get('news_api_url', 'https://newsapi.org/v2/everything')
        )
        self.cache = {}
        self.cache_ttl = 7200  # 2 hours
    
    async def screen_entity(self, name: str, entity_type: str) -> List[Dict[str, Any]]:
        """
        Screen for adverse media mentions
        
        Args:
            name: Entity name
            entity_type: 'business' or 'individual'
            
        Returns:
            List of adverse media articles
            
        Raises:
            ScreeningUnavailableError: if no news provider is configured or
                the provider cannot be reached. Callers must force manual
                review.
        """
        # Check cache
        cache_key = hashlib.sha256(f"{name}:{entity_type}".encode()).hexdigest()
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return cached_data
        
        # Search for adverse keywords
        adverse_keywords = [
            'fraud', 'scam', 'investigation', 'lawsuit', 'criminal',
            'corruption', 'bribery', 'money laundering', 'embezzlement',
            'sanctions', 'penalty', 'fine', 'violation', 'misconduct'
        ]
        
        # Build search query
        query = f'"{name}" AND ({" OR ".join(adverse_keywords)})'
        
        # Search news sources (raises when unavailable)
        articles = await self._search_news_sources(query, name, entity_type)
        
        # Cache results (only real provider results)
        self.cache[cache_key] = (articles, datetime.now())
        
        return articles
    
    async def _search_news_sources(self, query: str, name: str, entity_type: str) -> List[Dict[str, Any]]:
        """Search the configured news provider for real articles"""
        if not self.news_api_key:
            raise ScreeningUnavailableError(
                "Adverse media provider not configured (NEWS_API_KEY missing); "
                "manual review required"
            )
        
        result = await _http_get_with_retry(
            self.news_api_url,
            params={
                "q": query,
                "apiKey": self.news_api_key,
                "language": "en",
                "sortBy": "relevancy",
                "pageSize": 20,
            },
        )
        
        if result is None:
            raise ScreeningUnavailableError(
                "Adverse media provider unreachable after retries; manual review required"
            )
        
        articles = []
        for article in result.get("articles") or []:
            articles.append({
                "title": article.get("title"),
                "source": (article.get("source") or {}).get("name"),
                "date": article.get("publishedAt"),
                "relevance_score": None,
                "sentiment": None,
                "summary": article.get("description"),
                "url": article.get("url"),
                "keywords": [],
            })
        
        return articles


class PEPScreeningService:
    """
    Politically Exposed Persons screening via a real PEP data provider.
    Raises ScreeningUnavailableError when no provider is configured — never
    guesses PEP status from name substrings.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.pep_api_url = os.getenv("PEP_API_URL", self.config.get('pep_api_url', ''))
        self.pep_api_key = os.getenv("PEP_API_KEY", self.config.get('pep_api_key', ''))
        self.cache = {}
        self.cache_ttl = 86400  # 24 hours
    
    async def check_pep_status(self, name: str, nationality: str) -> Dict[str, Any]:
        """
        Check if person is politically exposed
        
        Args:
            name: Person's full name
            nationality: Person's nationality
            
        Returns:
            PEP status and details from the real provider
            
        Raises:
            ScreeningUnavailableError: if no PEP provider is configured or
                reachable. Callers must force manual review.
        """
        # Check cache
        cache_key = hashlib.sha256(f"{name}:{nationality}".encode()).hexdigest()
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self.cache_ttl:
                return cached_data
        
        if not self.pep_api_url:
            raise ScreeningUnavailableError(
                "PEP screening provider not configured (PEP_API_URL missing); "
                "manual review required"
            )
        
        headers = {}
        if self.pep_api_key:
            headers["Authorization"] = f"Bearer {self.pep_api_key}"
        
        api_result = await _http_get_with_retry(
            f"{self.pep_api_url.rstrip('/')}/search",
            params={"name": name, "nationality": nationality},
            headers=headers,
        )
        
        if api_result is None:
            raise ScreeningUnavailableError(
                "PEP screening provider unreachable after retries; manual review required"
            )
        
        result = {
            "is_pep": bool(api_result.get("is_pep")),
            "details": api_result.get("details") or {},
        }
        
        # Cache result (only real provider results)
        self.cache[cache_key] = (result, datetime.now())
        
        return result
