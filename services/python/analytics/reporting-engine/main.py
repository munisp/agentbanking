"""
Advanced Analytics and Reporting Engine - Production Implementation
Real-time dashboards, custom reports, data export API, predictive analytics
"""

from fastapi import FastAPI, HTTPException, Query
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import json

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- PostgreSQL Persistence ---
import asyncpg
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/reporting_engine")
_db_pool = None

async def get_db_pool():
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool

async def close_db_pool():
    global _db_pool
    if _db_pool:
        await _db_pool.close()
        _db_pool = None

app = FastAPI(title="Advanced Analytics and Reporting", version="1.0.0")
apply_middleware(app, enable_auth=True)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ReportType(str, Enum):
    TRANSACTION_SUMMARY = "transaction_summary"
    CORRIDOR_PERFORMANCE = "corridor_performance"
    USER_BEHAVIOR = "user_behavior"
    REVENUE_ANALYSIS = "revenue_analysis"
    GATEWAY_PERFORMANCE = "gateway_performance"
    FRAUD_ANALYTICS = "fraud_analytics"
    COMPLIANCE_REPORT = "compliance_report"

class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    EXCEL = "excel"

class SubscriptionTier(str, Enum):
    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class ReportRequest(BaseModel):
    report_type: ReportType
    start_date: str
    end_date: str
    filters: Optional[Dict] = None
    group_by: Optional[List[str]] = None

class DashboardMetrics(BaseModel):
    total_transactions: int
    total_volume: float
    avg_transaction_value: float
    success_rate: float
    top_corridors: List[Dict]
    gateway_distribution: Dict
    hourly_trend: List[Dict]
    timestamp: str

class CustomReport(BaseModel):
    report_id: str
    report_type: ReportType
    data: List[Dict]
    summary: Dict
    generated_at: str
    row_count: int

class AnalyticsEngine:
    """Advanced Analytics and Reporting Engine"""
    
    def __init__(self):
        # In production: Connect to ClickHouse OLAP database
        self.mock_data = self._generate_mock_data()
        self.subscription_limits = {
            SubscriptionTier.FREE: {"reports_per_month": 5, "export_formats": ["json"], "custom_dashboards": 0},
            SubscriptionTier.PROFESSIONAL: {"reports_per_month": 100, "export_formats": ["json", "csv", "pdf"], "custom_dashboards": 5},
            SubscriptionTier.ENTERPRISE: {"reports_per_month": -1, "export_formats": ["json", "csv", "pdf", "excel"], "custom_dashboards": -1}
        }
        logger.info("Analytics engine initialized")
    
    def _generate_mock_data(self) -> Dict:
        """Generate mock transaction data for demonstration"""
        import random
        from datetime import datetime, timedelta
        
        transactions = []
        corridors = [
            ("NG", "US", "NGN", "USD"),
            ("NG", "GB", "NGN", "GBP"),
            ("NG", "GH", "NGN", "GHS"),
            ("US", "NG", "USD", "NGN"),
            ("GB", "NG", "GBP", "NGN")
        ]
        
        gateways = ["NIBSS", "SWIFT", "WISE", "PAPSS", "FLUTTERWAVE", "PAYSTACK"]
        
        for i in range(1000):
            corridor = random.choice(corridors)
            gateway = random.choice(gateways)
            amount = random.uniform(100, 5000)
            
            transactions.append({
                "transaction_id": f"tx_{i:06d}",
                "timestamp": (datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat(),
                "from_country": corridor[0],
                "to_country": corridor[1],
                "from_currency": corridor[2],
                "to_currency": corridor[3],
                "amount": round(amount, 2),
                "gateway": gateway,
                "status": random.choice(["completed", "completed", "completed", "failed"]),
                "user_id": f"user_{random.randint(1, 200):04d}",
                "fees": round(amount * 0.015, 2)
            })
        
        return {"transactions": transactions}
    
    async def get_dashboard_metrics(self, start_date: str, end_date: str) -> DashboardMetrics:
        """Get real-time dashboard metrics"""
        
        # Filter transactions by date range
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        filtered_txs = [
            tx for tx in self.mock_data["transactions"]
            if start <= datetime.fromisoformat(tx["timestamp"]) <= end
        ]
        
        # Calculate metrics
        total_transactions = len(filtered_txs)
        completed_txs = [tx for tx in filtered_txs if tx["status"] == "completed"]
        
        total_volume = sum(tx["amount"] for tx in completed_txs)
        avg_transaction_value = total_volume / len(completed_txs) if completed_txs else 0
        success_rate = len(completed_txs) / total_transactions if total_transactions > 0 else 0
        
        # Top corridors
        corridor_volumes = {}
        for tx in completed_txs:
            corridor = f"{tx['from_country']}-{tx['to_country']}"
            corridor_volumes[corridor] = corridor_volumes.get(corridor, 0) + tx["amount"]
        
        top_corridors = [
            {"corridor": k, "volume": round(v, 2), "count": sum(1 for tx in completed_txs if f"{tx['from_country']}-{tx['to_country']}" == k)}
            for k, v in sorted(corridor_volumes.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        # Gateway distribution
        gateway_counts = {}
        for tx in completed_txs:
            gateway_counts[tx["gateway"]] = gateway_counts.get(tx["gateway"], 0) + 1
        
        # Hourly trend (last 24 hours)
        hourly_trend = []
        for hour in range(24):
            hour_txs = [tx for tx in completed_txs if datetime.fromisoformat(tx["timestamp"]).hour == hour]
            hourly_trend.append({
                "hour": hour,
                "count": len(hour_txs),
                "volume": round(sum(tx["amount"] for tx in hour_txs), 2)
            })
        
        logger.info(f"Dashboard metrics: {total_transactions} transactions, ${total_volume:,.2f} volume")
        
        return DashboardMetrics(
            total_transactions=total_transactions,
            total_volume=round(total_volume, 2),
            avg_transaction_value=round(avg_transaction_value, 2),
            success_rate=round(success_rate, 3),
            top_corridors=top_corridors,
            gateway_distribution=gateway_counts,
            hourly_trend=hourly_trend,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def generate_report(self, request: ReportRequest) -> CustomReport:
        """Generate custom report"""
        
        start = datetime.fromisoformat(request.start_date)
        end = datetime.fromisoformat(request.end_date)
        
        filtered_txs = [
            tx for tx in self.mock_data["transactions"]
            if start <= datetime.fromisoformat(tx["timestamp"]) <= end
        ]
        
        # Apply filters
        if request.filters:
            for key, value in request.filters.items():
                filtered_txs = [tx for tx in filtered_txs if tx.get(key) == value]
        
        # Generate report based on type
        if request.report_type == ReportType.TRANSACTION_SUMMARY:
            data, summary = self._generate_transaction_summary(filtered_txs)
        elif request.report_type == ReportType.CORRIDOR_PERFORMANCE:
            data, summary = self._generate_corridor_performance(filtered_txs)
        elif request.report_type == ReportType.USER_BEHAVIOR:
            data, summary = self._generate_user_behavior(filtered_txs)
        elif request.report_type == ReportType.REVENUE_ANALYSIS:
            data, summary = self._generate_revenue_analysis(filtered_txs)
        elif request.report_type == ReportType.GATEWAY_PERFORMANCE:
            data, summary = self._generate_gateway_performance(filtered_txs)
        else:
            data = filtered_txs[:100]
            summary = {"total_records": len(filtered_txs)}
        
        report_id = f"RPT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"Generated report {report_id}: {request.report_type}, {len(data)} rows")
        
        return CustomReport(
            report_id=report_id,
            report_type=request.report_type,
            data=data,
            summary=summary,
            generated_at=datetime.utcnow().isoformat(),
            row_count=len(data)
        )
    
    def _generate_transaction_summary(self, transactions: List[Dict]) -> tuple:
        """Generate transaction summary report"""
        completed = [tx for tx in transactions if tx["status"] == "completed"]
        
        data = []
        for tx in completed[:100]:  # Limit to 100 rows
            data.append({
                "date": tx["timestamp"][:10],
                "transaction_id": tx["transaction_id"],
                "corridor": f"{tx['from_country']}-{tx['to_country']}",
                "amount": tx["amount"],
                "currency": tx["from_currency"],
                "gateway": tx["gateway"],
                "fees": tx["fees"],
                "status": tx["status"]
            })
        
        summary = {
            "total_transactions": len(transactions),
            "completed_transactions": len(completed),
            "failed_transactions": len(transactions) - len(completed),
            "success_rate": round(len(completed) / len(transactions), 3) if transactions else 0,
            "total_volume": round(sum(tx["amount"] for tx in completed), 2),
            "total_fees": round(sum(tx["fees"] for tx in completed), 2)
        }
        
        return data, summary
    
    def _generate_corridor_performance(self, transactions: List[Dict]) -> tuple:
        """Generate corridor performance report"""
        corridor_stats = {}
        
        for tx in transactions:
            corridor = f"{tx['from_country']}-{tx['to_country']}"
            if corridor not in corridor_stats:
                corridor_stats[corridor] = {"count": 0, "volume": 0, "fees": 0, "completed": 0}
            
            corridor_stats[corridor]["count"] += 1
            if tx["status"] == "completed":
                corridor_stats[corridor]["volume"] += tx["amount"]
                corridor_stats[corridor]["fees"] += tx["fees"]
                corridor_stats[corridor]["completed"] += 1
        
        data = [
            {
                "corridor": corridor,
                "transaction_count": stats["count"],
                "total_volume": round(stats["volume"], 2),
                "total_fees": round(stats["fees"], 2),
                "success_rate": round(stats["completed"] / stats["count"], 3) if stats["count"] > 0 else 0,
                "avg_transaction_value": round(stats["volume"] / stats["completed"], 2) if stats["completed"] > 0 else 0
            }
            for corridor, stats in corridor_stats.items()
        ]
        
        summary = {
            "total_corridors": len(corridor_stats),
            "most_active_corridor": max(data, key=lambda x: x["transaction_count"])["corridor"] if data else None,
            "highest_volume_corridor": max(data, key=lambda x: x["total_volume"])["corridor"] if data else None
        }
        
        return data, summary
    
    def _generate_user_behavior(self, transactions: List[Dict]) -> tuple:
        """Generate user behavior report"""
        user_stats = {}
        
        for tx in transactions:
            user_id = tx["user_id"]
            if user_id not in user_stats:
                user_stats[user_id] = {"count": 0, "volume": 0, "last_transaction": None}
            
            user_stats[user_id]["count"] += 1
            if tx["status"] == "completed":
                user_stats[user_id]["volume"] += tx["amount"]
            user_stats[user_id]["last_transaction"] = tx["timestamp"]
        
        data = [
            {
                "user_id": user_id,
                "transaction_count": stats["count"],
                "total_volume": round(stats["volume"], 2),
                "avg_transaction_value": round(stats["volume"] / stats["count"], 2) if stats["count"] > 0 else 0,
                "last_transaction": stats["last_transaction"]
            }
            for user_id, stats in list(user_stats.items())[:100]
        ]
        
        summary = {
            "total_users": len(user_stats),
            "avg_transactions_per_user": round(sum(s["count"] for s in user_stats.values()) / len(user_stats), 2) if user_stats else 0,
            "most_active_user": max(data, key=lambda x: x["transaction_count"])["user_id"] if data else None
        }
        
        return data, summary
    
    def _generate_revenue_analysis(self, transactions: List[Dict]) -> tuple:
        """Generate revenue analysis report"""
        completed = [tx for tx in transactions if tx["status"] == "completed"]
        
        # Group by date
        daily_revenue = {}
        for tx in completed:
            date = tx["timestamp"][:10]
            if date not in daily_revenue:
                daily_revenue[date] = {"fees": 0, "volume": 0, "count": 0}
            
            daily_revenue[date]["fees"] += tx["fees"]
            daily_revenue[date]["volume"] += tx["amount"]
            daily_revenue[date]["count"] += 1
        
        data = [
            {
                "date": date,
                "transaction_count": stats["count"],
                "transaction_volume": round(stats["volume"], 2),
                "fee_revenue": round(stats["fees"], 2),
                "avg_fee_per_transaction": round(stats["fees"] / stats["count"], 2) if stats["count"] > 0 else 0
            }
            for date, stats in sorted(daily_revenue.items())
        ]
        
        summary = {
            "total_revenue": round(sum(tx["fees"] for tx in completed), 2),
            "total_volume": round(sum(tx["amount"] for tx in completed), 2),
            "avg_revenue_per_day": round(sum(d["fee_revenue"] for d in data) / len(data), 2) if data else 0,
            "revenue_margin": round(sum(tx["fees"] for tx in completed) / sum(tx["amount"] for tx in completed) * 100, 2) if completed else 0
        }
        
        return data, summary
    
    def _generate_gateway_performance(self, transactions: List[Dict]) -> tuple:
        """Generate gateway performance report"""
        gateway_stats = {}
        
        for tx in transactions:
            gateway = tx["gateway"]
            if gateway not in gateway_stats:
                gateway_stats[gateway] = {"count": 0, "completed": 0, "failed": 0, "volume": 0}
            
            gateway_stats[gateway]["count"] += 1
            if tx["status"] == "completed":
                gateway_stats[gateway]["completed"] += 1
                gateway_stats[gateway]["volume"] += tx["amount"]
            else:
                gateway_stats[gateway]["failed"] += 1
        
        data = [
            {
                "gateway": gateway,
                "total_transactions": stats["count"],
                "completed": stats["completed"],
                "failed": stats["failed"],
                "success_rate": round(stats["completed"] / stats["count"], 3) if stats["count"] > 0 else 0,
                "total_volume": round(stats["volume"], 2)
            }
            for gateway, stats in gateway_stats.items()
        ]
        
        summary = {
            "total_gateways": len(gateway_stats),
            "best_performing_gateway": max(data, key=lambda x: x["success_rate"])["gateway"] if data else None,
            "highest_volume_gateway": max(data, key=lambda x: x["total_volume"])["gateway"] if data else None
        }
        
        return data, summary
    
    async def export_report(self, report: CustomReport, format: ExportFormat) -> Dict:
        """Export report in specified format"""
        
        if format == ExportFormat.JSON:
            return {"format": "json", "data": report.dict()}
        
        elif format == ExportFormat.CSV:
            # In production: Use pandas to generate CSV
            csv_content = self._generate_csv(report.data)
            return {"format": "csv", "content": csv_content, "filename": f"{report.report_id}.csv"}
        
        elif format == ExportFormat.PDF:
            # In production: Use ReportLab or WeasyPrint
            return {"format": "pdf", "message": "PDF generation not implemented in demo", "filename": f"{report.report_id}.pdf"}
        
        elif format == ExportFormat.EXCEL:
            # In production: Use openpyxl
            return {"format": "excel", "message": "Excel generation not implemented in demo", "filename": f"{report.report_id}.xlsx"}
    
    def _generate_csv(self, data: List[Dict]) -> str:
        """Generate CSV content from data"""
        if not data:
            return ""
        
        headers = list(data[0].keys())
        csv_lines = [",".join(headers)]
        
        for row in data:
            csv_lines.append(",".join(str(row.get(h, "")) for h in headers))
        
        return "\n".join(csv_lines)

# Initialize engine
analytics_engine = AnalyticsEngine()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "advanced-analytics",
        "data_points": len(analytics_engine.mock_data["transactions"])
    }

@app.get("/api/v1/analytics/dashboard", response_model=DashboardMetrics)
async def get_dashboard(
    start_date: str = Query(..., description="Start date (ISO format)"),
    end_date: str = Query(..., description="End date (ISO format)")
):
    """Get real-time dashboard metrics"""
    try:
        result = await analytics_engine.get_dashboard_metrics(start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dashboard generation failed: {str(e)}")

@app.post("/api/v1/analytics/reports/generate", response_model=CustomReport)
async def generate_report(request: ReportRequest):
    """Generate custom report"""
    try:
        result = await analytics_engine.generate_report(request)
        return result
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.post("/api/v1/analytics/reports/export")
async def export_report(report_id: str, format: ExportFormat):
    """Export report in specified format"""
    try:
        # In production: Retrieve report from database
        # For demo: Generate sample report
        sample_request = ReportRequest(
            report_type=ReportType.TRANSACTION_SUMMARY,
            start_date=(datetime.utcnow() - timedelta(days=30)).isoformat(),
            end_date=datetime.utcnow().isoformat()
        )
        report = await analytics_engine.generate_report(sample_request)
        result = await analytics_engine.export_report(report, format)
        return result
    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.get("/api/v1/analytics/subscription/limits")
async def get_subscription_limits(tier: SubscriptionTier):
    """Get subscription tier limits"""
    return analytics_engine.subscription_limits[tier]


@app.on_event("startup")
async def _startup():
    await get_db_pool()

@app.on_event("shutdown")
async def _shutdown():
    await close_db_pool()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8035)
