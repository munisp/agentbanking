"""
Customer Behavior Analytics - Production Implementation
Churn Prediction, Segmentation, LTV, Recommendation Engine
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
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

app = FastAPI(title="Customer Behavior Analytics", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class CustomerProfile(BaseModel):
    user_id: str
    registration_date: str
    transaction_history: List[Dict]
    engagement_metrics: Dict
    demographic_data: Optional[Dict] = None

class ChurnPrediction(BaseModel):
    user_id: str
    churn_probability: float
    churn_risk: str
    risk_factors: List[str]
    recommended_interventions: List[str]
    predicted_churn_date: Optional[str]
    timestamp: str

class CustomerSegment(BaseModel):
    segment_id: str
    segment_name: str
    characteristics: Dict
    user_count: int
    avg_ltv: float
    avg_transaction_value: float

class LTVCalculation(BaseModel):
    user_id: str
    lifetime_value: float
    predicted_ltv_12m: float
    predicted_ltv_24m: float
    confidence_interval: Dict
    value_drivers: List[Dict]
    timestamp: str

class Recommendation(BaseModel):
    user_id: str
    recommendations: List[Dict]
    reasoning: str
    expected_conversion_rate: float
    timestamp: str

class CustomerBehaviorEngine:
    """Customer Behavior Analytics and ML Engine"""
    
    def __init__(self):
        self.churn_model_weights = {
            "recency": 0.30,
            "frequency": 0.25,
            "monetary": 0.20,
            "engagement": 0.15,
            "tenure": 0.10
        }
        self.segments = self._initialize_segments()
        logger.info("Customer behavior engine initialized")
    
    def _initialize_segments(self) -> Dict:
        """Initialize customer segments"""
        return {
            "high_value": {
                "name": "High Value Customers",
                "criteria": {"avg_transaction": ">1000", "frequency": ">10/month", "tenure": ">12 months"},
                "ltv_multiplier": 2.5
            },
            "growing": {
                "name": "Growing Customers",
                "criteria": {"transaction_growth": ">20%", "engagement": "increasing"},
                "ltv_multiplier": 1.8
            },
            "at_risk": {
                "name": "At-Risk Customers",
                "criteria": {"recency": ">30 days", "frequency": "declining"},
                "ltv_multiplier": 0.5
            },
            "dormant": {
                "name": "Dormant Customers",
                "criteria": {"recency": ">90 days", "frequency": "0"},
                "ltv_multiplier": 0.1
            },
            "new": {
                "name": "New Customers",
                "criteria": {"tenure": "<3 months"},
                "ltv_multiplier": 1.2
            }
        }
    
    def _calculate_rfm_scores(self, transaction_history: List[Dict]) -> Dict:
        """Calculate Recency, Frequency, Monetary scores"""
        
        if not transaction_history:
            return {"recency": 0, "frequency": 0, "monetary": 0}
        
        # Recency: days since last transaction
        last_transaction = max([datetime.fromisoformat(t["timestamp"]) for t in transaction_history])
        recency_days = (datetime.utcnow() - last_transaction).days
        recency_score = max(0, 100 - recency_days)  # 0 days = 100, 100+ days = 0
        
        # Frequency: transaction count
        frequency = len(transaction_history)
        frequency_score = min(frequency * 5, 100)  # 20+ transactions = 100
        
        # Monetary: average transaction value
        avg_value = np.mean([t["amount"] for t in transaction_history])
        monetary_score = min(avg_value / 10, 100)  # $1000 avg = 100
        
        return {
            "recency": recency_score,
            "recency_days": recency_days,
            "frequency": frequency_score,
            "frequency_count": frequency,
            "monetary": monetary_score,
            "monetary_avg": avg_value
        }
    
    async def predict_churn(self, profile: CustomerProfile) -> ChurnPrediction:
        """Predict customer churn probability"""
        
        rfm = self._calculate_rfm_scores(profile.transaction_history)
        
        # Calculate engagement score
        engagement_metrics = profile.engagement_metrics
        login_frequency = engagement_metrics.get("login_count_30d", 0)
        feature_usage = engagement_metrics.get("feature_usage_score", 50)
        engagement_score = min((login_frequency * 5 + feature_usage) / 2, 100)
        
        # Calculate tenure score
        registration = datetime.fromisoformat(profile.registration_date)
        tenure_days = (datetime.utcnow() - registration).days
        tenure_score = min(tenure_days / 3.65, 100)  # 365 days = 100
        
        # Weighted churn risk score
        churn_risk_score = (
            (100 - rfm["recency"]) * self.churn_model_weights["recency"] +
            (100 - rfm["frequency"]) * self.churn_model_weights["frequency"] +
            (100 - rfm["monetary"]) * self.churn_model_weights["monetary"] +
            (100 - engagement_score) * self.churn_model_weights["engagement"] +
            (100 - tenure_score) * self.churn_model_weights["tenure"]
        )
        
        churn_probability = churn_risk_score / 100
        
        # Determine risk level
        if churn_probability >= 0.7:
            churn_risk = "CRITICAL"
        elif churn_probability >= 0.5:
            churn_risk = "HIGH"
        elif churn_probability >= 0.3:
            churn_risk = "MEDIUM"
        else:
            churn_risk = "LOW"
        
        # Identify risk factors
        risk_factors = []
        if rfm["recency_days"] > 30:
            risk_factors.append(f"No transaction in {rfm['recency_days']} days")
        if rfm["frequency_count"] < 5:
            risk_factors.append(f"Low transaction frequency ({rfm['frequency_count']} total)")
        if engagement_score < 30:
            risk_factors.append("Low platform engagement")
        if tenure_days < 90:
            risk_factors.append("New customer (high early churn risk)")
        
        # Recommend interventions
        interventions = []
        if churn_probability >= 0.5:
            interventions.append("Send personalized retention offer")
            interventions.append("Assign to customer success team")
        if rfm["recency_days"] > 30:
            interventions.append("Send re-engagement campaign")
        if engagement_score < 50:
            interventions.append("Provide onboarding assistance")
        
        # Predict churn date
        predicted_churn_date = None
        if churn_probability >= 0.5:
            days_to_churn = int(30 * (1 - churn_probability))
            predicted_churn_date = (datetime.utcnow() + timedelta(days=days_to_churn)).isoformat()
        
        logger.info(f"Churn prediction for {profile.user_id}: {churn_probability:.2%} ({churn_risk})")
        
        return ChurnPrediction(
            user_id=profile.user_id,
            churn_probability=round(churn_probability, 3),
            churn_risk=churn_risk,
            risk_factors=risk_factors if risk_factors else ["No significant risk factors"],
            recommended_interventions=interventions if interventions else ["Continue standard engagement"],
            predicted_churn_date=predicted_churn_date,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def segment_customer(self, profile: CustomerProfile) -> CustomerSegment:
        """Assign customer to segment"""
        
        rfm = self._calculate_rfm_scores(profile.transaction_history)
        registration = datetime.fromisoformat(profile.registration_date)
        tenure_days = (datetime.utcnow() - registration).days
        
        # Determine segment
        if rfm["recency_days"] > 90:
            segment_id = "dormant"
        elif rfm["recency_days"] > 30 or rfm["frequency_count"] < 3:
            segment_id = "at_risk"
        elif tenure_days < 90:
            segment_id = "new"
        elif rfm["monetary_avg"] > 1000 and rfm["frequency_count"] > 10:
            segment_id = "high_value"
        else:
            segment_id = "growing"
        
        segment_info = self.segments[segment_id]
        
        return CustomerSegment(
            segment_id=segment_id,
            segment_name=segment_info["name"],
            characteristics=segment_info["criteria"],
            user_count=1,  # In production: query database for segment count
            avg_ltv=rfm["monetary_avg"] * rfm["frequency_count"] * segment_info["ltv_multiplier"],
            avg_transaction_value=rfm["monetary_avg"]
        )
    
    async def calculate_ltv(self, profile: CustomerProfile) -> LTVCalculation:
        """Calculate Customer Lifetime Value"""
        
        rfm = self._calculate_rfm_scores(profile.transaction_history)
        segment = await self.segment_customer(profile)
        
        # Historical LTV
        historical_ltv = sum([t["amount"] for t in profile.transaction_history])
        
        # Predict future LTV
        avg_monthly_value = rfm["monetary_avg"] * (rfm["frequency_count"] / max(1, len(profile.transaction_history) / 30))
        
        # Adjust for churn probability
        churn_pred = await self.predict_churn(profile)
        retention_rate = 1 - churn_pred.churn_probability
        
        # 12-month prediction
        predicted_ltv_12m = historical_ltv + (avg_monthly_value * 12 * retention_rate)
        
        # 24-month prediction with compounding retention
        retention_24m = retention_rate ** 2
        predicted_ltv_24m = historical_ltv + (avg_monthly_value * 24 * retention_24m)
        
        # Confidence intervals (simplified)
        confidence_interval = {
            "lower_bound": predicted_ltv_12m * 0.7,
            "upper_bound": predicted_ltv_12m * 1.3
        }
        
        # Value drivers
        value_drivers = [
            {"driver": "Average Transaction Value", "contribution": rfm["monetary_avg"], "weight": 0.40},
            {"driver": "Transaction Frequency", "contribution": rfm["frequency_count"], "weight": 0.35},
            {"driver": "Retention Rate", "contribution": retention_rate, "weight": 0.25}
        ]
        
        logger.info(f"LTV for {profile.user_id}: current=${historical_ltv:.2f}, 12m=${predicted_ltv_12m:.2f}")
        
        return LTVCalculation(
            user_id=profile.user_id,
            lifetime_value=round(historical_ltv, 2),
            predicted_ltv_12m=round(predicted_ltv_12m, 2),
            predicted_ltv_24m=round(predicted_ltv_24m, 2),
            confidence_interval=confidence_interval,
            value_drivers=value_drivers,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def generate_recommendations(self, profile: CustomerProfile) -> Recommendation:
        """Generate personalized recommendations"""
        
        rfm = self._calculate_rfm_scores(profile.transaction_history)
        segment = await self.segment_customer(profile)
        
        recommendations = []
        
        # Recommend based on segment
        if segment.segment_id == "high_value":
            recommendations.append({
                "type": "premium_feature",
                "title": "Upgrade to Premium",
                "description": "Get exclusive benefits and lower fees",
                "expected_value": 200
            })
        elif segment.segment_id == "at_risk":
            recommendations.append({
                "type": "retention_offer",
                "title": "Special Offer: 50% Off Fees",
                "description": "We value your business - enjoy reduced fees",
                "expected_value": 50
            })
        elif segment.segment_id == "new":
            recommendations.append({
                "type": "onboarding",
                "title": "Complete Your Profile",
                "description": "Add beneficiaries for faster transfers",
                "expected_value": 30
            })
        
        # Recommend based on transaction patterns
        if rfm["frequency_count"] > 5:
            recommendations.append({
                "type": "cross_sell",
                "title": "Try Bulk Transfers",
                "description": "Save time with batch payments",
                "expected_value": 100
            })
        
        # Recommend based on recency
        if rfm["recency_days"] > 14:
            recommendations.append({
                "type": "engagement",
                "title": "Send Money to Family",
                "description": "Quick transfer to your saved beneficiaries",
                "expected_value": rfm["monetary_avg"]
            })
        
        reasoning = f"Based on {segment.segment_name} segment and {rfm['frequency_count']} transactions"
        expected_conversion = 0.15 if segment.segment_id == "high_value" else 0.08
        
        return Recommendation(
            user_id=profile.user_id,
            recommendations=recommendations[:3],  # Top 3
            reasoning=reasoning,
            expected_conversion_rate=expected_conversion,
            timestamp=datetime.utcnow().isoformat()
        )

# Initialize engine
behavior_engine = CustomerBehaviorEngine()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "customer-behavior-analytics",
        "segments": len(behavior_engine.segments)
    }

@app.post("/api/v1/analytics/churn/predict", response_model=ChurnPrediction)
async def predict_churn(profile: CustomerProfile):
    """Predict customer churn probability"""
    try:
        result = await behavior_engine.predict_churn(profile)
        return result
    except Exception as e:
        logger.error(f"Churn prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Churn prediction failed: {str(e)}")

@app.post("/api/v1/analytics/segment", response_model=CustomerSegment)
async def segment_customer(profile: CustomerProfile):
    """Assign customer to segment"""
    try:
        result = await behavior_engine.segment_customer(profile)
        return result
    except Exception as e:
        logger.error(f"Segmentation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Segmentation failed: {str(e)}")

@app.post("/api/v1/analytics/ltv/calculate", response_model=LTVCalculation)
async def calculate_ltv(profile: CustomerProfile):
    """Calculate Customer Lifetime Value"""
    try:
        result = await behavior_engine.calculate_ltv(profile)
        return result
    except Exception as e:
        logger.error(f"LTV calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LTV calculation failed: {str(e)}")

@app.post("/api/v1/analytics/recommendations", response_model=Recommendation)
async def generate_recommendations(profile: CustomerProfile):
    """Generate personalized recommendations"""
    try:
        result = await behavior_engine.generate_recommendations(profile)
        return result
    except Exception as e:
        logger.error(f"Recommendation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recommendation generation failed: {str(e)}")

@app.get("/api/v1/analytics/segments")
async def list_segments():
    """List all customer segments"""
    return {"segments": behavior_engine.segments}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8034)
