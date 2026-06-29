"""
Risk Management Framework - Production Implementation
Credit Risk, Operational Risk, Market Risk, Liquidity Risk
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime, timedelta
import logging
import numpy as np

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Risk Management Framework", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class RiskType(str, Enum):
    CREDIT = "credit"
    OPERATIONAL = "operational"
    MARKET = "market"
    LIQUIDITY = "liquidity"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CreditRiskRequest(BaseModel):
    entity_id: str
    entity_type: str  # "individual" or "business"
    credit_amount: float
    currency: str
    duration_days: int
    financial_data: Dict
    transaction_history: Optional[List[Dict]] = None

class CreditScore(BaseModel):
    entity_id: str
    credit_score: int  # 300-850
    risk_level: RiskLevel
    probability_of_default: float
    recommended_limit: float
    interest_rate_adjustment: float
    factors: List[Dict]
    timestamp: str

class VaRCalculation(BaseModel):
    portfolio_id: str
    var_95: float
    var_99: float
    expected_shortfall: float
    confidence_level: float
    time_horizon_days: int
    currency: str

class RiskAlert(BaseModel):
    alert_id: str
    risk_type: RiskType
    severity: RiskLevel
    message: str
    affected_entities: List[str]
    recommended_action: str
    timestamp: str

class RiskManagementEngine:
    """Comprehensive Risk Management System"""
    
    def __init__(self):
        self.risk_limits = self._initialize_risk_limits()
        self.credit_models = self._initialize_credit_models()
        self.market_data = self._initialize_market_data()
        logger.info("Risk management engine initialized")
    
    def _initialize_risk_limits(self) -> Dict:
        """Initialize risk limit thresholds"""
        return {
            "credit": {
                "individual_max": 50000,
                "business_max": 500000,
                "portfolio_concentration": 0.10,  # Max 10% to single entity
                "total_exposure_limit": 10000000
            },
            "operational": {
                "max_downtime_minutes": 60,
                "max_transaction_failures": 100,
                "max_processing_delay_seconds": 30
            },
            "market": {
                "max_fx_exposure": 1000000,
                "max_single_currency_exposure": 0.30,
                "var_limit_95": 100000
            },
            "liquidity": {
                "min_cash_reserve": 500000,
                "min_liquidity_ratio": 0.20,
                "max_maturity_mismatch_days": 30
            }
        }
    
    def _initialize_credit_models(self) -> Dict:
        """Initialize credit scoring models"""
        return {
            "individual": {
                "transaction_history_weight": 0.35,
                "payment_behavior_weight": 0.25,
                "account_age_weight": 0.15,
                "transaction_volume_weight": 0.15,
                "fraud_history_weight": 0.10
            },
            "business": {
                "revenue_weight": 0.30,
                "payment_history_weight": 0.25,
                "business_age_weight": 0.15,
                "transaction_volume_weight": 0.20,
                "industry_risk_weight": 0.10
            }
        }
    
    def _initialize_market_data(self) -> Dict:
        """Initialize market risk data"""
        return {
            "fx_volatility": {
                "USD_NGN": 0.08,
                "USD_GBP": 0.05,
                "USD_EUR": 0.04,
                "NGN_GHS": 0.12
            },
            "correlation_matrix": {
                ("USD", "EUR"): 0.85,
                ("USD", "GBP"): 0.75,
                ("USD", "NGN"): -0.20
            }
        }
    
    async def calculate_credit_score(self, request: CreditRiskRequest) -> CreditScore:
        """Calculate credit score and risk assessment"""
        
        model_weights = self.credit_models[request.entity_type]
        
        # Extract features from financial data
        transaction_count = len(request.transaction_history) if request.transaction_history else 0
        avg_transaction = np.mean([t.get("amount", 0) for t in request.transaction_history]) if transaction_count > 0 else 0
        
        # Calculate component scores (0-100)
        transaction_history_score = min(transaction_count / 50 * 100, 100)  # 50+ transactions = 100
        
        payment_behavior_score = request.financial_data.get("payment_success_rate", 0.95) * 100
        
        account_age_days = request.financial_data.get("account_age_days", 0)
        account_age_score = min(account_age_days / 365 * 100, 100)  # 1 year = 100
        
        transaction_volume_score = min(avg_transaction / 1000 * 100, 100)  # $1000 avg = 100
        
        fraud_incidents = request.financial_data.get("fraud_incidents", 0)
        fraud_history_score = max(100 - (fraud_incidents * 20), 0)  # Each incident -20 points
        
        # Weighted credit score (300-850 scale)
        raw_score = (
            transaction_history_score * model_weights["transaction_history_weight"] +
            payment_behavior_score * model_weights["payment_behavior_weight"] +
            account_age_score * model_weights["account_age_weight"] +
            transaction_volume_score * model_weights["transaction_volume_weight"] +
            fraud_history_score * model_weights["fraud_history_weight"]
        )
        
        # Scale to 300-850
        credit_score = int(300 + (raw_score / 100) * 550)
        
        # Calculate probability of default (PD)
        if credit_score >= 750:
            pd = 0.01  # 1%
            risk_level = RiskLevel.LOW
        elif credit_score >= 650:
            pd = 0.05  # 5%
            risk_level = RiskLevel.MEDIUM
        elif credit_score >= 550:
            pd = 0.15  # 15%
            risk_level = RiskLevel.HIGH
        else:
            pd = 0.30  # 30%
            risk_level = RiskLevel.CRITICAL
        
        # Calculate recommended credit limit
        base_limit = self.risk_limits["credit"][f"{request.entity_type}_max"]
        recommended_limit = base_limit * (1 - pd)
        
        # Interest rate adjustment (basis points)
        interest_adjustment = pd * 1000  # 1% PD = 100 bps
        
        # Risk factors
        factors = []
        if transaction_history_score < 50:
            factors.append({"factor": "Limited transaction history", "impact": "negative", "score": transaction_history_score})
        if payment_behavior_score < 90:
            factors.append({"factor": "Payment reliability concerns", "impact": "negative", "score": payment_behavior_score})
        if fraud_incidents > 0:
            factors.append({"factor": f"{fraud_incidents} fraud incidents", "impact": "negative", "score": fraud_history_score})
        if account_age_score < 30:
            factors.append({"factor": "New account", "impact": "negative", "score": account_age_score})
        
        if not factors:
            factors.append({"factor": "Strong credit profile", "impact": "positive", "score": credit_score})
        
        logger.info(f"Credit score for {request.entity_id}: {credit_score}, PD: {pd:.2%}, limit: ${recommended_limit:,.2f}")
        
        return CreditScore(
            entity_id=request.entity_id,
            credit_score=credit_score,
            risk_level=risk_level,
            probability_of_default=round(pd, 4),
            recommended_limit=round(recommended_limit, 2),
            interest_rate_adjustment=round(interest_adjustment, 2),
            factors=factors,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def calculate_var(self, portfolio_id: str, positions: List[Dict], confidence: float = 0.95, horizon_days: int = 1) -> VaRCalculation:
        """Calculate Value at Risk (VaR) for portfolio"""
        
        # Extract portfolio value and currency exposures
        total_value = sum(p["value"] for p in positions)
        
        # Calculate portfolio volatility (simplified)
        currency_exposures = {}
        for pos in positions:
            currency = pos["currency"]
            currency_exposures[currency] = currency_exposures.get(currency, 0) + pos["value"]
        
        # Weighted volatility
        portfolio_volatility = 0
        for currency, exposure in currency_exposures.items():
            weight = exposure / total_value
            vol = self.market_data["fx_volatility"].get(f"USD_{currency}", 0.05)
            portfolio_volatility += (weight * vol) ** 2
        
        portfolio_volatility = np.sqrt(portfolio_volatility)
        
        # Adjust for time horizon
        volatility_adjusted = portfolio_volatility * np.sqrt(horizon_days)
        
        # Calculate VaR at different confidence levels
        z_95 = 1.645  # 95% confidence
        z_99 = 2.326  # 99% confidence
        
        var_95 = total_value * volatility_adjusted * z_95
        var_99 = total_value * volatility_adjusted * z_99
        
        # Expected Shortfall (CVaR) - average loss beyond VaR
        expected_shortfall = var_99 * 1.2  # Approximation
        
        logger.info(f"VaR calculation for {portfolio_id}: 95%=${var_95:,.2f}, 99%=${var_99:,.2f}")
        
        return VaRCalculation(
            portfolio_id=portfolio_id,
            var_95=round(var_95, 2),
            var_99=round(var_99, 2),
            expected_shortfall=round(expected_shortfall, 2),
            confidence_level=confidence,
            time_horizon_days=horizon_days,
            currency="USD"
        )
    
    async def check_operational_risk(self, metrics: Dict) -> List[RiskAlert]:
        """Monitor operational risk metrics"""
        
        alerts = []
        limits = self.risk_limits["operational"]
        
        # Check downtime
        if metrics.get("downtime_minutes", 0) > limits["max_downtime_minutes"]:
            alerts.append(RiskAlert(
                alert_id=f"OPS-{datetime.utcnow().timestamp()}",
                risk_type=RiskType.OPERATIONAL,
                severity=RiskLevel.CRITICAL,
                message=f"System downtime exceeded limit: {metrics['downtime_minutes']} minutes",
                affected_entities=["platform"],
                recommended_action="Investigate and restore service immediately",
                timestamp=datetime.utcnow().isoformat()
            ))
        
        # Check transaction failures
        if metrics.get("failed_transactions", 0) > limits["max_transaction_failures"]:
            alerts.append(RiskAlert(
                alert_id=f"OPS-{datetime.utcnow().timestamp()}",
                risk_type=RiskType.OPERATIONAL,
                severity=RiskLevel.HIGH,
                message=f"Transaction failure rate exceeded threshold: {metrics['failed_transactions']} failures",
                affected_entities=["transaction_service"],
                recommended_action="Review transaction logs and gateway status",
                timestamp=datetime.utcnow().isoformat()
            ))
        
        return alerts
    
    async def check_liquidity_risk(self, cash_position: float, liabilities_30d: float) -> Dict:
        """Assess liquidity risk"""
        
        limits = self.risk_limits["liquidity"]
        
        liquidity_ratio = cash_position / liabilities_30d if liabilities_30d > 0 else 1.0
        
        if cash_position < limits["min_cash_reserve"]:
            risk_level = RiskLevel.CRITICAL
            message = f"Cash reserve below minimum: ${cash_position:,.2f} < ${limits['min_cash_reserve']:,.2f}"
        elif liquidity_ratio < limits["min_liquidity_ratio"]:
            risk_level = RiskLevel.HIGH
            message = f"Liquidity ratio below threshold: {liquidity_ratio:.2%} < {limits['min_liquidity_ratio']:.2%}"
        else:
            risk_level = RiskLevel.LOW
            message = "Liquidity position healthy"
        
        return {
            "cash_position": cash_position,
            "liabilities_30d": liabilities_30d,
            "liquidity_ratio": round(liquidity_ratio, 4),
            "risk_level": risk_level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }

# Initialize engine
risk_engine = RiskManagementEngine()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "risk-management",
        "risk_types": ["credit", "operational", "market", "liquidity"]
    }

@app.post("/api/v1/risk/credit/score", response_model=CreditScore)
async def calculate_credit_score(request: CreditRiskRequest):
    """Calculate credit score and risk assessment"""
    try:
        result = await risk_engine.calculate_credit_score(request)
        return result
    except Exception as e:
        logger.error(f"Credit scoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Credit scoring failed: {str(e)}")

@app.post("/api/v1/risk/market/var", response_model=VaRCalculation)
async def calculate_portfolio_var(portfolio_id: str, positions: List[Dict], confidence: float = 0.95):
    """Calculate Value at Risk for portfolio"""
    try:
        result = await risk_engine.calculate_var(portfolio_id, positions, confidence)
        return result
    except Exception as e:
        logger.error(f"VaR calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"VaR calculation failed: {str(e)}")

@app.post("/api/v1/risk/operational/check", response_model=List[RiskAlert])
async def check_operational_risk(metrics: Dict):
    """Check operational risk metrics"""
    try:
        alerts = await risk_engine.check_operational_risk(metrics)
        return alerts
    except Exception as e:
        logger.error(f"Operational risk check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk check failed: {str(e)}")

@app.post("/api/v1/risk/liquidity/check")
async def check_liquidity_risk(cash_position: float, liabilities_30d: float):
    """Assess liquidity risk"""
    try:
        result = await risk_engine.check_liquidity_risk(cash_position, liabilities_30d)
        return result
    except Exception as e:
        logger.error(f"Liquidity risk check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Liquidity check failed: {str(e)}")

@app.get("/api/v1/risk/limits")
async def get_risk_limits():
    """Get current risk limits"""
    return risk_engine.risk_limits

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8033)
