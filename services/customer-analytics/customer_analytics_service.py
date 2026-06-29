"""
Customer Analytics Service for Remittance Platform
Provides comprehensive customer behavior analysis, segmentation, and insights
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn
from contextlib import asynccontextmanager

import os
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Models
class CustomerSegment(BaseModel):
    segment_id: str
    segment_name: str
    description: str
    criteria: Dict[str, Any]
    customer_count: int
    avg_transaction_value: float
    avg_monthly_transactions: int
    risk_level: str
    profitability_score: float

class CustomerBehaviorAnalysis(BaseModel):
    customer_id: str
    segment: str
    transaction_frequency: str  # high, medium, low
    avg_transaction_amount: float
    preferred_channels: List[str]
    peak_activity_hours: List[int]
    risk_indicators: List[str]
    lifetime_value: float
    churn_probability: float
    next_best_action: str

class CustomerInsights(BaseModel):
    customer_id: str
    insights: List[str]
    recommendations: List[str]
    risk_score: float
    opportunity_score: float
    engagement_level: str
    last_updated: datetime

class AnalyticsRequest(BaseModel):
    customer_ids: Optional[List[str]] = None
    date_range: Optional[Dict[str, str]] = None
    segment_filter: Optional[str] = None
    analysis_type: str = Field(..., description="behavior, segmentation, insights, churn_prediction")

@dataclass
class CustomerMetrics:
    customer_id: str
    total_transactions: int
    total_amount: float
    avg_transaction_amount: float
    transaction_frequency: float
    days_since_last_transaction: int
    unique_agents: int
    unique_channels: int
    failed_transactions: int
    success_rate: float
    peak_hour: int
    weekend_activity: float
    mobile_usage: float
    web_usage: float
    agent_usage: float

class CustomerAnalyticsService:
    """Comprehensive customer analytics and segmentation service"""
    
    def __init__(self):
        self.db_pool = None
        self.redis_client = None
        self.scaler = StandardScaler()
        self.kmeans_model = None
        self.churn_model = None
        self.segments = {}
        
    async def initialize(self):
        """Initialize database connections and ML models"""
        try:
            # Initialize PostgreSQL connection
            self.db_pool = await asyncpg.create_pool(
                host="postgres",
                port=5432,
                user="remittance_user",
                password=os.getenv('DB_PASSWORD', ''),
                database="remittance_db",
                min_size=5,
                max_size=20
            )
            
            # Initialize Redis connection
            self.redis_client = redis.Redis(
                host="redis",
                port=6379,
                decode_responses=True
            )
            
            # Initialize ML models
            await self._initialize_ml_models()
            
            # Load customer segments
            await self._load_customer_segments()
            
            logger.info("Customer Analytics Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Customer Analytics Service: {str(e)}")
            raise
    
    async def _initialize_ml_models(self):
        """Initialize and train ML models"""
        try:
            # Load historical data for model training
            historical_data = await self._load_historical_data()
            
            if len(historical_data) > 100:  # Minimum data for training
                # Prepare features for clustering
                features = self._prepare_features(historical_data)
                
                # Train customer segmentation model
                self.kmeans_model = KMeans(n_clusters=5, random_state=42)
                self.scaler.fit(features)
                scaled_features = self.scaler.transform(features)
                self.kmeans_model.fit(scaled_features)
                
                # Train churn prediction model
                churn_data = await self._prepare_churn_data(historical_data)
                if len(churn_data) > 50:
                    X = churn_data.drop(['customer_id', 'churned'], axis=1)
                    y = churn_data['churned']
                    
                    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
                    
                    self.churn_model = RandomForestClassifier(n_estimators=100, random_state=42)
                    self.churn_model.fit(X_train, y_train)
                    
                    # Evaluate model
                    y_pred = self.churn_model.predict(X_test)
                    logger.info(f"Churn model performance:\n{classification_report(y_test, y_pred)}")
                
                logger.info("ML models initialized and trained successfully")
            else:
                logger.warning("Insufficient data for ML model training, using default models")
                
        except Exception as e:
            logger.error(f"Failed to initialize ML models: {str(e)}")
    
    async def _load_historical_data(self) -> List[Dict]:
        """Load historical customer and transaction data"""
        query = """
        SELECT 
            c.customer_id,
            c.created_at as customer_since,
            COUNT(t.transaction_id) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            COALESCE(AVG(t.amount), 0) as avg_amount,
            COUNT(DISTINCT t.agent_id) as unique_agents,
            COUNT(DISTINCT DATE(t.created_at)) as active_days,
            COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_transactions,
            MAX(t.created_at) as last_transaction,
            COUNT(CASE WHEN EXTRACT(dow FROM t.created_at) IN (0, 6) THEN 1 END) as weekend_transactions,
            COUNT(CASE WHEN EXTRACT(hour FROM t.created_at) BETWEEN 9 AND 17 THEN 1 END) as business_hours_transactions
        FROM customers c
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE c.created_at >= NOW() - INTERVAL '1 year'
        GROUP BY c.customer_id, c.created_at
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [dict(row) for row in rows]
    
    def _prepare_features(self, data: List[Dict]) -> np.ndarray:
        """Prepare features for ML models"""
        features = []
        
        for customer in data:
            # Calculate derived metrics
            days_since_signup = (datetime.now() - customer['customer_since']).days
            days_since_last_transaction = (datetime.now() - customer['last_transaction']).days if customer['last_transaction'] else 365
            
            transaction_frequency = customer['total_transactions'] / max(days_since_signup, 1) * 30  # per month
            success_rate = (customer['total_transactions'] - customer['failed_transactions']) / max(customer['total_transactions'], 1)
            weekend_ratio = customer['weekend_transactions'] / max(customer['total_transactions'], 1)
            business_hours_ratio = customer['business_hours_transactions'] / max(customer['total_transactions'], 1)
            
            feature_vector = [
                customer['total_transactions'],
                customer['total_amount'],
                customer['avg_amount'],
                transaction_frequency,
                days_since_last_transaction,
                customer['unique_agents'],
                success_rate,
                weekend_ratio,
                business_hours_ratio,
                days_since_signup
            ]
            
            features.append(feature_vector)
        
        return np.array(features)
    
    async def _prepare_churn_data(self, data: List[Dict]) -> pd.DataFrame:
        """Prepare data for churn prediction"""
        churn_data = []
        
        for customer in data:
            days_since_last = (datetime.now() - customer['last_transaction']).days if customer['last_transaction'] else 365
            churned = 1 if days_since_last > 90 else 0  # Consider churned if no activity for 90 days
            
            churn_data.append({
                'customer_id': customer['customer_id'],
                'total_transactions': customer['total_transactions'],
                'total_amount': customer['total_amount'],
                'avg_amount': customer['avg_amount'],
                'unique_agents': customer['unique_agents'],
                'failed_transactions': customer['failed_transactions'],
                'weekend_transactions': customer['weekend_transactions'],
                'business_hours_transactions': customer['business_hours_transactions'],
                'days_since_last_transaction': days_since_last,
                'churned': churned
            })
        
        return pd.DataFrame(churn_data)
    
    async def _load_customer_segments(self):
        """Load predefined customer segments"""
        self.segments = {
            "high_value": {
                "name": "High Value Customers",
                "description": "Customers with high transaction volumes and amounts",
                "criteria": {"min_monthly_amount": 10000, "min_transactions": 20},
                "risk_level": "low"
            },
            "frequent_users": {
                "name": "Frequent Users",
                "description": "Customers with high transaction frequency",
                "criteria": {"min_transactions": 15, "max_days_inactive": 7},
                "risk_level": "low"
            },
            "occasional_users": {
                "name": "Occasional Users",
                "description": "Customers with moderate activity",
                "criteria": {"min_transactions": 5, "max_days_inactive": 30},
                "risk_level": "medium"
            },
            "at_risk": {
                "name": "At Risk Customers",
                "description": "Customers showing signs of churn",
                "criteria": {"max_transactions": 3, "min_days_inactive": 30},
                "risk_level": "high"
            },
            "new_customers": {
                "name": "New Customers",
                "description": "Recently onboarded customers",
                "criteria": {"max_days_since_signup": 30},
                "risk_level": "medium"
            }
        }
    
    async def analyze_customer_behavior(self, customer_id: str) -> CustomerBehaviorAnalysis:
        """Analyze individual customer behavior"""
        try:
            # Get customer metrics
            metrics = await self._get_customer_metrics(customer_id)
            
            # Determine segment
            segment = await self._classify_customer_segment(metrics)
            
            # Analyze transaction patterns
            patterns = await self._analyze_transaction_patterns(customer_id)
            
            # Calculate lifetime value
            ltv = await self._calculate_lifetime_value(customer_id)
            
            # Predict churn probability
            churn_prob = await self._predict_churn_probability(metrics)
            
            # Generate next best action
            next_action = await self._generate_next_best_action(metrics, segment, churn_prob)
            
            return CustomerBehaviorAnalysis(
                customer_id=customer_id,
                segment=segment,
                transaction_frequency=self._categorize_frequency(metrics.transaction_frequency),
                avg_transaction_amount=metrics.avg_transaction_amount,
                preferred_channels=patterns['preferred_channels'],
                peak_activity_hours=patterns['peak_hours'],
                risk_indicators=patterns['risk_indicators'],
                lifetime_value=ltv,
                churn_probability=churn_prob,
                next_best_action=next_action
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze customer behavior for {customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to analyze customer behavior")
    
    async def _get_customer_metrics(self, customer_id: str) -> CustomerMetrics:
        """Get comprehensive customer metrics"""
        query = """
        SELECT 
            c.customer_id,
            COUNT(t.transaction_id) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            COALESCE(AVG(t.amount), 0) as avg_transaction_amount,
            COUNT(DISTINCT t.agent_id) as unique_agents,
            COUNT(DISTINCT t.channel) as unique_channels,
            COUNT(CASE WHEN t.status = 'failed' THEN 1 END) as failed_transactions,
            EXTRACT(EPOCH FROM (NOW() - MAX(t.created_at)))/86400 as days_since_last_transaction,
            MODE() WITHIN GROUP (ORDER BY EXTRACT(hour FROM t.created_at)) as peak_hour,
            COUNT(CASE WHEN EXTRACT(dow FROM t.created_at) IN (0, 6) THEN 1 END)::float / 
                NULLIF(COUNT(t.transaction_id), 0) as weekend_activity,
            COUNT(CASE WHEN t.channel = 'mobile' THEN 1 END)::float / 
                NULLIF(COUNT(t.transaction_id), 0) as mobile_usage,
            COUNT(CASE WHEN t.channel = 'web' THEN 1 END)::float / 
                NULLIF(COUNT(t.transaction_id), 0) as web_usage,
            COUNT(CASE WHEN t.channel = 'agent' THEN 1 END)::float / 
                NULLIF(COUNT(t.transaction_id), 0) as agent_usage
        FROM customers c
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        WHERE c.customer_id = $1
        GROUP BY c.customer_id
        """
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, customer_id)
            
            if not row:
                raise HTTPException(status_code=404, detail="Customer not found")
            
            total_transactions = row['total_transactions'] or 0
            success_rate = ((total_transactions - (row['failed_transactions'] or 0)) / max(total_transactions, 1)) * 100
            
            # Calculate transaction frequency (transactions per month)
            days_active = max((datetime.now() - datetime.now().replace(month=1, day=1)).days, 1)
            transaction_frequency = (total_transactions / days_active) * 30
            
            return CustomerMetrics(
                customer_id=customer_id,
                total_transactions=total_transactions,
                total_amount=float(row['total_amount'] or 0),
                avg_transaction_amount=float(row['avg_transaction_amount'] or 0),
                transaction_frequency=transaction_frequency,
                days_since_last_transaction=int(row['days_since_last_transaction'] or 365),
                unique_agents=row['unique_agents'] or 0,
                unique_channels=row['unique_channels'] or 0,
                failed_transactions=row['failed_transactions'] or 0,
                success_rate=success_rate,
                peak_hour=int(row['peak_hour'] or 12),
                weekend_activity=float(row['weekend_activity'] or 0),
                mobile_usage=float(row['mobile_usage'] or 0),
                web_usage=float(row['web_usage'] or 0),
                agent_usage=float(row['agent_usage'] or 0)
            )
    
    async def _classify_customer_segment(self, metrics: CustomerMetrics) -> str:
        """Classify customer into segment"""
        # High value customers
        if metrics.avg_transaction_amount > 1000 and metrics.transaction_frequency > 10:
            return "high_value"
        
        # Frequent users
        elif metrics.transaction_frequency > 8 and metrics.days_since_last_transaction < 7:
            return "frequent_users"
        
        # At risk customers
        elif metrics.days_since_last_transaction > 30 or metrics.success_rate < 80:
            return "at_risk"
        
        # Occasional users
        elif metrics.transaction_frequency > 2:
            return "occasional_users"
        
        # New customers (default)
        else:
            return "new_customers"
    
    async def _analyze_transaction_patterns(self, customer_id: str) -> Dict[str, Any]:
        """Analyze customer transaction patterns"""
        query = """
        SELECT 
            channel,
            EXTRACT(hour FROM created_at) as hour,
            status,
            amount,
            agent_id
        FROM transactions 
        WHERE customer_id = $1 
        AND created_at >= NOW() - INTERVAL '6 months'
        ORDER BY created_at DESC
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)
        
        if not rows:
            return {
                'preferred_channels': [],
                'peak_hours': [],
                'risk_indicators': []
            }
        
        # Analyze channels
        channel_counts = {}
        hour_counts = {}
        risk_indicators = []
        
        for row in rows:
            # Channel analysis
            channel = row['channel']
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
            
            # Hour analysis
            hour = int(row['hour'])
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            # Risk indicators
            if row['status'] == 'failed':
                risk_indicators.append("High failure rate")
            if row['amount'] > 10000:
                risk_indicators.append("Large transaction amounts")
        
        # Get top channels and hours
        preferred_channels = sorted(channel_counts.keys(), key=lambda x: channel_counts[x], reverse=True)[:3]
        peak_hours = sorted(hour_counts.keys(), key=lambda x: hour_counts[x], reverse=True)[:3]
        
        # Remove duplicates from risk indicators
        risk_indicators = list(set(risk_indicators))
        
        return {
            'preferred_channels': preferred_channels,
            'peak_hours': peak_hours,
            'risk_indicators': risk_indicators
        }
    
    async def _calculate_lifetime_value(self, customer_id: str) -> float:
        """Calculate customer lifetime value"""
        query = """
        SELECT 
            SUM(amount) as total_spent,
            COUNT(*) as total_transactions,
            MIN(created_at) as first_transaction,
            MAX(created_at) as last_transaction
        FROM transactions 
        WHERE customer_id = $1 AND status = 'completed'
        """
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(query, customer_id)
        
        if not row or not row['total_spent']:
            return 0.0
        
        total_spent = float(row['total_spent'])
        total_transactions = row['total_transactions']
        
        # Calculate customer lifespan in months
        if row['first_transaction'] and row['last_transaction']:
            lifespan_days = (row['last_transaction'] - row['first_transaction']).days
            lifespan_months = max(lifespan_days / 30, 1)
        else:
            lifespan_months = 1
        
        # Simple LTV calculation: average monthly value * estimated future months
        monthly_value = total_spent / lifespan_months
        estimated_future_months = 24  # Assume 2 years future value
        
        ltv = monthly_value * estimated_future_months
        
        return round(ltv, 2)
    
    async def _predict_churn_probability(self, metrics: CustomerMetrics) -> float:
        """Predict customer churn probability"""
        if not self.churn_model:
            # Simple rule-based churn prediction
            if metrics.days_since_last_transaction > 90:
                return 0.9
            elif metrics.days_since_last_transaction > 60:
                return 0.7
            elif metrics.days_since_last_transaction > 30:
                return 0.4
            elif metrics.success_rate < 70:
                return 0.6
            else:
                return 0.1
        
        try:
            # Use trained model for prediction
            features = np.array([[
                metrics.total_transactions,
                metrics.total_amount,
                metrics.avg_transaction_amount,
                metrics.unique_agents,
                metrics.failed_transactions,
                metrics.weekend_activity,
                metrics.mobile_usage,
                metrics.days_since_last_transaction
            ]])
            
            churn_probability = self.churn_model.predict_proba(features)[0][1]
            return round(churn_probability, 3)
            
        except Exception as e:
            logger.error(f"Failed to predict churn probability: {str(e)}")
            return 0.5  # Default moderate risk
    
    async def _generate_next_best_action(self, metrics: CustomerMetrics, segment: str, churn_prob: float) -> str:
        """Generate next best action recommendation"""
        if churn_prob > 0.7:
            return "Immediate retention campaign - offer incentives"
        elif churn_prob > 0.4:
            return "Engagement campaign - send personalized offers"
        elif segment == "high_value":
            return "VIP treatment - assign dedicated agent"
        elif segment == "frequent_users":
            return "Loyalty program enrollment"
        elif segment == "new_customers":
            return "Onboarding completion - tutorial and support"
        elif metrics.success_rate < 80:
            return "Technical support - resolve transaction issues"
        else:
            return "Cross-sell opportunities - additional services"
    
    def _categorize_frequency(self, frequency: float) -> str:
        """Categorize transaction frequency"""
        if frequency > 15:
            return "high"
        elif frequency > 5:
            return "medium"
        else:
            return "low"
    
    async def generate_customer_segments(self) -> List[CustomerSegment]:
        """Generate customer segments with analytics"""
        try:
            segments = []
            
            for segment_id, segment_info in self.segments.items():
                # Get customers in this segment
                customers = await self._get_customers_in_segment(segment_id)
                
                if customers:
                    # Calculate segment metrics
                    total_amount = sum(c['total_amount'] for c in customers)
                    total_transactions = sum(c['total_transactions'] for c in customers)
                    
                    avg_transaction_value = total_amount / max(total_transactions, 1)
                    avg_monthly_transactions = sum(c['transaction_frequency'] for c in customers) / len(customers)
                    
                    # Calculate profitability score (simplified)
                    profitability_score = (avg_transaction_value * avg_monthly_transactions) / 1000
                    
                    segment = CustomerSegment(
                        segment_id=segment_id,
                        segment_name=segment_info['name'],
                        description=segment_info['description'],
                        criteria=segment_info['criteria'],
                        customer_count=len(customers),
                        avg_transaction_value=round(avg_transaction_value, 2),
                        avg_monthly_transactions=round(avg_monthly_transactions, 1),
                        risk_level=segment_info['risk_level'],
                        profitability_score=round(profitability_score, 2)
                    )
                    
                    segments.append(segment)
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to generate customer segments: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate customer segments")
    
    async def _get_customers_in_segment(self, segment_id: str) -> List[Dict]:
        """Get customers belonging to a specific segment"""
        # This would typically involve complex queries based on segment criteria
        # For now, we'll use a simplified approach
        
        query = """
        SELECT 
            c.customer_id,
            COUNT(t.transaction_id) as total_transactions,
            COALESCE(SUM(t.amount), 0) as total_amount,
            EXTRACT(EPOCH FROM (NOW() - MAX(t.created_at)))/86400 as days_since_last_transaction,
            EXTRACT(EPOCH FROM (NOW() - c.created_at))/86400 as days_since_signup
        FROM customers c
        LEFT JOIN transactions t ON c.customer_id = t.customer_id
        GROUP BY c.customer_id, c.created_at
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query)
        
        customers = []
        for row in rows:
            # Calculate transaction frequency
            days_active = max(row['days_since_signup'] or 1, 1)
            transaction_frequency = (row['total_transactions'] / days_active) * 30
            
            customer_data = {
                'customer_id': row['customer_id'],
                'total_transactions': row['total_transactions'],
                'total_amount': float(row['total_amount']),
                'transaction_frequency': transaction_frequency,
                'days_since_last_transaction': row['days_since_last_transaction'] or 365,
                'days_since_signup': row['days_since_signup'] or 0
            }
            
            # Check if customer belongs to this segment
            if self._customer_matches_segment(customer_data, segment_id):
                customers.append(customer_data)
        
        return customers
    
    def _customer_matches_segment(self, customer: Dict, segment_id: str) -> bool:
        """Check if customer matches segment criteria"""
        criteria = self.segments[segment_id]['criteria']
        
        if segment_id == "high_value":
            monthly_amount = customer['total_amount'] / max(customer['days_since_signup'] / 30, 1)
            return (monthly_amount >= criteria.get('min_monthly_amount', 0) and 
                   customer['transaction_frequency'] >= criteria.get('min_transactions', 0))
        
        elif segment_id == "frequent_users":
            return (customer['transaction_frequency'] >= criteria.get('min_transactions', 0) and
                   customer['days_since_last_transaction'] <= criteria.get('max_days_inactive', 999))
        
        elif segment_id == "occasional_users":
            return (customer['transaction_frequency'] >= criteria.get('min_transactions', 0) and
                   customer['days_since_last_transaction'] <= criteria.get('max_days_inactive', 999))
        
        elif segment_id == "at_risk":
            return (customer['transaction_frequency'] <= criteria.get('max_transactions', 999) or
                   customer['days_since_last_transaction'] >= criteria.get('min_days_inactive', 0))
        
        elif segment_id == "new_customers":
            return customer['days_since_signup'] <= criteria.get('max_days_since_signup', 999)
        
        return False
    
    async def generate_customer_insights(self, customer_id: str) -> CustomerInsights:
        """Generate comprehensive customer insights"""
        try:
            # Get customer behavior analysis
            behavior = await self.analyze_customer_behavior(customer_id)
            
            # Generate insights
            insights = []
            recommendations = []
            
            # Transaction frequency insights
            if behavior.transaction_frequency == "high":
                insights.append("Customer shows high engagement with frequent transactions")
                recommendations.append("Consider offering premium services or loyalty rewards")
            elif behavior.transaction_frequency == "low":
                insights.append("Customer has low transaction frequency")
                recommendations.append("Implement engagement campaigns to increase activity")
            
            # Channel preference insights
            if "mobile" in behavior.preferred_channels:
                insights.append("Customer prefers mobile channel")
                recommendations.append("Optimize mobile experience and send mobile notifications")
            
            # Risk insights
            if behavior.churn_probability > 0.5:
                insights.append("Customer shows signs of potential churn")
                recommendations.append("Implement retention strategies immediately")
            
            if "High failure rate" in behavior.risk_indicators:
                insights.append("Customer experiencing transaction failures")
                recommendations.append("Provide technical support and investigate issues")
            
            # Value insights
            if behavior.lifetime_value > 10000:
                insights.append("High-value customer with significant lifetime value")
                recommendations.append("Assign dedicated relationship manager")
            
            # Calculate overall scores
            risk_score = behavior.churn_probability * 100
            opportunity_score = min(behavior.lifetime_value / 100, 100)
            
            # Determine engagement level
            if behavior.transaction_frequency == "high" and behavior.churn_probability < 0.3:
                engagement_level = "high"
            elif behavior.transaction_frequency == "medium" and behavior.churn_probability < 0.5:
                engagement_level = "medium"
            else:
                engagement_level = "low"
            
            return CustomerInsights(
                customer_id=customer_id,
                insights=insights,
                recommendations=recommendations,
                risk_score=round(risk_score, 1),
                opportunity_score=round(opportunity_score, 1),
                engagement_level=engagement_level,
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Failed to generate customer insights for {customer_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to generate customer insights")

# FastAPI Application
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await analytics_service.initialize()
    yield
    # Shutdown
    if analytics_service.db_pool:
        await analytics_service.db_pool.close()
    if analytics_service.redis_client:
        await analytics_service.redis_client.close()

app = FastAPI(
    title="Customer Analytics Service",
    description="Comprehensive customer behavior analysis and segmentation for Remittance Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Global service instance
analytics_service = CustomerAnalyticsService()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "customer-analytics",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/v1/customers/{customer_id}/behavior", response_model=CustomerBehaviorAnalysis)
async def get_customer_behavior(customer_id: str):
    """Get comprehensive customer behavior analysis"""
    return await analytics_service.analyze_customer_behavior(customer_id)

@app.get("/v1/customers/{customer_id}/insights", response_model=CustomerInsights)
async def get_customer_insights(customer_id: str):
    """Get customer insights and recommendations"""
    return await analytics_service.generate_customer_insights(customer_id)

@app.get("/v1/segments", response_model=List[CustomerSegment])
async def get_customer_segments():
    """Get all customer segments with analytics"""
    return await analytics_service.generate_customer_segments()

@app.post("/v1/analytics/batch")
async def batch_analytics(request: AnalyticsRequest):
    """Perform batch analytics on multiple customers"""
    try:
        results = []
        
        if request.customer_ids:
            for customer_id in request.customer_ids:
                if request.analysis_type == "behavior":
                    result = await analytics_service.analyze_customer_behavior(customer_id)
                elif request.analysis_type == "insights":
                    result = await analytics_service.generate_customer_insights(customer_id)
                else:
                    continue
                
                results.append({"customer_id": customer_id, "analysis": result})
        
        return {"results": results, "total_processed": len(results)}
        
    except Exception as e:
        logger.error(f"Batch analytics failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Batch analytics failed")

@app.get("/v1/analytics/dashboard")
async def get_analytics_dashboard():
    """Get analytics dashboard data"""
    try:
        # Get segments
        segments = await analytics_service.generate_customer_segments()
        
        # Calculate overall metrics
        total_customers = sum(s.customer_count for s in segments)
        total_value = sum(s.avg_transaction_value * s.customer_count for s in segments)
        
        return {
            "total_customers": total_customers,
            "total_value": round(total_value, 2),
            "segments": segments,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8020)
