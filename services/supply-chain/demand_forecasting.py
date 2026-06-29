"""
Demand Forecasting Service
AI-powered demand prediction and automatic stock replenishment
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date, timedelta
from enum import Enum
import uuid
import os
import logging
import numpy as np
from pydantic import BaseModel

from inventory_service import get_db

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
# ============================================================================

class ForecastType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class ForecastMethod(str, Enum):
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_REGRESSION = "linear_regression"
    SEASONAL_ARIMA = "seasonal_arima"
    PROPHET = "prophet"
    LSTM = "lstm"

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ForecastRequest(BaseModel):
    product_id: str
    warehouse_id: Optional[str] = None
    forecast_type: ForecastType = ForecastType.DAILY
    forecast_periods: int = 30
    method: ForecastMethod = ForecastMethod.EXPONENTIAL_SMOOTHING

class ReplenishmentRecommendation(BaseModel):
    product_id: str
    warehouse_id: str
    current_stock: int
    reorder_point: int
    recommended_quantity: int
    reason: str

class AutoReplenishmentConfig(BaseModel):
    enabled: bool = True
    check_frequency_hours: int = 24
    auto_create_po: bool = False
    require_approval: bool = True
    safety_stock_days: int = 7

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Demand Forecasting Service",
    description="AI-powered demand prediction and automatic stock replenishment",
    version="1.0.0"
)

# ============================================================================
# DEMAND FORECASTING CLASS
# ============================================================================

class DemandForecaster:
    """Demand forecasting and replenishment"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========================================================================
    # DEMAND FORECASTING
    # ========================================================================
    
    async def generate_forecast(
        self,
        request: ForecastRequest
    ) -> Dict[str, Any]:
        """Generate demand forecast"""
        
        # Get historical sales data
        historical_data = await self._get_historical_sales(
            request.product_id,
            request.warehouse_id,
            request.forecast_type
        )
        
        if len(historical_data) < 7:
            logger.warning(f"Insufficient historical data for product {request.product_id}")
            return {
                "product_id": request.product_id,
                "warehouse_id": request.warehouse_id,
                "forecast_type": request.forecast_type.value,
                "method": request.method.value,
                "error": "Insufficient historical data (minimum 7 periods required)",
                "forecasts": []
            }
        
        # Generate forecast based on method
        if request.method == ForecastMethod.MOVING_AVERAGE:
            forecasts = self._moving_average_forecast(
                historical_data,
                request.forecast_periods
            )
        elif request.method == ForecastMethod.EXPONENTIAL_SMOOTHING:
            forecasts = self._exponential_smoothing_forecast(
                historical_data,
                request.forecast_periods
            )
        elif request.method == ForecastMethod.LINEAR_REGRESSION:
            forecasts = self._linear_regression_forecast(
                historical_data,
                request.forecast_periods
            )
        else:
            # Default to exponential smoothing
            forecasts = self._exponential_smoothing_forecast(
                historical_data,
                request.forecast_periods
            )
        
        # Store forecasts in database
        await self._store_forecasts(
            request.product_id,
            request.warehouse_id,
            request.forecast_type,
            forecasts,
            request.method.value
        )
        
        logger.info(f"Forecast generated: product={request.product_id}, periods={len(forecasts)}")
        
        return {
            "product_id": request.product_id,
            "warehouse_id": request.warehouse_id,
            "forecast_type": request.forecast_type.value,
            "method": request.method.value,
            "historical_periods": len(historical_data),
            "forecast_periods": len(forecasts),
            "forecasts": forecasts,
            "generated_at": datetime.utcnow().isoformat()
        }
    
    async def _get_historical_sales(
        self,
        product_id: str,
        warehouse_id: Optional[str],
        forecast_type: ForecastType
    ) -> List[Dict[str, Any]]:
        """Get historical sales data"""
        
        # Determine date grouping based on forecast type
        if forecast_type == ForecastType.DAILY:
            date_trunc = "day"
            lookback_days = 90
        elif forecast_type == ForecastType.WEEKLY:
            date_trunc = "week"
            lookback_days = 365
        else:  # MONTHLY
            date_trunc = "month"
            lookback_days = 730
        
        query = f"""
            SELECT 
                DATE_TRUNC('{date_trunc}', sm.movement_date) AS period,
                SUM(CASE WHEN sm.movement_type = 'outbound' THEN sm.quantity ELSE 0 END) AS demand
            FROM stock_movements sm
            WHERE sm.product_id = :product_id
            AND sm.movement_date >= NOW() - INTERVAL '{lookback_days} days'
        """
        
        params = {"product_id": uuid.UUID(product_id)}
        
        if warehouse_id:
            query += " AND sm.warehouse_id = :warehouse_id"
            params["warehouse_id"] = uuid.UUID(warehouse_id)
        
        query += f"""
            GROUP BY DATE_TRUNC('{date_trunc}', sm.movement_date)
            ORDER BY period
        """
        
        result = self.db.execute(query, params)
        
        historical_data = []
        for row in result:
            historical_data.append({
                "period": row.period.isoformat(),
                "demand": int(row.demand)
            })
        
        return historical_data
    
    def _moving_average_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_periods: int,
        window: int = 7
    ) -> List[Dict[str, Any]]:
        """Moving average forecast"""
        
        demands = [d['demand'] for d in historical_data]
        
        forecasts = []
        last_date = datetime.fromisoformat(historical_data[-1]['period'])
        
        for i in range(forecast_periods):
            # Calculate moving average of last 'window' periods
            recent_demands = demands[-window:]
            forecast_value = int(np.mean(recent_demands))
            
            # Calculate confidence interval (simplified)
            std_dev = np.std(recent_demands)
            lower_bound = max(0, int(forecast_value - 1.96 * std_dev))
            upper_bound = int(forecast_value + 1.96 * std_dev)
            
            forecast_date = last_date + timedelta(days=i+1)
            
            forecasts.append({
                "period": forecast_date.isoformat(),
                "predicted_demand": forecast_value,
                "confidence_level": 95.0,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            })
            
            # Add forecast to demands for next iteration
            demands.append(forecast_value)
        
        return forecasts
    
    def _exponential_smoothing_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_periods: int,
        alpha: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Exponential smoothing forecast"""
        
        demands = [d['demand'] for d in historical_data]
        
        # Initialize with first value
        smoothed = [demands[0]]
        
        # Calculate smoothed values
        for i in range(1, len(demands)):
            smoothed_value = alpha * demands[i] + (1 - alpha) * smoothed[i-1]
            smoothed.append(smoothed_value)
        
        # Generate forecasts
        forecasts = []
        last_date = datetime.fromisoformat(historical_data[-1]['period'])
        last_smoothed = smoothed[-1]
        
        for i in range(forecast_periods):
            forecast_value = int(last_smoothed)
            
            # Calculate confidence interval
            residuals = [demands[j] - smoothed[j] for j in range(len(demands))]
            std_dev = np.std(residuals)
            lower_bound = max(0, int(forecast_value - 1.96 * std_dev))
            upper_bound = int(forecast_value + 1.96 * std_dev)
            
            forecast_date = last_date + timedelta(days=i+1)
            
            forecasts.append({
                "period": forecast_date.isoformat(),
                "predicted_demand": forecast_value,
                "confidence_level": 95.0,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            })
        
        return forecasts
    
    def _linear_regression_forecast(
        self,
        historical_data: List[Dict[str, Any]],
        forecast_periods: int
    ) -> List[Dict[str, Any]]:
        """Linear regression forecast"""
        
        demands = [d['demand'] for d in historical_data]
        X = np.arange(len(demands)).reshape(-1, 1)
        y = np.array(demands)
        
        # Calculate linear regression coefficients
        X_mean = np.mean(X)
        y_mean = np.mean(y)
        
        numerator = np.sum((X.flatten() - X_mean) * (y - y_mean))
        denominator = np.sum((X.flatten() - X_mean) ** 2)
        
        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * X_mean
        
        # Generate forecasts
        forecasts = []
        last_date = datetime.fromisoformat(historical_data[-1]['period'])
        
        # Calculate residuals for confidence interval
        y_pred = slope * X.flatten() + intercept
        residuals = y - y_pred
        std_dev = np.std(residuals)
        
        for i in range(forecast_periods):
            x_new = len(demands) + i
            forecast_value = int(slope * x_new + intercept)
            forecast_value = max(0, forecast_value)  # Ensure non-negative
            
            # Confidence interval
            lower_bound = max(0, int(forecast_value - 1.96 * std_dev))
            upper_bound = int(forecast_value + 1.96 * std_dev)
            
            forecast_date = last_date + timedelta(days=i+1)
            
            forecasts.append({
                "period": forecast_date.isoformat(),
                "predicted_demand": forecast_value,
                "confidence_level": 95.0,
                "lower_bound": lower_bound,
                "upper_bound": upper_bound
            })
        
        return forecasts
    
    async def _store_forecasts(
        self,
        product_id: str,
        warehouse_id: Optional[str],
        forecast_type: ForecastType,
        forecasts: List[Dict[str, Any]],
        model_version: str
    ):
        """Store forecasts in database"""
        
        for forecast in forecasts:
            self.db.execute(
                """
                INSERT INTO demand_forecasts (
                    id, product_id, warehouse_id, forecast_date, forecast_type,
                    predicted_demand, confidence_level, lower_bound, upper_bound,
                    model_version
                ) VALUES (
                    :id, :product_id, :warehouse_id, :forecast_date, :forecast_type,
                    :predicted_demand, :confidence_level, :lower_bound, :upper_bound,
                    :model_version
                )
                ON CONFLICT (product_id, warehouse_id, forecast_date, forecast_type)
                DO UPDATE SET
                    predicted_demand = EXCLUDED.predicted_demand,
                    confidence_level = EXCLUDED.confidence_level,
                    lower_bound = EXCLUDED.lower_bound,
                    upper_bound = EXCLUDED.upper_bound,
                    model_version = EXCLUDED.model_version,
                    updated_at = NOW()
                """,
                {
                    "id": uuid.uuid4(),
                    "product_id": uuid.UUID(product_id),
                    "warehouse_id": uuid.UUID(warehouse_id) if warehouse_id else None,
                    "forecast_date": datetime.fromisoformat(forecast['period']).date(),
                    "forecast_type": forecast_type.value,
                    "predicted_demand": forecast['predicted_demand'],
                    "confidence_level": forecast['confidence_level'],
                    "lower_bound": forecast['lower_bound'],
                    "upper_bound": forecast['upper_bound'],
                    "model_version": model_version
                }
            )
        
        self.db.commit()
    
    # ========================================================================
    # STOCK REPLENISHMENT
    # ========================================================================
    
    async def get_replenishment_recommendations(
        self,
        warehouse_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get stock replenishment recommendations"""
        
        # Get low stock items
        query = """
            SELECT 
                i.warehouse_id,
                w.name AS warehouse_name,
                i.product_id,
                i.quantity_available,
                i.reorder_point,
                i.reorder_quantity,
                i.min_stock_level
            FROM inventory i
            JOIN warehouses w ON i.warehouse_id = w.id
            WHERE i.quantity_available <= i.reorder_point
            AND w.is_active = TRUE
        """
        
        params = {}
        
        if warehouse_id:
            query += " AND i.warehouse_id = :warehouse_id"
            params["warehouse_id"] = uuid.UUID(warehouse_id)
        
        query += " ORDER BY i.warehouse_id, i.product_id"
        
        result = self.db.execute(query, params)
        
        recommendations = []
        
        for row in result:
            # Get forecast for next 30 days
            forecast = await self._get_forecast_summary(
                str(row.product_id),
                str(row.warehouse_id),
                30
            )
            
            # Calculate recommended quantity
            shortage = row.reorder_point - row.quantity_available
            forecast_demand = forecast.get('total_demand', 0)
            safety_stock = row.min_stock_level
            
            recommended_quantity = max(
                row.reorder_quantity,
                shortage + forecast_demand + safety_stock
            )
            
            # Determine reason
            reasons = []
            if row.quantity_available <= row.min_stock_level:
                reasons.append("Below minimum stock level")
            if row.quantity_available <= row.reorder_point:
                reasons.append("At or below reorder point")
            if forecast_demand > row.quantity_available:
                reasons.append(f"Forecasted demand ({forecast_demand}) exceeds current stock")
            
            recommendations.append({
                "warehouse_id": str(row.warehouse_id),
                "warehouse_name": row.warehouse_name,
                "product_id": str(row.product_id),
                "current_stock": row.quantity_available,
                "reorder_point": row.reorder_point,
                "min_stock_level": row.min_stock_level,
                "recommended_quantity": recommended_quantity,
                "forecast_demand_30d": forecast_demand,
                "reasons": reasons,
                "urgency": "high" if row.quantity_available <= row.min_stock_level else "medium"
            })
        
        logger.info(f"Replenishment recommendations: {len(recommendations)} items")
        
        return recommendations
    
    async def _get_forecast_summary(
        self,
        product_id: str,
        warehouse_id: str,
        days: int
    ) -> Dict[str, Any]:
        """Get forecast summary for a product"""
        
        end_date = date.today() + timedelta(days=days)
        
        result = self.db.execute(
            """
            SELECT 
                SUM(predicted_demand) AS total_demand,
                AVG(confidence_level) AS avg_confidence
            FROM demand_forecasts
            WHERE product_id = :product_id
            AND warehouse_id = :warehouse_id
            AND forecast_date BETWEEN CURRENT_DATE AND :end_date
            AND forecast_type = 'daily'
            """,
            {
                "product_id": uuid.UUID(product_id),
                "warehouse_id": uuid.UUID(warehouse_id),
                "end_date": end_date
            }
        ).first()
        
        if result and result.total_demand:
            return {
                "total_demand": int(result.total_demand),
                "avg_confidence": float(result.avg_confidence)
            }
        else:
            return {"total_demand": 0, "avg_confidence": 0.0}
    
    async def create_auto_replenishment_orders(
        self,
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Automatically create replenishment purchase orders"""
        
        recommendations = await self.get_replenishment_recommendations(warehouse_id)
        
        # Group by warehouse and preferred supplier
        orders_to_create = {}
        
        for rec in recommendations:
            # Get preferred supplier for product
            supplier = self.db.execute(
                """
                SELECT sp.supplier_id, s.name AS supplier_name
                FROM supplier_products sp
                JOIN suppliers s ON sp.supplier_id = s.id
                WHERE sp.product_id = :product_id
                AND sp.is_preferred = TRUE
                AND s.status = 'active'
                LIMIT 1
                """,
                {"product_id": uuid.UUID(rec['product_id'])}
            ).first()
            
            if not supplier:
                continue
            
            key = (rec['warehouse_id'], str(supplier.supplier_id))
            
            if key not in orders_to_create:
                orders_to_create[key] = {
                    "warehouse_id": rec['warehouse_id'],
                    "supplier_id": str(supplier.supplier_id),
                    "supplier_name": supplier.supplier_name,
                    "items": []
                }
            
            orders_to_create[key]["items"].append({
                "product_id": rec['product_id'],
                "quantity": rec['recommended_quantity']
            })
        
        logger.info(f"Auto-replenishment: {len(orders_to_create)} POs to create")
        
        return {
            "recommendations_processed": len(recommendations),
            "purchase_orders_to_create": len(orders_to_create),
            "orders": list(orders_to_create.values())
        }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/forecast/generate", response_model=Dict[str, Any])
async def generate_forecast(
    request: ForecastRequest,
    db: Session = Depends(get_db)
):
    """Generate demand forecast"""
    forecaster = DemandForecaster(db)
    return await forecaster.generate_forecast(request)

@app.get("/replenishment/recommendations", response_model=List[Dict[str, Any]])
async def get_replenishment_recommendations(
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get replenishment recommendations"""
    forecaster = DemandForecaster(db)
    return await forecaster.get_replenishment_recommendations(warehouse_id)

@app.post("/replenishment/auto-create", response_model=Dict[str, Any])
async def create_auto_replenishment_orders(
    warehouse_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create auto-replenishment orders"""
    forecaster = DemandForecaster(db)
    return await forecaster.create_auto_replenishment_orders(warehouse_id)

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "demand-forecasting",
        "version": "1.0.0"
    }

# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

