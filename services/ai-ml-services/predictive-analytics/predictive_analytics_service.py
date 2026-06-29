"""
Predictive Analytics Service
Transaction pattern prediction, churn prediction, and revenue forecasting
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
import joblib


class PredictiveAnalyticsService:
    """Predictive analytics for transaction patterns and business metrics"""
    
    def __init__(self):
        self.transaction_model = None
        self.churn_model = None
        self.revenue_model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def _extract_transaction_features(self, transactions: List[Dict]) -> pd.DataFrame:
        """Extract features from transaction history"""
        df = pd.DataFrame(transactions)
        
        features = pd.DataFrame()
        
        # Time-based features
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        features['hour'] = df['timestamp'].dt.hour
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        features['day_of_month'] = df['timestamp'].dt.day
        features['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)
        
        # Amount features
        features['amount'] = df['amount']
        features['log_amount'] = np.log1p(df['amount'])
        
        # Aggregated features
        features['avg_amount_7d'] = df.groupby('user_id')['amount'].transform(
            lambda x: x.rolling(window=7, min_periods=1).mean()
        )
        features['tx_count_7d'] = df.groupby('user_id')['amount'].transform(
            lambda x: x.rolling(window=7, min_periods=1).count()
        )
        features['max_amount_30d'] = df.groupby('user_id')['amount'].transform(
            lambda x: x.rolling(window=30, min_periods=1).max()
        )
        
        # Categorical features
        features['currency'] = pd.Categorical(df['currency']).codes
        features['payment_method'] = pd.Categorical(df['payment_method']).codes
        features['transaction_type'] = pd.Categorical(df['transaction_type']).codes
        
        return features
    
    async def train_transaction_predictor(self, historical_data: List[Dict]) -> Dict:
        """
        Train model to predict transaction patterns
        
        Args:
            historical_data: Historical transaction data with labels
        """
        try:
            features = self._extract_transaction_features(historical_data)
            labels = pd.DataFrame(historical_data)['will_complete'].values
            
            # Scale features
            features_scaled = self.scaler.fit_transform(features)
            
            # Train model
            self.transaction_model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.transaction_model.fit(features_scaled, labels)
            
            # Calculate accuracy
            accuracy = self.transaction_model.score(features_scaled, labels)
            
            self.is_trained = True
            
            return {
                "status": "success",
                "model": "transaction_predictor",
                "accuracy": accuracy,
                "samples_trained": len(historical_data)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def predict_transaction_success(self, transaction_data: Dict) -> Dict:
        """
        Predict if transaction will succeed
        
        Args:
            transaction_data: Transaction details
        """
        if not self.is_trained or not self.transaction_model:
            return {
                "status": "failed",
                "error": "Model not trained"
            }
        
        try:
            # Extract features
            features = self._extract_transaction_features([transaction_data])
            features_scaled = self.scaler.transform(features)
            
            # Predict
            probability = self.transaction_model.predict_proba(features_scaled)[0][1]
            prediction = self.transaction_model.predict(features_scaled)[0]
            
            # Risk level
            if probability >= 0.8:
                risk_level = "low"
            elif probability >= 0.5:
                risk_level = "medium"
            else:
                risk_level = "high"
            
            return {
                "status": "success",
                "will_succeed": bool(prediction),
                "success_probability": float(probability),
                "risk_level": risk_level,
                "confidence": float(max(probability, 1 - probability))
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def predict_churn(self, user_data: Dict) -> Dict:
        """
        Predict if user will churn
        
        Args:
            user_data: User activity data
        """
        try:
            features = []
            
            # User engagement features
            features.append(user_data.get('days_since_last_transaction', 0))
            features.append(user_data.get('transaction_count_30d', 0))
            features.append(user_data.get('transaction_count_90d', 0))
            features.append(user_data.get('avg_transaction_amount', 0))
            features.append(user_data.get('total_volume_30d', 0))
            features.append(user_data.get('unique_recipients', 0))
            features.append(user_data.get('failed_transactions_ratio', 0))
            features.append(user_data.get('support_tickets_count', 0))
            features.append(user_data.get('days_since_registration', 0))
            features.append(user_data.get('kyc_level', 0))
            
            # Simple rule-based prediction (can be replaced with ML model)
            days_inactive = features[0]
            tx_count_30d = features[1]
            failed_ratio = features[6]
            
            # Churn score calculation
            churn_score = 0.0
            
            if days_inactive > 30:
                churn_score += 0.3
            if days_inactive > 60:
                churn_score += 0.2
            
            if tx_count_30d == 0:
                churn_score += 0.3
            elif tx_count_30d < 2:
                churn_score += 0.1
            
            if failed_ratio > 0.3:
                churn_score += 0.2
            
            # Risk level
            if churn_score >= 0.7:
                risk_level = "high"
                will_churn = True
            elif churn_score >= 0.4:
                risk_level = "medium"
                will_churn = False
            else:
                risk_level = "low"
                will_churn = False
            
            # Retention recommendations
            recommendations = []
            if days_inactive > 30:
                recommendations.append("Send re-engagement email with special offer")
            if tx_count_30d < 2:
                recommendations.append("Offer cashback on next transaction")
            if failed_ratio > 0.3:
                recommendations.append("Provide customer support outreach")
            
            return {
                "status": "success",
                "will_churn": will_churn,
                "churn_probability": churn_score,
                "risk_level": risk_level,
                "recommendations": recommendations,
                "factors": {
                    "days_inactive": days_inactive,
                    "recent_transactions": tx_count_30d,
                    "failed_ratio": failed_ratio
                }
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def forecast_revenue(self, historical_revenue: List[Dict], periods: int = 30) -> Dict:
        """
        Forecast revenue for next N periods
        
        Args:
            historical_revenue: Historical revenue data
            periods: Number of periods to forecast
        """
        try:
            df = pd.DataFrame(historical_revenue)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Extract features
            df['day_of_year'] = df['date'].dt.dayofyear
            df['day_of_week'] = df['date'].dt.dayofweek
            df['month'] = df['date'].dt.month
            df['is_weekend'] = (df['date'].dt.dayofweek >= 5).astype(int)
            
            # Rolling features
            df['revenue_7d_avg'] = df['revenue'].rolling(window=7, min_periods=1).mean()
            df['revenue_30d_avg'] = df['revenue'].rolling(window=30, min_periods=1).mean()
            df['revenue_7d_std'] = df['revenue'].rolling(window=7, min_periods=1).std()
            
            # Prepare training data
            feature_cols = ['day_of_year', 'day_of_week', 'month', 'is_weekend', 
                          'revenue_7d_avg', 'revenue_30d_avg', 'revenue_7d_std']
            X = df[feature_cols].fillna(0)
            y = df['revenue']
            
            # Train model
            model = GradientBoostingRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)
            
            # Generate future dates
            last_date = df['date'].max()
            future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=periods)
            
            # Prepare future features
            future_df = pd.DataFrame({'date': future_dates})
            future_df['day_of_year'] = future_df['date'].dt.dayofyear
            future_df['day_of_week'] = future_df['date'].dt.dayofweek
            future_df['month'] = future_df['date'].dt.month
            future_df['is_weekend'] = (future_df['date'].dt.dayofweek >= 5).astype(int)
            
            # Use last known values for rolling features
            future_df['revenue_7d_avg'] = df['revenue_7d_avg'].iloc[-1]
            future_df['revenue_30d_avg'] = df['revenue_30d_avg'].iloc[-1]
            future_df['revenue_7d_std'] = df['revenue_7d_std'].iloc[-1]
            
            # Predict
            future_X = future_df[feature_cols]
            predictions = model.predict(future_X)
            
            # Calculate confidence intervals (simple approach)
            std_error = np.std(y - model.predict(X))
            lower_bound = predictions - 1.96 * std_error
            upper_bound = predictions + 1.96 * std_error
            
            # Format results
            forecast = []
            for i, date in enumerate(future_dates):
                forecast.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_revenue": float(predictions[i]),
                    "lower_bound": float(max(0, lower_bound[i])),
                    "upper_bound": float(upper_bound[i])
                })
            
            # Calculate summary statistics
            total_forecast = float(np.sum(predictions))
            avg_daily = float(np.mean(predictions))
            
            return {
                "status": "success",
                "forecast": forecast,
                "summary": {
                    "total_forecast": total_forecast,
                    "avg_daily_revenue": avg_daily,
                    "periods": periods,
                    "model_accuracy": float(model.score(X, y))
                }
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def detect_anomalies(self, metrics: List[Dict]) -> Dict:
        """
        Detect anomalies in business metrics
        
        Args:
            metrics: Time series metrics data
        """
        try:
            df = pd.DataFrame(metrics)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Calculate rolling statistics
            window = min(30, len(df) // 2)
            df['rolling_mean'] = df['value'].rolling(window=window, min_periods=1).mean()
            df['rolling_std'] = df['value'].rolling(window=window, min_periods=1).std()
            
            # Detect anomalies (values beyond 3 standard deviations)
            df['z_score'] = (df['value'] - df['rolling_mean']) / (df['rolling_std'] + 1e-6)
            df['is_anomaly'] = (np.abs(df['z_score']) > 3).astype(int)
            
            # Find anomalies
            anomalies = df[df['is_anomaly'] == 1].to_dict('records')
            
            anomaly_list = []
            for anomaly in anomalies:
                anomaly_list.append({
                    "timestamp": anomaly['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
                    "value": float(anomaly['value']),
                    "expected_value": float(anomaly['rolling_mean']),
                    "deviation": float(anomaly['z_score']),
                    "severity": "high" if abs(anomaly['z_score']) > 4 else "medium"
                })
            
            return {
                "status": "success",
                "anomalies_detected": len(anomaly_list),
                "anomalies": anomaly_list,
                "total_data_points": len(df)
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def save_models(self, path: str) -> Dict:
        """Save trained models to disk"""
        try:
            if self.transaction_model:
                joblib.dump(self.transaction_model, f"{path}/transaction_model.pkl")
            if self.churn_model:
                joblib.dump(self.churn_model, f"{path}/churn_model.pkl")
            if self.revenue_model:
                joblib.dump(self.revenue_model, f"{path}/revenue_model.pkl")
            joblib.dump(self.scaler, f"{path}/scaler.pkl")
            
            return {
                "status": "success",
                "message": "Models saved successfully"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def load_models(self, path: str) -> Dict:
        """Load trained models from disk"""
        try:
            self.transaction_model = joblib.load(f"{path}/transaction_model.pkl")
            self.scaler = joblib.load(f"{path}/scaler.pkl")
            self.is_trained = True
            
            return {
                "status": "success",
                "message": "Models loaded successfully"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
