"""
Agent Scorecard API Router
All endpoints for computing, retrieving, and managing agent scorecards.
"""
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .config import get_db
from .models import (
    BenchmarkOut, DismissRecommendationRequest,
    HistoryPoint, NetworkLeaderboardEntry,
    ScorecardComputeRequest, ScorecardOut, ScorecardSummary,
    ScoreTier,
)
from . import service

router = APIRouter(
    prefix="/agent-scorecard",
    tags=["Agent Scorecard"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/compute",
    response_model=ScorecardOut,
    status_code=status.HTTP_201_CREATED,
    summary="Compute and persist a new agent scorecard",
    description=(
        "Accepts raw performance metrics for an agent over a given period and computes "
        "a holistic 360-degree scorecard across 5 weighted dimensions. "
        "Also generates actionable recommendations and persists a history point."
    ),
)
def compute_scorecard(
    req: ScorecardComputeRequest,
    db: Session = Depends(get_db),
):
    try:
        scorecard = service.compute_scorecard(db, req)
        return scorecard
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scorecard computation failed: {str(exc)}",
        )


@router.get(
    "/agent/{agent_id}/latest",
    response_model=ScorecardOut,
    summary="Get the latest scorecard for an agent",
)
def get_latest_scorecard(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    sc = service.get_scorecard(db, agent_id)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scorecard found for agent {agent_id}",
        )
    return sc


@router.get(
    "/agent/{agent_id}/date/{score_date}",
    response_model=ScorecardOut,
    summary="Get scorecard for a specific date",
)
def get_scorecard_by_date(
    agent_id: uuid.UUID,
    score_date: date,
    db: Session = Depends(get_db),
):
    sc = service.get_scorecard(db, agent_id, score_date)
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scorecard found for agent {agent_id} on {score_date}",
        )
    return sc


@router.get(
    "/agent/{agent_id}/history",
    response_model=List[HistoryPoint],
    summary="Get scorecard score history for trend analysis",
    description="Returns daily composite scores for the last N days (default 90).",
)
def get_scorecard_history(
    agent_id: uuid.UUID,
    days: int = Query(default=90, ge=7, le=365, description="Number of days of history to return"),
    db: Session = Depends(get_db),
):
    return service.get_scorecard_history(db, agent_id, days)


@router.get(
    "/leaderboard",
    response_model=List[ScorecardSummary],
    summary="Get network-wide agent leaderboard",
    description="Returns the top N agents by composite score for today.",
)
def get_leaderboard(
    tenant_id: uuid.UUID = Query(..., description="Tenant ID to scope the leaderboard"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return service.get_network_leaderboard(db, tenant_id, limit)


@router.get(
    "/benchmark",
    response_model=BenchmarkOut,
    summary="Get network benchmark statistics",
    description="Returns aggregate benchmark statistics for the tenant's agent network today.",
)
def get_benchmark(
    tenant_id: uuid.UUID = Query(..., description="Tenant ID"),
    db: Session = Depends(get_db),
):
    bm = service.get_or_compute_benchmark(db, tenant_id)
    return BenchmarkOut(
        benchmark_date=bm.benchmark_date,
        avg_score=float(bm.avg_score),
        median_score=float(bm.median_score),
        p75_score=float(bm.p75_score),
        p90_score=float(bm.p90_score),
        tier_distribution={
            "platinum": bm.platinum_count,
            "gold": bm.gold_count,
            "silver": bm.silver_count,
            "bronze": bm.bronze_count,
            "unrated": bm.unrated_count,
        },
        total_agents=bm.total_agents,
    )


@router.post(
    "/recommendations/dismiss",
    status_code=status.HTTP_200_OK,
    summary="Dismiss a scorecard recommendation",
)
def dismiss_recommendation(
    req: DismissRecommendationRequest,
    agent_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
):
    success = service.dismiss_recommendation(db, req.recommendation_id, agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found or does not belong to this agent.",
        )
    return {"message": "Recommendation dismissed successfully."}


@router.get(
    "/health",
    summary="Health check",
    include_in_schema=False,
)
def health():
    return {"status": "healthy", "service": "agent-scorecard"}
