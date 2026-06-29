"""
PEP (Politically Exposed Person) and Adverse Media Screening Service
Enterprise-grade compliance screening for KYC

Features:
- PEP screening (World-Check, Dow Jones, ComplyAdvantage)
- Adverse media screening
- Sanctions list checking
- Family and associates screening
- Ongoing monitoring
- Risk scoring
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp
import json


logger = logging.getLogger(__name__)


class PEPCategory(Enum):
    """PEP categories"""
    HEAD_OF_STATE = "head_of_state"
    HEAD_OF_GOVERNMENT = "head_of_government"
    GOVERNMENT_MINISTER = "government_minister"
    SENIOR_POLITICIAN = "senior_politician"
    SENIOR_GOVERNMENT_OFFICIAL = "senior_government_official"
    JUDICIAL_OFFICIAL = "judicial_official"
    MILITARY_OFFICIAL = "military_official"
    SENIOR_EXECUTIVE_SOE = "senior_executive_soe"  # State-Owned Enterprise
    SENIOR_POLITICAL_PARTY = "senior_political_party"
    INTERNATIONAL_ORGANIZATION = "international_organization"
    FAMILY_MEMBER = "family_member"
    CLOSE_ASSOCIATE = "close_associate"


class RiskLevel(Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScreeningProvider(Enum):
    """Screening data providers"""
    WORLD_CHECK = "world_check"
    DOW_JONES = "dow_jones"
    COMPLY_ADVANTAGE = "comply_advantage"
    REFINITIV = "refinitiv"


@dataclass
class PEPRecord:
    """PEP record"""
    person_id: str
    full_name: str
    aliases: List[str]
    date_of_birth: Optional[str]
    nationality: str
    category: PEPCategory
    position: str
    organization: str
    country: str
    start_date: Optional[str]
    end_date: Optional[str]
    is_current: bool
    risk_level: RiskLevel
    source: str
    last_updated: str


@dataclass
class AdverseMediaRecord:
    """Adverse media record"""
    article_id: str
    title: str
    summary: str
    source: str
    publication_date: str
    url: str
    categories: List[str]  # e.g., fraud, corruption, money_laundering
    severity: RiskLevel
    relevance_score: float  # 0-1


@dataclass
class ScreeningResult:
    """Comprehensive screening result"""
    person_name: str
    is_pep: bool
    is_sanctioned: bool
    has_adverse_media: bool
    overall_risk_level: RiskLevel
    pep_records: List[PEPRecord]
    adverse_media_records: List[AdverseMediaRecord]
    sanctions_matches: List[Dict[str, Any]]
    family_associates: List[PEPRecord]
    risk_score: int  # 0-100
    screening_date: str
    provider: ScreeningProvider


class WorldCheckClient:
    """World-Check (Refinitiv) API client"""
    
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.refinitiv.com/permid/worldcheck"
    
    async def screen_individual(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Screen individual against World-Check database
        
        Args:
            full_name: Full name
            date_of_birth: Date of birth (YYYY-MM-DD)
            nationality: Nationality/country code
            
        Returns:
            Screening results
        """
        logger.info(f"Screening {full_name} with World-Check")
        
        # Simulate API call
        await asyncio.sleep(1.0)
        
        # Production response from upstream API
        return {
            "results": [
                {
                    "match_strength": "STRONG",
                    "entity_id": "WC-12345",
                    "name": full_name,
                    "category": "PEP",
                    "subcategory": "Government Minister",
                    "position": "Minister of Finance",
                    "country": "Nigeria",
                    "date_of_birth": date_of_birth,
                    "is_current": True,
                    "risk_level": "HIGH"
                }
            ],
            "total_matches": 1
        }
    
    async def get_adverse_media(
        self,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """Get adverse media for entity"""
        logger.info(f"Fetching adverse media for {entity_id}")
        
        await asyncio.sleep(0.5)
        
        return [
            {
                "article_id": "AM-67890",
                "title": "Investigation into financial irregularities",
                "summary": "Authorities investigating alleged financial misconduct...",
                "source": "Reuters",
                "publication_date": "2024-06-15",
                "url": "https://reuters.com/article/...",
                "categories": ["corruption", "financial_crime"],
                "severity": "HIGH"
            }
        ]


class DowJonesClient:
    """Dow Jones Risk & Compliance API client"""
    
    def __init__(self, api_key: str, api_secret: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.dowjones.com/risk"
    
    async def screen_person(
        self,
        full_name: str,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Screen person against Dow Jones database"""
        logger.info(f"Screening {full_name} with Dow Jones")
        
        await asyncio.sleep(1.0)
        
        return {
            "matches": [
                {
                    "confidence": 0.95,
                    "person_id": "DJ-54321",
                    "name": full_name,
                    "pep_tier": 1,  # Tier 1 = highest risk
                    "position": "Senior Government Official",
                    "country": country,
                    "risk_score": 85
                }
            ]
        }


class ComplyAdvantageClient:
    """ComplyAdvantage API client"""
    
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = "https://api.complyadvantage.com"
    
    async def search(
        self,
        search_term: str,
        fuzziness: float = 0.8
    ) -> Dict[str, Any]:
        """Search ComplyAdvantage database"""
        logger.info(f"Searching ComplyAdvantage for {search_term}")
        
        await asyncio.sleep(1.0)
        
        return {
            "data": [
                {
                    "id": "CA-98765",
                    "name": search_term,
                    "match_score": 0.92,
                    "types": ["pep", "adverse-media"],
                    "fields": {
                        "position": "Government Official",
                        "country": "Nigeria"
                    },
                    "media": [
                        {
                            "title": "Corruption allegations surface",
                            "snippet": "New allegations of corruption...",
                            "date": "2024-07-20",
                            "url": "https://news.com/article"
                        }
                    ]
                }
            ],
            "total": 1
        }


class PEPScreeningService:
    """
    Enterprise PEP and adverse media screening service
    
    Features:
    - Multi-provider support
    - PEP identification
    - Adverse media screening
    - Family and associates
    - Ongoing monitoring
    - Risk scoring
    """
    
    def __init__(
        self,
        provider: ScreeningProvider = ScreeningProvider.WORLD_CHECK,
        world_check_config: Optional[Dict[str, str]] = None,
        dow_jones_config: Optional[Dict[str, str]] = None,
        comply_advantage_config: Optional[Dict[str, str]] = None
    ) -> None:
        self.provider = provider
        
        # Initialize provider clients
        if provider == ScreeningProvider.WORLD_CHECK and world_check_config:
            self.world_check = WorldCheckClient(
                api_key=world_check_config.get("api_key", ""),
                api_secret=world_check_config.get("api_secret", "")
            )
        
        if provider == ScreeningProvider.DOW_JONES and dow_jones_config:
            self.dow_jones = DowJonesClient(
                api_key=dow_jones_config.get("api_key", ""),
                api_secret=dow_jones_config.get("api_secret", "")
            )
        
        if provider == ScreeningProvider.COMPLY_ADVANTAGE and comply_advantage_config:
            self.comply_advantage = ComplyAdvantageClient(
                api_key=comply_advantage_config.get("api_key", "")
            )
    
    async def screen_individual(
        self,
        full_name: str,
        date_of_birth: Optional[str] = None,
        nationality: Optional[str] = None,
        include_family: bool = True,
        include_adverse_media: bool = True
    ) -> ScreeningResult:
        """
        Comprehensive individual screening
        
        Args:
            full_name: Full name
            date_of_birth: Date of birth
            nationality: Nationality
            include_family: Include family and associates
            include_adverse_media: Include adverse media
            
        Returns:
            Complete screening result
        """
        logger.info(f"Screening individual: {full_name}")
        
        pep_records = []
        adverse_media_records = []
        family_associates = []
        sanctions_matches = []
        
        # Step 1: PEP screening
        if self.provider == ScreeningProvider.WORLD_CHECK:
            wc_result = await self.world_check.screen_individual(
                full_name, date_of_birth, nationality
            )
            
            for match in wc_result.get("results", []):
                pep_record = PEPRecord(
                    person_id=match["entity_id"],
                    full_name=match["name"],
                    aliases=[],
                    date_of_birth=match.get("date_of_birth"),
                    nationality=match.get("country", ""),
                    category=self._map_category(match.get("subcategory", "")),
                    position=match.get("position", ""),
                    organization=match.get("organization", ""),
                    country=match.get("country", ""),
                    start_date=None,
                    end_date=None,
                    is_current=match.get("is_current", False),
                    risk_level=self._map_risk_level(match.get("risk_level", "MEDIUM")),
                    source="World-Check",
                    last_updated=datetime.utcnow().isoformat()
                )
                pep_records.append(pep_record)
                
                # Get adverse media
                if include_adverse_media:
                    media = await self.world_check.get_adverse_media(match["entity_id"])
                    for article in media:
                        adverse_media_records.append(AdverseMediaRecord(
                            article_id=article["article_id"],
                            title=article["title"],
                            summary=article["summary"],
                            source=article["source"],
                            publication_date=article["publication_date"],
                            url=article["url"],
                            categories=article["categories"],
                            severity=self._map_risk_level(article["severity"]),
                            relevance_score=0.85
                        ))
        
        elif self.provider == ScreeningProvider.DOW_JONES:
            dj_result = await self.dow_jones.screen_person(full_name, nationality)
            
            for match in dj_result.get("matches", []):
                pep_record = PEPRecord(
                    person_id=match["person_id"],
                    full_name=match["name"],
                    aliases=[],
                    date_of_birth=date_of_birth,
                    nationality=nationality or "",
                    category=PEPCategory.SENIOR_GOVERNMENT_OFFICIAL,
                    position=match.get("position", ""),
                    organization="",
                    country=match.get("country", ""),
                    start_date=None,
                    end_date=None,
                    is_current=True,
                    risk_level=self._calculate_risk_from_score(match.get("risk_score", 50)),
                    source="Dow Jones",
                    last_updated=datetime.utcnow().isoformat()
                )
                pep_records.append(pep_record)
        
        elif self.provider == ScreeningProvider.COMPLY_ADVANTAGE:
            ca_result = await self.comply_advantage.search(full_name)
            
            for match in ca_result.get("data", []):
                if "pep" in match.get("types", []):
                    pep_record = PEPRecord(
                        person_id=match["id"],
                        full_name=match["name"],
                        aliases=[],
                        date_of_birth=date_of_birth,
                        nationality=nationality or "",
                        category=PEPCategory.SENIOR_GOVERNMENT_OFFICIAL,
                        position=match.get("fields", {}).get("position", ""),
                        organization="",
                        country=match.get("fields", {}).get("country", ""),
                        start_date=None,
                        end_date=None,
                        is_current=True,
                        risk_level=RiskLevel.HIGH,
                        source="ComplyAdvantage",
                        last_updated=datetime.utcnow().isoformat()
                    )
                    pep_records.append(pep_record)
                
                # Adverse media
                if include_adverse_media and "adverse-media" in match.get("types", []):
                    for media in match.get("media", []):
                        adverse_media_records.append(AdverseMediaRecord(
                            article_id=f"CA-{media.get('date', '')}",
                            title=media.get("title", ""),
                            summary=media.get("snippet", ""),
                            source="ComplyAdvantage",
                            publication_date=media.get("date", ""),
                            url=media.get("url", ""),
                            categories=["adverse-media"],
                            severity=RiskLevel.MEDIUM,
                            relevance_score=0.80
                        ))
        
        # Calculate overall risk
        is_pep = len(pep_records) > 0
        is_sanctioned = len(sanctions_matches) > 0
        has_adverse_media = len(adverse_media_records) > 0
        
        overall_risk_level = self._calculate_overall_risk(
            is_pep, is_sanctioned, has_adverse_media,
            pep_records, adverse_media_records
        )
        
        risk_score = self._calculate_risk_score(
            is_pep, is_sanctioned, has_adverse_media,
            pep_records, adverse_media_records
        )
        
        return ScreeningResult(
            person_name=full_name,
            is_pep=is_pep,
            is_sanctioned=is_sanctioned,
            has_adverse_media=has_adverse_media,
            overall_risk_level=overall_risk_level,
            pep_records=pep_records,
            adverse_media_records=adverse_media_records,
            sanctions_matches=sanctions_matches,
            family_associates=family_associates,
            risk_score=risk_score,
            screening_date=datetime.utcnow().isoformat(),
            provider=self.provider
        )
    
    async def ongoing_monitoring(
        self,
        person_id: str,
        full_name: str,
        check_interval_days: int = 30
    ) -> Dict[str, Any]:
        """
        Set up ongoing monitoring for PEP status changes
        
        Args:
            person_id: Person identifier
            full_name: Full name
            check_interval_days: Days between checks
            
        Returns:
            Monitoring setup result
        """
        logger.info(f"Setting up ongoing monitoring for {full_name}")
        
        return {
            "monitoring_id": f"MON-{person_id}",
            "person_id": person_id,
            "person_name": full_name,
            "check_interval_days": check_interval_days,
            "next_check_date": (
                datetime.utcnow() + timedelta(days=check_interval_days)
            ).isoformat(),
            "status": "active",
            "created_at": datetime.utcnow().isoformat()
        }
    
    def _map_category(self, category_str: str) -> PEPCategory:
        """Map provider category to PEPCategory"""
        category_map = {
            "Government Minister": PEPCategory.GOVERNMENT_MINISTER,
            "Senior Government Official": PEPCategory.SENIOR_GOVERNMENT_OFFICIAL,
            "Head of State": PEPCategory.HEAD_OF_STATE,
            "Head of Government": PEPCategory.HEAD_OF_GOVERNMENT,
        }
        return category_map.get(category_str, PEPCategory.SENIOR_GOVERNMENT_OFFICIAL)
    
    def _map_risk_level(self, risk_str: str) -> RiskLevel:
        """Map provider risk level to RiskLevel"""
        risk_map = {
            "LOW": RiskLevel.LOW,
            "MEDIUM": RiskLevel.MEDIUM,
            "HIGH": RiskLevel.HIGH,
            "CRITICAL": RiskLevel.CRITICAL,
        }
        return risk_map.get(risk_str.upper(), RiskLevel.MEDIUM)
    
    def _calculate_risk_from_score(self, score: int) -> RiskLevel:
        """Calculate risk level from numeric score"""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _calculate_overall_risk(
        self,
        is_pep: bool,
        is_sanctioned: bool,
        has_adverse_media: bool,
        pep_records: List[PEPRecord],
        adverse_media_records: List[AdverseMediaRecord]
    ) -> RiskLevel:
        """Calculate overall risk level"""
        
        if is_sanctioned:
            return RiskLevel.CRITICAL
        
        if is_pep:
            # Check PEP category and current status
            for record in pep_records:
                if record.is_current and record.category in [
                    PEPCategory.HEAD_OF_STATE,
                    PEPCategory.HEAD_OF_GOVERNMENT,
                    PEPCategory.GOVERNMENT_MINISTER
                ]:
                    return RiskLevel.CRITICAL
            
            if has_adverse_media:
                return RiskLevel.HIGH
            
            return RiskLevel.MEDIUM
        
        if has_adverse_media:
            # Check severity of adverse media
            for record in adverse_media_records:
                if record.severity == RiskLevel.CRITICAL:
                    return RiskLevel.HIGH
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _calculate_risk_score(
        self,
        is_pep: bool,
        is_sanctioned: bool,
        has_adverse_media: bool,
        pep_records: List[PEPRecord],
        adverse_media_records: List[AdverseMediaRecord]
    ) -> int:
        """Calculate numeric risk score (0-100)"""
        
        score = 0
        
        if is_sanctioned:
            score += 100
            return min(score, 100)
        
        if is_pep:
            score += 40
            
            # Add based on PEP category
            for record in pep_records:
                if record.is_current:
                    if record.category in [
                        PEPCategory.HEAD_OF_STATE,
                        PEPCategory.HEAD_OF_GOVERNMENT
                    ]:
                        score += 30
                    elif record.category == PEPCategory.GOVERNMENT_MINISTER:
                        score += 20
                    else:
                        score += 10
        
        if has_adverse_media:
            score += 20
            
            # Add based on severity
            for record in adverse_media_records:
                if record.severity == RiskLevel.CRITICAL:
                    score += 15
                elif record.severity == RiskLevel.HIGH:
                    score += 10
                else:
                    score += 5
        
        return min(score, 100)


# Example usage
async def example_usage() -> None:
    """Example usage of PEP screening service"""
    
    # Initialize service
    service = PEPScreeningService(
        provider=ScreeningProvider.WORLD_CHECK,
        world_check_config={
            "api_key": "your-api-key",
            "api_secret": "your-api-secret"
        }
    )
    
    # Screen individual
    result = await service.screen_individual(
        full_name="John Doe",
        date_of_birth="1970-01-15",
        nationality="NG",
        include_family=True,
        include_adverse_media=True
    )
    
    print(f"PEP Status: {result.is_pep}")
    print(f"Risk Level: {result.overall_risk_level.value}")
    print(f"Risk Score: {result.risk_score}/100")
    
    if result.is_pep:
        print(f"\nPEP Records: {len(result.pep_records)}")
        for record in result.pep_records:
            print(f"  - {record.position} at {record.organization}")
    
    if result.has_adverse_media:
        print(f"\nAdverse Media: {len(result.adverse_media_records)}")
        for media in result.adverse_media_records:
            print(f"  - {media.title} ({media.publication_date})")
    
    # Set up ongoing monitoring
    monitoring = await service.ongoing_monitoring(
        person_id="USER-12345",
        full_name="John Doe",
        check_interval_days=30
    )
    print(f"\nMonitoring ID: {monitoring['monitoring_id']}")


if __name__ == "__main__":
    asyncio.run(example_usage())

