"""
Agent Scorecard Service — Full Scoring Engine
Computes a holistic 360-degree agent performance score across 5 weighted dimensions.
"""
import math
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from .models import (
    AgentScorecard, ScorecardBenchmark, ScorecardHistory,
    ScorecardRecommendation, ScoreTier, TrendDirection,
    RecommendationPriority, RawMetricsInput, ScorecardComputeRequest,
)


# ─── Dimension Weights ────────────────────────────────────────────────────────

WEIGHTS = {
    "transaction": 0.30,
    "customer_experience": 0.20,
    "compliance": 0.25,
    "training": 0.15,
    "network": 0.10,
}

# Score scale: each dimension sub-score is 0-100; composite is 0-1000
MAX_DIMENSION_SCORE = 100.0
COMPOSITE_SCALE = 10.0  # composite = sum(dim_score * weight) * 10 → 0-1000


# ─── Tier Thresholds ─────────────────────────────────────────────────────────

def _compute_tier(composite: float) -> ScoreTier:
    if composite >= 850:
        return ScoreTier.PLATINUM
    elif composite >= 700:
        return ScoreTier.GOLD
    elif composite >= 550:
        return ScoreTier.SILVER
    elif composite >= 350:
        return ScoreTier.BRONZE
    return ScoreTier.UNRATED


# ─── Scoring Helpers ──────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


def _score_volume(count: int, benchmarks: dict) -> float:
    """Score transaction volume against network benchmarks."""
    p50 = benchmarks.get("txn_p50", 500)
    p90 = benchmarks.get("txn_p90", 2000)
    if count >= p90:
        return 100.0
    elif count >= p50:
        return 50.0 + 50.0 * ((count - p50) / max(p90 - p50, 1))
    else:
        return _clamp(50.0 * (count / max(p50, 1)))


def _score_success_rate(successful: int, total: int) -> float:
    if total == 0:
        return 0.0
    rate = successful / total
    # Non-linear: 99%+ = 100, 95% = 80, 90% = 60, below 85% = 0-40
    if rate >= 0.99:
        return 100.0
    elif rate >= 0.95:
        return 80.0 + 20.0 * ((rate - 0.95) / 0.04)
    elif rate >= 0.90:
        return 60.0 + 20.0 * ((rate - 0.90) / 0.05)
    elif rate >= 0.85:
        return 40.0 + 20.0 * ((rate - 0.85) / 0.05)
    else:
        return _clamp(40.0 * (rate / 0.85))


def _score_growth(current: float, previous: float) -> float:
    if previous == 0:
        return 50.0  # neutral if no history
    growth_rate = (current - previous) / previous
    # +20% growth = 100, 0% = 50, -20% = 0
    score = 50.0 + (growth_rate / 0.20) * 50.0
    return _clamp(score)


def _score_customer_satisfaction(avg_rating: float) -> float:
    """Convert 1-5 star rating to 0-100 score."""
    if avg_rating <= 0:
        return 0.0
    return _clamp((avg_rating - 1) / 4.0 * 100.0)


def _score_complaint_resolution(resolved: int, total: int) -> float:
    if total == 0:
        return 100.0  # no complaints = perfect
    rate = resolved / total
    return _clamp(rate * 100.0)


def _score_retention(returning: int, active: int) -> float:
    if active == 0:
        return 0.0
    return _clamp(_safe_ratio(returning, active) * 100.0)


def _score_kyc_compliance(passed: int, total: int) -> float:
    if total == 0:
        return 100.0
    return _clamp(_safe_ratio(passed, total) * 100.0)


def _score_aml(flags: int) -> float:
    """Penalise for AML flags raised."""
    if flags == 0:
        return 100.0
    elif flags == 1:
        return 70.0
    elif flags <= 3:
        return 40.0
    return 0.0


def _score_fraud(incidents: int) -> float:
    """Zero tolerance for fraud incidents."""
    if incidents == 0:
        return 100.0
    elif incidents == 1:
        return 30.0
    return 0.0


def _score_geo_compliance(violations: int) -> float:
    if violations == 0:
        return 100.0
    elif violations <= 2:
        return 60.0
    return 0.0


def _score_limit_compliance(breaches: int) -> float:
    if breaches == 0:
        return 100.0
    elif breaches <= 1:
        return 50.0
    return 0.0


def _score_training_completion(completed: int, total: int) -> float:
    if total == 0:
        return 100.0
    return _clamp(_safe_ratio(completed, total) * 100.0)


def _score_certifications(active: int, required: int) -> float:
    if required == 0:
        return 100.0
    return _clamp(_safe_ratio(active, required) * 100.0)


def _score_network_size(active_sub: int) -> float:
    """Score based on active sub-agent count (log scale)."""
    if active_sub == 0:
        return 0.0
    return _clamp(min(100.0, math.log10(active_sub + 1) / math.log10(101) * 100.0))


def _score_network_activation(active: int, total: int) -> float:
    if total == 0:
        return 0.0
    return _clamp(_safe_ratio(active, total) * 100.0)


def _score_referrals(made: int, converted: int) -> float:
    if made == 0:
        return 0.0
    conversion_rate = _safe_ratio(converted, made)
    volume_score = _clamp(min(100.0, made * 5.0))  # 20 referrals = 100
    return _clamp((conversion_rate * 60.0) + (volume_score * 0.40))


# ─── Main Scoring Engine ──────────────────────────────────────────────────────

def compute_scorecard(
    db: Session,
    req: ScorecardComputeRequest,
    network_benchmarks: Optional[dict] = None,
) -> AgentScorecard:
    """
    Full scoring engine. Computes all 5 dimensions and composite score.
    Persists the scorecard and generates recommendations.
    """
    m = req.metrics
    benchmarks = network_benchmarks or {}

    # ── Dimension 1: Transaction Performance ──────────────────────────────────
    txn_volume = _score_volume(m.total_transactions, benchmarks)
    txn_value = _score_volume(m.total_transaction_value, {
        "txn_p50": benchmarks.get("value_p50", 500_000),
        "txn_p90": benchmarks.get("value_p90", 2_000_000),
    })
    txn_success = _score_success_rate(m.successful_transactions, m.total_transactions)
    txn_growth = _score_growth(m.total_transactions, m.prev_period_transactions)
    txn_dim = (txn_volume * 0.30 + txn_value * 0.25 + txn_success * 0.30 + txn_growth * 0.15)

    # ── Dimension 2: Customer Experience ──────────────────────────────────────
    csat = _score_customer_satisfaction(m.avg_customer_rating)
    complaint_res = _score_complaint_resolution(m.resolved_complaints, m.total_complaints)
    retention = _score_retention(m.returning_customers, m.active_customers)
    acquisition = _score_volume(m.new_customers, {
        "txn_p50": benchmarks.get("cust_p50", 50),
        "txn_p90": benchmarks.get("cust_p90", 200),
    })
    cx_dim = (csat * 0.35 + complaint_res * 0.25 + retention * 0.25 + acquisition * 0.15)

    # ── Dimension 3: Compliance & Risk ────────────────────────────────────────
    kyc_comp = _score_kyc_compliance(m.kyc_checks_passed, m.kyc_checks_total)
    aml_comp = _score_aml(m.aml_flags_raised)
    fraud_comp = _score_fraud(m.fraud_incidents)
    geo_comp = _score_geo_compliance(m.geo_violations)
    limit_comp = _score_limit_compliance(m.limit_breaches)
    compliance_dim = (kyc_comp * 0.25 + aml_comp * 0.25 + fraud_comp * 0.25 + geo_comp * 0.15 + limit_comp * 0.10)

    # ── Dimension 4: Training & Certification ─────────────────────────────────
    training_comp = _score_training_completion(m.training_modules_completed, m.training_modules_total)
    cert_score = _score_certifications(m.certifications_active, m.certifications_required)
    assessment = _clamp(m.last_assessment_score)
    training_dim = (training_comp * 0.40 + cert_score * 0.35 + assessment * 0.25)

    # ── Dimension 5: Network Growth ───────────────────────────────────────────
    sub_size = _score_network_size(m.active_sub_agents)
    net_activation = _score_network_activation(m.active_sub_agents, m.total_sub_agents)
    referral = _score_referrals(m.referrals_made, m.referrals_converted)
    network_dim = (sub_size * 0.40 + net_activation * 0.30 + referral * 0.30)

    # ── Composite Score (0-1000) ───────────────────────────────────────────────
    composite = (
        txn_dim * WEIGHTS["transaction"] +
        cx_dim * WEIGHTS["customer_experience"] +
        compliance_dim * WEIGHTS["compliance"] +
        training_dim * WEIGHTS["training"] +
        network_dim * WEIGHTS["network"]
    ) * COMPOSITE_SCALE

    composite = round(_clamp(composite, 0, 1000), 2)
    tier = _compute_tier(composite)

    # ── Trend: compare with previous scorecard ────────────────────────────────
    prev = (
        db.query(AgentScorecard)
        .filter(
            AgentScorecard.agent_id == req.agent_id,
            AgentScorecard.tenant_id == req.tenant_id,
            AgentScorecard.computation_date < date.today(),
        )
        .order_by(AgentScorecard.computation_date.desc())
        .first()
    )
    prev_score = float(prev.composite_score) if prev else None
    if prev_score is None:
        trend = TrendDirection.STABLE
    elif composite > prev_score + 10:
        trend = TrendDirection.IMPROVING
    elif composite < prev_score - 10:
        trend = TrendDirection.DECLINING
    else:
        trend = TrendDirection.STABLE

    # ── Percentile Rank ───────────────────────────────────────────────────────
    total_agents = db.query(func.count(AgentScorecard.id)).filter(
        AgentScorecard.tenant_id == req.tenant_id,
        AgentScorecard.computation_date == date.today(),
    ).scalar() or 0

    agents_below = db.query(func.count(AgentScorecard.id)).filter(
        AgentScorecard.tenant_id == req.tenant_id,
        AgentScorecard.computation_date == date.today(),
        AgentScorecard.composite_score < composite,
    ).scalar() or 0

    percentile = round((agents_below / max(total_agents, 1)) * 100, 1) if total_agents > 0 else None

    # ── Build raw metrics dict ────────────────────────────────────────────────
    raw = m.model_dump()

    # ── Persist scorecard ─────────────────────────────────────────────────────
    scorecard = AgentScorecard(
        agent_id=req.agent_id,
        tenant_id=req.tenant_id,
        period_start=req.period_start,
        period_end=req.period_end,
        composite_score=composite,
        previous_composite_score=prev_score,
        tier=tier,
        trend=trend,
        percentile_rank=percentile,
        txn_volume_score=round(txn_volume, 2),
        txn_value_score=round(txn_value, 2),
        txn_success_rate_score=round(txn_success, 2),
        txn_growth_rate_score=round(txn_growth, 2),
        txn_dimension_score=round(txn_dim, 2),
        customer_satisfaction_score=round(csat, 2),
        complaint_resolution_score=round(complaint_res, 2),
        customer_retention_score=round(retention, 2),
        new_customer_acquisition_score=round(acquisition, 2),
        cx_dimension_score=round(cx_dim, 2),
        kyc_compliance_score=round(kyc_comp, 2),
        aml_compliance_score=round(aml_comp, 2),
        fraud_incident_score=round(fraud_comp, 2),
        geo_compliance_score=round(geo_comp, 2),
        transaction_limit_score=round(limit_comp, 2),
        compliance_dimension_score=round(compliance_dim, 2),
        training_completion_score=round(training_comp, 2),
        certification_score=round(cert_score, 2),
        assessment_score=round(assessment, 2),
        training_dimension_score=round(training_dim, 2),
        sub_agent_count_score=round(sub_size, 2),
        network_activation_score=round(net_activation, 2),
        referral_score=round(referral, 2),
        network_dimension_score=round(network_dim, 2),
        raw_metrics=raw,
        is_published=True,
        published_at=datetime.utcnow(),
    )
    db.add(scorecard)
    db.flush()  # get the ID before adding recommendations

    # ── Generate Recommendations ──────────────────────────────────────────────
    recommendations = _generate_recommendations(scorecard, m)
    for rec in recommendations:
        rec.scorecard_id = scorecard.id
        db.add(rec)

    # ── Persist History Point ─────────────────────────────────────────────────
    history = ScorecardHistory(
        agent_id=req.agent_id,
        tenant_id=req.tenant_id,
        score_date=date.today(),
        composite_score=composite,
        tier=tier,
    )
    db.add(history)

    db.commit()
    db.refresh(scorecard)
    return scorecard


def _generate_recommendations(
    sc: AgentScorecard,
    m: RawMetricsInput,
) -> List[ScorecardRecommendation]:
    recs = []

    def add(dimension, priority, title, desc, action_url=None, impact=None):
        recs.append(ScorecardRecommendation(
            agent_id=sc.agent_id,
            dimension=dimension,
            priority=priority,
            title=title,
            description=desc,
            action_url=action_url,
            impact_score=impact,
        ))

    # Compliance — always critical
    if float(sc.fraud_incident_score) < 100:
        add("compliance", RecommendationPriority.CRITICAL,
            "Fraud Incident Detected",
            f"Your account has {m.fraud_incidents} fraud incident(s) recorded this period. "
            "Immediate review is required to avoid suspension.",
            "/compliance/fraud-review", impact=25.0)

    if float(sc.aml_compliance_score) < 70:
        add("compliance", RecommendationPriority.CRITICAL,
            "AML Flags Require Attention",
            f"{m.aml_flags_raised} AML flag(s) were raised this period. "
            "Complete your AML refresher training and review flagged transactions.",
            "/training/aml-refresher", impact=20.0)

    if float(sc.kyc_compliance_score) < 90:
        rate = round(_safe_ratio(m.kyc_checks_passed, m.kyc_checks_total) * 100, 1)
        add("compliance", RecommendationPriority.HIGH,
            "KYC Compliance Below Target",
            f"Your KYC pass rate is {rate}%. Ensure all customers complete full verification before transacting.",
            "/compliance/kyc-guide", impact=15.0)

    if float(sc.geo_compliance_score) < 100:
        add("compliance", RecommendationPriority.HIGH,
            "Geo-Fencing Violations Detected",
            f"{m.geo_violations} transaction(s) were processed outside your registered location. "
            "Ensure your POS device is only used at your approved business address.",
            "/pos/location-settings", impact=10.0)

    # Training
    if float(sc.training_completion_score) < 80:
        remaining = m.training_modules_total - m.training_modules_completed
        add("training", RecommendationPriority.HIGH,
            "Complete Outstanding Training Modules",
            f"You have {remaining} training module(s) remaining. "
            "Completing all modules can improve your scorecard by up to 15 points.",
            "/training/my-courses", impact=15.0)

    if float(sc.certification_score) < 100:
        add("training", RecommendationPriority.MEDIUM,
            "Renew or Obtain Required Certifications",
            "Some required certifications are missing or expired. "
            "Active certifications are required to maintain your agent tier.",
            "/training/certifications", impact=10.0)

    # Customer Experience
    if float(sc.customer_satisfaction_score) < 70:
        add("customer_experience", RecommendationPriority.HIGH,
            "Improve Customer Satisfaction Rating",
            f"Your average customer rating is {m.avg_customer_rating:.1f}/5.0. "
            "Review customer feedback and complete the Customer Service Excellence module.",
            "/training/customer-service", impact=12.0)

    if float(sc.complaint_resolution_score) < 80 and m.total_complaints > 0:
        unresolved = m.total_complaints - m.resolved_complaints
        add("customer_experience", RecommendationPriority.MEDIUM,
            "Resolve Outstanding Customer Complaints",
            f"You have {unresolved} unresolved complaint(s). "
            "Timely resolution improves your customer experience score significantly.",
            "/complaints/my-cases", impact=8.0)

    # Transaction Performance
    if float(sc.txn_success_rate_score) < 80:
        rate = round(_safe_ratio(m.successful_transactions, m.total_transactions) * 100, 1)
        add("transaction", RecommendationPriority.MEDIUM,
            "Reduce Failed Transactions",
            f"Your transaction success rate is {rate}%. "
            "Check your POS device connectivity and ensure sufficient float balance.",
            "/pos/diagnostics", impact=10.0)

    if float(sc.txn_growth_rate_score) < 40:
        add("transaction", RecommendationPriority.LOW,
            "Grow Your Transaction Volume",
            "Your transaction volume has declined compared to the previous period. "
            "Consider promoting your services to new customers in your area.",
            "/marketing/agent-toolkit", impact=8.0)

    # Network Growth
    if float(sc.network_dimension_score) < 30 and m.total_sub_agents == 0:
        add("network", RecommendationPriority.LOW,
            "Expand Your Agent Network",
            "You currently have no sub-agents. Recruiting and activating sub-agents "
            "can significantly boost your network score and commission earnings.",
            "/agents/recruit", impact=10.0)

    return recs


def get_scorecard(db: Session, agent_id: uuid.UUID, scorecard_date: Optional[date] = None) -> Optional[AgentScorecard]:
    q = db.query(AgentScorecard).filter(AgentScorecard.agent_id == agent_id)
    if scorecard_date:
        q = q.filter(AgentScorecard.computation_date == scorecard_date)
    else:
        q = q.order_by(AgentScorecard.computation_date.desc())
    return q.first()


def get_scorecard_history(
    db: Session,
    agent_id: uuid.UUID,
    days: int = 90,
) -> List[ScorecardHistory]:
    since = date.today() - timedelta(days=days)
    return (
        db.query(ScorecardHistory)
        .filter(ScorecardHistory.agent_id == agent_id, ScorecardHistory.score_date >= since)
        .order_by(ScorecardHistory.score_date.asc())
        .all()
    )


def get_network_leaderboard(
    db: Session,
    tenant_id: uuid.UUID,
    limit: int = 20,
) -> List[AgentScorecard]:
    today = date.today()
    return (
        db.query(AgentScorecard)
        .filter(AgentScorecard.tenant_id == tenant_id, AgentScorecard.computation_date == today)
        .order_by(AgentScorecard.composite_score.desc())
        .limit(limit)
        .all()
    )


def get_or_compute_benchmark(db: Session, tenant_id: uuid.UUID) -> ScorecardBenchmark:
    today = date.today()
    existing = db.query(ScorecardBenchmark).filter(
        ScorecardBenchmark.tenant_id == tenant_id,
        ScorecardBenchmark.benchmark_date == today,
    ).first()
    if existing:
        return existing

    # Compute fresh benchmark
    scores = [
        float(r.composite_score)
        for r in db.query(AgentScorecard.composite_score)
        .filter(AgentScorecard.tenant_id == tenant_id, AgentScorecard.computation_date == today)
        .all()
    ]
    if not scores:
        return ScorecardBenchmark(
            tenant_id=tenant_id, avg_score=0, median_score=0,
            p75_score=0, p90_score=0, total_agents=0,
        )

    scores_sorted = sorted(scores)
    n = len(scores_sorted)
    avg = sum(scores_sorted) / n
    median = scores_sorted[n // 2]
    p75 = scores_sorted[int(n * 0.75)]
    p90 = scores_sorted[int(n * 0.90)]

    tier_counts = {t: 0 for t in ScoreTier}
    for s in scores_sorted:
        tier_counts[_compute_tier(s)] += 1

    bm = ScorecardBenchmark(
        tenant_id=tenant_id,
        avg_score=round(avg, 2),
        median_score=round(median, 2),
        p75_score=round(p75, 2),
        p90_score=round(p90, 2),
        platinum_count=tier_counts[ScoreTier.PLATINUM],
        gold_count=tier_counts[ScoreTier.GOLD],
        silver_count=tier_counts[ScoreTier.SILVER],
        bronze_count=tier_counts[ScoreTier.BRONZE],
        unrated_count=tier_counts[ScoreTier.UNRATED],
        total_agents=n,
    )
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return bm


def dismiss_recommendation(db: Session, rec_id: uuid.UUID, agent_id: uuid.UUID) -> bool:
    rec = db.query(ScorecardRecommendation).filter(
        ScorecardRecommendation.id == rec_id,
        ScorecardRecommendation.agent_id == agent_id,
    ).first()
    if not rec:
        return False
    rec.is_dismissed = True
    rec.dismissed_at = datetime.utcnow()
    db.commit()
    return True
