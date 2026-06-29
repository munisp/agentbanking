#!/usr/bin/env python3
"""
AI Personalization Platform - Phase 2
Advanced ML models, recommendations, predictive analytics, and conversational AI
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid
import numpy as np
from dataclasses import dataclass, asdict
import json

# ML libraries
try:
    import tensorflow as tf
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    import torch
    import torch.nn as nn
    HAS_ML = True
except ImportError:
    HAS_ML = False
    logging.warning("ML libraries not installed. Using rule-based fallbacks.")

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CustomerSegment(str, Enum):
    """Customer segments"""
    HIGH_VALUE = "high_value"
    FREQUENT_SENDER = "frequent_sender"
    OCCASIONAL_USER = "occasional_user"
    NEW_USER = "new_user"
    AT_RISK = "at_risk"
    DORMANT = "dormant"


class RecommendationType(str, Enum):
    """Recommendation types"""
    BENEFICIARY = "beneficiary"
    AMOUNT = "amount"
    TIMING = "timing"
    SPEED_TIER = "speed_tier"
    CURRENCY = "currency"
    FEATURE = "feature"


@dataclass
class Recommendation:
    """Personalized recommendation"""
    type: str
    title: str
    description: str
    confidence: float
    value: any
    reasoning: str
    created_at: str


@dataclass
class CustomerInsight:
    """Customer behavioral insight"""
    insight_type: str
    title: str
    description: str
    impact: str  # high, medium, low
    actionable: bool
    action_suggestion: Optional[str]
    created_at: str


class AIPersonalizationService:
    """
    Comprehensive AI personalization platform
    
    Features:
    - Advanced fraud detection with ML
    - Personalized recommendations
    - Predictive analytics
    - Customer segmentation
    - Behavioral insights
    - Conversational AI chatbot
    - A/B testing framework
    - Churn prediction
    """
    
    def __init__(self, config: Dict):
        """Initialize AI personalization service"""
        self.config = config
        
        # ML models
        self.fraud_model = None
        self.churn_model = None
        self.ltv_model = None
        self.recommendation_model = None
        
        # Initialize models
        if HAS_ML:
            self._initialize_ml_models()
        
        # Feature scalers
        self.scaler = StandardScaler() if HAS_ML else None
        
        # Customer data cache
        self.customer_profiles = {}
        self.transaction_history = {}
        self.behavioral_patterns = {}
        
        # Recommendation cache
        self.recommendations_cache = {}
        
        # Chatbot state
        self.conversation_contexts = {}
        
        logger.info("AI personalization service initialized")
    
    def _initialize_ml_models(self):
        """Initialize ML models"""
        try:
            # Fraud detection model (ensemble)
            self.fraud_model = self._build_fraud_detection_model()
            
            # Churn prediction model
            self.churn_model = self._build_churn_prediction_model()
            
            # LTV prediction model
            self.ltv_model = self._build_ltv_prediction_model()
            
            # Recommendation model (collaborative filtering)
            self.recommendation_model = self._build_recommendation_model()
            
            logger.info("ML models initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ML models: {e}")
    
    def _build_fraud_detection_model(self):
        """Build fraud detection model"""
        if not HAS_ML:
            return None
        
        # Neural network for fraud detection
        model = tf.keras.Sequential([
            tf.keras.layers.Dense(128, activation='relu', input_shape=(20,)),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(64, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer='adam',
            loss='binary_crossentropy',
            metrics=['accuracy', 'precision', 'recall']
        )
        
        return model
    
    def _build_churn_prediction_model(self):
        """Build churn prediction model"""
        if not HAS_ML:
            return None
        
        # Gradient boosting for churn prediction
        return GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
    
    def _build_ltv_prediction_model(self):
        """Build lifetime value prediction model"""
        if not HAS_ML:
            return None
        
        # Random forest for LTV prediction
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
    
    def _build_recommendation_model(self):
        """Build recommendation model"""
        if not HAS_ML:
            return None
        
        # Simple collaborative filtering model
        class RecommendationNet(nn.Module):
            def __init__(self, n_users, n_items, embedding_dim=50):
                super().__init__()
                self.user_embedding = nn.Embedding(n_users, embedding_dim)
                self.item_embedding = nn.Embedding(n_items, embedding_dim)
                self.fc = nn.Linear(embedding_dim * 2, 1)
            
            def forward(self, user_ids, item_ids):
                user_embeds = self.user_embedding(user_ids)
                item_embeds = self.item_embedding(item_ids)
                x = torch.cat([user_embeds, item_embeds], dim=1)
                return torch.sigmoid(self.fc(x))
        
        return RecommendationNet(n_users=10000, n_items=1000)
    
    async def detect_fraud_ml(
        self,
        transaction: Dict,
        user_profile: Dict,
        historical_data: List[Dict]
    ) -> Dict:
        """
        Advanced fraud detection using ML
        
        Args:
            transaction: Transaction details
            user_profile: User profile data
            historical_data: Historical transaction data
            
        Returns:
            Fraud detection result with risk score and explanation
        """
        # Extract features
        features = self._extract_fraud_features(transaction, user_profile, historical_data)
        
        if HAS_ML and self.fraud_model:
            # Use ML model
            features_array = np.array([features])
            if self.scaler:
                features_array = self.scaler.transform(features_array)
            
            fraud_probability = float(self.fraud_model.predict(features_array)[0][0])
        else:
            # Fallback to rule-based
            fraud_probability = self._rule_based_fraud_score(transaction, user_profile, historical_data)
        
        # Determine risk level
        if fraud_probability >= 0.8:
            risk_level = RiskLevel.CRITICAL
            action = "block"
        elif fraud_probability >= 0.6:
            risk_level = RiskLevel.HIGH
            action = "review"
        elif fraud_probability >= 0.4:
            risk_level = RiskLevel.MEDIUM
            action = "2fa"
        else:
            risk_level = RiskLevel.LOW
            action = "approve"
        
        # Generate explanation
        explanation = self._generate_fraud_explanation(features, fraud_probability)
        
        return {
            "fraud_probability": fraud_probability,
            "risk_level": risk_level.value,
            "action": action,
            "explanation": explanation,
            "features_analyzed": len(features),
            "model_version": "v2.0_ml",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_fraud_features(
        self,
        transaction: Dict,
        user_profile: Dict,
        historical_data: List[Dict]
    ) -> List[float]:
        """Extract features for fraud detection"""
        features = []
        
        # Transaction features
        features.append(float(transaction.get("amount", 0)))
        features.append(float(transaction.get("hour_of_day", 0)))
        features.append(float(transaction.get("day_of_week", 0)))
        
        # User features
        features.append(float(user_profile.get("account_age_days", 0)))
        features.append(float(user_profile.get("total_transactions", 0)))
        features.append(float(user_profile.get("average_transaction_amount", 0)))
        features.append(float(user_profile.get("kyc_level", 0)))
        
        # Velocity features
        transactions_24h = len([t for t in historical_data if self._is_within_hours(t, 24)])
        transactions_7d = len([t for t in historical_data if self._is_within_days(t, 7)])
        features.append(float(transactions_24h))
        features.append(float(transactions_7d))
        
        # Amount anomaly
        if historical_data:
            avg_amount = np.mean([float(t.get("amount", 0)) for t in historical_data])
            std_amount = np.std([float(t.get("amount", 0)) for t in historical_data])
            z_score = (float(transaction.get("amount", 0)) - avg_amount) / (std_amount + 1e-6)
            features.append(z_score)
        else:
            features.append(0.0)
        
        # Location features
        features.append(float(transaction.get("location_risk_score", 0)))
        features.append(float(transaction.get("location_changed", 0)))
        
        # Device features
        features.append(float(transaction.get("new_device", 0)))
        features.append(float(transaction.get("device_risk_score", 0)))
        
        # Beneficiary features
        features.append(float(transaction.get("new_beneficiary", 0)))
        features.append(float(transaction.get("beneficiary_risk_score", 0)))
        
        # Time-based features
        features.append(float(transaction.get("unusual_time", 0)))
        features.append(float(transaction.get("time_since_last_transaction_hours", 0)))
        
        # Pad to 20 features
        while len(features) < 20:
            features.append(0.0)
        
        return features[:20]
    
    def _rule_based_fraud_score(
        self,
        transaction: Dict,
        user_profile: Dict,
        historical_data: List[Dict]
    ) -> float:
        """Rule-based fraud scoring (fallback)"""
        score = 0.0
        
        # High amount
        if transaction.get("amount", 0) > 5000:
            score += 0.2
        
        # New user
        if user_profile.get("account_age_days", 0) < 30:
            score += 0.15
        
        # Velocity abuse
        recent_count = len([t for t in historical_data if self._is_within_hours(t, 24)])
        if recent_count > 5:
            score += 0.25
        
        # New beneficiary
        if transaction.get("new_beneficiary"):
            score += 0.1
        
        # Location change
        if transaction.get("location_changed"):
            score += 0.15
        
        # New device
        if transaction.get("new_device"):
            score += 0.15
        
        return min(score, 1.0)
    
    def _generate_fraud_explanation(self, features: List[float], probability: float) -> str:
        """Generate human-readable fraud explanation"""
        reasons = []
        
        if features[0] > 5000:  # High amount
            reasons.append("High transaction amount")
        
        if features[7] > 5:  # High velocity
            reasons.append("Multiple transactions in short time")
        
        if features[9] > 3:  # Amount anomaly
            reasons.append("Amount significantly different from usual")
        
        if features[11] > 0:  # Location changed
            reasons.append("Transaction from new location")
        
        if features[12] > 0:  # New device
            reasons.append("Transaction from new device")
        
        if features[14] > 0:  # New beneficiary
            reasons.append("Sending to new beneficiary")
        
        if not reasons:
            reasons.append("Normal transaction pattern")
        
        return "; ".join(reasons)
    
    async def get_personalized_recommendations(
        self,
        user_id: str,
        context: Optional[Dict] = None
    ) -> List[Recommendation]:
        """
        Get personalized recommendations for user
        
        Args:
            user_id: User identifier
            context: Current context (page, action, etc.)
            
        Returns:
            List of personalized recommendations
        """
        recommendations = []
        
        # Get user profile and history
        profile = self.customer_profiles.get(user_id, {})
        history = self.transaction_history.get(user_id, [])
        
        # Beneficiary recommendations
        beneficiary_recs = await self._recommend_beneficiaries(user_id, history)
        recommendations.extend(beneficiary_recs)
        
        # Amount recommendations
        amount_recs = await self._recommend_amounts(user_id, history)
        recommendations.extend(amount_recs)
        
        # Timing recommendations
        timing_recs = await self._recommend_timing(user_id, history)
        recommendations.extend(timing_recs)
        
        # Speed tier recommendations
        speed_recs = await self._recommend_speed_tier(user_id, history)
        recommendations.extend(speed_recs)
        
        # Feature recommendations
        feature_recs = await self._recommend_features(user_id, profile)
        recommendations.extend(feature_recs)
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x.confidence, reverse=True)
        
        return recommendations[:5]  # Top 5
    
    async def _recommend_beneficiaries(self, user_id: str, history: List[Dict]) -> List[Recommendation]:
        """Recommend beneficiaries to send to"""
        recommendations = []
        
        if not history:
            return recommendations
        
        # Analyze frequency
        beneficiary_counts = {}
        for txn in history:
            ben_id = txn.get("beneficiary_id")
            if ben_id:
                beneficiary_counts[ben_id] = beneficiary_counts.get(ben_id, 0) + 1
        
        # Get top beneficiaries
        top_beneficiaries = sorted(beneficiary_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for ben_id, count in top_beneficiaries:
            # Get beneficiary details
            ben_name = f"Beneficiary {ben_id}"  # Fetch from DB
            
            recommendations.append(Recommendation(
                type=RecommendationType.BENEFICIARY.value,
                title=f"Send to {ben_name}",
                description=f"You've sent to {ben_name} {count} times",
                confidence=min(count / 10, 1.0),
                value=ben_id,
                reasoning=f"Frequently used beneficiary ({count} transactions)",
                created_at=datetime.utcnow().isoformat()
            ))
        
        return recommendations
    
    async def _recommend_amounts(self, user_id: str, history: List[Dict]) -> List[Recommendation]:
        """Recommend transaction amounts"""
        recommendations = []
        
        if len(history) < 3:
            return recommendations
        
        # Calculate typical amounts
        amounts = [float(t.get("amount", 0)) for t in history]
        avg_amount = np.mean(amounts)
        median_amount = np.median(amounts)
        
        # Recommend median amount
        recommendations.append(Recommendation(
            type=RecommendationType.AMOUNT.value,
            title=f"Typical amount: ${median_amount:.2f}",
            description="Based on your sending history",
            confidence=0.8,
            value=float(median_amount),
            reasoning=f"Median of your last {len(history)} transactions",
            created_at=datetime.utcnow().isoformat()
        ))
        
        return recommendations
    
    async def _recommend_timing(self, user_id: str, history: List[Dict]) -> List[Recommendation]:
        """Recommend optimal timing"""
        recommendations = []
        
        if len(history) < 5:
            return recommendations
        
        # Analyze timing patterns
        hours = [datetime.fromisoformat(t.get("created_at", datetime.utcnow().isoformat())).hour 
                for t in history if t.get("created_at")]
        
        if hours:
            most_common_hour = max(set(hours), key=hours.count)
            
            recommendations.append(Recommendation(
                type=RecommendationType.TIMING.value,
                title=f"Best time: {most_common_hour}:00",
                description="When you usually send money",
                confidence=0.7,
                value=most_common_hour,
                reasoning=f"You typically send at this hour",
                created_at=datetime.utcnow().isoformat()
            ))
        
        return recommendations
    
    async def _recommend_speed_tier(self, user_id: str, history: List[Dict]) -> List[Recommendation]:
        """Recommend transfer speed tier"""
        recommendations = []
        
        if not history:
            return recommendations
        
        # Analyze speed preferences
        speed_counts = {}
        for txn in history:
            speed = txn.get("speed_tier", "standard")
            speed_counts[speed] = speed_counts.get(speed, 0) + 1
        
        if speed_counts:
            preferred_speed = max(speed_counts, key=speed_counts.get)
            
            recommendations.append(Recommendation(
                type=RecommendationType.SPEED_TIER.value,
                title=f"Preferred speed: {preferred_speed.title()}",
                description="Your usual choice",
                confidence=0.75,
                value=preferred_speed,
                reasoning=f"You chose this {speed_counts[preferred_speed]} times",
                created_at=datetime.utcnow().isoformat()
            ))
        
        return recommendations
    
    async def _recommend_features(self, user_id: str, profile: Dict) -> List[Recommendation]:
        """Recommend features to try"""
        recommendations = []
        
        # Check feature usage
        used_features = profile.get("used_features", [])
        
        available_features = [
            ("multi_currency", "Multi-Currency Wallet", "Hold money in multiple currencies"),
            ("virtual_iban", "Virtual IBAN", "Receive international payments"),
            ("stablecoin", "Stablecoin Transfers", "Save 50% on fees"),
            ("recurring", "Recurring Transfers", "Set up automatic payments"),
        ]
        
        for feature_id, title, description in available_features:
            if feature_id not in used_features:
                recommendations.append(Recommendation(
                    type=RecommendationType.FEATURE.value,
                    title=f"Try {title}",
                    description=description,
                    confidence=0.6,
                    value=feature_id,
                    reasoning="Feature you haven't tried yet",
                    created_at=datetime.utcnow().isoformat()
                ))
                break  # Only recommend one new feature at a time
        
        return recommendations
    
    async def predict_churn(self, user_id: str) -> Dict:
        """
        Predict customer churn probability
        
        Args:
            user_id: User identifier
            
        Returns:
            Churn prediction with probability and risk factors
        """
        profile = self.customer_profiles.get(user_id, {})
        history = self.transaction_history.get(user_id, [])
        
        # Extract features
        features = self._extract_churn_features(profile, history)
        
        if HAS_ML and self.churn_model:
            # Use ML model
            features_array = np.array([features])
            churn_probability = float(self.churn_model.predict(features_array)[0])
        else:
            # Rule-based fallback
            churn_probability = self._rule_based_churn_score(profile, history)
        
        # Identify risk factors
        risk_factors = self._identify_churn_risk_factors(profile, history)
        
        # Generate retention strategies
        retention_strategies = self._generate_retention_strategies(risk_factors, churn_probability)
        
        return {
            "user_id": user_id,
            "churn_probability": churn_probability,
            "risk_level": "high" if churn_probability > 0.7 else "medium" if churn_probability > 0.4 else "low",
            "risk_factors": risk_factors,
            "retention_strategies": retention_strategies,
            "predicted_at": datetime.utcnow().isoformat()
        }
    
    def _extract_churn_features(self, profile: Dict, history: List[Dict]) -> List[float]:
        """Extract features for churn prediction"""
        features = []
        
        # Recency
        if history:
            last_txn_date = datetime.fromisoformat(history[-1].get("created_at", datetime.utcnow().isoformat()))
            days_since_last = (datetime.utcnow() - last_txn_date).days
            features.append(float(days_since_last))
        else:
            features.append(365.0)
        
        # Frequency
        features.append(float(len(history)))
        
        # Monetary
        total_value = sum(float(t.get("amount", 0)) for t in history)
        features.append(total_value)
        
        # Account age
        features.append(float(profile.get("account_age_days", 0)))
        
        # Engagement metrics
        features.append(float(profile.get("login_count_30d", 0)))
        features.append(float(profile.get("feature_usage_count", 0)))
        
        # Trend (declining usage)
        if len(history) >= 6:
            recent_count = len([t for t in history if self._is_within_days(t, 30)])
            older_count = len([t for t in history if self._is_within_days(t, 60) and not self._is_within_days(t, 30)])
            trend = (recent_count - older_count) / (older_count + 1)
            features.append(trend)
        else:
            features.append(0.0)
        
        return features
    
    def _rule_based_churn_score(self, profile: Dict, history: List[Dict]) -> float:
        """Rule-based churn scoring"""
        score = 0.0
        
        # No recent activity
        if history:
            last_txn_date = datetime.fromisoformat(history[-1].get("created_at", datetime.utcnow().isoformat()))
            days_since_last = (datetime.utcnow() - last_txn_date).days
            if days_since_last > 60:
                score += 0.4
            elif days_since_last > 30:
                score += 0.2
        else:
            score += 0.5
        
        # Low frequency
        if len(history) < 3:
            score += 0.2
        
        # Declining usage
        if len(history) >= 6:
            recent_count = len([t for t in history if self._is_within_days(t, 30)])
            if recent_count == 0:
                score += 0.3
        
        return min(score, 1.0)
    
    def _identify_churn_risk_factors(self, profile: Dict, history: List[Dict]) -> List[str]:
        """Identify churn risk factors"""
        factors = []
        
        if history:
            last_txn_date = datetime.fromisoformat(history[-1].get("created_at", datetime.utcnow().isoformat()))
            days_since_last = (datetime.utcnow() - last_txn_date).days
            if days_since_last > 30:
                factors.append(f"No activity for {days_since_last} days")
        
        if len(history) < 3:
            factors.append("Low transaction frequency")
        
        if profile.get("login_count_30d", 0) < 2:
            factors.append("Low engagement (few logins)")
        
        if profile.get("support_tickets", 0) > 2:
            factors.append("Multiple support tickets (potential dissatisfaction)")
        
        return factors
    
    def _generate_retention_strategies(self, risk_factors: List[str], churn_prob: float) -> List[str]:
        """Generate retention strategies"""
        strategies = []
        
        if churn_prob > 0.7:
            strategies.append("Offer special promotion or cashback")
            strategies.append("Personal outreach from account manager")
        
        if "No activity" in str(risk_factors):
            strategies.append("Send re-engagement email with incentive")
            strategies.append("Highlight new features")
        
        if "Low engagement" in str(risk_factors):
            strategies.append("Improve onboarding experience")
            strategies.append("Gamification to increase engagement")
        
        if "support tickets" in str(risk_factors):
            strategies.append("Proactive customer support outreach")
            strategies.append("Address pain points")
        
        return strategies
    
    async def segment_customer(self, user_id: str) -> Dict:
        """
        Segment customer based on behavior
        
        Args:
            user_id: User identifier
            
        Returns:
            Customer segment with characteristics
        """
        profile = self.customer_profiles.get(user_id, {})
        history = self.transaction_history.get(user_id, [])
        
        # Calculate RFM scores
        recency_score = self._calculate_recency_score(history)
        frequency_score = self._calculate_frequency_score(history)
        monetary_score = self._calculate_monetary_score(history)
        
        # Determine segment
        if monetary_score >= 4 and frequency_score >= 4:
            segment = CustomerSegment.HIGH_VALUE
        elif frequency_score >= 4:
            segment = CustomerSegment.FREQUENT_SENDER
        elif recency_score <= 2:
            segment = CustomerSegment.DORMANT
        elif len(history) < 3:
            segment = CustomerSegment.NEW_USER
        elif recency_score <= 3 and frequency_score <= 2:
            segment = CustomerSegment.AT_RISK
        else:
            segment = CustomerSegment.OCCASIONAL_USER
        
        return {
            "user_id": user_id,
            "segment": segment.value,
            "rfm_scores": {
                "recency": recency_score,
                "frequency": frequency_score,
                "monetary": monetary_score
            },
            "characteristics": self._get_segment_characteristics(segment),
            "marketing_strategy": self._get_segment_marketing_strategy(segment),
            "segmented_at": datetime.utcnow().isoformat()
        }
    
    def _calculate_recency_score(self, history: List[Dict]) -> int:
        """Calculate recency score (1-5, 5 is best)"""
        if not history:
            return 1
        
        last_txn_date = datetime.fromisoformat(history[-1].get("created_at", datetime.utcnow().isoformat()))
        days_since_last = (datetime.utcnow() - last_txn_date).days
        
        if days_since_last <= 7:
            return 5
        elif days_since_last <= 30:
            return 4
        elif days_since_last <= 60:
            return 3
        elif days_since_last <= 90:
            return 2
        else:
            return 1
    
    def _calculate_frequency_score(self, history: List[Dict]) -> int:
        """Calculate frequency score (1-5, 5 is best)"""
        count = len(history)
        
        if count >= 20:
            return 5
        elif count >= 10:
            return 4
        elif count >= 5:
            return 3
        elif count >= 2:
            return 2
        else:
            return 1
    
    def _calculate_monetary_score(self, history: List[Dict]) -> int:
        """Calculate monetary score (1-5, 5 is best)"""
        total = sum(float(t.get("amount", 0)) for t in history)
        
        if total >= 10000:
            return 5
        elif total >= 5000:
            return 4
        elif total >= 1000:
            return 3
        elif total >= 100:
            return 2
        else:
            return 1
    
    def _get_segment_characteristics(self, segment: CustomerSegment) -> List[str]:
        """Get segment characteristics"""
        characteristics = {
            CustomerSegment.HIGH_VALUE: [
                "High transaction volume",
                "High transaction value",
                "Frequent user",
                "Low churn risk"
            ],
            CustomerSegment.FREQUENT_SENDER: [
                "Regular transactions",
                "Moderate transaction value",
                "Engaged user"
            ],
            CustomerSegment.OCCASIONAL_USER: [
                "Infrequent transactions",
                "Moderate value",
                "Potential for growth"
            ],
            CustomerSegment.NEW_USER: [
                "Recently joined",
                "Few transactions",
                "High growth potential"
            ],
            CustomerSegment.AT_RISK: [
                "Declining activity",
                "Churn risk",
                "Needs re-engagement"
            ],
            CustomerSegment.DORMANT: [
                "No recent activity",
                "High churn risk",
                "Requires win-back campaign"
            ]
        }
        return characteristics.get(segment, [])
    
    def _get_segment_marketing_strategy(self, segment: CustomerSegment) -> List[str]:
        """Get marketing strategy for segment"""
        strategies = {
            CustomerSegment.HIGH_VALUE: [
                "VIP treatment",
                "Exclusive features",
                "Personal account manager",
                "Premium support"
            ],
            CustomerSegment.FREQUENT_SENDER: [
                "Loyalty rewards",
                "Referral incentives",
                "Feature education"
            ],
            CustomerSegment.OCCASIONAL_USER: [
                "Engagement campaigns",
                "Feature highlights",
                "Use case education"
            ],
            CustomerSegment.NEW_USER: [
                "Onboarding optimization",
                "First transaction incentive",
                "Tutorial content"
            ],
            CustomerSegment.AT_RISK: [
                "Re-engagement campaign",
                "Special offers",
                "Feedback survey"
            ],
            CustomerSegment.DORMANT: [
                "Win-back campaign",
                "Significant incentive",
                "Product updates"
            ]
        }
        return strategies.get(segment, [])
    
    # Helper methods
    
    def _is_within_hours(self, transaction: Dict, hours: int) -> bool:
        """Check if transaction is within specified hours"""
        txn_date = datetime.fromisoformat(transaction.get("created_at", datetime.utcnow().isoformat()))
        return (datetime.utcnow() - txn_date).total_seconds() / 3600 <= hours
    
    def _is_within_days(self, transaction: Dict, days: int) -> bool:
        """Check if transaction is within specified days"""
        txn_date = datetime.fromisoformat(transaction.get("created_at", datetime.utcnow().isoformat()))
        return (datetime.utcnow() - txn_date).days <= days


# Example usage
if __name__ == "__main__":
    config = {}
    service = AIPersonalizationService(config)
    
    async def example():
        # Fraud detection
        transaction = {
            "amount": 5000,
            "hour_of_day": 2,
            "new_beneficiary": True,
            "location_changed": True
        }
        user_profile = {
            "account_age_days": 15,
            "total_transactions": 2
        }
        fraud_result = await service.detect_fraud_ml(transaction, user_profile, [])
        print(f"Fraud detection: {fraud_result}")
        
        # Recommendations
        recommendations = await service.get_personalized_recommendations("user_123")
        print(f"Recommendations: {[r.title for r in recommendations]}")
        
        # Churn prediction
        churn_result = await service.predict_churn("user_123")
        print(f"Churn prediction: {churn_result}")
        
        # Customer segmentation
        segment_result = await service.segment_customer("user_123")
        print(f"Customer segment: {segment_result}")
    
    # asyncio.run(example())

