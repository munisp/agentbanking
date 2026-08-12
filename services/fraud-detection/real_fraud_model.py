#!/usr/bin/env python3
"""
Fraud Detection Model — trained-artifact serving

This module serves fraud predictions ONLY from a versioned, previously
trained model artifact (joblib bundle produced by an offline training
pipeline). It never trains on synthetic random data at boot and refuses to
serve when no artifact is configured or loadable.
"""

import numpy as np
import pandas as pd
import pickle
import joblib
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import lightgbm as lgb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class FraudDetectionResult:
    transaction_id: str
    fraud_probability: float
    risk_score: float
    risk_level: str
    model_predictions: Dict[str, float]
    feature_importance: Dict[str, float]
    explanation: List[str]
    confidence: float
    timestamp: datetime

class RealFraudDetectionModel:
    """Fraud detection model served exclusively from a trained artifact.

    The artifact (a joblib bundle with models, scalers, feature names and
    model weights) must be produced by the offline training pipeline and
    provided via FRAUD_MODEL_ARTIFACT_PATH or the constructor argument.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.models = {}
        self.scalers = {}
        self.feature_names = []
        self.model_weights = {}
        self.is_trained = False
        self.model_version: Optional[str] = None
        
        # Load the trained artifact (refuses to serve without one)
        self._initialize_real_models(model_path)
        
    def _initialize_real_models(self, model_path: Optional[str] = None):
        """Load the versioned trained artifact or refuse to serve."""
        path = model_path or os.environ.get("FRAUD_MODEL_ARTIFACT_PATH", "")
        if not path:
            raise RuntimeError(
                "FRAUD_MODEL_ARTIFACT_PATH is not configured; refusing to serve "
                "fraud scores without a trained model artifact"
            )
        if not os.path.exists(path):
            raise RuntimeError(
                f"Trained model artifact not found at '{path}'; refusing to serve "
                "fraud scores without a trained model artifact"
            )
        try:
            self.load_models(path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load trained model artifact '{path}': {e}; refusing to serve"
            ) from e
        if not self.is_trained or not self.models:
            raise RuntimeError(
                f"Model artifact '{path}' is not a valid trained bundle; refusing to serve"
            )
        logger.info(
            f"Fraud detection models loaded from artifact {path} "
            f"(version: {self.model_version or 'unknown'})"
        )
    
    def predict_fraud(self, transaction_features: Dict[str, Any]) -> FraudDetectionResult:
        """Predict fraud probability for a transaction"""
        if not self.is_trained:
            raise ValueError("Models not loaded. A trained artifact is required.")
        
        # Convert features to DataFrame
        feature_vector = self._prepare_features(transaction_features)
        
        # Get predictions from all models
        model_predictions = {}
        
        # Random Forest prediction
        rf_scaled = self.scalers['random_forest'].transform([feature_vector])
        rf_prob = self.models['random_forest'].predict_proba(rf_scaled)[0, 1]
        model_predictions['random_forest'] = rf_prob
        
        # XGBoost prediction
        xgb_scaled = self.scalers['xgboost'].transform([feature_vector])
        xgb_prob = self.models['xgboost'].predict_proba(xgb_scaled)[0, 1]
        model_predictions['xgboost'] = xgb_prob
        
        # Isolation Forest prediction
        iso_scaled = self.scalers['isolation_forest'].transform([feature_vector])
        iso_score = self.models['isolation_forest'].decision_function(iso_scaled)[0]
        iso_prob = 1 / (1 + np.exp(-iso_score))  # Convert to probability
        model_predictions['isolation_forest'] = iso_prob
        
        # Ensemble prediction
        ensemble_features = np.array([[rf_prob, xgb_prob, iso_prob]])
        ensemble_prob = self.models['ensemble'].predict_proba(ensemble_features)[0, 1]
        model_predictions['ensemble'] = ensemble_prob
        
        # Calculate weighted average
        weighted_prob = sum(
            prob * self.model_weights[model] 
            for model, prob in model_predictions.items()
        )
        
        # Calculate risk score and level
        risk_score = weighted_prob * 100
        risk_level = self._determine_risk_level(risk_score)
        
        # Generate explanation
        explanation = self._generate_explanation(
            transaction_features, model_predictions, feature_vector
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(model_predictions)
        
        # Get feature importance
        feature_importance = self._get_feature_importance(feature_vector)
        
        return FraudDetectionResult(
            transaction_id=transaction_features.get('transaction_id', 'unknown'),
            fraud_probability=weighted_prob,
            risk_score=risk_score,
            risk_level=risk_level,
            model_predictions=model_predictions,
            feature_importance=feature_importance,
            explanation=explanation,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _prepare_features(self, transaction_features: Dict[str, Any]) -> List[float]:
        """Prepare feature vector from transaction features"""
        feature_vector = []
        
        for feature_name in self.feature_names:
            if feature_name in transaction_features:
                value = transaction_features[feature_name]
                if isinstance(value, (int, float)):
                    feature_vector.append(float(value))
                else:
                    # Handle categorical or string features
                    feature_vector.append(float(hash(str(value)) % 1000))
            else:
                # Default value for missing features
                feature_vector.append(0.0)
        
        return feature_vector
    
    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level based on risk score"""
        if risk_score >= 80:
            return "CRITICAL"
        elif risk_score >= 60:
            return "HIGH"
        elif risk_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_explanation(self, transaction_features: Dict[str, Any], 
                            model_predictions: Dict[str, float], 
                            feature_vector: List[float]) -> List[str]:
        """Generate human-readable explanation for the prediction"""
        explanations = []
        
        # High-level model agreement
        high_risk_models = [model for model, prob in model_predictions.items() if prob > 0.7]
        if len(high_risk_models) >= 2:
            explanations.append(f"Multiple models ({', '.join(high_risk_models)}) indicate high fraud risk")
        
        # Feature-based explanations
        amount = transaction_features.get('amount', 0)
        if amount > 10000:
            explanations.append(f"High transaction amount: ${amount:,.2f}")
        
        velocity_1h = transaction_features.get('transaction_count_1h', 0)
        if velocity_1h > 5:
            explanations.append(f"High transaction velocity: {velocity_1h} transactions in 1 hour")
        
        distance = transaction_features.get('distance_from_home', 0)
        if distance > 100:
            explanations.append(f"Transaction far from usual location: {distance:.1f} km")
        
        is_night = transaction_features.get('is_night', False)
        if is_night:
            explanations.append("Transaction during unusual hours (night time)")
        
        network_risk = transaction_features.get('network_risk', 0)
        if network_risk > 0.7:
            explanations.append("High network risk score detected")
        
        if not explanations:
            explanations.append("Transaction appears normal based on available features")
        
        return explanations
    
    def _calculate_confidence(self, model_predictions: Dict[str, float]) -> float:
        """Calculate confidence based on model agreement"""
        predictions = list(model_predictions.values())
        
        # Calculate standard deviation of predictions
        std_dev = np.std(predictions)
        
        # Lower standard deviation means higher confidence
        confidence = max(0.0, 1.0 - (std_dev * 2))
        
        return confidence
    
    def _get_feature_importance(self, feature_vector: List[float]) -> Dict[str, float]:
        """Get feature importance for the current prediction"""
        # Use Random Forest feature importance as baseline
        rf_importance = self.models['random_forest_importance']
        
        # Weight by feature values
        weighted_importance = {}
        for i, feature_name in enumerate(self.feature_names):
            base_importance = rf_importance.get(feature_name, 0)
            feature_value = feature_vector[i]
            
            # Normalize feature value and combine with importance
            normalized_value = min(abs(feature_value) / 100, 1.0)
            weighted_importance[feature_name] = base_importance * (1 + normalized_value)
        
        # Sort by importance
        sorted_importance = dict(sorted(
            weighted_importance.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10])  # Top 10 features
        
        return sorted_importance
    
    def save_models(self, model_path: str, model_version: Optional[str] = None):
        """Save trained models to disk (offline training pipeline only)"""
        model_data = {
            'models': self.models,
            'scalers': self.scalers,
            'feature_names': self.feature_names,
            'model_weights': self.model_weights,
            'is_trained': self.is_trained,
            'model_version': model_version,
        }
        
        joblib.dump(model_data, model_path)
        logger.info(f"Models saved to {model_path}")
    
    def load_models(self, model_path: str):
        """Load trained models from disk"""
        model_data = joblib.load(model_path)
        
        self.models = model_data['models']
        self.scalers = model_data['scalers']
        self.feature_names = model_data['feature_names']
        self.model_weights = model_data['model_weights']
        self.is_trained = model_data['is_trained']
        self.model_version = model_data.get('model_version')
        
        logger.info(f"Models loaded from {model_path}")

# Example usage and testing
if __name__ == "__main__":
    # Initialize fraud detection model from the trained artifact
    try:
        fraud_model = RealFraudDetectionModel()
    except RuntimeError as e:
        print(f"Refusing to serve fraud model: {e}")
        raise SystemExit(1)
    
    # Test with sample transaction
    sample_transaction = {
        'transaction_id': 'TXN_123456',
        'amount': 15000.0,
        'hour': 23,
        'day_of_week': 6,
        'merchant_category': 5,
        'transaction_count_1h': 8,
        'transaction_count_24h': 25,
        'amount_sum_1h': 50000.0,
        'amount_sum_24h': 150000.0,
        'distance_from_home': 250.0,
        'is_weekend': 1,
        'is_night': 1,
        'device_score': 0.3,
        'location_risk': 0.8,
        'velocity_score': 8.5,
        'behavioral_score': 2.1,
        'network_risk': 0.9,
        'customer_age_days': 30,
        'avg_amount_30d': 2000.0,
        'transaction_frequency': 5.2,
        'cross_border': 1,
    }
    
    # Make prediction
    result = fraud_model.predict_fraud(sample_transaction)
    
    print(f"Transaction ID: {result.transaction_id}")
    print(f"Fraud Probability: {result.fraud_probability:.4f}")
    print(f"Risk Score: {result.risk_score:.1f}")
    print(f"Risk Level: {result.risk_level}")
    print(f"Confidence: {result.confidence:.4f}")
    print(f"Model Predictions: {result.model_predictions}")
    print(f"Explanations: {result.explanation}")
    print(f"Top Features: {list(result.feature_importance.keys())[:5]}")
