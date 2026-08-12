"""
Churn Prediction Service
Customer churn prediction model

Fail-loud contract:
  - analyze()/batch_analyze() require a trained model artifact (joblib) loaded
    via the constructor or load_model(); without one they raise RuntimeError.
    There is NO rule-based fallback masquerading as a model prediction.
  - confidence is reported only when the estimator provides predict_proba;
    otherwise it is None — a hardcoded confidence is never returned.
  - get_insights() is not implemented: it previously returned canned insights
    ("Spending increased by 15%"), which is fabricated data. It now raises
    NotImplementedError until a real data source is wired in.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib

class ChurnpredictionService:
    """
    Customer churn prediction model
    Uses machine learning to provide intelligent insights
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False

        if model_path:
            self.load_model(model_path)

    def load_model(self, path: str) -> bool:
        """Load pre-trained model from disk"""
        try:
            self.model = joblib.load(path)
            self.is_trained = True
            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def _require_model(self):
        if not (self.is_trained and self.model is not None):
            raise RuntimeError(
                "churn prediction model is not trained/loaded; provide a real "
                "model artifact via model_path before calling analyze()"
            )

    async def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze input data and return insights

        Args:
            data: Input data for analysis

        Returns:
            Dict containing analysis results and insights

        Raises:
            RuntimeError: when no trained model artifact is loaded.
        """
        self._require_model()

        # Extract features
        features = self._extract_features(data)

        prediction = self.model.predict([features])
        confidence = self._calculate_confidence(features)

        return {
            "prediction": prediction[0] if hasattr(prediction, "__len__") else prediction,
            "confidence": confidence,
            "features": features,
            "timestamp": datetime.utcnow().isoformat(),
            "model_version": "1.0.0"
        }

    def _extract_features(self, data: Dict[str, Any]) -> List[float]:
        """Extract numerical features from input data"""
        features = []

        if "amount" in data:
            features.append(float(data["amount"]))
        if "frequency" in data:
            features.append(float(data["frequency"]))
        if "recency" in data:
            features.append(float(data["recency"]))

        return features

    def _calculate_confidence(self, features: List[float]) -> Optional[float]:
        """
        Prediction confidence from the model's own calibrated probabilities.
        Returns None when the estimator cannot report probabilities — a
        hardcoded confidence is never fabricated.
        """
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba([features])[0]
            return float(max(proba))
        return None

    async def batch_analyze(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple data points in batch

        Args:
            data_list: List of data points to analyze

        Returns:
            List of analysis results
        """
        results = []
        for data in data_list:
            result = await self.analyze(data)
            results.append(result)
        return results

    async def get_insights(self, user_id: str, timeframe: int = 30) -> Dict[str, Any]:
        """
        Get aggregated insights for a user.

        NOT IMPLEMENTED: this previously returned canned, fabricated insights
        (e.g. "Spending increased by 15%"). It now fails loud until a real
        data source is wired in.
        """
        raise NotImplementedError(
            "get_insights requires a real user transaction data source; "
            "fabricated insights have been removed"
        )
