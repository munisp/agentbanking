import sys as _sys, os as _os

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

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Credit Scoring Service for Remittance Platform
Provides credit scoring and risk assessment capabilities

NOTE: Scores are only served from a versioned, trained model artifact
(configured via CREDIT_MODEL_PATH / CREDIT_SCALER_PATH / CREDIT_ENCODERS_PATH)
that was trained on real repayment data. If no artifact is available the
service refuses to score (HTTP 503) rather than training on synthetic data.
Training requires a real labeled dataset (CREDIT_TRAINING_DATA_PATH, CSV
with a 'credit_score' target column). Model provenance is surfaced in every
response and in /health.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("credit-scoring-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/credit_scoring")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Model artifact configuration (trained on real repayment data, produced offline)
MODEL_PATH = os.getenv("CREDIT_MODEL_PATH", "/models/credit_scoring/credit_scoring_model.joblib")
SCALER_PATH = os.getenv("CREDIT_SCALER_PATH", "/models/credit_scoring/credit_scoring_scaler.joblib")
ENCODERS_PATH = os.getenv("CREDIT_ENCODERS_PATH", "/models/credit_scoring/credit_scoring_encoders.joblib")
MODEL_METADATA_PATH = os.getenv("CREDIT_MODEL_METADATA_PATH", "/models/credit_scoring/credit_scoring_metadata.json")
TRAINING_DATA_PATH = os.getenv("CREDIT_TRAINING_DATA_PATH", "")  # CSV with real labeled repayment data

class CreditScoreRange(str, Enum):
    EXCELLENT = "excellent"  # 800-850
    VERY_GOOD = "very_good"  # 740-799
    GOOD = "good"           # 670-739
    FAIR = "fair"           # 580-669
    POOR = "poor"           # 300-579

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class CreditScoreRequest:
    customer_id: str
    personal_info: Dict[str, Any]
    financial_info: Dict[str, Any]
    credit_history: Dict[str, Any]
    employment_info: Dict[str, Any]

@dataclass
class CreditScoreResponse:
    customer_id: str
    credit_score: int
    score_range: CreditScoreRange
    risk_level: RiskLevel
    confidence: Optional[float]  # None unless the model artifact provides a calibrated estimate
    factors: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime
    model_version: str = "unknown"
    model_provenance: Optional[Dict[str, Any]] = None

class CreditProfile(Base):
    __tablename__ = "credit_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, nullable=False, unique=True)
    credit_score = Column(Integer, nullable=False)
    score_range = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)
    factors = Column(Text)  # JSON string
    recommendations = Column(Text)  # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class CreditScoreHistory(Base):
    __tablename__ = "credit_score_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String, nullable=False)
    credit_score = Column(Integer, nullable=False)
    score_change = Column(Integer)
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class CreditScoringService:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.label_encoders = {}
        self.feature_names = []
        self.model_loaded = False
        self.model_version: Optional[str] = None
        self.model_provenance: Dict[str, Any] = {}
        self.load_error: Optional[str] = None

    async def initialize(self):
        """Initialize the credit scoring service by loading the trained artifact.

        The service starts even when no artifact is present, but scoring
        requests are refused with HTTP 503 until a real trained model is
        deployed.
        """
        await self.load_model()
        if self.model_loaded:
            logger.info(f"Credit Scoring Service initialized (model version: {self.model_version})")
        else:
            logger.error(
                "Credit Scoring Service started WITHOUT a trained model artifact "
                f"({self.load_error}). Scoring requests will return 503."
            )

    async def load_model(self):
        """Load the versioned trained model artifact. Never trains on
        synthetic data as a fallback."""
        if not (os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH) and os.path.exists(ENCODERS_PATH)):
            self.load_error = (
                f"Trained model artifact not found (expected model at {MODEL_PATH}, "
                f"scaler at {SCALER_PATH}, encoders at {ENCODERS_PATH})"
            )
            self.model_loaded = False
            return

        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.label_encoders = joblib.load(ENCODERS_PATH)

            # Load provenance metadata (who/what/when the model was trained on)
            if os.path.exists(MODEL_METADATA_PATH):
                with open(MODEL_METADATA_PATH) as f:
                    self.model_provenance = json.load(f)
            else:
                self.model_provenance = {}
                logger.warning(
                    f"No model metadata at {MODEL_METADATA_PATH} — provenance unknown"
                )

            self.model_version = str(self.model_provenance.get("version", "unversioned"))
            self.model_loaded = True
            self.load_error = None
            logger.info(f"Loaded trained credit scoring model (version: {self.model_version})")
        except Exception as e:
            self.load_error = f"Failed to load model artifact: {e}"
            self.model_loaded = False
            logger.error(self.load_error)

    async def train_model(self):
        """Train a credit scoring model on REAL labeled repayment data.

        Requires CREDIT_TRAINING_DATA_PATH pointing to a CSV of real, labeled
        credit outcomes (must contain a 'credit_score' target column).
        Refuses to train on synthetic/random data.
        """
        if not TRAINING_DATA_PATH or not os.path.exists(TRAINING_DATA_PATH):
            raise RuntimeError(
                "No real training data configured. Set CREDIT_TRAINING_DATA_PATH to a CSV "
                "of labeled repayment/credit outcome data. Training on synthetic data is "
                "not permitted in this service."
            )

        try:
            data = pd.read_csv(TRAINING_DATA_PATH)

            if "credit_score" not in data.columns:
                raise RuntimeError(
                    f"Training data at {TRAINING_DATA_PATH} has no 'credit_score' target column"
                )

            logger.info(f"Training on {len(data)} real labeled records from {TRAINING_DATA_PATH}")

            # Prepare features
            X, y = self.prepare_features(data)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # Train model
            self.model = GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )

            self.model.fit(X_train_scaled, y_train)

            # Evaluate model
            y_pred = self.model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            logger.info(f"Model trained on real data - MAE: {mae:.2f}, MSE: {mse:.2f}, R2: {r2:.3f}")

            # Persist artifact + provenance metadata
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            joblib.dump(self.model, MODEL_PATH)
            joblib.dump(self.scaler, SCALER_PATH)
            joblib.dump(self.label_encoders, ENCODERS_PATH)

            version = f"v{int(datetime.utcnow().timestamp())}"
            metadata = {
                "version": version,
                "trained_at": datetime.utcnow().isoformat(),
                "training_data_path": TRAINING_DATA_PATH,
                "training_samples": int(len(data)),
                "model_type": "sklearn.GradientBoostingRegressor",
                "metrics": {"mae": float(mae), "mse": float(mse), "r2": float(r2)},
            }
            with open(MODEL_METADATA_PATH, "w") as f:
                json.dump(metadata, f, indent=2)

            self.model_provenance = metadata
            self.model_version = version
            self.model_loaded = True
            self.load_error = None

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise

    def prepare_features(self, data: pd.DataFrame) -> tuple:
        """Prepare features for model training"""
        # Separate target variable
        y = data['credit_score'].values
        X_data = data.drop(['credit_score'], axis=1)

        # Encode categorical variables
        categorical_columns = ['education_level']

        for col in categorical_columns:
            if col in X_data.columns:
                if col not in self.label_encoders:
                    self.label_encoders[col] = LabelEncoder()
                    X_data[col] = self.label_encoders[col].fit_transform(X_data[col])
                else:
                    X_data[col] = self.label_encoders[col].transform(X_data[col])

        self.feature_names = list(X_data.columns)
        X = X_data.values

        return X, y

    async def calculate_credit_score(self, request: CreditScoreRequest) -> CreditScoreResponse:
        """Calculate credit score for a customer using the trained artifact."""
        try:
            if not self.model_loaded or self.model is None:
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "No trained credit scoring model is deployed. "
                        f"{self.load_error or 'Model artifact missing.'} "
                        "Scoring is refused rather than estimated."
                    ),
                )

            # Prepare input features
            features = self.prepare_input_features(request)

            # Scale features
            features_scaled = self.scaler.transform([features])

            # Predict credit score
            predicted_score = self.model.predict(features_scaled)[0]
            credit_score = int(np.clip(predicted_score, 300, 850))

            # Determine score range and risk level
            score_range = self.get_score_range(credit_score)
            risk_level = self.get_risk_level(credit_score)

            # No fabricated confidence: only surface a calibrated estimate if
            # the deployed model artifact provides one (e.g. prediction intervals).
            confidence = None
            if hasattr(self.model, "predict_proba"):
                try:
                    confidence = float(np.max(self.model.predict_proba(features_scaled)[0]))
                except Exception:
                    confidence = None

            # Generate factors and recommendations
            factors = self.analyze_factors(request, credit_score)
            recommendations = self.generate_recommendations(request, credit_score, factors)

            # Save to database
            await self.save_credit_profile(request.customer_id, credit_score,
                                         score_range, risk_level, confidence,
                                         factors, recommendations)

            return CreditScoreResponse(
                customer_id=request.customer_id,
                credit_score=credit_score,
                score_range=score_range,
                risk_level=risk_level,
                confidence=confidence,
                factors=factors,
                recommendations=recommendations,
                timestamp=datetime.utcnow(),
                model_version=self.model_version or "unknown",
                model_provenance={
                    "model_type": self.model_provenance.get("model_type", "unknown"),
                    "trained_at": self.model_provenance.get("trained_at"),
                    "training_data": self.model_provenance.get("training_data_path"),
                    "training_samples": self.model_provenance.get("training_samples"),
                    "metrics": self.model_provenance.get("metrics"),
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Credit score calculation failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def prepare_input_features(self, request: CreditScoreRequest) -> List[float]:
        """Prepare input features from request"""
        features = []

        # Personal info
        features.append(request.personal_info.get('age', 30))
        features.append(request.financial_info.get('income', 50000))
        features.append(request.employment_info.get('employment_length', 5))

        # Education level (encode)
        education = request.personal_info.get('education_level', 'bachelor')
        if 'education_level' in self.label_encoders:
            try:
                education_encoded = self.label_encoders['education_level'].transform([education])[0]
            except ValueError:
                education_encoded = 1  # Default to bachelor
        else:
            education_encoded = 1
        features.append(education_encoded)

        # Credit history
        features.append(request.credit_history.get('credit_history_length', 5))
        features.append(request.credit_history.get('number_of_accounts', 3))
        features.append(request.credit_history.get('total_credit_limit', 10000))
        features.append(request.credit_history.get('credit_utilization', 0.3))
        features.append(request.credit_history.get('payment_history', 0.9))
        features.append(request.credit_history.get('number_of_inquiries', 1))
        features.append(request.credit_history.get('delinquencies', 0))

        # Financial behavior
        features.append(request.financial_info.get('debt_to_income', 0.2))
        features.append(request.financial_info.get('savings_account', 1))
        features.append(request.financial_info.get('checking_account', 1))
        features.append(request.financial_info.get('mortgage', 0))
        features.append(request.financial_info.get('auto_loan', 0))

        return features

    def get_score_range(self, score: int) -> CreditScoreRange:
        """Get credit score range category"""
        if score >= 800:
            return CreditScoreRange.EXCELLENT
        elif score >= 740:
            return CreditScoreRange.VERY_GOOD
        elif score >= 670:
            return CreditScoreRange.GOOD
        elif score >= 580:
            return CreditScoreRange.FAIR
        else:
            return CreditScoreRange.POOR

    def get_risk_level(self, score: int) -> RiskLevel:
        """Get risk level based on credit score"""
        if score >= 740:
            return RiskLevel.LOW
        elif score >= 670:
            return RiskLevel.MEDIUM
        elif score >= 580:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH

    def analyze_factors(self, request: CreditScoreRequest, score: int) -> Dict[str, Any]:
        """Analyze factors affecting credit score"""
        factors = {
            'positive_factors': [],
            'negative_factors': [],
            'neutral_factors': [],
            'score_breakdown': {}
        }

        # Payment history analysis
        payment_history = request.credit_history.get('payment_history', 0.9)
        if payment_history > 0.95:
            factors['positive_factors'].append('Excellent payment history')
        elif payment_history < 0.8:
            factors['negative_factors'].append('Poor payment history')

        # Credit utilization analysis
        utilization = request.credit_history.get('credit_utilization', 0.3)
        if utilization < 0.1:
            factors['positive_factors'].append('Very low credit utilization')
        elif utilization > 0.7:
            factors['negative_factors'].append('High credit utilization')

        # Credit history length
        history_length = request.credit_history.get('credit_history_length', 5)
        if history_length > 10:
            factors['positive_factors'].append('Long credit history')
        elif history_length < 2:
            factors['negative_factors'].append('Limited credit history')

        # Income analysis
        income = request.financial_info.get('income', 50000)
        if income > 100000:
            factors['positive_factors'].append('High income')
        elif income < 30000:
            factors['negative_factors'].append('Low income')

        # Delinquencies
        delinquencies = request.credit_history.get('delinquencies', 0)
        if delinquencies == 0:
            factors['positive_factors'].append('No delinquencies')
        elif delinquencies > 2:
            factors['negative_factors'].append('Multiple delinquencies')

        # Score breakdown (estimated contribution)
        factors['score_breakdown'] = {
            'payment_history': int(payment_history * 200),
            'credit_utilization': int((1 - utilization) * 100),
            'credit_history_length': min(history_length * 8, 80),
            'income_factor': min(int(np.log(max(income, 1000)) * 20), 100),
            'delinquencies_impact': -delinquencies * 30
        }

        return factors

    def generate_recommendations(self, request: CreditScoreRequest, score: int,
                               factors: Dict[str, Any]) -> List[str]:
        """Generate recommendations to improve credit score"""
        recommendations = []

        # Payment history recommendations
        payment_history = request.credit_history.get('payment_history', 0.9)
        if payment_history < 0.95:
            recommendations.append("Make all payments on time to improve payment history")

        # Credit utilization recommendations
        utilization = request.credit_history.get('credit_utilization', 0.3)
        if utilization > 0.3:
            recommendations.append("Reduce credit utilization below 30%")
        elif utilization > 0.1:
            recommendations.append("Consider reducing credit utilization below 10% for optimal score")

        # Credit history recommendations
        history_length = request.credit_history.get('credit_history_length', 5)
        if history_length < 5:
            recommendations.append("Keep old accounts open to increase credit history length")

        # Account diversity
        num_accounts = request.credit_history.get('number_of_accounts', 3)
        if num_accounts < 3:
            recommendations.append("Consider diversifying credit types (credit cards, loans)")

        # Inquiries
        inquiries = request.credit_history.get('number_of_inquiries', 1)
        if inquiries > 3:
            recommendations.append("Limit new credit applications to reduce hard inquiries")

        # Income recommendations
        income = request.financial_info.get('income', 50000)
        if income < 50000:
            recommendations.append("Consider ways to increase income for better creditworthiness")

        # General recommendations based on score
        if score < 600:
            recommendations.append("Focus on paying down existing debt")
            recommendations.append("Consider a secured credit card to rebuild credit")
        elif score < 700:
            recommendations.append("Monitor credit report regularly for errors")
            recommendations.append("Consider becoming an authorized user on a family member's account")

        return recommendations

    async def save_credit_profile(self, customer_id: str, credit_score: int,
                                score_range: CreditScoreRange, risk_level: RiskLevel,
                                confidence: Optional[float], factors: Dict[str, Any],
                                recommendations: List[str]):
        """Save credit profile to database"""
        db = SessionLocal()
        try:
            # Check for existing profile
            existing_profile = db.query(CreditProfile).filter(
                CreditProfile.customer_id == customer_id,
                CreditProfile.is_active == True
            ).first()

            if existing_profile:
                # Update existing profile
                score_change = credit_score - existing_profile.credit_score

                existing_profile.credit_score = credit_score
                existing_profile.score_range = score_range.value
                existing_profile.risk_level = risk_level.value
                existing_profile.confidence = confidence
                existing_profile.model_version = self.model_version
                existing_profile.factors = json.dumps(factors)
                existing_profile.recommendations = json.dumps(recommendations)
                existing_profile.updated_at = datetime.utcnow()

                # Log score change
                if score_change != 0:
                    history_entry = CreditScoreHistory(
                        customer_id=customer_id,
                        credit_score=credit_score,
                        score_change=score_change,
                        reason="Profile update"
                    )
                    db.add(history_entry)
            else:
                # Create new profile
                new_profile = CreditProfile(
                    customer_id=customer_id,
                    credit_score=credit_score,
                    score_range=score_range.value,
                    risk_level=risk_level.value,
                    confidence=confidence,
                    model_version=self.model_version,
                    factors=json.dumps(factors),
                    recommendations=json.dumps(recommendations)
                )
                db.add(new_profile)

                # Log initial score
                history_entry = CreditScoreHistory(
                    customer_id=customer_id,
                    credit_score=credit_score,
                    score_change=0,
                    reason="Initial scoring"
                )
                db.add(history_entry)

            db.commit()

        except Exception as e:
            logger.error(f"Failed to save credit profile: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def get_credit_profile(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get existing credit profile"""
        db = SessionLocal()
        try:
            profile = db.query(CreditProfile).filter(
                CreditProfile.customer_id == customer_id,
                CreditProfile.is_active == True
            ).first()

            if profile:
                return {
                    'customer_id': profile.customer_id,
                    'credit_score': profile.credit_score,
                    'score_range': profile.score_range,
                    'risk_level': profile.risk_level,
                    'confidence': profile.confidence,
                    'model_version': profile.model_version,
                    'factors': json.loads(profile.factors),
                    'recommendations': json.loads(profile.recommendations),
                    'created_at': profile.created_at.isoformat(),
                    'updated_at': profile.updated_at.isoformat()
                }

            return None

        finally:
            db.close()

    async def get_score_history(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get credit score history for customer"""
        db = SessionLocal()
        try:
            history = db.query(CreditScoreHistory).filter(
                CreditScoreHistory.customer_id == customer_id
            ).order_by(CreditScoreHistory.timestamp.desc()).limit(50).all()

            return [
                {
                    'credit_score': entry.credit_score,
                    'score_change': entry.score_change,
                    'reason': entry.reason,
                    'timestamp': entry.timestamp.isoformat()
                }
                for entry in history
            ]

        finally:
            db.close()

    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            'status': 'healthy' if self.model_loaded else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'credit-scoring',
            'version': '1.0.0',
            'model_loaded': self.model_loaded,
            'model_version': self.model_version,
            'model_provenance': self.model_provenance or None,
            'load_error': self.load_error,
        }

# FastAPI application
app = FastAPI(title="Credit Scoring Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
credit_service = CreditScoringService()

# Pydantic models for API
class CreditScoreRequestModel(BaseModel):
    customer_id: str
    personal_info: Dict[str, Any]
    financial_info: Dict[str, Any]
    credit_history: Dict[str, Any]
    employment_info: Dict[str, Any]

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await credit_service.initialize()

@app.post("/credit-score")
async def calculate_credit_score(request: CreditScoreRequestModel):
    """Calculate credit score for a customer"""
    credit_request = CreditScoreRequest(
        customer_id=request.customer_id,
        personal_info=request.personal_info,
        financial_info=request.financial_info,
        credit_history=request.credit_history,
        employment_info=request.employment_info
    )

    response = await credit_service.calculate_credit_score(credit_request)
    return asdict(response)

@app.get("/credit-profile/{customer_id}")
async def get_credit_profile(customer_id: str):
    """Get existing credit profile"""
    profile = await credit_service.get_credit_profile(customer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Credit profile not found")
    return profile

@app.get("/credit-history/{customer_id}")
async def get_score_history(customer_id: str):
    """Get credit score history"""
    history = await credit_service.get_score_history(customer_id)
    return {'customer_id': customer_id, 'history': history}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await credit_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
