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
Risk Assessment Service for Remittance Platform
Provides comprehensive risk assessment for transactions, customers, and portfolios
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("risk-assessment-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import joblib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/risk_assessment")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class RiskType(str, Enum):
    TRANSACTION = "transaction"
    CUSTOMER = "customer"
    PORTFOLIO = "portfolio"
    OPERATIONAL = "operational"
    MARKET = "market"

class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"

class RiskCategory(str, Enum):
    FRAUD = "fraud"
    CREDIT = "credit"
    LIQUIDITY = "liquidity"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    MARKET = "market"

@dataclass
class RiskAssessmentRequest:
    risk_type: RiskType
    entity_id: str
    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None

@dataclass
class RiskAssessmentResponse:
    entity_id: str
    risk_type: RiskType
    overall_risk_level: RiskLevel
    overall_risk_score: float
    risk_categories: Dict[RiskCategory, Dict[str, Any]]
    recommendations: List[str]
    confidence: float
    timestamp: datetime

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, nullable=False)
    risk_type = Column(String, nullable=False)
    overall_risk_level = Column(String, nullable=False)
    overall_risk_score = Column(Float, nullable=False)
    risk_categories = Column(Text)  # JSON string
    recommendations = Column(Text)  # JSON string
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class RiskAlert(Base):
    __tablename__ = "risk_alerts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String, nullable=False)
    risk_type = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    risk_category = Column(String, nullable=False)
    message = Column(String, nullable=False)
    details = Column(Text)  # JSON string
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class RiskAssessmentService:
    def __init__(self):
        self.fraud_model = None
        self.anomaly_model = None
        self.credit_model = None
        self.scaler = None
        self.risk_thresholds = {
            RiskLevel.VERY_LOW: 0.1,
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.7,
            RiskLevel.VERY_HIGH: 0.9,
            RiskLevel.CRITICAL: 1.0
        }
        
    async def initialize(self):
        """Initialize the risk assessment service"""
        try:
            # Load or train risk models
            await self.load_or_train_models()
            
            logger.info("Risk Assessment Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Risk Assessment Service: {e}")
            raise

    async def load_or_train_models(self):
        """Load existing models or train new ones"""
        fraud_model_path = "/tmp/fraud_risk_model.joblib"
        anomaly_model_path = "/tmp/anomaly_risk_model.joblib"
        scaler_path = "/tmp/risk_scaler.joblib"
        
        if (os.path.exists(fraud_model_path) and 
            os.path.exists(anomaly_model_path) and 
            os.path.exists(scaler_path)):
            
            # Load existing models
            self.fraud_model = joblib.load(fraud_model_path)
            self.anomaly_model = joblib.load(anomaly_model_path)
            self.scaler = joblib.load(scaler_path)
            
            logger.info("Loaded existing risk assessment models")
        else:
            # Train new models
            await self.train_models()

    async def train_models(self):
        """Train risk assessment models"""
        try:
            # Generate synthetic training data
            data = self.generate_synthetic_risk_data(5000)
            
            # Prepare features
            X = data.drop(['fraud_label', 'anomaly_label'], axis=1).values
            y_fraud = data['fraud_label'].values
            y_anomaly = data['anomaly_label'].values
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train fraud detection model
            self.fraud_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.fraud_model.fit(X_scaled, y_fraud)
            
            # Train anomaly detection model
            self.anomaly_model = IsolationForest(
                contamination=0.1,
                random_state=42
            )
            self.anomaly_model.fit(X_scaled)
            
            # Save models
            joblib.dump(self.fraud_model, "/tmp/fraud_risk_model.joblib")
            joblib.dump(self.anomaly_model, "/tmp/anomaly_risk_model.joblib")
            joblib.dump(self.scaler, "/tmp/risk_scaler.joblib")
            
            logger.info("Risk assessment models trained successfully")
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise

    def generate_synthetic_risk_data(self, n_samples: int) -> pd.DataFrame:
        """Generate synthetic risk data for training"""
        np.random.seed(42)
        
        data = {
            # Transaction features
            'transaction_amount': np.random.lognormal(5, 2, n_samples),
            'transaction_frequency': np.random.poisson(5, n_samples),
            'time_since_last_transaction': np.random.exponential(24, n_samples),
            'transaction_velocity': np.random.gamma(2, 2, n_samples),
            
            # Customer features
            'customer_age': np.random.randint(18, 80, n_samples),
            'account_age_days': np.random.randint(1, 3650, n_samples),
            'customer_risk_score': np.random.beta(2, 5, n_samples),
            'kyc_status': np.random.choice([0, 1], n_samples, p=[0.1, 0.9]),
            
            # Behavioral features
            'unusual_time': np.random.choice([0, 1], n_samples, p=[0.8, 0.2]),
            'unusual_location': np.random.choice([0, 1], n_samples, p=[0.9, 0.1]),
            'device_change': np.random.choice([0, 1], n_samples, p=[0.95, 0.05]),
            'ip_reputation': np.random.beta(8, 2, n_samples),
            
            # Financial features
            'balance_ratio': np.random.beta(3, 2, n_samples),
            'credit_utilization': np.random.beta(2, 5, n_samples),
            'debt_to_income': np.random.beta(2, 3, n_samples),
            'payment_history': np.random.beta(8, 2, n_samples),
            
            # Network features
            'network_risk': np.random.beta(1, 9, n_samples),
            'peer_risk_score': np.random.beta(2, 8, n_samples),
            'connection_strength': np.random.beta(3, 2, n_samples),
        }
        
        df = pd.DataFrame(data)
        
        # Generate fraud labels based on risk factors
        fraud_score = (
            (df['transaction_amount'] > df['transaction_amount'].quantile(0.95)).astype(int) * 0.3 +
            (df['unusual_time'] == 1).astype(int) * 0.2 +
            (df['unusual_location'] == 1).astype(int) * 0.2 +
            (df['device_change'] == 1).astype(int) * 0.15 +
            (df['ip_reputation'] < 0.3).astype(int) * 0.15 +
            np.random.normal(0, 0.1, n_samples)
        )
        
        df['fraud_label'] = (fraud_score > 0.5).astype(int)
        
        # Generate anomaly labels
        anomaly_score = (
            (df['transaction_velocity'] > df['transaction_velocity'].quantile(0.9)).astype(int) * 0.4 +
            (df['balance_ratio'] < 0.1).astype(int) * 0.3 +
            (df['network_risk'] > 0.7).astype(int) * 0.3 +
            np.random.normal(0, 0.1, n_samples)
        )
        
        df['anomaly_label'] = (anomaly_score > 0.4).astype(int)
        
        return df

    async def assess_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Perform comprehensive risk assessment"""
        try:
            if request.risk_type == RiskType.TRANSACTION:
                return await self.assess_transaction_risk(request)
            elif request.risk_type == RiskType.CUSTOMER:
                return await self.assess_customer_risk(request)
            elif request.risk_type == RiskType.PORTFOLIO:
                return await self.assess_portfolio_risk(request)
            else:
                return await self.assess_operational_risk(request)
                
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def assess_transaction_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Assess transaction-specific risks"""
        data = request.data
        
        # Prepare features for ML models
        features = self.prepare_transaction_features(data)
        features_scaled = self.scaler.transform([features])
        
        # Get fraud probability
        fraud_prob = self.fraud_model.predict_proba(features_scaled)[0][1]
        
        # Get anomaly score
        anomaly_score = self.anomaly_model.decision_function(features_scaled)[0]
        anomaly_prob = max(0, min(1, (anomaly_score + 0.5) / 1.0))  # Normalize to 0-1
        
        # Calculate risk categories
        risk_categories = {
            RiskCategory.FRAUD: {
                'score': float(fraud_prob),
                'level': self.get_risk_level(fraud_prob),
                'factors': self.analyze_fraud_factors(data, fraud_prob)
            },
            RiskCategory.OPERATIONAL: {
                'score': float(anomaly_prob),
                'level': self.get_risk_level(anomaly_prob),
                'factors': self.analyze_operational_factors(data, anomaly_prob)
            },
            RiskCategory.LIQUIDITY: {
                'score': self.calculate_liquidity_risk(data),
                'level': self.get_risk_level(self.calculate_liquidity_risk(data)),
                'factors': self.analyze_liquidity_factors(data)
            },
            RiskCategory.COMPLIANCE: {
                'score': self.calculate_compliance_risk(data),
                'level': self.get_risk_level(self.calculate_compliance_risk(data)),
                'factors': self.analyze_compliance_factors(data)
            }
        }
        
        # Calculate overall risk
        overall_risk_score = self.calculate_overall_risk(risk_categories)
        overall_risk_level = self.get_risk_level(overall_risk_score)
        
        # Generate recommendations
        recommendations = self.generate_transaction_recommendations(risk_categories, data)
        
        # Calculate confidence
        confidence = min(0.95, max(0.6, 1.0 - np.std([cat['score'] for cat in risk_categories.values()])))
        
        # Save assessment
        await self.save_risk_assessment(request.entity_id, request.risk_type, 
                                      overall_risk_level, overall_risk_score,
                                      risk_categories, recommendations, confidence)
        
        # Check for alerts
        await self.check_and_create_alerts(request.entity_id, request.risk_type, 
                                         risk_categories, overall_risk_level)
        
        return RiskAssessmentResponse(
            entity_id=request.entity_id,
            risk_type=request.risk_type,
            overall_risk_level=overall_risk_level,
            overall_risk_score=overall_risk_score,
            risk_categories=risk_categories,
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )

    async def assess_customer_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Assess customer-specific risks"""
        data = request.data
        
        # Calculate risk categories for customers
        risk_categories = {
            RiskCategory.CREDIT: {
                'score': self.calculate_credit_risk(data),
                'level': self.get_risk_level(self.calculate_credit_risk(data)),
                'factors': self.analyze_credit_factors(data)
            },
            RiskCategory.FRAUD: {
                'score': self.calculate_customer_fraud_risk(data),
                'level': self.get_risk_level(self.calculate_customer_fraud_risk(data)),
                'factors': self.analyze_customer_fraud_factors(data)
            },
            RiskCategory.COMPLIANCE: {
                'score': self.calculate_compliance_risk(data),
                'level': self.get_risk_level(self.calculate_compliance_risk(data)),
                'factors': self.analyze_compliance_factors(data)
            },
            RiskCategory.OPERATIONAL: {
                'score': self.calculate_operational_risk(data),
                'level': self.get_risk_level(self.calculate_operational_risk(data)),
                'factors': self.analyze_operational_factors(data, 0.5)
            }
        }
        
        # Calculate overall risk
        overall_risk_score = self.calculate_overall_risk(risk_categories)
        overall_risk_level = self.get_risk_level(overall_risk_score)
        
        # Generate recommendations
        recommendations = self.generate_customer_recommendations(risk_categories, data)
        
        # Calculate confidence
        confidence = min(0.95, max(0.6, 1.0 - np.std([cat['score'] for cat in risk_categories.values()])))
        
        # Save assessment
        await self.save_risk_assessment(request.entity_id, request.risk_type, 
                                      overall_risk_level, overall_risk_score,
                                      risk_categories, recommendations, confidence)
        
        return RiskAssessmentResponse(
            entity_id=request.entity_id,
            risk_type=request.risk_type,
            overall_risk_level=overall_risk_level,
            overall_risk_score=overall_risk_score,
            risk_categories=risk_categories,
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )

    async def assess_portfolio_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Assess portfolio-level risks"""
        data = request.data
        
        # Calculate portfolio risk categories
        risk_categories = {
            RiskCategory.MARKET: {
                'score': self.calculate_market_risk(data),
                'level': self.get_risk_level(self.calculate_market_risk(data)),
                'factors': self.analyze_market_factors(data)
            },
            RiskCategory.CREDIT: {
                'score': self.calculate_portfolio_credit_risk(data),
                'level': self.get_risk_level(self.calculate_portfolio_credit_risk(data)),
                'factors': self.analyze_portfolio_credit_factors(data)
            },
            RiskCategory.LIQUIDITY: {
                'score': self.calculate_portfolio_liquidity_risk(data),
                'level': self.get_risk_level(self.calculate_portfolio_liquidity_risk(data)),
                'factors': self.analyze_portfolio_liquidity_factors(data)
            },
            RiskCategory.OPERATIONAL: {
                'score': self.calculate_operational_risk(data),
                'level': self.get_risk_level(self.calculate_operational_risk(data)),
                'factors': self.analyze_operational_factors(data, 0.5)
            }
        }
        
        # Calculate overall risk
        overall_risk_score = self.calculate_overall_risk(risk_categories)
        overall_risk_level = self.get_risk_level(overall_risk_score)
        
        # Generate recommendations
        recommendations = self.generate_portfolio_recommendations(risk_categories, data)
        
        # Calculate confidence
        confidence = 0.8  # Portfolio assessments typically have lower confidence
        
        # Save assessment
        await self.save_risk_assessment(request.entity_id, request.risk_type, 
                                      overall_risk_level, overall_risk_score,
                                      risk_categories, recommendations, confidence)
        
        return RiskAssessmentResponse(
            entity_id=request.entity_id,
            risk_type=request.risk_type,
            overall_risk_level=overall_risk_level,
            overall_risk_score=overall_risk_score,
            risk_categories=risk_categories,
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )

    async def assess_operational_risk(self, request: RiskAssessmentRequest) -> RiskAssessmentResponse:
        """Assess operational risks"""
        data = request.data
        
        # Calculate operational risk categories
        risk_categories = {
            RiskCategory.OPERATIONAL: {
                'score': self.calculate_operational_risk(data),
                'level': self.get_risk_level(self.calculate_operational_risk(data)),
                'factors': self.analyze_operational_factors(data, 0.5)
            },
            RiskCategory.COMPLIANCE: {
                'score': self.calculate_compliance_risk(data),
                'level': self.get_risk_level(self.calculate_compliance_risk(data)),
                'factors': self.analyze_compliance_factors(data)
            }
        }
        
        # Calculate overall risk
        overall_risk_score = self.calculate_overall_risk(risk_categories)
        overall_risk_level = self.get_risk_level(overall_risk_score)
        
        # Generate recommendations
        recommendations = self.generate_operational_recommendations(risk_categories, data)
        
        # Calculate confidence
        confidence = 0.75
        
        # Save assessment
        await self.save_risk_assessment(request.entity_id, request.risk_type, 
                                      overall_risk_level, overall_risk_score,
                                      risk_categories, recommendations, confidence)
        
        return RiskAssessmentResponse(
            entity_id=request.entity_id,
            risk_type=request.risk_type,
            overall_risk_level=overall_risk_level,
            overall_risk_score=overall_risk_score,
            risk_categories=risk_categories,
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )

    def prepare_transaction_features(self, data: Dict[str, Any]) -> List[float]:
        """Prepare transaction features for ML models"""
        features = []
        
        # Transaction features
        features.append(data.get('amount', 0))
        features.append(data.get('frequency', 1))
        features.append(data.get('time_since_last', 24))
        features.append(data.get('velocity', 1))
        
        # Customer features
        features.append(data.get('customer_age', 30))
        features.append(data.get('account_age_days', 365))
        features.append(data.get('customer_risk_score', 0.5))
        features.append(data.get('kyc_status', 1))
        
        # Behavioral features
        features.append(data.get('unusual_time', 0))
        features.append(data.get('unusual_location', 0))
        features.append(data.get('device_change', 0))
        features.append(data.get('ip_reputation', 0.8))
        
        # Financial features
        features.append(data.get('balance_ratio', 0.5))
        features.append(data.get('credit_utilization', 0.3))
        features.append(data.get('debt_to_income', 0.2))
        features.append(data.get('payment_history', 0.9))
        
        # Network features
        features.append(data.get('network_risk', 0.1))
        features.append(data.get('peer_risk_score', 0.2))
        features.append(data.get('connection_strength', 0.7))
        
        return features

    def get_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        if score <= self.risk_thresholds[RiskLevel.VERY_LOW]:
            return RiskLevel.VERY_LOW
        elif score <= self.risk_thresholds[RiskLevel.LOW]:
            return RiskLevel.LOW
        elif score <= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        elif score <= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score <= self.risk_thresholds[RiskLevel.VERY_HIGH]:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.CRITICAL

    def calculate_overall_risk(self, risk_categories: Dict[RiskCategory, Dict[str, Any]]) -> float:
        """Calculate overall risk score from category scores"""
        # Weight different risk categories
        weights = {
            RiskCategory.FRAUD: 0.3,
            RiskCategory.CREDIT: 0.25,
            RiskCategory.OPERATIONAL: 0.2,
            RiskCategory.LIQUIDITY: 0.15,
            RiskCategory.COMPLIANCE: 0.1,
            RiskCategory.MARKET: 0.2
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for category, risk_info in risk_categories.items():
            if category in weights:
                weighted_sum += risk_info['score'] * weights[category]
                total_weight += weights[category]
        
        return weighted_sum / total_weight if total_weight > 0 else 0.5

    # Risk calculation methods for different categories
    def calculate_liquidity_risk(self, data: Dict[str, Any]) -> float:
        """Calculate liquidity risk score"""
        balance_ratio = data.get('balance_ratio', 0.5)
        transaction_amount = data.get('amount', 0)
        account_balance = data.get('account_balance', 10000)
        
        if account_balance == 0:
            return 1.0
        
        amount_ratio = transaction_amount / account_balance
        liquidity_score = min(1.0, amount_ratio * 2 + (1 - balance_ratio) * 0.5)
        
        return liquidity_score

    def calculate_compliance_risk(self, data: Dict[str, Any]) -> float:
        """Calculate compliance risk score"""
        kyc_status = data.get('kyc_status', 1)
        aml_flags = data.get('aml_flags', 0)
        sanctions_check = data.get('sanctions_check', 1)
        
        compliance_score = (
            (1 - kyc_status) * 0.4 +
            min(aml_flags / 5, 1.0) * 0.4 +
            (1 - sanctions_check) * 0.2
        )
        
        return compliance_score

    def calculate_credit_risk(self, data: Dict[str, Any]) -> float:
        """Calculate credit risk score"""
        credit_score = data.get('credit_score', 650)
        debt_to_income = data.get('debt_to_income', 0.3)
        payment_history = data.get('payment_history', 0.9)
        
        # Normalize credit score to 0-1 scale (300-850 range)
        normalized_credit = max(0, min(1, (850 - credit_score) / 550))
        
        credit_risk = (
            normalized_credit * 0.5 +
            debt_to_income * 0.3 +
            (1 - payment_history) * 0.2
        )
        
        return credit_risk

    def calculate_customer_fraud_risk(self, data: Dict[str, Any]) -> float:
        """Calculate customer fraud risk score"""
        unusual_activity = data.get('unusual_activity_score', 0.1)
        device_changes = data.get('device_changes', 0)
        location_changes = data.get('location_changes', 0)
        
        fraud_risk = min(1.0, unusual_activity + device_changes * 0.1 + location_changes * 0.05)
        
        return fraud_risk

    def calculate_operational_risk(self, data: Dict[str, Any]) -> float:
        """Calculate operational risk score"""
        system_downtime = data.get('system_downtime', 0)
        error_rate = data.get('error_rate', 0.01)
        process_failures = data.get('process_failures', 0)
        
        operational_risk = min(1.0, system_downtime * 0.4 + error_rate * 10 + process_failures * 0.1)
        
        return operational_risk

    def calculate_market_risk(self, data: Dict[str, Any]) -> float:
        """Calculate market risk score"""
        volatility = data.get('volatility', 0.2)
        correlation = data.get('correlation', 0.5)
        concentration = data.get('concentration', 0.3)
        
        market_risk = min(1.0, volatility * 0.4 + correlation * 0.3 + concentration * 0.3)
        
        return market_risk

    def calculate_portfolio_credit_risk(self, data: Dict[str, Any]) -> float:
        """Calculate portfolio credit risk score"""
        default_rate = data.get('default_rate', 0.02)
        concentration_risk = data.get('concentration_risk', 0.3)
        avg_credit_score = data.get('avg_credit_score', 650)
        
        # Normalize average credit score
        normalized_credit = max(0, min(1, (850 - avg_credit_score) / 550))
        
        portfolio_credit_risk = (
            default_rate * 10 * 0.4 +
            concentration_risk * 0.3 +
            normalized_credit * 0.3
        )
        
        return min(1.0, portfolio_credit_risk)

    def calculate_portfolio_liquidity_risk(self, data: Dict[str, Any]) -> float:
        """Calculate portfolio liquidity risk score"""
        liquidity_ratio = data.get('liquidity_ratio', 0.2)
        funding_gap = data.get('funding_gap', 0.1)
        maturity_mismatch = data.get('maturity_mismatch', 0.15)
        
        liquidity_risk = (
            (1 - liquidity_ratio) * 0.4 +
            funding_gap * 0.3 +
            maturity_mismatch * 0.3
        )
        
        return min(1.0, liquidity_risk)

    # Factor analysis methods
    def analyze_fraud_factors(self, data: Dict[str, Any], fraud_prob: float) -> List[str]:
        """Analyze factors contributing to fraud risk"""
        factors = []
        
        if data.get('unusual_time', 0) == 1:
            factors.append("Transaction at unusual time")
        if data.get('unusual_location', 0) == 1:
            factors.append("Transaction from unusual location")
        if data.get('device_change', 0) == 1:
            factors.append("New device detected")
        if data.get('ip_reputation', 1) < 0.5:
            factors.append("Low IP reputation")
        if data.get('amount', 0) > data.get('avg_amount', 100) * 5:
            factors.append("Unusually high transaction amount")
        
        return factors

    def analyze_operational_factors(self, data: Dict[str, Any], anomaly_prob: float) -> List[str]:
        """Analyze operational risk factors"""
        factors = []
        
        if data.get('transaction_velocity', 1) > 10:
            factors.append("High transaction velocity")
        if data.get('system_downtime', 0) > 0:
            factors.append("Recent system downtime")
        if data.get('error_rate', 0) > 0.05:
            factors.append("High error rate")
        
        return factors

    def analyze_liquidity_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze liquidity risk factors"""
        factors = []
        
        balance_ratio = data.get('balance_ratio', 0.5)
        if balance_ratio < 0.2:
            factors.append("Low account balance")
        
        amount = data.get('amount', 0)
        balance = data.get('account_balance', 10000)
        if amount > balance * 0.8:
            factors.append("Large transaction relative to balance")
        
        return factors

    def analyze_compliance_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze compliance risk factors"""
        factors = []
        
        if data.get('kyc_status', 1) == 0:
            factors.append("KYC not completed")
        if data.get('aml_flags', 0) > 0:
            factors.append("AML flags detected")
        if data.get('sanctions_check', 1) == 0:
            factors.append("Sanctions screening failed")
        
        return factors

    def analyze_credit_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze credit risk factors"""
        factors = []
        
        credit_score = data.get('credit_score', 650)
        if credit_score < 600:
            factors.append("Low credit score")
        
        debt_to_income = data.get('debt_to_income', 0.3)
        if debt_to_income > 0.4:
            factors.append("High debt-to-income ratio")
        
        payment_history = data.get('payment_history', 0.9)
        if payment_history < 0.8:
            factors.append("Poor payment history")
        
        return factors

    def analyze_customer_fraud_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze customer fraud risk factors"""
        factors = []
        
        if data.get('unusual_activity_score', 0) > 0.5:
            factors.append("High unusual activity score")
        if data.get('device_changes', 0) > 3:
            factors.append("Frequent device changes")
        if data.get('location_changes', 0) > 5:
            factors.append("Frequent location changes")
        
        return factors

    def analyze_market_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze market risk factors"""
        factors = []
        
        if data.get('volatility', 0.2) > 0.4:
            factors.append("High market volatility")
        if data.get('correlation', 0.5) > 0.8:
            factors.append("High correlation risk")
        if data.get('concentration', 0.3) > 0.5:
            factors.append("High concentration risk")
        
        return factors

    def analyze_portfolio_credit_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze portfolio credit risk factors"""
        factors = []
        
        if data.get('default_rate', 0.02) > 0.05:
            factors.append("High default rate")
        if data.get('concentration_risk', 0.3) > 0.5:
            factors.append("High concentration risk")
        if data.get('avg_credit_score', 650) < 600:
            factors.append("Low average credit score")
        
        return factors

    def analyze_portfolio_liquidity_factors(self, data: Dict[str, Any]) -> List[str]:
        """Analyze portfolio liquidity risk factors"""
        factors = []
        
        if data.get('liquidity_ratio', 0.2) < 0.1:
            factors.append("Low liquidity ratio")
        if data.get('funding_gap', 0.1) > 0.2:
            factors.append("High funding gap")
        if data.get('maturity_mismatch', 0.15) > 0.3:
            factors.append("High maturity mismatch")
        
        return factors

    # Recommendation generation methods
    def generate_transaction_recommendations(self, risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                           data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for transaction risks"""
        recommendations = []
        
        for category, risk_info in risk_categories.items():
            if risk_info['level'] in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                if category == RiskCategory.FRAUD:
                    recommendations.append("Implement additional fraud verification steps")
                    recommendations.append("Monitor customer behavior patterns")
                elif category == RiskCategory.LIQUIDITY:
                    recommendations.append("Verify account balance before processing")
                    recommendations.append("Consider transaction limits")
                elif category == RiskCategory.COMPLIANCE:
                    recommendations.append("Complete KYC verification")
                    recommendations.append("Perform enhanced due diligence")
        
        return recommendations

    def generate_customer_recommendations(self, risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                        data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for customer risks"""
        recommendations = []
        
        for category, risk_info in risk_categories.items():
            if risk_info['level'] in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                if category == RiskCategory.CREDIT:
                    recommendations.append("Review credit limits")
                    recommendations.append("Consider additional collateral")
                elif category == RiskCategory.FRAUD:
                    recommendations.append("Implement enhanced monitoring")
                    recommendations.append("Require additional authentication")
                elif category == RiskCategory.COMPLIANCE:
                    recommendations.append("Update customer documentation")
                    recommendations.append("Perform periodic reviews")
        
        return recommendations

    def generate_portfolio_recommendations(self, risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                         data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for portfolio risks"""
        recommendations = []
        
        for category, risk_info in risk_categories.items():
            if risk_info['level'] in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                if category == RiskCategory.MARKET:
                    recommendations.append("Diversify portfolio holdings")
                    recommendations.append("Implement hedging strategies")
                elif category == RiskCategory.CREDIT:
                    recommendations.append("Review credit concentration")
                    recommendations.append("Strengthen underwriting standards")
                elif category == RiskCategory.LIQUIDITY:
                    recommendations.append("Increase liquid asset holdings")
                    recommendations.append("Improve funding diversification")
        
        return recommendations

    def generate_operational_recommendations(self, risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                           data: Dict[str, Any]) -> List[str]:
        """Generate recommendations for operational risks"""
        recommendations = []
        
        for category, risk_info in risk_categories.items():
            if risk_info['level'] in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                if category == RiskCategory.OPERATIONAL:
                    recommendations.append("Improve system reliability")
                    recommendations.append("Enhance process controls")
                elif category == RiskCategory.COMPLIANCE:
                    recommendations.append("Update compliance procedures")
                    recommendations.append("Increase staff training")
        
        return recommendations

    async def save_risk_assessment(self, entity_id: str, risk_type: RiskType, 
                                 overall_risk_level: RiskLevel, overall_risk_score: float,
                                 risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                 recommendations: List[str], confidence: float):
        """Save risk assessment to database"""
        db = SessionLocal()
        try:
            # Deactivate old assessments
            db.query(RiskAssessment).filter(
                RiskAssessment.entity_id == entity_id,
                RiskAssessment.risk_type == risk_type.value,
                RiskAssessment.is_active == True
            ).update({'is_active': False})
            
            # Create new assessment
            assessment = RiskAssessment(
                entity_id=entity_id,
                risk_type=risk_type.value,
                overall_risk_level=overall_risk_level.value,
                overall_risk_score=overall_risk_score,
                risk_categories=json.dumps({k.value: v for k, v in risk_categories.items()}),
                recommendations=json.dumps(recommendations),
                confidence=confidence
            )
            
            db.add(assessment)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to save risk assessment: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def check_and_create_alerts(self, entity_id: str, risk_type: RiskType, 
                                    risk_categories: Dict[RiskCategory, Dict[str, Any]], 
                                    overall_risk_level: RiskLevel):
        """Check for high-risk conditions and create alerts"""
        db = SessionLocal()
        try:
            # Create alerts for high-risk categories
            for category, risk_info in risk_categories.items():
                if risk_info['level'] in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                    alert = RiskAlert(
                        entity_id=entity_id,
                        risk_type=risk_type.value,
                        risk_level=risk_info['level'].value,
                        risk_category=category.value,
                        message=f"High {category.value} risk detected for {entity_id}",
                        details=json.dumps(risk_info)
                    )
                    db.add(alert)
            
            # Create overall risk alert if critical
            if overall_risk_level == RiskLevel.CRITICAL:
                alert = RiskAlert(
                    entity_id=entity_id,
                    risk_type=risk_type.value,
                    risk_level=overall_risk_level.value,
                    risk_category="overall",
                    message=f"Critical overall risk detected for {entity_id}",
                    details=json.dumps({"overall_risk_level": overall_risk_level.value})
                )
                db.add(alert)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create risk alerts: {e}")
            db.rollback()
        finally:
            db.close()

    async def get_risk_assessment(self, entity_id: str, risk_type: RiskType) -> Optional[Dict[str, Any]]:
        """Get latest risk assessment for entity"""
        db = SessionLocal()
        try:
            assessment = db.query(RiskAssessment).filter(
                RiskAssessment.entity_id == entity_id,
                RiskAssessment.risk_type == risk_type.value,
                RiskAssessment.is_active == True
            ).first()
            
            if assessment:
                return {
                    'entity_id': assessment.entity_id,
                    'risk_type': assessment.risk_type,
                    'overall_risk_level': assessment.overall_risk_level,
                    'overall_risk_score': assessment.overall_risk_score,
                    'risk_categories': json.loads(assessment.risk_categories),
                    'recommendations': json.loads(assessment.recommendations),
                    'confidence': assessment.confidence,
                    'created_at': assessment.created_at.isoformat()
                }
            
            return None
            
        finally:
            db.close()

    async def get_risk_alerts(self, entity_id: Optional[str] = None, 
                            acknowledged: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get risk alerts"""
        db = SessionLocal()
        try:
            query = db.query(RiskAlert)
            
            if entity_id:
                query = query.filter(RiskAlert.entity_id == entity_id)
            
            if acknowledged is not None:
                query = query.filter(RiskAlert.acknowledged == acknowledged)
            
            alerts = query.order_by(RiskAlert.created_at.desc()).limit(100).all()
            
            return [
                {
                    'id': alert.id,
                    'entity_id': alert.entity_id,
                    'risk_type': alert.risk_type,
                    'risk_level': alert.risk_level,
                    'risk_category': alert.risk_category,
                    'message': alert.message,
                    'details': json.loads(alert.details),
                    'acknowledged': alert.acknowledged,
                    'created_at': alert.created_at.isoformat()
                }
                for alert in alerts
            ]
            
        finally:
            db.close()

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge a risk alert"""
        db = SessionLocal()
        try:
            alert = db.query(RiskAlert).filter(RiskAlert.id == alert_id).first()
            if alert:
                alert.acknowledged = True
                db.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            db.rollback()
            return False
        finally:
            db.close()

    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'risk-assessment',
            'version': '1.0.0',
            'models_loaded': {
                'fraud_model': self.fraud_model is not None,
                'anomaly_model': self.anomaly_model is not None,
                'scaler': self.scaler is not None
            }
        }

# FastAPI application
app = FastAPI(title="Risk Assessment Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
risk_service = RiskAssessmentService()

# Pydantic models for API
class RiskAssessmentRequestModel(BaseModel):
    risk_type: RiskType
    entity_id: str
    data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await risk_service.initialize()

@app.post("/assess-risk")
async def assess_risk(request: RiskAssessmentRequestModel):
    """Perform risk assessment"""
    risk_request = RiskAssessmentRequest(
        risk_type=request.risk_type,
        entity_id=request.entity_id,
        data=request.data,
        context=request.context
    )
    
    response = await risk_service.assess_risk(risk_request)
    return asdict(response)

@app.get("/risk-assessment/{entity_id}")
async def get_risk_assessment(entity_id: str, risk_type: RiskType):
    """Get latest risk assessment"""
    assessment = await risk_service.get_risk_assessment(entity_id, risk_type)
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found")
    return assessment

@app.get("/risk-alerts")
async def get_risk_alerts(entity_id: Optional[str] = None, acknowledged: Optional[bool] = None):
    """Get risk alerts"""
    alerts = await risk_service.get_risk_alerts(entity_id, acknowledged)
    return {'alerts': alerts}

@app.post("/risk-alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge a risk alert"""
    success = await risk_service.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {'message': 'Alert acknowledged successfully'}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await risk_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
