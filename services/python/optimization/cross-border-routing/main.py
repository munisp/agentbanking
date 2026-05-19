"""
Cross-Border Payment Optimization Service - Production Implementation
Smart routing, FX optimization, corridor analytics
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Cross-Border Payment Optimization", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class PaymentRequest(BaseModel):
    amount: float
    from_currency: str
    to_currency: str
    from_country: str
    to_country: str
    speed_preference: str  # "instant", "fast", "economy"
    metadata: Optional[Dict] = None

class RouteOption(BaseModel):
    route_id: str
    gateway: str
    total_cost: float
    fx_rate: float
    fees: Dict[str, float]
    estimated_time: str
    success_rate: float
    score: float

class OptimizedRoute(BaseModel):
    request_id: str
    recommended_route: RouteOption
    alternative_routes: List[RouteOption]
    savings_vs_default: float
    optimization_factors: Dict[str, float]
    timestamp: str

class CorridorAnalytics(BaseModel):
    corridor: str
    avg_cost: float
    avg_time: str
    volume_24h: int
    success_rate: float
    best_gateway: str
    peak_hours: List[int]

class CrossBorderOptimizer:
    """Smart routing and FX optimization engine"""
    
    def __init__(self):
        self.gateway_costs = self._initialize_gateway_costs()
        self.fx_rates = self._initialize_fx_rates()
        self.corridor_data = self._initialize_corridor_data()
        self.gateway_performance = self._initialize_performance_data()
        logger.info("Cross-border optimizer initialized")
    
    def _initialize_gateway_costs(self) -> Dict:
        """Initialize gateway cost structures"""
        return {
            "SWIFT": {"fixed": 25.0, "percentage": 0.003, "fx_markup": 0.015},
            "WISE": {"fixed": 5.0, "percentage": 0.005, "fx_markup": 0.004},
            "NIBSS": {"fixed": 2.0, "percentage": 0.002, "fx_markup": 0.008},
            "PAPSS": {"fixed": 3.0, "percentage": 0.0025, "fx_markup": 0.006},
            "BRICS_PAY": {"fixed": 4.0, "percentage": 0.003, "fx_markup": 0.005},
            "M_PESA": {"fixed": 1.5, "percentage": 0.004, "fx_markup": 0.010},
            "PAYSTACK": {"fixed": 3.5, "percentage": 0.0035, "fx_markup": 0.007},
            "FLUTTERWAVE": {"fixed": 3.0, "percentage": 0.004, "fx_markup": 0.008}
        }
    
    def _initialize_fx_rates(self) -> Dict:
        """Initialize FX rates (in production: fetch from multiple providers)"""
        return {
            "USD_NGN": 1580.50,
            "NGN_USD": 0.000633,
            "USD_GBP": 0.79,
            "GBP_USD": 1.27,
            "USD_EUR": 0.92,
            "EUR_USD": 1.09,
            "NGN_GHS": 0.095,
            "GHS_NGN": 10.53,
            "USD_KES": 129.50,
            "KES_USD": 0.0077
        }
    
    def _initialize_corridor_data(self) -> Dict:
        """Initialize corridor-specific data"""
        return {
            "NG_US": {"volume": 15000, "avg_amount": 500, "best_gateway": "WISE", "avg_cost_pct": 0.8},
            "NG_GB": {"volume": 12000, "avg_amount": 600, "best_gateway": "WISE", "avg_cost_pct": 0.7},
            "NG_GH": {"volume": 8000, "avg_amount": 300, "best_gateway": "PAPSS", "avg_cost_pct": 0.5},
            "NG_KE": {"volume": 5000, "avg_amount": 400, "best_gateway": "M_PESA", "avg_cost_pct": 0.6},
            "US_NG": {"volume": 20000, "avg_amount": 1000, "best_gateway": "FLUTTERWAVE", "avg_cost_pct": 0.9}
        }
    
    def _initialize_performance_data(self) -> Dict:
        """Initialize gateway performance metrics"""
        return {
            "SWIFT": {"success_rate": 0.98, "avg_time_hours": 24},
            "WISE": {"success_rate": 0.99, "avg_time_hours": 2},
            "NIBSS": {"success_rate": 0.97, "avg_time_hours": 1},
            "PAPSS": {"success_rate": 0.96, "avg_time_hours": 3},
            "BRICS_PAY": {"success_rate": 0.95, "avg_time_hours": 4},
            "M_PESA": {"success_rate": 0.98, "avg_time_hours": 0.5},
            "PAYSTACK": {"success_rate": 0.97, "avg_time_hours": 1},
            "FLUTTERWAVE": {"success_rate": 0.98, "avg_time_hours": 1.5}
        }
    
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """Get FX rate with fallback"""
        pair = f"{from_currency}_{to_currency}"
        if pair in self.fx_rates:
            return self.fx_rates[pair]
        
        # Try reverse pair
        reverse_pair = f"{to_currency}_{from_currency}"
        if reverse_pair in self.fx_rates:
            return 1.0 / self.fx_rates[reverse_pair]
        
        # Fallback: use USD as intermediary
        if from_currency != "USD" and to_currency != "USD":
            from_usd = self.get_fx_rate(from_currency, "USD")
            usd_to = self.get_fx_rate("USD", to_currency)
            return from_usd * usd_to
        
        return 1.0  # Same currency
    
    def calculate_route_cost(self, gateway: str, amount: float, from_currency: str, to_currency: str) -> Dict:
        """Calculate total cost for a specific gateway"""
        costs = self.gateway_costs.get(gateway, {"fixed": 10.0, "percentage": 0.005, "fx_markup": 0.01})
        
        # Base FX rate
        base_fx_rate = self.get_fx_rate(from_currency, to_currency)
        
        # Apply FX markup
        fx_rate_with_markup = base_fx_rate * (1 - costs["fx_markup"])
        
        # Calculate fees
        fixed_fee = costs["fixed"]
        percentage_fee = amount * costs["percentage"]
        fx_cost = amount * base_fx_rate * costs["fx_markup"]
        
        total_cost = fixed_fee + percentage_fee + fx_cost
        
        return {
            "fx_rate": round(fx_rate_with_markup, 6),
            "fixed_fee": round(fixed_fee, 2),
            "percentage_fee": round(percentage_fee, 2),
            "fx_cost": round(fx_cost, 2),
            "total_cost": round(total_cost, 2),
            "total_cost_pct": round((total_cost / amount) * 100, 2)
        }
    
    def calculate_route_score(self, gateway: str, cost_data: Dict, speed_preference: str) -> float:
        """Calculate optimization score for route"""
        perf = self.gateway_performance.get(gateway, {"success_rate": 0.95, "avg_time_hours": 12})
        
        # Weights based on speed preference
        if speed_preference == "instant":
            weights = {"cost": 0.3, "speed": 0.5, "reliability": 0.2}
        elif speed_preference == "fast":
            weights = {"cost": 0.4, "speed": 0.4, "reliability": 0.2}
        else:  # economy
            weights = {"cost": 0.6, "speed": 0.2, "reliability": 0.2}
        
        # Normalize metrics (0-1 scale, higher is better)
        cost_score = max(0, 1 - (cost_data["total_cost_pct"] / 10))  # Assume 10% is worst
        speed_score = max(0, 1 - (perf["avg_time_hours"] / 48))  # Assume 48h is worst
        reliability_score = perf["success_rate"]
        
        # Weighted score
        total_score = (
            cost_score * weights["cost"] +
            speed_score * weights["speed"] +
            reliability_score * weights["reliability"]
        )
        
        return round(total_score, 3)
    
    async def optimize_route(self, request: PaymentRequest) -> OptimizedRoute:
        """Find optimal route for cross-border payment"""
        
        corridor = f"{request.from_country}_{request.to_country}"
        corridor_info = self.corridor_data.get(corridor, {})
        
        # Evaluate all gateways
        routes = []
        
        for gateway in self.gateway_costs.keys():
            cost_data = self.calculate_route_cost(
                gateway,
                request.amount,
                request.from_currency,
                request.to_currency
            )
            
            score = self.calculate_route_score(gateway, cost_data, request.speed_preference)
            
            perf = self.gateway_performance[gateway]
            
            route = RouteOption(
                route_id=f"{gateway}-{datetime.utcnow().timestamp()}",
                gateway=gateway,
                total_cost=cost_data["total_cost"],
                fx_rate=cost_data["fx_rate"],
                fees={
                    "fixed": cost_data["fixed_fee"],
                    "percentage": cost_data["percentage_fee"],
                    "fx_markup": cost_data["fx_cost"]
                },
                estimated_time=f"{perf['avg_time_hours']} hours",
                success_rate=perf["success_rate"],
                score=score
            )
            
            routes.append(route)
        
        # Sort by score (highest first)
        routes.sort(key=lambda r: r.score, reverse=True)
        
        recommended = routes[0]
        alternatives = routes[1:4]  # Top 3 alternatives
        
        # Calculate savings vs default (SWIFT)
        swift_route = next((r for r in routes if r.gateway == "SWIFT"), None)
        savings = swift_route.total_cost - recommended.total_cost if swift_route else 0
        
        logger.info(f"Optimized route for {corridor}: {recommended.gateway} (score: {recommended.score}, savings: ${savings:.2f})")
        
        return OptimizedRoute(
            request_id=f"OPT-{datetime.utcnow().timestamp()}",
            recommended_route=recommended,
            alternative_routes=alternatives,
            savings_vs_default=round(savings, 2),
            optimization_factors={
                "cost_weight": 0.6 if request.speed_preference == "economy" else 0.3,
                "speed_weight": 0.5 if request.speed_preference == "instant" else 0.2,
                "reliability_weight": 0.2
            },
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def get_corridor_analytics(self, from_country: str, to_country: str) -> CorridorAnalytics:
        """Get analytics for specific corridor"""
        corridor = f"{from_country}_{to_country}"
        data = self.corridor_data.get(corridor, {
            "volume": 0,
            "avg_amount": 0,
            "best_gateway": "SWIFT",
            "avg_cost_pct": 1.0
        })
        
        return CorridorAnalytics(
            corridor=corridor,
            avg_cost=round(data["avg_amount"] * data["avg_cost_pct"] / 100, 2),
            avg_time="2-4 hours",
            volume_24h=data["volume"],
            success_rate=0.97,
            best_gateway=data["best_gateway"],
            peak_hours=[9, 10, 11, 14, 15, 16]  # Business hours
        )

# Initialize optimizer
optimizer = CrossBorderOptimizer()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "cross-border-optimization",
        "gateways": len(optimizer.gateway_costs),
        "corridors": len(optimizer.corridor_data)
    }

@app.post("/api/v1/optimize/route", response_model=OptimizedRoute)
async def optimize_payment_route(request: PaymentRequest):
    """Get optimized payment route"""
    try:
        result = await optimizer.optimize_route(request)
        return result
    except Exception as e:
        logger.error(f"Route optimization error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@app.get("/api/v1/optimize/corridor/{from_country}/{to_country}", response_model=CorridorAnalytics)
async def get_corridor_info(from_country: str, to_country: str):
    """Get corridor analytics"""
    try:
        result = await optimizer.get_corridor_analytics(from_country, to_country)
        return result
    except Exception as e:
        logger.error(f"Corridor analytics error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")

@app.get("/api/v1/optimize/fx/{from_currency}/{to_currency}")
async def get_fx_rate(from_currency: str, to_currency: str):
    """Get current FX rate"""
    rate = optimizer.get_fx_rate(from_currency, to_currency)
    return {
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/optimize/gateways")
async def list_gateways():
    """List all available gateways with performance metrics"""
    gateways = []
    for gateway, costs in optimizer.gateway_costs.items():
        perf = optimizer.gateway_performance[gateway]
        gateways.append({
            "name": gateway,
            "fixed_fee": costs["fixed"],
            "percentage_fee": costs["percentage"] * 100,
            "fx_markup": costs["fx_markup"] * 100,
            "success_rate": perf["success_rate"] * 100,
            "avg_time": f"{perf['avg_time_hours']} hours"
        })
    
    return {"gateways": gateways}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8032)
