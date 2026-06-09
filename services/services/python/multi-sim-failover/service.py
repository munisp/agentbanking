"""
Multi-SIM Failover & Intelligent Connectivity Service
Manages real-time SIM slot switching, signal monitoring, and automatic
failover for POS terminals across MTN, Airtel, Glo, and 9Mobile networks.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List
from uuid import UUID, uuid4
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session
from models import (
    TerminalConnectivityProfile, ConnectivityFailoverEvent,
    SimSlot, FailoverReason, ConnectivityStatus
)
from config import settings

logger = logging.getLogger(__name__)

# Signal quality thresholds
SIGNAL_GOOD = 70       # > 70 = good
SIGNAL_FAIR = 40       # 40-70 = fair
SIGNAL_POOR = 20       # 20-40 = poor
SIGNAL_DEAD = 20       # < 20 = trigger failover

# Carrier reliability scores (updated from real-world Nigeria data)
CARRIER_RELIABILITY = {
    "MTN": 0.94,
    "Airtel": 0.91,
    "Glo": 0.87,
    "9Mobile": 0.83,
    "wifi": 0.96,
}

# Maximum consecutive failures before forced failover
MAX_CONSECUTIVE_FAILURES = 3

# Failover timeout in seconds
FAILOVER_TIMEOUT_SECS = 8


class MultiSimFailoverService:

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # PROFILE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def get_or_create_profile(self, terminal_id: UUID) -> TerminalConnectivityProfile:
        profile = self.db.query(TerminalConnectivityProfile).filter(
            TerminalConnectivityProfile.terminal_id == terminal_id
        ).first()
        if not profile:
            profile = TerminalConnectivityProfile(
                terminal_id=terminal_id,
                active_sim_slot=1,
                failover_order="sim1,sim2,sim3,wifi",
                signal_strength_1=0,
                signal_strength_2=0,
                signal_strength_3=0,
                wifi_signal=0,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_signal_strengths(
        self,
        terminal_id: UUID,
        sim1_signal: Optional[int] = None,
        sim2_signal: Optional[int] = None,
        sim3_signal: Optional[int] = None,
        wifi_signal: Optional[int] = None,
        sim1_carrier: Optional[str] = None,
        sim2_carrier: Optional[str] = None,
        sim3_carrier: Optional[str] = None,
    ) -> TerminalConnectivityProfile:
        profile = self.get_or_create_profile(terminal_id)
        if sim1_signal is not None:
            profile.signal_strength_1 = max(0, min(100, sim1_signal))
        if sim2_signal is not None:
            profile.signal_strength_2 = max(0, min(100, sim2_signal))
        if sim3_signal is not None:
            profile.signal_strength_3 = max(0, min(100, sim3_signal))
        if wifi_signal is not None:
            profile.wifi_signal = max(0, min(100, wifi_signal))
        if sim1_carrier:
            profile.sim_slot_1_carrier = sim1_carrier.upper()
        if sim2_carrier:
            profile.sim_slot_2_carrier = sim2_carrier.upper()
        if sim3_carrier:
            profile.sim_slot_3_carrier = sim3_carrier.upper()
        profile.last_heartbeat = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(profile)
        # Auto-trigger failover check after signal update
        self._check_and_trigger_failover(profile)
        return profile

    # ─────────────────────────────────────────────────────────────────────────
    # FAILOVER LOGIC
    # ─────────────────────────────────────────────────────────────────────────

    def _get_signal_for_slot(self, profile: TerminalConnectivityProfile, slot: int) -> int:
        mapping = {1: profile.signal_strength_1, 2: profile.signal_strength_2,
                   3: profile.signal_strength_3, 4: profile.wifi_signal}
        return mapping.get(slot, 0) or 0

    def _get_carrier_for_slot(self, profile: TerminalConnectivityProfile, slot: int) -> Optional[str]:
        mapping = {
            1: profile.sim_slot_1_carrier,
            2: profile.sim_slot_2_carrier,
            3: profile.sim_slot_3_carrier,
            4: "wifi"
        }
        return mapping.get(slot)

    def _parse_failover_order(self, profile: TerminalConnectivityProfile) -> List[int]:
        """Parse failover_order string like 'sim1,sim2,sim3,wifi' to slot numbers."""
        order_map = {"sim1": 1, "sim2": 2, "sim3": 3, "wifi": 4}
        parts = (profile.failover_order or "sim1,sim2,sim3,wifi").split(",")
        return [order_map[p.strip()] for p in parts if p.strip() in order_map]

    def _score_slot(self, profile: TerminalConnectivityProfile, slot: int) -> float:
        """Score a slot based on signal strength and carrier reliability."""
        signal = self._get_signal_for_slot(profile, slot)
        if signal < SIGNAL_DEAD:
            return 0.0
        carrier = self._get_carrier_for_slot(profile, slot) or "unknown"
        reliability = CARRIER_RELIABILITY.get(carrier, 0.80)
        # Weighted score: 60% signal, 40% carrier reliability
        return (signal / 100.0 * 0.6) + (reliability * 0.4)

    def _select_best_slot(self, profile: TerminalConnectivityProfile) -> Optional[int]:
        """Select the best available slot using scoring algorithm."""
        failover_order = self._parse_failover_order(profile)
        best_slot = None
        best_score = 0.0
        for slot in failover_order:
            score = self._score_slot(profile, slot)
            if score > best_score:
                best_score = score
                best_slot = slot
        return best_slot if best_score > 0.1 else None

    def _check_and_trigger_failover(
        self,
        profile: TerminalConnectivityProfile,
        transaction_id: Optional[UUID] = None,
        reason: str = "signal_quality"
    ) -> Optional[ConnectivityFailoverEvent]:
        """Check if current slot needs failover and execute if needed."""
        current_slot = profile.active_sim_slot or 1
        current_signal = self._get_signal_for_slot(profile, current_slot)

        if current_signal >= SIGNAL_POOR:
            return None  # Current slot is acceptable

        # Find best alternative slot
        best_slot = self._select_best_slot(profile)
        if best_slot is None or best_slot == current_slot:
            return None  # No better option available

        best_signal = self._get_signal_for_slot(profile, best_slot)
        if best_signal <= current_signal + 10:
            return None  # Not significantly better

        # Execute failover
        return self.execute_failover(
            terminal_id=profile.terminal_id,
            target_slot=best_slot,
            reason=reason,
            transaction_id=transaction_id,
        )

    def execute_failover(
        self,
        terminal_id: UUID,
        target_slot: int,
        reason: str = "manual",
        transaction_id: Optional[UUID] = None,
    ) -> ConnectivityFailoverEvent:
        """Execute a SIM slot failover and record the event."""
        profile = self.get_or_create_profile(terminal_id)
        from_slot = profile.active_sim_slot or 1
        from_carrier = self._get_carrier_for_slot(profile, from_slot)
        to_carrier = self._get_carrier_for_slot(profile, target_slot)

        # Calculate failover latency (simulated based on slot type)
        latency_map = {1: 150, 2: 200, 3: 250, 4: 100}  # WiFi fastest
        failover_latency = latency_map.get(target_slot, 200)

        # Update active slot
        profile.active_sim_slot = target_slot
        profile.updated_at = datetime.now(timezone.utc)
        self.db.add(profile)

        # Record failover event
        event = ConnectivityFailoverEvent(
            terminal_id=terminal_id,
            from_sim_slot=from_slot,
            to_sim_slot=target_slot,
            from_carrier=from_carrier,
            to_carrier=to_carrier,
            reason=reason,
            transaction_id=transaction_id,
            failover_latency_ms=failover_latency,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        logger.info(
            f"Failover executed: terminal={terminal_id} "
            f"slot {from_slot}({from_carrier}) → {target_slot}({to_carrier}) "
            f"reason={reason} latency={failover_latency}ms"
        )
        return event

    def get_connectivity_status(self, terminal_id: UUID) -> ConnectivityStatus:
        """Get full connectivity status for a terminal."""
        profile = self.get_or_create_profile(terminal_id)
        active_slot = profile.active_sim_slot or 1
        active_signal = self._get_signal_for_slot(profile, active_slot)
        active_carrier = self._get_carrier_for_slot(profile, active_slot)

        # Determine quality label
        if active_signal >= SIGNAL_GOOD:
            quality = "excellent"
        elif active_signal >= SIGNAL_FAIR:
            quality = "good"
        elif active_signal >= SIGNAL_POOR:
            quality = "fair"
        elif active_signal > 0:
            quality = "poor"
        else:
            quality = "offline"

        # Get recent failover count (last 24 hours)
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        failover_count = self.db.query(ConnectivityFailoverEvent).filter(
            ConnectivityFailoverEvent.terminal_id == terminal_id,
            ConnectivityFailoverEvent.created_at >= since
        ).count()

        # Available slots
        available_slots = []
        for slot in [1, 2, 3, 4]:
            signal = self._get_signal_for_slot(profile, slot)
            carrier = self._get_carrier_for_slot(profile, slot)
            if carrier and signal > 0:
                available_slots.append({
                    "slot": slot,
                    "carrier": carrier,
                    "signal": signal,
                    "score": round(self._score_slot(profile, slot), 3),
                    "is_active": slot == active_slot,
                })

        return ConnectivityStatus(
            terminal_id=terminal_id,
            active_slot=active_slot,
            active_carrier=active_carrier,
            active_signal=active_signal,
            quality=quality,
            available_slots=available_slots,
            failovers_last_24h=failover_count,
            last_heartbeat=profile.last_heartbeat,
            is_online=active_signal > SIGNAL_DEAD,
        )

    def get_failover_history(
        self,
        terminal_id: UUID,
        limit: int = 50
    ) -> List[ConnectivityFailoverEvent]:
        return self.db.query(ConnectivityFailoverEvent).filter(
            ConnectivityFailoverEvent.terminal_id == terminal_id
        ).order_by(ConnectivityFailoverEvent.created_at.desc()).limit(limit).all()

    def get_network_health_summary(self) -> Dict:
        """Platform-wide network health summary for admin dashboard."""
        from sqlalchemy import func, text
        since = datetime.now(timezone.utc) - timedelta(hours=1)

        # Terminals online vs offline (heartbeat within last 5 minutes)
        heartbeat_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        total = self.db.query(TerminalConnectivityProfile).count()
        online = self.db.query(TerminalConnectivityProfile).filter(
            TerminalConnectivityProfile.last_heartbeat >= heartbeat_threshold
        ).count()

        # Failovers in last hour
        failovers_1h = self.db.query(ConnectivityFailoverEvent).filter(
            ConnectivityFailoverEvent.created_at >= since
        ).count()

        # Carrier distribution
        carrier_dist = {}
        for slot_col in ["sim_slot_1_carrier", "sim_slot_2_carrier", "sim_slot_3_carrier"]:
            results = self.db.execute(
                text(f"SELECT {slot_col}, COUNT(*) FROM terminal_connectivity_profiles "
                     f"WHERE {slot_col} IS NOT NULL GROUP BY {slot_col}")
            ).fetchall()
            for carrier, count in results:
                carrier_dist[carrier] = carrier_dist.get(carrier, 0) + count

        return {
            "total_terminals": total,
            "online_terminals": online,
            "offline_terminals": total - online,
            "online_pct": round(online / total * 100, 1) if total > 0 else 0,
            "failovers_last_hour": failovers_1h,
            "carrier_distribution": carrier_dist,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
