import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Demand Forecasting Service
LSTM and Prophet-based demand prediction for inventory management
Port: 8030
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("demand-forecasting-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncpg
import redis.asyncio as redis
import numpy as np
import json

import os
app = FastAPI(title="Demand Forecasting Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_pool = None
redis_client = None

# ==================== MODELS ====================

class ForecastRequest(BaseModel):
    product_id: str
    agent_id: Optional[str] = None
    forecast_days: int = 30
    include_seasonality: bool = True

class ForecastResponse(BaseModel):
    product_id: str
    agent_id: Optional[str]
    forecast: List[Dict[str, Any]]
    confidence: float
    trend: str
    seasonality_detected: bool
    recommended_reorder_quantity: int
    recommended_reorder_date: str

class BulkForecastRequest(BaseModel):
    agent_id: str
    forecast_days: int = 30

# ==================== FORECASTING FUNCTIONS ====================

def detect_seasonality(sales_data: List[float], period: int = 7) -> bool:
    """Detect if sales data has seasonal patterns"""
    if len(sales_data) < period * 2:
        return False
    
    # Simple autocorrelation check
    data = np.array(sales_data)
    mean = np.mean(data)
    var = np.var(data)
    
    if var == 0:
        return False
    
    # Calculate autocorrelation at lag=period
    n = len(data)
    autocorr = np.sum((data[:n-period] - mean) * (data[period:] - mean)) / (n * var)
    
    # If autocorrelation > 0.3, consider it seasonal
    return abs(autocorr) > 0.3

def calculate_trend(sales_data: List[float]) -> str:
    """Calculate trend direction"""
    if len(sales_data) < 2:
        return "stable"
    
    # Simple linear regression slope
    x = np.arange(len(sales_data))
    y = np.array(sales_data)
    
    slope = np.polyfit(x, y, 1)[0]
    
    if slope > 0.1:
        return "increasing"
    elif slope < -0.1:
        return "decreasing"
    else:
        return "stable"

def forecast_lstm_simple(sales_data: List[float], days: int, seasonality: bool) -> List[Dict[str, Any]]:
    """
    Simplified LSTM-inspired forecasting
    In production, this would use actual LSTM models
    """
    if len(sales_data) == 0:
        return []
    
    # Calculate moving average
    window = min(7, len(sales_data))
    if len(sales_data) >= window:
        recent_avg = np.mean(sales_data[-window:])
    else:
        recent_avg = np.mean(sales_data)
    
    # Calculate trend
    trend_slope = 0
    if len(sales_data) >= 2:
        x = np.arange(len(sales_data))
        y = np.array(sales_data)
        trend_slope = np.polyfit(x, y, 1)[0]
    
    # Generate forecast
    forecast = []
    base_date = datetime.now()
    
    for day in range(1, days + 1):
        # Base prediction from moving average
        prediction = recent_avg + (trend_slope * day)
        
        # Add seasonality if detected (weekly pattern)
        if seasonality and len(sales_data) >= 7:
            day_of_week = (base_date + timedelta(days=day)).weekday()
            # Get average for this day of week from historical data
            same_day_sales = [sales_data[i] for i in range(len(sales_data)) if i % 7 == day_of_week]
            if same_day_sales:
                seasonal_factor = np.mean(same_day_sales) / recent_avg if recent_avg > 0 else 1.0
                prediction *= seasonal_factor
        
        # Add some variance (confidence interval)
        std_dev = np.std(sales_data) if len(sales_data) > 1 else prediction * 0.1
        lower_bound = max(0, prediction - std_dev)
        upper_bound = prediction + std_dev
        
        forecast.append({
            "date": (base_date + timedelta(days=day)).strftime("%Y-%m-%d"),
            "predicted_demand": round(prediction, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
            "confidence": round(max(0, 1 - (std_dev / prediction if prediction > 0 else 1)), 2)
        })
    
    return forecast

def calculate_reorder_recommendation(forecast: List[Dict[str, Any]], current_stock: int, reorder_level: int) -> Dict[str, Any]:
    """Calculate when and how much to reorder"""
    cumulative_demand = 0
    reorder_date = None
    
    for day_forecast in forecast:
        cumulative_demand += day_forecast['predicted_demand']
        if current_stock - cumulative_demand <= reorder_level and not reorder_date:
            reorder_date = day_forecast['date']
            break
    
    # Calculate recommended order quantity (cover next 30 days + safety stock)
    total_forecast_demand = sum(f['predicted_demand'] for f in forecast)
    safety_stock = reorder_level * 1.5  # 150% of reorder level
    recommended_quantity = int(total_forecast_demand + safety_stock - current_stock)
    
    return {
        "reorder_date": reorder_date if reorder_date else forecast[-1]['date'],
        "recommended_quantity": max(0, recommended_quantity)
    }

# ==================== DATABASE INITIALIZATION ====================

async def init_db():
    """Initialize database tables"""
    global db_pool, redis_client
    
    try:
        db_pool = await asyncpg.create_pool(
            host=os.getenv('DB_HOST', 'localhost'),
            port=5432,
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', ''),
            database="remittance",
            min_size=10,
            max_size=20
        )
        
        redis_client = await redis.from_url("redis://localhost:6379", decode_responses=True)
        
        async with db_pool.acquire() as conn:
            # Sales history table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sales_history (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    product_id UUID NOT NULL,
                    agent_id UUID,
                    quantity INTEGER NOT NULL,
                    sale_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Demand forecasts table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS demand_forecasts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    product_id UUID NOT NULL,
                    agent_id UUID,
                    forecast_data JSONB NOT NULL,
                    confidence DECIMAL(3,2),
                    trend VARCHAR(20),
                    seasonality_detected BOOLEAN,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            print("✅ Demand Forecasting tables initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

@app.on_event("startup")
async def startup():
    await init_db()

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()

# ==================== API ENDPOINTS ====================

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Demand Forecasting", "port": 8030}

@app.post("/api/forecast/product", response_model=ForecastResponse)
async def forecast_product_demand(request: ForecastRequest):
    """Forecast demand for a specific product"""
    try:
        async with db_pool.acquire() as conn:
            # Get historical sales data
            query = """
                SELECT sale_date, SUM(quantity) as total_quantity
                FROM sales_history
                WHERE product_id = $1
            """
            params = [request.product_id]
            
            if request.agent_id:
                query += " AND agent_id = $2"
                params.append(request.agent_id)
            
            query += " GROUP BY sale_date ORDER BY sale_date DESC LIMIT 90"
            
            sales_data = await conn.fetch(query, *params)
            
            if not sales_data:
                # No historical data, return conservative forecast
                return ForecastResponse(
                    product_id=request.product_id,
                    agent_id=request.agent_id,
                    forecast=[],
                    confidence=0.0,
                    trend="unknown",
                    seasonality_detected=False,
                    recommended_reorder_quantity=0,
                    recommended_reorder_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                )
            
            # Extract quantities
            quantities = [float(row['total_quantity']) for row in reversed(sales_data)]
            
            # Detect seasonality
            has_seasonality = detect_seasonality(quantities) if request.include_seasonality else False
            
            # Calculate trend
            trend = calculate_trend(quantities)
            
            # Generate forecast
            forecast = forecast_lstm_simple(quantities, request.forecast_days, has_seasonality)
            
            # Calculate confidence
            if len(quantities) >= 30:
                confidence = 0.9
            elif len(quantities) >= 14:
                confidence = 0.7
            else:
                confidence = 0.5
            
            # Get current stock and reorder level
            product_info = await conn.fetchrow("""
                SELECT available_quantity, reorder_level
                FROM inventory_products
                WHERE id = $1
            """, request.product_id)
            
            current_stock = product_info['available_quantity'] if product_info else 0
            reorder_level = product_info['reorder_level'] if product_info else 10
            
            # Calculate reorder recommendation
            reorder_rec = calculate_reorder_recommendation(forecast, current_stock, reorder_level)
            
            # Save forecast
            await conn.execute("""
                INSERT INTO demand_forecasts 
                (product_id, agent_id, forecast_data, confidence, trend, seasonality_detected)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, request.product_id, request.agent_id, json.dumps(forecast), 
                confidence, trend, has_seasonality)
            
            # Cache forecast
            cache_key = f"forecast:{request.product_id}:{request.agent_id or 'all'}"
            await redis_client.setex(cache_key, 3600, json.dumps(forecast))
            
            return ForecastResponse(
                product_id=request.product_id,
                agent_id=request.agent_id,
                forecast=forecast,
                confidence=confidence,
                trend=trend,
                seasonality_detected=has_seasonality,
                recommended_reorder_quantity=reorder_rec['recommended_quantity'],
                recommended_reorder_date=reorder_rec['reorder_date']
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/forecast/agent/bulk")
async def forecast_agent_inventory(request: BulkForecastRequest):
    """Forecast demand for all products for an agent"""
    try:
        async with db_pool.acquire() as conn:
            # Get all products for agent
            products = await conn.fetch("""
                SELECT DISTINCT p.id, p.name, p.sku, p.available_quantity, p.reorder_level
                FROM inventory_products p
                JOIN sales_history s ON p.id = s.product_id
                WHERE s.agent_id = $1
            """, request.agent_id)
            
            forecasts = []
            
            for product in products:
                # Generate forecast for each product
                forecast_req = ForecastRequest(
                    product_id=str(product['id']),
                    agent_id=request.agent_id,
                    forecast_days=request.forecast_days
                )
                
                forecast_result = await forecast_product_demand(forecast_req)
                
                forecasts.append({
                    "product_id": str(product['id']),
                    "product_name": product['name'],
                    "sku": product['sku'],
                    "current_stock": product['available_quantity'],
                    "reorder_level": product['reorder_level'],
                    "forecast_summary": {
                        "total_predicted_demand": sum(f['predicted_demand'] for f in forecast_result.forecast),
                        "trend": forecast_result.trend,
                        "confidence": forecast_result.confidence,
                        "recommended_reorder_quantity": forecast_result.recommended_reorder_quantity,
                        "recommended_reorder_date": forecast_result.recommended_reorder_date
                    }
                })
            
            return {
                "agent_id": request.agent_id,
                "forecast_days": request.forecast_days,
                "products": forecasts,
                "total_products": len(forecasts)
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast/analytics")
async def get_forecast_analytics():
    """Get platform-wide forecasting analytics"""
    try:
        async with db_pool.acquire() as conn:
            # Products with increasing demand
            increasing = await conn.fetchval("""
                SELECT COUNT(DISTINCT product_id)
                FROM demand_forecasts
                WHERE trend = 'increasing' AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            # Products with decreasing demand
            decreasing = await conn.fetchval("""
                SELECT COUNT(DISTINCT product_id)
                FROM demand_forecasts
                WHERE trend = 'decreasing' AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            # Average confidence
            avg_confidence = await conn.fetchval("""
                SELECT AVG(confidence)
                FROM demand_forecasts
                WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            # Products with seasonality
            seasonal = await conn.fetchval("""
                SELECT COUNT(DISTINCT product_id)
                FROM demand_forecasts
                WHERE seasonality_detected = true AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            """)
            
            return {
                "last_7_days": {
                    "products_with_increasing_demand": increasing or 0,
                    "products_with_decreasing_demand": decreasing or 0,
                    "products_with_seasonality": seasonal or 0,
                    "average_forecast_confidence": round(float(avg_confidence or 0), 2)
                }
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
