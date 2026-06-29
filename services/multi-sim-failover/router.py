"""API Router for Multi-SIM Failover Service."""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from models import (
    SignalUpdateRequest, ManualFailoverRequest,
    ConnectivityStatus, FailoverEventResponse
)
from service import MultiSimFailoverService
from config import get_db

router = APIRouter(prefix="/api/v1/connectivity", tags=["Multi-SIM Failover"])


def get_service(db: Session = Depends(get_db)) -> MultiSimFailoverService:
    return MultiSimFailoverService(db)


@router.post("/terminals/{terminal_id}/signal", summary="Update terminal signal strengths")
def update_signal(
    terminal_id: UUID,
    payload: SignalUpdateRequest,
    svc: MultiSimFailoverService = Depends(get_service),
):
    payload.terminal_id = terminal_id
    profile = svc.update_signal_strengths(
        terminal_id=terminal_id,
        sim1_signal=payload.sim1_signal,
        sim2_signal=payload.sim2_signal,
        sim3_signal=payload.sim3_signal,
        wifi_signal=payload.wifi_signal,
        sim1_carrier=payload.sim1_carrier,
        sim2_carrier=payload.sim2_carrier,
        sim3_carrier=payload.sim3_carrier,
    )
    return {"status": "updated", "active_slot": profile.active_sim_slot}


@router.get("/terminals/{terminal_id}/status", response_model=ConnectivityStatus)
def get_status(
    terminal_id: UUID,
    svc: MultiSimFailoverService = Depends(get_service),
):
    return svc.get_connectivity_status(terminal_id)


@router.post("/terminals/{terminal_id}/failover", summary="Manually trigger SIM failover")
def manual_failover(
    terminal_id: UUID,
    payload: ManualFailoverRequest,
    svc: MultiSimFailoverService = Depends(get_service),
):
    payload.terminal_id = terminal_id
    event = svc.execute_failover(
        terminal_id=terminal_id,
        target_slot=payload.target_slot,
        reason=payload.reason,
        transaction_id=payload.transaction_id,
    )
    return {
        "status": "failover_executed",
        "from_slot": event.from_sim_slot,
        "to_slot": event.to_sim_slot,
        "latency_ms": event.failover_latency_ms,
    }


@router.get("/terminals/{terminal_id}/history", response_model=List[FailoverEventResponse])
def get_failover_history(
    terminal_id: UUID,
    limit: int = 50,
    svc: MultiSimFailoverService = Depends(get_service),
):
    return svc.get_failover_history(terminal_id, limit=limit)


@router.get("/network/health", summary="Platform-wide network health summary")
def network_health(svc: MultiSimFailoverService = Depends(get_service)):
    return svc.get_network_health_summary()


@router.get("/health")
def health():
    return {"status": "healthy", "service": "multi-sim-failover"}
