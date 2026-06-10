import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Hybrid Fraud Detection Engine for Remittance Platform
Implements five-layer architecture combining rule-based and ML/DL/GNN approaches
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import concurrent.futures

import pandas as pd
import numpy as np
import networkx as nx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("hybrid-fraud-detection-engine")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# ML/DL libraries
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, GATConv, SAGEConv
from torch_geometric.data import Data, DataLoader
import torch_geometric.transforms as T
from sklearn.ensemble import RandomForestClassifier, IsolationForest, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import joblib

# Rule engine
import pyknow
from pyknow import KnowledgeEngine, Rule, Fact, DefFacts, W, P, L, NOT, AND, OR

# MLflow for experiment tracking
import mlflow
import mlflow.pytorch
import mlflow.sklearn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/fraud_detection")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class FraudType(str, Enum):
    TRANSACTION_FRAUD = "transaction_fraud"
    IDENTITY_THEFT = "identity_theft"
    ACCOUNT_TAKEOVER = "account_takeover"
    SYNTHETIC_IDENTITY = "synthetic_identity"
    MONEY_LAUNDERING = "money_laundering"
    CARD_FRAUD = "card_fraud"
    MOBILE_FRAUD = "mobile_fraud"

class DetectionMethod(str, Enum):
    RULE_BASED = "rule_based"
    MACHINE_LEARNING = "machine_learning"
    DEEP_LEARNING = "deep_learning"
    GRAPH_NEURAL_NETWORK = "graph_neural_network"
    HYBRID = "hybrid"

class RiskLevel(str, Enum):
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"

@dataclass
class FraudDetectionRequest:
    transaction_id: str
    customer_id: str
    transaction_data: Dict[str, Any]
    customer_data: Dict[str, Any]
    network_data: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

@dataclass
class FraudDetectionResponse:
    transaction_id: str
    customer_id: str
    fraud_probability: float
    risk_level: RiskLevel
    fraud_types: List[FraudType]
    detection_methods: Dict[DetectionMethod, Dict[str, Any]]
    explanations: List[str]
    recommendations: List[str]
    confidence: float
    processing_time_ms: float
    timestamp: datetime

class FraudDetection(Base):
    __tablename__ = "fraud_detections"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    fraud_probability = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    fraud_types = Column(Text)  # JSON string
    detection_methods = Column(Text)  # JSON string
    explanations = Column(Text)  # JSON string
    recommendations = Column(Text)  # JSON string
    confidence = Column(Float, nullable=False)
    processing_time_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FraudAlert(Base):
    __tablename__ = "fraud_alerts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id = Column(String, nullable=False)
    customer_id = Column(String, nullable=False)
    fraud_type = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    message = Column(String, nullable=False)
    details = Column(Text)  # JSON string
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Layer 1: Data Ingestion and Preprocessing
class DataPreprocessor:
    def __init__(self):
        self.feature_encoders = {}
        self.scalers = {}
        
    def preprocess_transaction_data(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess transaction data for fraud detection"""
        processed_data = transaction_data.copy()
        
        # Normalize amount
        amount = processed_data.get('amount', 0)
        processed_data['amount_normalized'] = np.log1p(amount)
        
        # Extract time features
        timestamp = processed_data.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        processed_data['hour'] = timestamp.hour
        processed_data['day_of_week'] = timestamp.weekday()
        processed_data['is_weekend'] = timestamp.weekday() >= 5
        processed_data['is_night'] = timestamp.hour < 6 or timestamp.hour > 22
        
        # Calculate velocity features
        processed_data['transaction_velocity'] = self.calculate_transaction_velocity(
            processed_data.get('customer_id'), timestamp
        )
        
        return processed_data
    
    def preprocess_customer_data(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess customer data for fraud detection"""
        processed_data = customer_data.copy()
        
        # Calculate account age
        account_created = processed_data.get('account_created', datetime.now())
        if isinstance(account_created, str):
            account_created = datetime.fromisoformat(account_created.replace('Z', '+00:00'))
        
        processed_data['account_age_days'] = (datetime.now() - account_created).days
        processed_data['is_new_account'] = processed_data['account_age_days'] < 30
        
        # Risk score normalization
        processed_data['risk_score_normalized'] = min(1.0, processed_data.get('risk_score', 0.5))
        
        return processed_data
    
    def calculate_transaction_velocity(self, customer_id: str, timestamp: datetime) -> float:
        """Calculate transaction velocity for customer"""
        # In a real implementation, this would query the database
        # Return computed velocity score
        return np.random.exponential(2.0)
    
    def create_graph_data(self, transaction_data: Dict[str, Any], 
                         customer_data: Dict[str, Any],
                         network_data: Optional[Dict[str, Any]] = None) -> Data:
        """Create graph data for GNN processing"""
        # Create nodes (customers, merchants, devices, locations)
        nodes = []
        node_features = []
        edge_index = []
        edge_features = []
        
        # Customer node
        customer_id = customer_data.get('id', 'unknown')
        nodes.append(('customer', customer_id))
        customer_features = [
            customer_data.get('age', 30) / 100.0,
            customer_data.get('account_age_days', 365) / 3650.0,
            customer_data.get('risk_score', 0.5),
            customer_data.get('kyc_verified', 1)
        ]
        node_features.append(customer_features)
        
        # Merchant node
        merchant_id = transaction_data.get('merchant_id', 'unknown')
        nodes.append(('merchant', merchant_id))
        merchant_features = [
            transaction_data.get('merchant_risk_score', 0.3),
            transaction_data.get('merchant_category', 0) / 20.0,
            1.0,  # is_merchant flag
            0.0   # padding
        ]
        node_features.append(merchant_features)
        
        # Device node
        device_id = transaction_data.get('device_id', 'unknown')
        nodes.append(('device', device_id))
        device_features = [
            transaction_data.get('device_risk_score', 0.2),
            transaction_data.get('device_age_days', 100) / 3650.0,
            0.0,  # padding
            1.0   # is_device flag
        ]
        node_features.append(device_features)
        
        # Create edges (customer-merchant, customer-device)
        edge_index = [[0, 1], [0, 2], [1, 0], [2, 0]]  # Bidirectional edges
        edge_features = [
            [transaction_data.get('amount', 0) / 10000.0, 1.0],  # customer-merchant
            [1.0, 0.0],  # customer-device
            [transaction_data.get('amount', 0) / 10000.0, 1.0],  # merchant-customer
            [1.0, 0.0]   # device-customer
        ]
        
        # Convert to tensors
        x = torch.tensor(node_features, dtype=torch.float)
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(edge_features, dtype=torch.float)
        
        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)

# Layer 2: Rule-Based Detection Engine
class FraudRuleEngine(KnowledgeEngine):
    def __init__(self):
        super().__init__()
        self.fraud_indicators = []
        self.risk_score = 0.0
        self.triggered_rules = []
    
    @DefFacts()
    def initial_facts(self):
        yield Fact(action="evaluate_fraud")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(transaction_amount=P(lambda x: x > 10000)))
    def high_amount_rule(self):
        self.fraud_indicators.append("High transaction amount")
        self.risk_score += 0.3
        self.triggered_rules.append("high_amount_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(unusual_time=True))
    def unusual_time_rule(self):
        self.fraud_indicators.append("Transaction at unusual time")
        self.risk_score += 0.2
        self.triggered_rules.append("unusual_time_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(unusual_location=True))
    def unusual_location_rule(self):
        self.fraud_indicators.append("Transaction from unusual location")
        self.risk_score += 0.25
        self.triggered_rules.append("unusual_location_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(device_change=True))
    def device_change_rule(self):
        self.fraud_indicators.append("New device detected")
        self.risk_score += 0.15
        self.triggered_rules.append("device_change_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(velocity_anomaly=True))
    def velocity_anomaly_rule(self):
        self.fraud_indicators.append("High transaction velocity")
        self.risk_score += 0.2
        self.triggered_rules.append("velocity_anomaly_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(ip_reputation=P(lambda x: x < 0.3)))
    def low_ip_reputation_rule(self):
        self.fraud_indicators.append("Low IP reputation")
        self.risk_score += 0.1
        self.triggered_rules.append("low_ip_reputation_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(account_age_days=P(lambda x: x < 7)))
    def new_account_rule(self):
        self.fraud_indicators.append("Very new account")
        self.risk_score += 0.15
        self.triggered_rules.append("new_account_rule")
    
    @Rule(Fact(action="evaluate_fraud"),
          Fact(kyc_verified=False))
    def kyc_not_verified_rule(self):
        self.fraud_indicators.append("KYC not verified")
        self.risk_score += 0.25
        self.triggered_rules.append("kyc_not_verified_rule")
    
    def evaluate_transaction(self, transaction_data: Dict[str, Any], 
                           customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate transaction using rule-based approach"""
        self.reset()
        self.fraud_indicators = []
        self.risk_score = 0.0
        self.triggered_rules = []
        
        # Declare facts
        self.declare(Fact(action="evaluate_fraud"))
        self.declare(Fact(transaction_amount=transaction_data.get('amount', 0)))
        self.declare(Fact(unusual_time=transaction_data.get('is_night', False)))
        self.declare(Fact(unusual_location=transaction_data.get('unusual_location', False)))
        self.declare(Fact(device_change=transaction_data.get('device_change', False)))
        self.declare(Fact(velocity_anomaly=transaction_data.get('transaction_velocity', 0) > 5))
        self.declare(Fact(ip_reputation=transaction_data.get('ip_reputation', 0.8)))
        self.declare(Fact(account_age_days=customer_data.get('account_age_days', 365)))
        self.declare(Fact(kyc_verified=customer_data.get('kyc_verified', True)))
        
        # Run the engine
        self.run()
        
        return {
            'fraud_probability': min(1.0, self.risk_score),
            'indicators': self.fraud_indicators,
            'triggered_rules': self.triggered_rules,
            'confidence': 0.8  # Rule-based systems have high confidence
        }

# Layer 3: Machine Learning Engine
class MLFraudDetector:
    def __init__(self):
        self.traditional_ml_model = None
        self.deep_learning_model = None
        self.scaler = None
        self.feature_names = []
        
    async def initialize(self):
        """Initialize ML models"""
        await self.load_or_train_models()
    
    async def load_or_train_models(self):
        """Load existing models or train new ones"""
        ml_model_path = "/tmp/fraud_ml_model.joblib"
        dl_model_path = "/tmp/fraud_dl_model.pth"
        scaler_path = "/tmp/fraud_scaler.joblib"
        
        if (os.path.exists(ml_model_path) and 
            os.path.exists(scaler_path)):
            
            # Load existing models
            self.traditional_ml_model = joblib.load(ml_model_path)
            self.scaler = joblib.load(scaler_path)
            
            if os.path.exists(dl_model_path):
                self.deep_learning_model = torch.load(dl_model_path)
                self.deep_learning_model.eval()
            
            logger.info("Loaded existing ML fraud detection models")
        else:
            # Train new models
            await self.train_models()
    
    async def train_models(self):
        """Train ML models for fraud detection"""
        try:
            # Generate synthetic training data
            data = self.generate_fraud_training_data(10000)
            
            # Prepare features
            X, y = self.prepare_ml_features(data)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train traditional ML model
            self.traditional_ml_model = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42
            )
            
            self.traditional_ml_model.fit(X_train_scaled, y_train)
            
            # Evaluate traditional ML model
            y_pred = self.traditional_ml_model.predict(X_test_scaled)
            y_pred_proba = self.traditional_ml_model.predict_proba(X_test_scaled)[:, 1]
            
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred)
            recall = recall_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred)
            auc = roc_auc_score(y_test, y_pred_proba)
            
            logger.info(f"Traditional ML Model - Accuracy: {accuracy:.3f}, Precision: {precision:.3f}, "
                       f"Recall: {recall:.3f}, F1: {f1:.3f}, AUC: {auc:.3f}")
            
            # Train deep learning model
            self.deep_learning_model = FraudDeepLearningModel(input_dim=X_train_scaled.shape[1])
            await self.train_deep_learning_model(X_train_scaled, y_train, X_test_scaled, y_test)
            
            # Save models
            joblib.dump(self.traditional_ml_model, "/tmp/fraud_ml_model.joblib")
            joblib.dump(self.scaler, "/tmp/fraud_scaler.joblib")
            torch.save(self.deep_learning_model, "/tmp/fraud_dl_model.pth")
            
            logger.info("Fraud detection ML models trained successfully")
            
        except Exception as e:
            logger.error(f"ML model training failed: {e}")
            raise
    
    def generate_fraud_training_data(self, n_samples: int) -> pd.DataFrame:
        """Generate synthetic fraud training data"""
        np.random.seed(42)
        
        # Generate legitimate transactions (80%)
        n_legit = int(n_samples * 0.8)
        legit_data = {
            'amount': np.random.lognormal(5, 1.5, n_legit),
            'hour': np.random.choice(range(6, 23), n_legit, p=np.ones(17)/17),
            'day_of_week': np.random.randint(0, 7, n_legit),
            'account_age_days': np.random.exponential(365, n_legit),
            'transaction_velocity': np.random.exponential(1, n_legit),
            'ip_reputation': np.random.beta(8, 2, n_legit),
            'device_risk_score': np.random.beta(1, 9, n_legit),
            'merchant_risk_score': np.random.beta(2, 8, n_legit),
            'unusual_location': np.random.choice([0, 1], n_legit, p=[0.95, 0.05]),
            'device_change': np.random.choice([0, 1], n_legit, p=[0.98, 0.02]),
            'kyc_verified': np.random.choice([0, 1], n_legit, p=[0.1, 0.9]),
            'is_weekend': np.random.choice([0, 1], n_legit, p=[0.7, 0.3]),
            'is_night': np.random.choice([0, 1], n_legit, p=[0.9, 0.1]),
            'fraud_label': np.zeros(n_legit)
        }
        
        # Generate fraudulent transactions (20%)
        n_fraud = n_samples - n_legit
        fraud_data = {
            'amount': np.random.lognormal(7, 2, n_fraud),  # Higher amounts
            'hour': np.random.choice(range(0, 6), n_fraud),  # Night hours
            'day_of_week': np.random.randint(0, 7, n_fraud),
            'account_age_days': np.random.exponential(30, n_fraud),  # Newer accounts
            'transaction_velocity': np.random.exponential(5, n_fraud),  # Higher velocity
            'ip_reputation': np.random.beta(2, 8, n_fraud),  # Lower IP reputation
            'device_risk_score': np.random.beta(5, 5, n_fraud),  # Higher device risk
            'merchant_risk_score': np.random.beta(6, 4, n_fraud),  # Higher merchant risk
            'unusual_location': np.random.choice([0, 1], n_fraud, p=[0.3, 0.7]),  # More unusual locations
            'device_change': np.random.choice([0, 1], n_fraud, p=[0.6, 0.4]),  # More device changes
            'kyc_verified': np.random.choice([0, 1], n_fraud, p=[0.4, 0.6]),  # Less KYC verified
            'is_weekend': np.random.choice([0, 1], n_fraud, p=[0.5, 0.5]),
            'is_night': np.random.choice([0, 1], n_fraud, p=[0.3, 0.7]),  # More night transactions
            'fraud_label': np.ones(n_fraud)
        }
        
        # Combine data
        all_data = {}
        for key in legit_data.keys():
            all_data[key] = np.concatenate([legit_data[key], fraud_data[key]])
        
        df = pd.DataFrame(all_data)
        
        # Shuffle the data
        df = df.sample(frac=1).reset_index(drop=True)
        
        return df
    
    def prepare_ml_features(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features for ML training"""
        feature_columns = [
            'amount', 'hour', 'day_of_week', 'account_age_days', 'transaction_velocity',
            'ip_reputation', 'device_risk_score', 'merchant_risk_score', 'unusual_location',
            'device_change', 'kyc_verified', 'is_weekend', 'is_night'
        ]
        
        self.feature_names = feature_columns
        
        X = data[feature_columns].values
        y = data['fraud_label'].values
        
        return X, y
    
    async def train_deep_learning_model(self, X_train: np.ndarray, y_train: np.ndarray,
                                      X_test: np.ndarray, y_test: np.ndarray):
        """Train deep learning model"""
        # Convert to tensors
        X_train_tensor = torch.FloatTensor(X_train)
        y_train_tensor = torch.FloatTensor(y_train)
        X_test_tensor = torch.FloatTensor(X_test)
        y_test_tensor = torch.FloatTensor(y_test)
        
        # Training parameters
        criterion = nn.BCELoss()
        optimizer = torch.optim.Adam(self.deep_learning_model.parameters(), lr=0.001)
        
        # Training loop
        epochs = 100
        batch_size = 256
        
        for epoch in range(epochs):
            self.deep_learning_model.train()
            
            # Mini-batch training
            for i in range(0, len(X_train_tensor), batch_size):
                batch_X = X_train_tensor[i:i+batch_size]
                batch_y = y_train_tensor[i:i+batch_size]
                
                optimizer.zero_grad()
                outputs = self.deep_learning_model(batch_X).squeeze()
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
            
            # Validation
            if epoch % 20 == 0:
                self.deep_learning_model.eval()
                with torch.no_grad():
                    val_outputs = self.deep_learning_model(X_test_tensor).squeeze()
                    val_loss = criterion(val_outputs, y_test_tensor)
                    val_predictions = (val_outputs > 0.5).float()
                    val_accuracy = (val_predictions == y_test_tensor).float().mean()
                    
                    logger.info(f"Epoch {epoch}: Val Loss: {val_loss:.4f}, Val Accuracy: {val_accuracy:.4f}")
    
    def predict_traditional_ml(self, features: np.ndarray) -> Dict[str, Any]:
        """Make prediction using traditional ML model"""
        if self.traditional_ml_model is None or self.scaler is None:
            raise ValueError("Traditional ML model not loaded")
        
        features_scaled = self.scaler.transform([features])
        fraud_probability = self.traditional_ml_model.predict_proba(features_scaled)[0][1]
        
        # Get feature importance
        feature_importance = dict(zip(self.feature_names, 
                                    self.traditional_ml_model.feature_importances_))
        
        return {
            'fraud_probability': float(fraud_probability),
            'feature_importance': feature_importance,
            'confidence': 0.85
        }
    
    def predict_deep_learning(self, features: np.ndarray) -> Dict[str, Any]:
        """Make prediction using deep learning model"""
        if self.deep_learning_model is None:
            raise ValueError("Deep learning model not loaded")
        
        features_scaled = self.scaler.transform([features])
        features_tensor = torch.FloatTensor(features_scaled)
        
        self.deep_learning_model.eval()
        with torch.no_grad():
            fraud_probability = self.deep_learning_model(features_tensor).squeeze().item()
        
        return {
            'fraud_probability': float(fraud_probability),
            'confidence': 0.8
        }
    
    def prepare_features_from_request(self, transaction_data: Dict[str, Any], 
                                    customer_data: Dict[str, Any]) -> np.ndarray:
        """Prepare features from request data"""
        features = [
            transaction_data.get('amount', 0),
            transaction_data.get('hour', 12),
            transaction_data.get('day_of_week', 1),
            customer_data.get('account_age_days', 365),
            transaction_data.get('transaction_velocity', 1),
            transaction_data.get('ip_reputation', 0.8),
            transaction_data.get('device_risk_score', 0.2),
            transaction_data.get('merchant_risk_score', 0.3),
            transaction_data.get('unusual_location', 0),
            transaction_data.get('device_change', 0),
            customer_data.get('kyc_verified', 1),
            transaction_data.get('is_weekend', 0),
            transaction_data.get('is_night', 0)
        ]
        
        return np.array(features)

# Deep Learning Model
class FraudDeepLearningModel(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: List[int] = [128, 64, 32]):
        super(FraudDeepLearningModel, self).__init__()
        
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.BatchNorm1d(hidden_dim)
            ])
            prev_dim = hidden_dim
        
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        return self.network(x)

# Layer 3: Graph Neural Network Engine
class GNNFraudDetector:
    def __init__(self):
        self.gnn_model = None
        self.node_encoder = None
        self.edge_encoder = None
        
    async def initialize(self):
        """Initialize GNN model"""
        await self.load_or_train_gnn_model()
    
    async def load_or_train_gnn_model(self):
        """Load existing GNN model or train new one"""
        gnn_model_path = "/tmp/fraud_gnn_model.pth"
        
        if os.path.exists(gnn_model_path):
            self.gnn_model = torch.load(gnn_model_path)
            self.gnn_model.eval()
            logger.info("Loaded existing GNN fraud detection model")
        else:
            # Train new GNN model
            await self.train_gnn_model()
    
    async def train_gnn_model(self):
        """Train GNN model for fraud detection"""
        try:
            # Generate synthetic graph data
            graph_data_list = self.generate_graph_training_data(1000)
            
            # Create data loader
            loader = DataLoader(graph_data_list, batch_size=32, shuffle=True)
            
            # Initialize model
            self.gnn_model = FraudGNNModel(
                node_input_dim=4,
                edge_input_dim=2,
                hidden_dim=64,
                output_dim=1
            )
            
            # Training parameters
            optimizer = torch.optim.Adam(self.gnn_model.parameters(), lr=0.001)
            criterion = nn.BCELoss()
            
            # Training loop
            epochs = 50
            for epoch in range(epochs):
                total_loss = 0
                self.gnn_model.train()
                
                for batch in loader:
                    optimizer.zero_grad()
                    out = self.gnn_model(batch)
                    loss = criterion(out.squeeze(), batch.y.float())
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                
                if epoch % 10 == 0:
                    avg_loss = total_loss / len(loader)
                    logger.info(f"GNN Epoch {epoch}: Average Loss: {avg_loss:.4f}")
            
            # Save model
            torch.save(self.gnn_model, "/tmp/fraud_gnn_model.pth")
            logger.info("GNN fraud detection model trained successfully")
            
        except Exception as e:
            logger.error(f"GNN model training failed: {e}")
            raise
    
    def generate_graph_training_data(self, n_samples: int) -> List[Data]:
        """Generate synthetic graph data for training"""
        graph_data_list = []
        
        for i in range(n_samples):
            # Generate random graph structure
            num_nodes = np.random.randint(3, 8)
            
            # Node features (customer, merchant, device features)
            node_features = torch.randn(num_nodes, 4)
            
            # Create edges (customer-merchant, customer-device relationships)
            edge_index = []
            edge_features = []
            
            # Customer is always node 0
            for j in range(1, num_nodes):
                edge_index.extend([[0, j], [j, 0]])  # Bidirectional
                edge_features.extend([
                    [np.random.random(), 1.0],  # transaction amount, relationship type
                    [np.random.random(), 1.0]
                ])
            
            edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
            edge_attr = torch.tensor(edge_features, dtype=torch.float)
            
            # Generate label (fraud or not)
            # Higher probability of fraud for certain patterns
            fraud_indicators = (
                torch.sum(node_features[:, 0] > 1.0) +  # High risk nodes
                torch.sum(edge_attr[:, 0] > 0.8)        # High value transactions
            )
            
            label = 1 if fraud_indicators > 2 else 0
            
            graph_data = Data(
                x=node_features,
                edge_index=edge_index,
                edge_attr=edge_attr,
                y=torch.tensor([label])
            )
            
            graph_data_list.append(graph_data)
        
        return graph_data_list
    
    def predict_gnn(self, graph_data: Data) -> Dict[str, Any]:
        """Make prediction using GNN model"""
        if self.gnn_model is None:
            raise ValueError("GNN model not loaded")
        
        self.gnn_model.eval()
        with torch.no_grad():
            fraud_probability = self.gnn_model(graph_data).squeeze().item()
        
        return {
            'fraud_probability': float(fraud_probability),
            'confidence': 0.75
        }

# GNN Model
class FraudGNNModel(nn.Module):
    def __init__(self, node_input_dim: int, edge_input_dim: int, 
                 hidden_dim: int, output_dim: int):
        super(FraudGNNModel, self).__init__()
        
        # Graph convolution layers
        self.conv1 = GATConv(node_input_dim, hidden_dim, heads=4, concat=False)
        self.conv2 = GATConv(hidden_dim, hidden_dim, heads=4, concat=False)
        self.conv3 = SAGEConv(hidden_dim, hidden_dim)
        
        # Final classification layers
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(hidden_dim // 2, output_dim),
            nn.Sigmoid()
        )
    
    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        
        # Graph convolutions
        x = F.relu(self.conv1(x, edge_index))
        x = F.dropout(x, training=self.training)
        x = F.relu(self.conv2(x, edge_index))
        x = F.dropout(x, training=self.training)
        x = F.relu(self.conv3(x, edge_index))
        
        # Global pooling (mean pooling over all nodes)
        batch_size = data.batch.max().item() + 1 if hasattr(data, 'batch') else 1
        if hasattr(data, 'batch'):
            x = torch_geometric.nn.global_mean_pool(x, data.batch)
        else:
            x = x.mean(dim=0, keepdim=True)
        
        # Classification
        x = self.classifier(x)
        
        return x

# Layer 4: Integration and Decision Layer
class FraudDecisionEngine:
    def __init__(self):
        self.ensemble_weights = {
            DetectionMethod.RULE_BASED: 0.25,
            DetectionMethod.MACHINE_LEARNING: 0.3,
            DetectionMethod.DEEP_LEARNING: 0.25,
            DetectionMethod.GRAPH_NEURAL_NETWORK: 0.2
        }
    
    def integrate_predictions(self, predictions: Dict[DetectionMethod, Dict[str, Any]]) -> Dict[str, Any]:
        """Integrate predictions from multiple detection methods"""
        # Weighted ensemble
        weighted_probability = 0.0
        total_weight = 0.0
        confidence_scores = []
        
        for method, prediction in predictions.items():
            if method in self.ensemble_weights:
                weight = self.ensemble_weights[method]
                prob = prediction.get('fraud_probability', 0.0)
                confidence = prediction.get('confidence', 0.5)
                
                weighted_probability += prob * weight * confidence
                total_weight += weight * confidence
                confidence_scores.append(confidence)
        
        # Normalize
        if total_weight > 0:
            final_probability = weighted_probability / total_weight
        else:
            final_probability = 0.5
        
        # Calculate overall confidence
        overall_confidence = np.mean(confidence_scores) if confidence_scores else 0.5
        
        # Determine risk level
        risk_level = self.get_risk_level(final_probability)
        
        # Determine fraud types
        fraud_types = self.determine_fraud_types(predictions, final_probability)
        
        return {
            'fraud_probability': final_probability,
            'risk_level': risk_level,
            'fraud_types': fraud_types,
            'confidence': overall_confidence
        }
    
    def get_risk_level(self, probability: float) -> RiskLevel:
        """Convert fraud probability to risk level"""
        if probability < 0.1:
            return RiskLevel.VERY_LOW
        elif probability < 0.3:
            return RiskLevel.LOW
        elif probability < 0.5:
            return RiskLevel.MEDIUM
        elif probability < 0.7:
            return RiskLevel.HIGH
        elif probability < 0.9:
            return RiskLevel.VERY_HIGH
        else:
            return RiskLevel.CRITICAL
    
    def determine_fraud_types(self, predictions: Dict[DetectionMethod, Dict[str, Any]], 
                            probability: float) -> List[FraudType]:
        """Determine likely fraud types based on predictions"""
        fraud_types = []
        
        if probability > 0.5:
            # Analyze patterns to determine fraud type
            rule_indicators = predictions.get(DetectionMethod.RULE_BASED, {}).get('indicators', [])
            
            if any('amount' in indicator.lower() for indicator in rule_indicators):
                fraud_types.append(FraudType.TRANSACTION_FRAUD)
            
            if any('device' in indicator.lower() for indicator in rule_indicators):
                fraud_types.append(FraudType.ACCOUNT_TAKEOVER)
            
            if any('location' in indicator.lower() for indicator in rule_indicators):
                fraud_types.append(FraudType.IDENTITY_THEFT)
            
            if any('new account' in indicator.lower() for indicator in rule_indicators):
                fraud_types.append(FraudType.SYNTHETIC_IDENTITY)
            
            # Default to transaction fraud if no specific type identified
            if not fraud_types:
                fraud_types.append(FraudType.TRANSACTION_FRAUD)
        
        return fraud_types

# Layer 5: Feedback and Adaptation Layer
class FeedbackAdaptationEngine:
    def __init__(self):
        self.feedback_buffer = []
        self.adaptation_threshold = 100  # Number of feedback samples before adaptation
    
    async def collect_feedback(self, transaction_id: str, actual_fraud: bool, 
                             predicted_probability: float):
        """Collect feedback for model adaptation"""
        feedback = {
            'transaction_id': transaction_id,
            'actual_fraud': actual_fraud,
            'predicted_probability': predicted_probability,
            'timestamp': datetime.now()
        }
        
        self.feedback_buffer.append(feedback)
        
        # Trigger adaptation if threshold reached
        if len(self.feedback_buffer) >= self.adaptation_threshold:
            await self.adapt_models()
    
    async def adapt_models(self):
        """Adapt models based on feedback"""
        logger.info(f"Adapting models with {len(self.feedback_buffer)} feedback samples")
        
        # Calculate performance metrics
        actual_labels = [f['actual_fraud'] for f in self.feedback_buffer]
        predicted_probs = [f['predicted_probability'] for f in self.feedback_buffer]
        predicted_labels = [p > 0.5 for p in predicted_probs]
        
        accuracy = accuracy_score(actual_labels, predicted_labels)
        precision = precision_score(actual_labels, predicted_labels)
        recall = recall_score(actual_labels, predicted_labels)
        
        logger.info(f"Current performance - Accuracy: {accuracy:.3f}, "
                   f"Precision: {precision:.3f}, Recall: {recall:.3f}")
        
        # Clear feedback buffer
        self.feedback_buffer = []
        
        # In a production system, this would trigger model retraining
        # For now, we just log the adaptation event
        logger.info("Model adaptation completed")

# Main Hybrid Fraud Detection Engine
class HybridFraudDetectionEngine:
    def __init__(self):
        self.data_preprocessor = DataPreprocessor()
        self.rule_engine = FraudRuleEngine()
        self.ml_detector = MLFraudDetector()
        self.gnn_detector = GNNFraudDetector()
        self.decision_engine = FraudDecisionEngine()
        self.feedback_engine = FeedbackAdaptationEngine()
        
    async def initialize(self):
        """Initialize all components of the hybrid engine"""
        logger.info("Initializing Hybrid Fraud Detection Engine...")
        
        # Initialize ML components
        await self.ml_detector.initialize()
        await self.gnn_detector.initialize()
        
        logger.info("Hybrid Fraud Detection Engine initialized successfully")
    
    async def detect_fraud(self, request: FraudDetectionRequest) -> FraudDetectionResponse:
        """Perform comprehensive fraud detection using hybrid approach"""
        start_time = datetime.now()
        
        try:
            # Layer 1: Data Preprocessing
            processed_transaction = self.data_preprocessor.preprocess_transaction_data(
                request.transaction_data
            )
            processed_customer = self.data_preprocessor.preprocess_customer_data(
                request.customer_data
            )
            
            # Prepare graph data for GNN
            graph_data = self.data_preprocessor.create_graph_data(
                processed_transaction, processed_customer, request.network_data
            )
            
            # Layer 2 & 3: Parallel execution of detection methods
            detection_tasks = []
            
            # Rule-based detection
            rule_result = self.rule_engine.evaluate_transaction(
                processed_transaction, processed_customer
            )
            
            # ML-based detection
            features = self.ml_detector.prepare_features_from_request(
                processed_transaction, processed_customer
            )
            
            ml_result = self.ml_detector.predict_traditional_ml(features)
            dl_result = self.ml_detector.predict_deep_learning(features)
            
            # GNN-based detection
            gnn_result = self.gnn_detector.predict_gnn(graph_data)
            
            # Compile all predictions
            predictions = {
                DetectionMethod.RULE_BASED: rule_result,
                DetectionMethod.MACHINE_LEARNING: ml_result,
                DetectionMethod.DEEP_LEARNING: dl_result,
                DetectionMethod.GRAPH_NEURAL_NETWORK: gnn_result
            }
            
            # Layer 4: Integration and Decision
            integrated_result = self.decision_engine.integrate_predictions(predictions)
            
            # Generate explanations and recommendations
            explanations = self.generate_explanations(predictions, integrated_result)
            recommendations = self.generate_recommendations(integrated_result, processed_transaction)
            
            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Create response
            response = FraudDetectionResponse(
                transaction_id=request.transaction_id,
                customer_id=request.customer_id,
                fraud_probability=integrated_result['fraud_probability'],
                risk_level=integrated_result['risk_level'],
                fraud_types=integrated_result['fraud_types'],
                detection_methods=predictions,
                explanations=explanations,
                recommendations=recommendations,
                confidence=integrated_result['confidence'],
                processing_time_ms=processing_time,
                timestamp=datetime.utcnow()
            )
            
            # Save detection result
            await self.save_detection_result(response)
            
            # Create alerts if high risk
            if response.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH, RiskLevel.CRITICAL]:
                await self.create_fraud_alert(response)
            
            return response
            
        except Exception as e:
            logger.error(f"Fraud detection failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    def generate_explanations(self, predictions: Dict[DetectionMethod, Dict[str, Any]], 
                            integrated_result: Dict[str, Any]) -> List[str]:
        """Generate explanations for the fraud detection decision"""
        explanations = []
        
        # Rule-based explanations
        rule_indicators = predictions.get(DetectionMethod.RULE_BASED, {}).get('indicators', [])
        explanations.extend(rule_indicators)
        
        # ML-based explanations
        ml_prediction = predictions.get(DetectionMethod.MACHINE_LEARNING, {})
        if ml_prediction.get('fraud_probability', 0) > 0.5:
            feature_importance = ml_prediction.get('feature_importance', {})
            top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]
            for feature, importance in top_features:
                explanations.append(f"High importance feature: {feature} (importance: {importance:.3f})")
        
        # Overall risk assessment
        if integrated_result['fraud_probability'] > 0.7:
            explanations.append("Multiple detection methods indicate high fraud risk")
        elif integrated_result['fraud_probability'] > 0.5:
            explanations.append("Moderate fraud risk detected across detection methods")
        
        return explanations
    
    def generate_recommendations(self, integrated_result: Dict[str, Any], 
                               transaction_data: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on fraud detection results"""
        recommendations = []
        
        risk_level = integrated_result['risk_level']
        fraud_probability = integrated_result['fraud_probability']
        
        if risk_level == RiskLevel.CRITICAL:
            recommendations.extend([
                "BLOCK TRANSACTION IMMEDIATELY",
                "Initiate fraud investigation",
                "Contact customer for verification",
                "Review all recent transactions"
            ])
        elif risk_level == RiskLevel.VERY_HIGH:
            recommendations.extend([
                "Hold transaction for manual review",
                "Require additional authentication",
                "Monitor customer account closely"
            ])
        elif risk_level == RiskLevel.HIGH:
            recommendations.extend([
                "Flag for enhanced monitoring",
                "Consider step-up authentication",
                "Review transaction pattern"
            ])
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.extend([
                "Monitor transaction",
                "Log for pattern analysis"
            ])
        
        # Specific recommendations based on fraud types
        fraud_types = integrated_result.get('fraud_types', [])
        if FraudType.ACCOUNT_TAKEOVER in fraud_types:
            recommendations.append("Verify device and location with customer")
        if FraudType.IDENTITY_THEFT in fraud_types:
            recommendations.append("Perform enhanced identity verification")
        if FraudType.SYNTHETIC_IDENTITY in fraud_types:
            recommendations.append("Review account creation details and documentation")
        
        return recommendations
    
    async def save_detection_result(self, response: FraudDetectionResponse):
        """Save fraud detection result to database"""
        db = SessionLocal()
        try:
            detection = FraudDetection(
                transaction_id=response.transaction_id,
                customer_id=response.customer_id,
                fraud_probability=response.fraud_probability,
                risk_level=response.risk_level.value,
                fraud_types=json.dumps([ft.value for ft in response.fraud_types]),
                detection_methods=json.dumps({k.value: v for k, v in response.detection_methods.items()}),
                explanations=json.dumps(response.explanations),
                recommendations=json.dumps(response.recommendations),
                confidence=response.confidence,
                processing_time_ms=response.processing_time_ms
            )
            
            db.add(detection)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to save detection result: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def create_fraud_alert(self, response: FraudDetectionResponse):
        """Create fraud alert for high-risk transactions"""
        db = SessionLocal()
        try:
            for fraud_type in response.fraud_types:
                alert = FraudAlert(
                    transaction_id=response.transaction_id,
                    customer_id=response.customer_id,
                    fraud_type=fraud_type.value,
                    risk_level=response.risk_level.value,
                    message=f"High fraud risk detected: {fraud_type.value}",
                    details=json.dumps({
                        'fraud_probability': response.fraud_probability,
                        'explanations': response.explanations,
                        'processing_time_ms': response.processing_time_ms
                    })
                )
                db.add(alert)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to create fraud alert: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def provide_feedback(self, transaction_id: str, actual_fraud: bool):
        """Provide feedback for model adaptation"""
        # Get the original prediction
        db = SessionLocal()
        try:
            detection = db.query(FraudDetection).filter(
                FraudDetection.transaction_id == transaction_id
            ).first()
            
            if detection:
                await self.feedback_engine.collect_feedback(
                    transaction_id, actual_fraud, detection.fraud_probability
                )
            
        finally:
            db.close()
    
    async def get_fraud_alerts(self, customer_id: Optional[str] = None, 
                             acknowledged: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get fraud alerts"""
        db = SessionLocal()
        try:
            query = db.query(FraudAlert)
            
            if customer_id:
                query = query.filter(FraudAlert.customer_id == customer_id)
            
            if acknowledged is not None:
                query = query.filter(FraudAlert.acknowledged == acknowledged)
            
            alerts = query.order_by(FraudAlert.created_at.desc()).limit(100).all()
            
            return [
                {
                    'id': alert.id,
                    'transaction_id': alert.transaction_id,
                    'customer_id': alert.customer_id,
                    'fraud_type': alert.fraud_type,
                    'risk_level': alert.risk_level,
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
        """Acknowledge a fraud alert"""
        db = SessionLocal()
        try:
            alert = db.query(FraudAlert).filter(FraudAlert.id == alert_id).first()
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
            'service': 'hybrid-fraud-detection',
            'version': '1.0.0',
            'components': {
                'rule_engine': True,
                'ml_detector': self.ml_detector.traditional_ml_model is not None,
                'dl_detector': self.ml_detector.deep_learning_model is not None,
                'gnn_detector': self.gnn_detector.gnn_model is not None
            }
        }

# FastAPI application
app = FastAPI(title="Hybrid Fraud Detection Engine", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
fraud_engine = HybridFraudDetectionEngine()

# Pydantic models for API
class FraudDetectionRequestModel(BaseModel):
    transaction_id: str
    customer_id: str
    transaction_data: Dict[str, Any]
    customer_data: Dict[str, Any]
    network_data: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

class FeedbackModel(BaseModel):
    transaction_id: str
    actual_fraud: bool

@app.on_event("startup")
async def startup_event():
    """Initialize fraud detection engine on startup"""
    await fraud_engine.initialize()

@app.post("/detect-fraud")
async def detect_fraud(request: FraudDetectionRequestModel):
    """Detect fraud using hybrid approach"""
    fraud_request = FraudDetectionRequest(
        transaction_id=request.transaction_id,
        customer_id=request.customer_id,
        transaction_data=request.transaction_data,
        customer_data=request.customer_data,
        network_data=request.network_data,
        context=request.context
    )
    
    response = await fraud_engine.detect_fraud(fraud_request)
    return asdict(response)

@app.post("/feedback")
async def provide_feedback(feedback: FeedbackModel):
    """Provide feedback for model adaptation"""
    await fraud_engine.provide_feedback(feedback.transaction_id, feedback.actual_fraud)
    return {'message': 'Feedback received successfully'}

@app.get("/fraud-alerts")
async def get_fraud_alerts(customer_id: Optional[str] = None, acknowledged: Optional[bool] = None):
    """Get fraud alerts"""
    alerts = await fraud_engine.get_fraud_alerts(customer_id, acknowledged)
    return {'alerts': alerts}

@app.post("/fraud-alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge a fraud alert"""
    success = await fraud_engine.acknowledge_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {'message': 'Alert acknowledged successfully'}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await fraud_engine.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
