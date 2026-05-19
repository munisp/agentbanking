import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
AI Orchestration Service for Remittance Platform
Coordinates AI/ML models for fraud detection, credit scoring, and risk assessment
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

import aioredis
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("ai-orchestration-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
import httpx
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/ai_orchestration")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ModelType(str, Enum):
    FRAUD_DETECTION = "fraud_detection"
    CREDIT_SCORING = "credit_scoring"
    RISK_ASSESSMENT = "risk_assessment"
    ANOMALY_DETECTION = "anomaly_detection"

class ModelStatus(str, Enum):
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"
    UPDATING = "updating"

@dataclass
class PredictionRequest:
    model_type: ModelType
    features: Dict[str, Any]
    customer_id: Optional[str] = None
    transaction_id: Optional[str] = None

@dataclass
class PredictionResponse:
    prediction: float
    confidence: float
    model_version: str
    features_used: List[str]
    explanation: Dict[str, Any]
    timestamp: datetime

class AIModel(Base):
    __tablename__ = "ai_models"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_type = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    model_path = Column(String)
    features = Column(Text)  # JSON string of feature names
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=False)

class PredictionLog(Base):
    __tablename__ = "prediction_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    model_type = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    customer_id = Column(String)
    transaction_id = Column(String)
    features = Column(Text)  # JSON string
    prediction = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    explanation = Column(Text)  # JSON string
    timestamp = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

class AIOrchestrationService:
    def __init__(self):
        self.models: Dict[ModelType, Dict] = {}
        self.redis_client = None
        self.mlflow_client = None
        self.feature_store = {}
        
    async def initialize(self):
        """Initialize the AI orchestration service"""
        try:
            # Initialize Redis connection
            self.redis_client = await aioredis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379")
            )
            
            # Initialize MLflow
            mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
            self.mlflow_client = mlflow.tracking.MlflowClient()
            
            # Load existing models
            await self.load_models()
            
            # Initialize feature store
            await self.initialize_feature_store()
            
            logger.info("AI Orchestration Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI Orchestration Service: {e}")
            raise

    async def load_models(self):
        """Load trained models from storage"""
        db = SessionLocal()
        try:
            active_models = db.query(AIModel).filter(AIModel.is_active == True).all()
            
            for model_record in active_models:
                try:
                    # Load model from MLflow
                    model_uri = f"models:/{model_record.model_type}/{model_record.version}"
                    model = mlflow.sklearn.load_model(model_uri)
                    
                    # Load scaler if exists
                    scaler_path = f"{model_record.model_path}_scaler.joblib"
                    scaler = None
                    if os.path.exists(scaler_path):
                        scaler = joblib.load(scaler_path)
                    
                    self.models[ModelType(model_record.model_type)] = {
                        'model': model,
                        'scaler': scaler,
                        'version': model_record.version,
                        'features': json.loads(model_record.features),
                        'metadata': {
                            'accuracy': model_record.accuracy,
                            'precision': model_record.precision,
                            'recall': model_record.recall
                        }
                    }
                    
                    logger.info(f"Loaded model {model_record.model_type} v{model_record.version}")
                    
                except Exception as e:
                    logger.error(f"Failed to load model {model_record.model_type}: {e}")
                    
        finally:
            db.close()

    async def initialize_feature_store(self):
        """Initialize feature store with sample data"""
        self.feature_store = {
            'customer_features': {},
            'transaction_features': {},
            'behavioral_features': {},
            'risk_features': {}
        }

    async def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Make prediction using specified model"""
        try:
            if request.model_type not in self.models:
                raise HTTPException(status_code=404, detail=f"Model {request.model_type} not found")
            
            model_info = self.models[request.model_type]
            model = model_info['model']
            scaler = model_info['scaler']
            features = model_info['features']
            
            # Prepare features
            feature_vector = self.prepare_features(request.features, features)
            
            # Scale features if scaler exists
            if scaler:
                feature_vector = scaler.transform([feature_vector])
            else:
                feature_vector = [feature_vector]
            
            # Make prediction
            prediction = model.predict(feature_vector)[0]
            
            # Get prediction probability if available
            confidence = 0.5
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(feature_vector)[0]
                confidence = max(probabilities)
            
            # Generate explanation
            explanation = self.generate_explanation(
                request.model_type, 
                request.features, 
                features, 
                prediction
            )
            
            # Log prediction
            await self.log_prediction(request, prediction, confidence, explanation)
            
            return PredictionResponse(
                prediction=float(prediction),
                confidence=float(confidence),
                model_version=model_info['version'],
                features_used=features,
                explanation=explanation,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def prepare_features(self, input_features: Dict[str, Any], required_features: List[str]) -> List[float]:
        """Prepare feature vector from input features"""
        feature_vector = []
        
        for feature_name in required_features:
            if feature_name in input_features:
                value = input_features[feature_name]
                # Convert to float, handle categorical variables
                if isinstance(value, (int, float)):
                    feature_vector.append(float(value))
                elif isinstance(value, str):
                    # Simple hash for categorical variables
                    feature_vector.append(float(hash(value) % 1000))
                else:
                    feature_vector.append(0.0)
            else:
                # Default value for missing features
                feature_vector.append(0.0)
        
        return feature_vector

    def generate_explanation(self, model_type: ModelType, features: Dict[str, Any], 
                           feature_names: List[str], prediction: float) -> Dict[str, Any]:
        """Generate explanation for the prediction"""
        explanation = {
            'model_type': model_type.value,
            'prediction_value': float(prediction),
            'key_factors': [],
            'risk_level': 'low'
        }
        
        # Simple rule-based explanation
        if model_type == ModelType.FRAUD_DETECTION:
            if prediction > 0.7:
                explanation['risk_level'] = 'high'
                explanation['key_factors'] = ['unusual_transaction_pattern', 'high_amount', 'new_device']
            elif prediction > 0.3:
                explanation['risk_level'] = 'medium'
                explanation['key_factors'] = ['moderate_risk_indicators']
            else:
                explanation['risk_level'] = 'low'
                explanation['key_factors'] = ['normal_transaction_pattern']
        
        elif model_type == ModelType.CREDIT_SCORING:
            if prediction > 700:
                explanation['risk_level'] = 'excellent'
                explanation['key_factors'] = ['good_payment_history', 'stable_income']
            elif prediction > 600:
                explanation['risk_level'] = 'good'
                explanation['key_factors'] = ['adequate_credit_history']
            else:
                explanation['risk_level'] = 'poor'
                explanation['key_factors'] = ['limited_credit_history', 'high_utilization']
        
        return explanation

    async def log_prediction(self, request: PredictionRequest, prediction: float, 
                           confidence: float, explanation: Dict[str, Any]):
        """Log prediction to database"""
        db = SessionLocal()
        try:
            model_version = self.models[request.model_type]['version']
            
            log_entry = PredictionLog(
                model_type=request.model_type.value,
                model_version=model_version,
                customer_id=request.customer_id,
                transaction_id=request.transaction_id,
                features=json.dumps(request.features),
                prediction=prediction,
                confidence=confidence,
                explanation=json.dumps(explanation)
            )
            
            db.add(log_entry)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")
            db.rollback()
        finally:
            db.close()

    async def train_model(self, model_type: ModelType, training_data: pd.DataFrame, 
                         target_column: str) -> str:
        """Train a new model"""
        try:
            # Start MLflow run
            with mlflow.start_run(run_name=f"{model_type.value}_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
                # Prepare data
                X = training_data.drop(columns=[target_column])
                y = training_data[target_column]
                
                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )
                
                # Scale features
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                
                # Train model based on type
                if model_type == ModelType.FRAUD_DETECTION:
                    model = RandomForestClassifier(n_estimators=100, random_state=42)
                elif model_type == ModelType.ANOMALY_DETECTION:
                    model = IsolationForest(contamination=0.1, random_state=42)
                else:
                    model = RandomForestClassifier(n_estimators=100, random_state=42)
                
                # Train
                model.fit(X_train_scaled, y_train)
                
                # Evaluate
                y_pred = model.predict(X_test_scaled)
                accuracy = accuracy_score(y_test, y_pred)
                precision = precision_score(y_test, y_pred, average='weighted')
                recall = recall_score(y_test, y_pred, average='weighted')
                
                # Log metrics
                mlflow.log_metric("accuracy", accuracy)
                mlflow.log_metric("precision", precision)
                mlflow.log_metric("recall", recall)
                
                # Log model
                model_version = f"v{int(datetime.now().timestamp())}"
                mlflow.sklearn.log_model(
                    model, 
                    model_type.value,
                    registered_model_name=model_type.value
                )
                
                # Save model and scaler
                model_path = f"/tmp/{model_type.value}_{model_version}.joblib"
                scaler_path = f"/tmp/{model_type.value}_{model_version}_scaler.joblib"
                
                joblib.dump(model, model_path)
                joblib.dump(scaler, scaler_path)
                
                # Update database
                await self.update_model_record(
                    model_type, model_version, accuracy, precision, recall,
                    model_path, list(X.columns)
                )
                
                # Update in-memory models
                self.models[model_type] = {
                    'model': model,
                    'scaler': scaler,
                    'version': model_version,
                    'features': list(X.columns),
                    'metadata': {
                        'accuracy': accuracy,
                        'precision': precision,
                        'recall': recall
                    }
                }
                
                logger.info(f"Model {model_type.value} v{model_version} trained successfully")
                return model_version
                
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            raise

    async def update_model_record(self, model_type: ModelType, version: str, 
                                accuracy: float, precision: float, recall: float,
                                model_path: str, features: List[str]):
        """Update model record in database"""
        db = SessionLocal()
        try:
            # Deactivate old models
            db.query(AIModel).filter(
                AIModel.model_type == model_type.value,
                AIModel.is_active == True
            ).update({'is_active': False})
            
            # Create new model record
            new_model = AIModel(
                model_type=model_type.value,
                version=version,
                status=ModelStatus.READY.value,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                model_path=model_path,
                features=json.dumps(features),
                is_active=True
            )
            
            db.add(new_model)
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update model record: {e}")
            db.rollback()
            raise
        finally:
            db.close()

    async def get_model_performance(self, model_type: ModelType) -> Dict[str, Any]:
        """Get model performance metrics"""
        if model_type not in self.models:
            raise HTTPException(status_code=404, detail=f"Model {model_type} not found")
        
        model_info = self.models[model_type]
        return {
            'model_type': model_type.value,
            'version': model_info['version'],
            'metrics': model_info['metadata'],
            'features': model_info['features']
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'ai-orchestration',
            'version': '1.0.0',
            'models_loaded': len(self.models),
            'available_models': list(self.models.keys())
        }

# FastAPI application
app = FastAPI(title="AI Orchestration Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instance
ai_service = AIOrchestrationService()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for API
class PredictionRequestModel(BaseModel):
    model_type: ModelType
    features: Dict[str, Any]
    customer_id: Optional[str] = None
    transaction_id: Optional[str] = None

class TrainingRequestModel(BaseModel):
    model_type: ModelType
    data_source: str
    target_column: str = "target"

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    await ai_service.initialize()

@app.post("/predict")
async def predict(request: PredictionRequestModel):
    """Make prediction using AI models"""
    prediction_request = PredictionRequest(
        model_type=request.model_type,
        features=request.features,
        customer_id=request.customer_id,
        transaction_id=request.transaction_id
    )
    
    response = await ai_service.predict(prediction_request)
    return asdict(response)

@app.post("/train")
async def train_model(request: TrainingRequestModel, background_tasks: BackgroundTasks):
    """Train a new model"""
    # In a real implementation, you would load data from the specified source
    # For demo purposes, we'll create sample data
    
    if request.model_type == ModelType.FRAUD_DETECTION:
        # Generate sample fraud detection data
        np.random.seed(42)
        n_samples = 1000
        
        data = pd.DataFrame({
            'transaction_amount': np.random.lognormal(3, 1, n_samples),
            'time_of_day': np.random.randint(0, 24, n_samples),
            'day_of_week': np.random.randint(0, 7, n_samples),
            'merchant_category': np.random.randint(0, 10, n_samples),
            'customer_age': np.random.randint(18, 80, n_samples),
            'account_age_days': np.random.randint(1, 3650, n_samples),
            'previous_transactions': np.random.randint(0, 100, n_samples),
            'target': np.random.choice([0, 1], n_samples, p=[0.95, 0.05])
        })
    else:
        # Generate sample data for other model types
        np.random.seed(42)
        n_samples = 1000
        
        data = pd.DataFrame({
            'feature_1': np.random.normal(0, 1, n_samples),
            'feature_2': np.random.normal(0, 1, n_samples),
            'feature_3': np.random.normal(0, 1, n_samples),
            'feature_4': np.random.normal(0, 1, n_samples),
            'target': np.random.choice([0, 1], n_samples)
        })
    
    # Train model in background
    version = await ai_service.train_model(request.model_type, data, request.target_column)
    
    return {
        'message': f'Model training started for {request.model_type}',
        'version': version,
        'status': 'completed'
    }

@app.get("/models/{model_type}/performance")
async def get_model_performance(model_type: ModelType):
    """Get model performance metrics"""
    return await ai_service.get_model_performance(model_type)

@app.get("/models")
async def list_models():
    """List all available models"""
    return {
        'available_models': [
            {
                'type': model_type.value,
                'version': model_info['version'],
                'features': model_info['features'],
                'metrics': model_info['metadata']
            }
            for model_type, model_info in ai_service.models.items()
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return await ai_service.health_check()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
