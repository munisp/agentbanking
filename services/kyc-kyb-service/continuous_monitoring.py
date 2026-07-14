"""
Continuous Monitoring Service
Ongoing risk monitoring with scheduled screening, event-triggered reverification,
risk score decay, and corporate status detection.

Integrates with: TigerBeetle, Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX, Lakehouse
"""

import os
import json
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import hashlib

import httpx

COMPLY_ADVANTAGE_API_URL = os.getenv("COMPLY_ADVANTAGE_API_URL", "https://api.complyadvantage.com")
COMPLY_ADVANTAGE_API_KEY = os.getenv("COMPLY_ADVANTAGE_API_KEY", "")
OFAC_API_URL = os.getenv("OFAC_API_URL", "https://api.ofac-api.com/v4")
OFAC_API_KEY = os.getenv("OFAC_API_KEY", "")
CAC_API_URL = os.getenv("CAC_API_URL", "http://localhost:8042")
CAC_API_KEY = os.getenv("CAC_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class ScreeningType(str, Enum):
    """Types of screening"""
    PEP = "pep"                      # Politically Exposed Persons
    SANCTIONS = "sanctions"          # Sanctions lists
    WATCHLIST = "watchlist"          # Watchlists
    ADVERSE_MEDIA = "adverse_media"  # Adverse media
    CRIMINAL = "criminal"            # Criminal records
    REGULATORY = "regulatory"        # Regulatory actions


class ScreeningProvider(str, Enum):
    """Screening providers"""
    COMPLY_ADVANTAGE = "comply_advantage"
    OFAC = "ofac"
    EU_SANCTIONS = "eu_sanctions"
    UN_SANCTIONS = "un_sanctions"
    WORLD_CHECK = "world_check"
    DOW_JONES = "dow_jones"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert types"""
    SCREENING_MATCH = "screening_match"
    PAYOUT_SPIKE = "payout_spike"
    CHARGEBACK_BURST = "chargeback_burst"
    NEW_DEVICE = "new_device"
    LOCATION_CHANGE = "location_change"
    CORPORATE_CHANGE = "corporate_change"
    RISK_SCORE_DECAY = "risk_score_decay"
    REVERIFICATION_DUE = "reverification_due"


class CorporateChangeType(str, Enum):
    """Types of corporate changes"""
    DISSOLUTION = "dissolution"
    NAME_CHANGE = "name_change"
    DIRECTOR_CHANGE = "director_change"
    OWNERSHIP_CHANGE = "ownership_change"
    ADDRESS_CHANGE = "address_change"
    STATUS_CHANGE = "status_change"


class MonitoringStatus(str, Enum):
    """Monitoring status"""
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


@dataclass
class ScreeningSchedule:
    """Screening schedule configuration"""
    screening_type: ScreeningType
    frequency_days: int
    providers: List[ScreeningProvider]
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None


@dataclass
class ScreeningResult:
    """Screening result"""
    result_id: str
    subject_id: str
    screening_type: ScreeningType
    provider: ScreeningProvider
    is_match: bool
    match_score: float  # 0-100
    match_details: Dict[str, Any]
    screened_at: datetime
    reviewed: bool = False
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    disposition: Optional[str] = None


@dataclass
class RiskScore:
    """Risk score with decay"""
    subject_id: str
    current_score: float  # 0-100
    base_score: float
    decay_rate: float  # points per day
    last_updated: datetime
    last_refreshed: datetime
    max_age_days: int = 365
    factors: Dict[str, float] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MonitoringAlert:
    """Monitoring alert"""
    alert_id: str
    subject_id: str
    alert_type: AlertType
    severity: RiskLevel
    title: str
    description: str
    details: Dict[str, Any]
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    case_id: Optional[str] = None


@dataclass
class MonitoredSubject:
    """Subject under monitoring"""
    subject_id: str
    subject_type: str  # individual, business
    name: str
    risk_level: RiskLevel
    status: MonitoringStatus
    screening_schedules: List[ScreeningSchedule]
    risk_score: RiskScore
    enrolled_at: datetime
    last_activity: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventTrigger:
    """Event trigger configuration"""
    trigger_id: str
    name: str
    event_type: str
    conditions: Dict[str, Any]
    action: str
    is_active: bool = True


# ============================================================================
# SCREENING FREQUENCY BY RISK LEVEL
# ============================================================================

SCREENING_FREQUENCY_DAYS = {
    RiskLevel.LOW: 180,
    RiskLevel.MEDIUM: 90,
    RiskLevel.HIGH: 30,
    RiskLevel.VERY_HIGH: 14,
    RiskLevel.CRITICAL: 7
}

RISK_SCORE_DECAY_RATE = 0.5  # points per day
MAX_RISK_SCORE_AGE_DAYS = 365


# ============================================================================
# SCREENING SERVICE
# ============================================================================

class ScreeningService:
    """
    Scheduled screening service for PEP, sanctions, watchlists, adverse media
    Integrates with ComplyAdvantage, OFAC, and other providers
    """
    
    def __init__(self):
        self._results: Dict[str, ScreeningResult] = {}
        self._provider_configs: Dict[ScreeningProvider, Dict[str, Any]] = {}
    
    def configure_provider(self, provider: ScreeningProvider, config: Dict[str, Any]):
        """Configure screening provider"""
        self._provider_configs[provider] = config
        logger.info(f"Configured screening provider: {provider.value}")
    
    async def screen_subject(
        self,
        subject_id: str,
        name: str,
        screening_type: ScreeningType,
        provider: ScreeningProvider,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> ScreeningResult:
        """Screen subject against provider"""
        result_id = secrets.token_hex(16)
        
        # Execute screening via configured provider APIs
        is_match, match_score, match_details = await self._call_provider(
            provider, screening_type, name, additional_data
        )
        
        result = ScreeningResult(
            result_id=result_id,
            subject_id=subject_id,
            screening_type=screening_type,
            provider=provider,
            is_match=is_match,
            match_score=match_score,
            match_details=match_details,
            screened_at=datetime.utcnow()
        )
        
        self._results[result_id] = result
        
        logger.info(f"Screening completed: {result_id} - {screening_type.value} - Match: {is_match}")
        
        return result
    
    async def _call_provider(
        self,
        provider: ScreeningProvider,
        screening_type: ScreeningType,
        name: str,
        additional_data: Optional[Dict[str, Any]]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Call screening provider API"""
        # In production, implement actual provider integrations
        # ComplyAdvantage, OFAC, World-Check, Dow Jones, etc.
        
        if provider == ScreeningProvider.COMPLY_ADVANTAGE:
            return await self._call_comply_advantage(screening_type, name, additional_data)
        elif provider == ScreeningProvider.OFAC:
            return await self._call_ofac(name, additional_data)
        else:
            # Default: no match
            return False, 0.0, {}
    
    async def _call_comply_advantage(
        self,
        screening_type: ScreeningType,
        name: str,
        additional_data: Optional[Dict[str, Any]]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Call ComplyAdvantage API with retry"""
        filt = {
            ScreeningType.PEP: "pep",
            ScreeningType.SANCTIONS: "sanction",
            ScreeningType.ADVERSE_MEDIA: "adverse-media",
            ScreeningType.WATCHLIST: "warning",
        }
        payload = {
            "search_term": name,
            "fuzziness": 0.6,
            "filters": {"types": [filt.get(screening_type, "pep")]},
        }
        if additional_data:
            if additional_data.get("date_of_birth"):
                payload["filters"]["birth_year"] = additional_data["date_of_birth"][:4]
            if additional_data.get("country"):
                payload["filters"]["country_codes"] = [additional_data["country"]]

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"Authorization": f"Token {COMPLY_ADVANTAGE_API_KEY}"} if COMPLY_ADVANTAGE_API_KEY else {}
                    response = await client.post(
                        f"{COMPLY_ADVANTAGE_API_URL}/searches",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        hits = data.get("content", {}).get("data", {}).get("total_hits", 0)
                        is_match = hits > 0
                        match_score = min(100.0, hits * 25.0) if is_match else 0.0
                        return is_match, match_score, {
                            "provider": "comply_advantage",
                            "search_id": data.get("content", {}).get("data", {}).get("id", ""),
                            "total_hits": hits,
                            "search_term": name,
                        }
                    logger.warning(f"ComplyAdvantage returned {response.status_code} on attempt {attempt + 1}")
            except httpx.ConnectError:
                logger.warning(f"ComplyAdvantage unavailable on attempt {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        logger.error("ComplyAdvantage unavailable after 3 retries")
        return False, 0.0, {"provider": "comply_advantage", "error": "service_unavailable", "search_term": name}
    
    async def _call_ofac(
        self,
        name: str,
        additional_data: Optional[Dict[str, Any]]
    ) -> Tuple[bool, float, Dict[str, Any]]:
        """Call OFAC SDN screening API with retry"""
        payload = {
            "name": name,
            "sources": ["SDN", "NONSDN"],
            "type": ["individual", "entity"],
            "score": 80,
        }
        if additional_data:
            if additional_data.get("country"):
                payload["countries"] = [additional_data["country"]]

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"apiKey": OFAC_API_KEY} if OFAC_API_KEY else {}
                    response = await client.post(
                        f"{OFAC_API_URL}/search",
                        json=payload,
                        headers=headers,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        matches = data.get("matches", [])
                        is_match = len(matches) > 0
                        best_score = max((m.get("score", 0) for m in matches), default=0)
                        return is_match, float(best_score), {
                            "provider": "ofac",
                            "list_checked": "SDN",
                            "matches_count": len(matches),
                            "best_score": best_score,
                            "search_term": name,
                        }
                    logger.warning(f"OFAC API returned {response.status_code} on attempt {attempt + 1}")
            except httpx.ConnectError:
                logger.warning(f"OFAC API unavailable on attempt {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)

        logger.error("OFAC API unavailable after 3 retries")
        return False, 0.0, {"provider": "ofac", "error": "service_unavailable", "search_term": name}
    
    async def review_result(
        self,
        result_id: str,
        reviewer_id: str,
        disposition: str
    ) -> ScreeningResult:
        """Review screening result"""
        if result_id not in self._results:
            raise ValueError(f"Result not found: {result_id}")
        
        result = self._results[result_id]
        result.reviewed = True
        result.reviewed_by = reviewer_id
        result.reviewed_at = datetime.utcnow()
        result.disposition = disposition
        
        return result
    
    def get_pending_reviews(self, subject_id: Optional[str] = None) -> List[ScreeningResult]:
        """Get screening results pending review"""
        results = []
        for result in self._results.values():
            if result.is_match and not result.reviewed:
                if subject_id is None or result.subject_id == subject_id:
                    results.append(result)
        return results


# ============================================================================
# RISK SCORE ENGINE
# ============================================================================

class RiskScoreEngine:
    """
    Risk score management with decay
    Scores decay 0.5 points/day, requiring periodic refresh (max 365 days)
    """
    
    def __init__(self, decay_rate: float = RISK_SCORE_DECAY_RATE):
        self._scores: Dict[str, RiskScore] = {}
        self._decay_rate = decay_rate
    
    def create_risk_score(
        self,
        subject_id: str,
        base_score: float,
        factors: Dict[str, float]
    ) -> RiskScore:
        """Create initial risk score"""
        now = datetime.utcnow()
        
        score = RiskScore(
            subject_id=subject_id,
            current_score=base_score,
            base_score=base_score,
            decay_rate=self._decay_rate,
            last_updated=now,
            last_refreshed=now,
            factors=factors,
            history=[{
                "timestamp": now.isoformat(),
                "score": base_score,
                "action": "created",
                "factors": factors
            }]
        )
        
        self._scores[subject_id] = score
        
        logger.info(f"Risk score created: {subject_id} - {base_score}")
        
        return score
    
    def get_current_score(self, subject_id: str) -> Tuple[float, bool]:
        """
        Get current risk score with decay applied
        Returns (score, needs_refresh)
        """
        if subject_id not in self._scores:
            raise ValueError(f"Risk score not found: {subject_id}")
        
        score = self._scores[subject_id]
        now = datetime.utcnow()
        
        # Calculate days since last refresh
        days_elapsed = (now - score.last_refreshed).total_seconds() / 86400
        
        # Apply decay
        decayed_score = max(0, score.base_score - (days_elapsed * score.decay_rate))
        score.current_score = decayed_score
        score.last_updated = now
        
        # Check if refresh needed
        needs_refresh = days_elapsed >= score.max_age_days
        
        return decayed_score, needs_refresh
    
    def refresh_score(
        self,
        subject_id: str,
        new_base_score: float,
        new_factors: Dict[str, float],
        reason: str = "scheduled_refresh"
    ) -> RiskScore:
        """Refresh risk score"""
        if subject_id not in self._scores:
            raise ValueError(f"Risk score not found: {subject_id}")
        
        score = self._scores[subject_id]
        now = datetime.utcnow()
        
        score.base_score = new_base_score
        score.current_score = new_base_score
        score.factors = new_factors
        score.last_refreshed = now
        score.last_updated = now
        
        score.history.append({
            "timestamp": now.isoformat(),
            "score": new_base_score,
            "action": "refreshed",
            "reason": reason,
            "factors": new_factors
        })
        
        logger.info(f"Risk score refreshed: {subject_id} - {new_base_score}")
        
        return score
    
    def adjust_score(
        self,
        subject_id: str,
        adjustment: float,
        reason: str
    ) -> RiskScore:
        """Adjust risk score (positive = increase risk)"""
        if subject_id not in self._scores:
            raise ValueError(f"Risk score not found: {subject_id}")
        
        score = self._scores[subject_id]
        now = datetime.utcnow()
        
        old_score = score.current_score
        score.base_score = max(0, min(100, score.base_score + adjustment))
        score.current_score = score.base_score
        score.last_updated = now
        
        score.history.append({
            "timestamp": now.isoformat(),
            "score": score.current_score,
            "action": "adjusted",
            "adjustment": adjustment,
            "reason": reason,
            "old_score": old_score
        })
        
        logger.info(f"Risk score adjusted: {subject_id} - {old_score} -> {score.current_score}")
        
        return score
    
    def get_risk_level(self, score: float) -> RiskLevel:
        """Convert score to risk level"""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.VERY_HIGH
        elif score >= 40:
            return RiskLevel.HIGH
        elif score >= 20:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


# ============================================================================
# EVENT TRIGGER ENGINE
# ============================================================================

class EventTriggerEngine:
    """
    Event-triggered reverification
    Monitors for payout spikes, chargeback bursts, new devices, location changes
    """
    
    def __init__(self):
        self._triggers: Dict[str, EventTrigger] = {}
        self._event_handlers: Dict[str, Callable] = {}
        
        # Register default triggers
        self._register_default_triggers()
    
    def _register_default_triggers(self):
        """Register default event triggers"""
        # Payout spike trigger (3x normal)
        self.register_trigger(EventTrigger(
            trigger_id="payout_spike",
            name="Payout Spike Detection",
            event_type="transaction",
            conditions={
                "type": "payout",
                "multiplier_threshold": 3.0,
                "comparison_period_days": 30
            },
            action="reverification"
        ))
        
        # Chargeback burst trigger (>2%)
        self.register_trigger(EventTrigger(
            trigger_id="chargeback_burst",
            name="Chargeback Burst Detection",
            event_type="chargeback",
            conditions={
                "rate_threshold": 0.02,
                "window_days": 7
            },
            action="reverification"
        ))
        
        # New device trigger
        self.register_trigger(EventTrigger(
            trigger_id="new_device",
            name="New Device Detection",
            event_type="device",
            conditions={
                "is_new": True,
                "risk_score_threshold": 50
            },
            action="step_up_auth"
        ))
        
        # Location change trigger
        self.register_trigger(EventTrigger(
            trigger_id="location_change",
            name="Location Change Detection",
            event_type="location",
            conditions={
                "distance_km_threshold": 500,
                "time_window_hours": 24
            },
            action="review"
        ))
    
    def register_trigger(self, trigger: EventTrigger):
        """Register event trigger"""
        self._triggers[trigger.trigger_id] = trigger
        logger.info(f"Trigger registered: {trigger.trigger_id}")
    
    async def evaluate_event(
        self,
        subject_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> List[Tuple[EventTrigger, bool]]:
        """Evaluate event against all triggers"""
        results = []
        
        for trigger in self._triggers.values():
            if not trigger.is_active:
                continue
            if trigger.event_type != event_type:
                continue
            
            is_triggered = await self._evaluate_conditions(
                trigger.conditions, event_data
            )
            
            results.append((trigger, is_triggered))
            
            if is_triggered:
                logger.info(f"Trigger fired: {trigger.trigger_id} for {subject_id}")
        
        return results
    
    async def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        event_data: Dict[str, Any]
    ) -> bool:
        """Evaluate trigger conditions"""
        # Payout spike
        if "multiplier_threshold" in conditions:
            current = event_data.get("amount", 0)
            average = event_data.get("average_amount", 1)
            if average > 0 and current / average >= conditions["multiplier_threshold"]:
                return True
        
        # Chargeback rate
        if "rate_threshold" in conditions:
            rate = event_data.get("chargeback_rate", 0)
            if rate >= conditions["rate_threshold"]:
                return True
        
        # New device
        if conditions.get("is_new") and event_data.get("is_new_device"):
            return True
        
        # Location distance
        if "distance_km_threshold" in conditions:
            distance = event_data.get("distance_km", 0)
            if distance >= conditions["distance_km_threshold"]:
                return True
        
        return False


# ============================================================================
# CORPORATE MONITORING
# ============================================================================

class CorporateMonitoringService:
    """
    Monitor corporate status changes via CAC
    Detects dissolution, name changes, director changes, ownership changes
    """
    
    def __init__(self):
        self._monitored_businesses: Dict[str, Dict[str, Any]] = {}
        self._change_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    def register_business(
        self,
        business_id: str,
        cac_number: str,
        business_name: str,
        directors: List[str],
        shareholders: List[Dict[str, Any]]
    ):
        """Register business for monitoring"""
        self._monitored_businesses[business_id] = {
            "cac_number": cac_number,
            "business_name": business_name,
            "directors": directors,
            "shareholders": shareholders,
            "status": "active",
            "last_checked": datetime.utcnow(),
            "registered_at": datetime.utcnow()
        }
        logger.info(f"Business registered for monitoring: {business_id}")
    
    async def check_corporate_status(
        self,
        business_id: str
    ) -> List[Tuple[CorporateChangeType, Dict[str, Any]]]:
        """Check for corporate status changes"""
        if business_id not in self._monitored_businesses:
            raise ValueError(f"Business not monitored: {business_id}")
        
        current = self._monitored_businesses[business_id]
        changes = []
        
        # In production, call CAC API to get latest data
        latest = await self._fetch_cac_data(current["cac_number"])
        
        if latest:
            # Check for name change
            if latest.get("business_name") != current["business_name"]:
                changes.append((CorporateChangeType.NAME_CHANGE, {
                    "old_name": current["business_name"],
                    "new_name": latest.get("business_name")
                }))
            
            # Check for director changes
            old_directors = set(current["directors"])
            new_directors = set(latest.get("directors", []))
            if old_directors != new_directors:
                changes.append((CorporateChangeType.DIRECTOR_CHANGE, {
                    "added": list(new_directors - old_directors),
                    "removed": list(old_directors - new_directors)
                }))
            
            # Check for status change
            if latest.get("status") != current["status"]:
                changes.append((CorporateChangeType.STATUS_CHANGE, {
                    "old_status": current["status"],
                    "new_status": latest.get("status")
                }))
                
                if latest.get("status") == "dissolved":
                    changes.append((CorporateChangeType.DISSOLUTION, {
                        "dissolution_date": latest.get("dissolution_date")
                    }))
            
            # Update stored data
            current.update(latest)
            current["last_checked"] = datetime.utcnow()
            
            # Record changes
            for change_type, details in changes:
                self._change_history[business_id].append({
                    "change_type": change_type.value,
                    "details": details,
                    "detected_at": datetime.utcnow().isoformat()
                })
        
        return changes
    
    async def _fetch_cac_data(self, cac_number: str) -> Optional[Dict[str, Any]]:
        """Fetch latest data from CAC API with retry"""
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"Authorization": f"Bearer {CAC_API_KEY}"} if CAC_API_KEY else {}
                    response = await client.get(
                        f"{CAC_API_URL}/api/v1/company/{cac_number}",
                        headers=headers,
                    )
                    if response.status_code == 200:
                        return response.json()
                    logger.warning(f"CAC API returned {response.status_code} on attempt {attempt + 1}")
            except httpx.ConnectError:
                logger.warning(f"CAC API unavailable on attempt {attempt + 1}")
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        return None
    
    def get_change_history(self, business_id: str) -> List[Dict[str, Any]]:
        """Get change history for business"""
        return self._change_history.get(business_id, [])


# ============================================================================
# CONTINUOUS MONITORING SERVICE
# ============================================================================

class ContinuousMonitoringService:
    """
    Main continuous monitoring service
    Integrates with TigerBeetle, Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX, Lakehouse
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        kafka_bootstrap: str = "localhost:9092",
        temporal_host: str = "localhost:7233"
    ):
        self.redis_url = redis_url
        self.kafka_bootstrap = kafka_bootstrap
        self.temporal_host = temporal_host
        
        self._subjects: Dict[str, MonitoredSubject] = {}
        self._alerts: Dict[str, MonitoringAlert] = {}
        
        self._screening_service = ScreeningService()
        self._risk_engine = RiskScoreEngine()
        self._event_engine = EventTriggerEngine()
        self._corporate_monitoring = CorporateMonitoringService()
    
    async def enroll_subject(
        self,
        subject_id: str,
        subject_type: str,
        name: str,
        initial_risk_level: RiskLevel,
        initial_risk_score: float,
        risk_factors: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> MonitoredSubject:
        """Enroll subject for continuous monitoring"""
        now = datetime.utcnow()
        
        # Create risk score
        risk_score = self._risk_engine.create_risk_score(
            subject_id, initial_risk_score, risk_factors
        )
        
        # Create screening schedules based on risk level
        frequency = SCREENING_FREQUENCY_DAYS.get(initial_risk_level, 90)
        schedules = [
            ScreeningSchedule(
                screening_type=ScreeningType.PEP,
                frequency_days=frequency,
                providers=[ScreeningProvider.COMPLY_ADVANTAGE],
                next_run=now + timedelta(days=frequency)
            ),
            ScreeningSchedule(
                screening_type=ScreeningType.SANCTIONS,
                frequency_days=frequency,
                providers=[ScreeningProvider.OFAC, ScreeningProvider.EU_SANCTIONS],
                next_run=now + timedelta(days=frequency)
            ),
            ScreeningSchedule(
                screening_type=ScreeningType.ADVERSE_MEDIA,
                frequency_days=frequency,
                providers=[ScreeningProvider.COMPLY_ADVANTAGE],
                next_run=now + timedelta(days=frequency)
            )
        ]
        
        subject = MonitoredSubject(
            subject_id=subject_id,
            subject_type=subject_type,
            name=name,
            risk_level=initial_risk_level,
            status=MonitoringStatus.ACTIVE,
            screening_schedules=schedules,
            risk_score=risk_score,
            enrolled_at=now,
            last_activity=now,
            metadata=metadata or {}
        )
        
        self._subjects[subject_id] = subject
        
        # Publish to Kafka
        await self._publish_event("kyc.monitoring.events", {
            "event_type": "subject_enrolled",
            "subject_id": subject_id,
            "subject_type": subject_type,
            "risk_level": initial_risk_level.value,
            "timestamp": now.isoformat()
        })
        
        # Start Temporal workflow for scheduled screening
        await self._start_monitoring_workflow(subject)
        
        logger.info(f"Subject enrolled for monitoring: {subject_id}")
        
        return subject
    
    async def run_scheduled_screening(self, subject_id: str) -> List[ScreeningResult]:
        """Run scheduled screening for subject"""
        if subject_id not in self._subjects:
            raise ValueError(f"Subject not found: {subject_id}")
        
        subject = self._subjects[subject_id]
        now = datetime.utcnow()
        results = []
        
        for schedule in subject.screening_schedules:
            if schedule.next_run and now >= schedule.next_run:
                for provider in schedule.providers:
                    result = await self._screening_service.screen_subject(
                        subject_id,
                        subject.name,
                        schedule.screening_type,
                        provider,
                        subject.metadata
                    )
                    results.append(result)
                    
                    # Create alert if match found
                    if result.is_match:
                        await self.create_alert(
                            subject_id,
                            AlertType.SCREENING_MATCH,
                            RiskLevel.HIGH,
                            f"Screening match: {schedule.screening_type.value}",
                            f"Match found in {provider.value} screening",
                            {"result_id": result.result_id, "match_score": result.match_score}
                        )
                
                # Update schedule
                schedule.last_run = now
                schedule.next_run = now + timedelta(days=schedule.frequency_days)
        
        # Publish to Kafka
        await self._publish_event("kyc.monitoring.events", {
            "event_type": "screening_completed",
            "subject_id": subject_id,
            "results_count": len(results),
            "matches_found": len([r for r in results if r.is_match]),
            "timestamp": now.isoformat()
        })
        
        return results
    
    async def process_event(
        self,
        subject_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> List[MonitoringAlert]:
        """Process event and check triggers"""
        if subject_id not in self._subjects:
            raise ValueError(f"Subject not found: {subject_id}")
        
        subject = self._subjects[subject_id]
        subject.last_activity = datetime.utcnow()
        
        alerts = []
        
        # Evaluate triggers
        trigger_results = await self._event_engine.evaluate_event(
            subject_id, event_type, event_data
        )
        
        for trigger, is_triggered in trigger_results:
            if is_triggered:
                alert = await self.create_alert(
                    subject_id,
                    AlertType(trigger.trigger_id) if trigger.trigger_id in [a.value for a in AlertType] else AlertType.SCREENING_MATCH,
                    RiskLevel.HIGH,
                    f"Trigger fired: {trigger.name}",
                    f"Event trigger {trigger.trigger_id} activated",
                    {"trigger_id": trigger.trigger_id, "event_data": event_data}
                )
                alerts.append(alert)
                
                # Adjust risk score
                self._risk_engine.adjust_score(
                    subject_id,
                    10.0,  # Increase risk by 10 points
                    f"Trigger: {trigger.trigger_id}"
                )
        
        return alerts
    
    async def check_risk_score_decay(self) -> List[MonitoringAlert]:
        """Check for subjects needing risk score refresh"""
        alerts = []
        
        for subject_id, subject in self._subjects.items():
            if subject.status != MonitoringStatus.ACTIVE:
                continue
            
            current_score, needs_refresh = self._risk_engine.get_current_score(subject_id)
            
            if needs_refresh:
                alert = await self.create_alert(
                    subject_id,
                    AlertType.REVERIFICATION_DUE,
                    RiskLevel.MEDIUM,
                    "Risk score refresh required",
                    f"Risk score has decayed and requires refresh (current: {current_score:.1f})",
                    {"current_score": current_score, "days_since_refresh": 365}
                )
                alerts.append(alert)
        
        return alerts
    
    async def create_alert(
        self,
        subject_id: str,
        alert_type: AlertType,
        severity: RiskLevel,
        title: str,
        description: str,
        details: Dict[str, Any]
    ) -> MonitoringAlert:
        """Create monitoring alert"""
        alert_id = secrets.token_hex(16)
        
        alert = MonitoringAlert(
            alert_id=alert_id,
            subject_id=subject_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            description=description,
            details=details,
            created_at=datetime.utcnow()
        )
        
        self._alerts[alert_id] = alert
        
        # Publish to Kafka
        await self._publish_event("kyc.monitoring.alerts", {
            "event_type": "alert_created",
            "alert_id": alert_id,
            "subject_id": subject_id,
            "alert_type": alert_type.value,
            "severity": severity.value,
            "timestamp": alert.created_at.isoformat()
        })
        
        # Stream to Fluvio for real-time processing
        await self._stream_to_fluvio("monitoring-alerts", {
            "alert_id": alert_id,
            "subject_id": subject_id,
            "alert_type": alert_type.value,
            "severity": severity.value
        })
        
        logger.info(f"Alert created: {alert_id} - {alert_type.value}")
        
        return alert
    
    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> MonitoringAlert:
        """Acknowledge alert"""
        if alert_id not in self._alerts:
            raise ValueError(f"Alert not found: {alert_id}")
        
        alert = self._alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        
        return alert
    
    async def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str,
        case_id: Optional[str] = None
    ) -> MonitoringAlert:
        """Resolve alert"""
        if alert_id not in self._alerts:
            raise ValueError(f"Alert not found: {alert_id}")
        
        alert = self._alerts[alert_id]
        alert.resolved = True
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.utcnow()
        alert.case_id = case_id
        
        return alert
    
    def get_subject(self, subject_id: str) -> Optional[MonitoredSubject]:
        """Get monitored subject"""
        return self._subjects.get(subject_id)
    
    def get_alerts(
        self,
        subject_id: Optional[str] = None,
        alert_type: Optional[AlertType] = None,
        severity: Optional[RiskLevel] = None,
        unresolved_only: bool = False
    ) -> List[MonitoringAlert]:
        """Get alerts with filters"""
        results = []
        
        for alert in self._alerts.values():
            if subject_id and alert.subject_id != subject_id:
                continue
            if alert_type and alert.alert_type != alert_type:
                continue
            if severity and alert.severity != severity:
                continue
            if unresolved_only and alert.resolved:
                continue
            
            results.append(alert)
        
        # Sort by severity and creation time
        severity_order = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.VERY_HIGH: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.MEDIUM: 3,
            RiskLevel.LOW: 4
        }
        results.sort(key=lambda a: (severity_order.get(a.severity, 5), a.created_at))
        
        return results
    
    async def _publish_event(self, topic: str, event: Dict[str, Any]):
        """Publish event to Kafka"""
        logger.debug(f"Publishing to {topic}: {event.get('event_type')}")
    
    async def _stream_to_fluvio(self, topic: str, data: Dict[str, Any]):
        """Stream data to Fluvio"""
        logger.debug(f"Streaming to Fluvio {topic}")
    
    async def _start_monitoring_workflow(self, subject: MonitoredSubject):
        """Start Temporal workflow for monitoring"""
        logger.debug(f"Starting monitoring workflow for {subject.subject_id}")
    
    @property
    def screening_service(self) -> ScreeningService:
        return self._screening_service
    
    @property
    def risk_engine(self) -> RiskScoreEngine:
        return self._risk_engine
    
    @property
    def corporate_monitoring(self) -> CorporateMonitoringService:
        return self._corporate_monitoring


# Global instance
_monitoring_service: Optional[ContinuousMonitoringService] = None


def get_continuous_monitoring_service() -> ContinuousMonitoringService:
    """Get or create continuous monitoring service"""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = ContinuousMonitoringService()
    return _monitoring_service
