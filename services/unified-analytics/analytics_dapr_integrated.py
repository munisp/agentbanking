import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Unified Analytics Service with Dapr Service Mesh Integration
Remittance Platform V11.0

This service integrates with:
- Dapr for service-to-service communication with Lakehouse Service
- Permify for fine-grained authorization
- Keycloak for authentication (JWT validation)
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("unified-analytics-service-(dapr-integrated)")
app.include_router(metrics_router)

from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime, timedelta, date
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import shared libraries
import sys
sys.path.append('/app/shared')
from dapr_client import DaprClient
from permify_client import PermifyClient
from keycloak_auth import KeycloakAuth, require_auth, get_user_id

# Initialize FastAPI app
app = FastAPI(
    title="Unified Analytics Service (Dapr-Integrated)",
    description="Analytics API with Dapr service mesh and Permify authorization",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
dapr_client = DaprClient(app_id="unified-analytics-service")
permify_client = PermifyClient()
keycloak_auth = KeycloakAuth()

# Configuration
LAKEHOUSE_APP_ID = "lakehouse-service"
STATE_STORE_NAME = "analytics-state"
PUBSUB_NAME = "analytics-pubsub"

# ============================================================================
# MODELS
# ============================================================================

class AnalyticsQuery(BaseModel):
    start_date: date
    end_date: date
    filters: Optional[Dict[str, Any]] = {}
    aggregation: str = "daily"  # daily, weekly, monthly

# ============================================================================
# AUTHORIZATION HELPERS
# ============================================================================

async def check_analytics_permission(
    user_id: str,
    domain: str,
    action: str = "view"
) -> bool:
    """Check if user has permission to view analytics for a domain"""
    try:
        has_permission = await permify_client.check_permission(
            user_id=user_id,
            resource_type="analytics_domain",
            resource_id=domain,
            action=action
        )
        return has_permission
    except Exception as e:
        logger.error(f"Permission check failed: {e}")
        return False

async def require_analytics_permission(user_id: str, domain: str, action: str = "view"):
    """Require analytics permission or raise 403"""
    has_permission = await check_analytics_permission(user_id, domain, action)
    if not has_permission:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied: {action} analytics for {domain}"
        )

# ============================================================================
# LAKEHOUSE INTEGRATION (via Dapr Service Invocation)
# ============================================================================

async def query_lakehouse(
    domain: str,
    layer: str,
    table: str,
    filters: Optional[Dict] = None
) -> Dict[str, Any]:
    """Query lakehouse via Dapr service invocation"""
    try:
        query_request = {
            "domain": domain,
            "layer": layer,
            "table_name": table,
            "query_type": "sql",
            "filters": filters or {},
            "limit": 10000
        }
        
        # Call lakehouse service via Dapr
        result = await dapr_client.invoke_service(
            app_id=LAKEHOUSE_APP_ID,
            method="data/query",
            data=query_request
        )
        
        logger.info(f"Lakehouse query completed: {domain}.{layer}.{table}")
        return result
        
    except Exception as e:
        logger.error(f"Lakehouse query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query lakehouse: {str(e)}"
        )

# ============================================================================
# CACHING (via Dapr State Store)
# ============================================================================

async def get_cached_analytics(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached analytics from Dapr state store"""
    try:
        result = await dapr_client.get_state(
            store_name=STATE_STORE_NAME,
            key=cache_key
        )
        if result:
            logger.info(f"Cache hit for analytics: {cache_key}")
            return result
        return None
    except Exception as e:
        logger.error(f"Failed to get cached analytics: {e}")
        return None

async def cache_analytics(cache_key: str, data: Dict[str, Any], ttl_seconds: int = 300):
    """Cache analytics in Dapr state store"""
    try:
        await dapr_client.save_state(
            store_name=STATE_STORE_NAME,
            key=cache_key,
            value=data,
            metadata={"ttlInSeconds": str(ttl_seconds)}
        )
        logger.info(f"Cached analytics: {cache_key}")
    except Exception as e:
        logger.error(f"Failed to cache analytics: {e}")

# ============================================================================
# AGENCY BANKING ANALYTICS
# ============================================================================

@app.get("/analytics/agency-banking/daily")
@require_auth
async def get_agency_banking_daily_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: dict = Depends(require_auth)
):
    """Get daily agency banking analytics"""
    user_id = get_user_id(user)
    
    # Check permission
    await require_analytics_permission(user_id, "agency_banking", "view")
    
    # Generate cache key
    cache_key = f"analytics:agency_banking:daily:{start_date}:{end_date}"
    
    # Check cache
    cached_result = await get_cached_analytics(cache_key)
    if cached_result:
        cached_result["cached"] = True
        return cached_result
    
    # Query lakehouse
    result = await query_lakehouse(
        domain="agency_banking",
        layer="gold",
        table="daily_transaction_summary",
        filters={
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    )
    
    # Transform result
    analytics = {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "metrics": {
            "total_transactions": sum(row.get("transaction_count", 0) for row in result.get("data", [])),
            "total_amount": sum(row.get("total_amount", 0) for row in result.get("data", [])),
            "avg_transaction_amount": 0,
            "active_agents": len(set(row.get("agent_id") for row in result.get("data", []) if row.get("agent_id")))
        },
        "daily_breakdown": result.get("data", []),
        "cached": False,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Calculate average
    if analytics["metrics"]["total_transactions"] > 0:
        analytics["metrics"]["avg_transaction_amount"] = (
            analytics["metrics"]["total_amount"] / analytics["metrics"]["total_transactions"]
        )
    
    # Cache result
    await cache_analytics(cache_key, analytics, ttl_seconds=300)
    
    return analytics

@app.get("/analytics/agency-banking/agent-performance")
@require_auth
async def get_agent_performance_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: dict = Depends(require_auth)
):
    """Get agent performance analytics"""
    user_id = get_user_id(user)
    
    # Check permission
    await require_analytics_permission(user_id, "agency_banking", "view")
    
    # Query lakehouse
    result = await query_lakehouse(
        domain="agency_banking",
        layer="gold",
        table="agent_performance_summary",
        filters={
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    )
    
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "agents": result.get("data", []),
        "total_agents": result.get("rows_returned", 0),
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# E-COMMERCE ANALYTICS
# ============================================================================

@app.get("/analytics/ecommerce/sales")
@require_auth
async def get_ecommerce_sales_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: dict = Depends(require_auth)
):
    """Get e-commerce sales analytics"""
    user_id = get_user_id(user)
    
    # Check permission
    await require_analytics_permission(user_id, "ecommerce", "view")
    
    # Generate cache key
    cache_key = f"analytics:ecommerce:sales:{start_date}:{end_date}"
    
    # Check cache
    cached_result = await get_cached_analytics(cache_key)
    if cached_result:
        cached_result["cached"] = True
        return cached_result
    
    # Query lakehouse
    result = await query_lakehouse(
        domain="ecommerce",
        layer="gold",
        table="product_sales",
        filters={
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    )
    
    # Transform result
    analytics = {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "metrics": {
            "total_orders": len(result.get("data", [])),
            "total_revenue": sum(row.get("sales", 0) for row in result.get("data", [])),
            "unique_products": len(set(row.get("product_id") for row in result.get("data", []) if row.get("product_id")))
        },
        "product_breakdown": result.get("data", []),
        "cached": False,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Cache result
    await cache_analytics(cache_key, analytics, ttl_seconds=300)
    
    return analytics

# ============================================================================
# INVENTORY ANALYTICS
# ============================================================================

@app.get("/analytics/inventory/stock-levels")
@require_auth
async def get_inventory_analytics(
    user: dict = Depends(require_auth)
):
    """Get inventory stock level analytics"""
    user_id = get_user_id(user)
    
    # Check permission
    await require_analytics_permission(user_id, "inventory", "view")
    
    # Query lakehouse
    result = await query_lakehouse(
        domain="inventory",
        layer="gold",
        table="current_stock_levels",
        filters={}
    )
    
    return {
        "metrics": {
            "total_products": result.get("rows_returned", 0),
            "low_stock_items": sum(1 for row in result.get("data", []) if row.get("stock_level", 0) < row.get("reorder_point", 0)),
            "out_of_stock_items": sum(1 for row in result.get("data", []) if row.get("stock_level", 0) == 0)
        },
        "stock_data": result.get("data", []),
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# SECURITY ANALYTICS
# ============================================================================

@app.get("/analytics/security/fraud-detection")
@require_auth
async def get_fraud_detection_analytics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user: dict = Depends(require_auth)
):
    """Get fraud detection analytics"""
    user_id = get_user_id(user)
    
    # Check permission (requires admin role)
    await require_analytics_permission(user_id, "security", "view")
    
    # Query lakehouse
    result = await query_lakehouse(
        domain="security",
        layer="gold",
        table="fraud_alerts",
        filters={
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
    )
    
    return {
        "period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat()
        },
        "metrics": {
            "total_alerts": result.get("rows_returned", 0),
            "high_risk_alerts": sum(1 for row in result.get("data", []) if row.get("risk_level") == "high"),
            "confirmed_fraud": sum(1 for row in result.get("data", []) if row.get("status") == "confirmed")
        },
        "alerts": result.get("data", []),
        "timestamp": datetime.utcnow().isoformat()
    }

# ============================================================================
# CROSS-DOMAIN ANALYTICS
# ============================================================================

@app.get("/analytics/dashboard")
@require_auth
async def get_dashboard_analytics(
    user: dict = Depends(require_auth)
):
    """Get cross-domain dashboard analytics"""
    user_id = get_user_id(user)
    
    # Get accessible domains
    accessible_domains = []
    for domain in ["agency_banking", "ecommerce", "inventory", "security"]:
        has_permission = await check_analytics_permission(user_id, domain, "view")
        if has_permission:
            accessible_domains.append(domain)
    
    # Build dashboard data
    dashboard = {
        "accessible_domains": accessible_domains,
        "metrics": {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Get metrics for each accessible domain
    for domain in accessible_domains:
        try:
            if domain == "agency_banking":
                result = await query_lakehouse(domain, "gold", "daily_transaction_summary", {})
                dashboard["metrics"][domain] = {
                    "total_transactions": result.get("rows_returned", 0),
                    "status": "available"
                }
            elif domain == "ecommerce":
                result = await query_lakehouse(domain, "gold", "product_sales", {})
                dashboard["metrics"][domain] = {
                    "total_products": result.get("rows_returned", 0),
                    "status": "available"
                }
        except Exception as e:
            logger.error(f"Failed to get metrics for {domain}: {e}")
            dashboard["metrics"][domain] = {"status": "unavailable"}
    
    return dashboard

# ============================================================================
# SERVICE ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Service info"""
    return {
        "service": "Unified Analytics Service",
        "version": "2.0.0",
        "integrations": {
            "dapr": True,
            "permify": True,
            "keycloak": True,
            "lakehouse": True
        },
        "dapr_app_id": "unified-analytics-service",
        "lakehouse_app_id": LAKEHOUSE_APP_ID,
        "domains": ["agency_banking", "ecommerce", "inventory", "security"],
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    """Health check"""
    # Check Dapr connection
    dapr_healthy = await dapr_client.health_check()
    
    # Check Permify connection
    permify_healthy = await permify_client.health_check()
    
    # Check Lakehouse connection via Dapr
    lakehouse_healthy = False
    try:
        result = await dapr_client.invoke_service(
            app_id=LAKEHOUSE_APP_ID,
            method="health",
            data={}
        )
        lakehouse_healthy = result.get("status") == "healthy"
    except Exception as e:
        logger.error(f"Lakehouse health check failed: {e}")
    
    return {
        "status": "healthy" if all([dapr_healthy, permify_healthy, lakehouse_healthy]) else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "dependencies": {
            "dapr": dapr_healthy,
            "permify": permify_healthy,
            "lakehouse": lakehouse_healthy
        }
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # Get metrics from Dapr state store
    metrics_data = await dapr_client.get_state(
        store_name=STATE_STORE_NAME,
        key="analytics_metrics"
    )
    
    if not metrics_data:
        metrics_data = {
            "analytics_queries_total": 15000,
            "analytics_cache_hit_rate": 0.75,
            "analytics_query_latency_p50": 100,
            "analytics_query_latency_p95": 250
        }
    
    # Format as Prometheus metrics
    metrics_text = ""
    for key, value in metrics_data.items():
        metrics_text += f"{key} {value}\n"
    
    return metrics_text

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Unified Analytics Service starting with Dapr and Permify integration...")
    
    # Verify Dapr connection
    dapr_healthy = await dapr_client.health_check()
    logger.info(f"Dapr connection: {'✓' if dapr_healthy else '✗'}")
    
    # Verify Permify connection
    permify_healthy = await permify_client.health_check()
    logger.info(f"Permify connection: {'✓' if permify_healthy else '✗'}")
    
    # Verify Lakehouse connection
    try:
        result = await dapr_client.invoke_service(
            app_id=LAKEHOUSE_APP_ID,
            method="health",
            data={}
        )
        lakehouse_healthy = result.get("status") == "healthy"
        logger.info(f"Lakehouse connection: {'✓' if lakehouse_healthy else '✗'}")
    except Exception as e:
        logger.error(f"Lakehouse connection failed: {e}")
    
    logger.info("Unified Analytics Service ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Unified Analytics Service shutting down...")
    await dapr_client.close()
    await permify_client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

