import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Lakehouse Service with JWT Authentication
Demonstrates how to add authentication to the lakehouse API endpoints
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("agent-banking-lakehouse-(authenticated)")
app.include_router(metrics_router)

from pydantic import BaseModel

# Import authentication module
from auth import (
    User, UserRole, LoginRequest, TokenResponse,
    get_current_user, get_current_active_user,
    require_admin, require_data_engineer, require_analyst, require_any_role,
    login, refresh_access_token, log_access
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Remittance Platform Lakehouse (Authenticated)",
    description="Production-ready lakehouse with JWT authentication and RBAC",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login_endpoint(login_request: LoginRequest):
    """
    Login endpoint - Returns JWT tokens
    
    Credentials:
    - Use configured users/passwords (no hardcoded credentials)
    """
    return await login(login_request)

@app.post("/auth/refresh", response_model=TokenResponse, tags=["Authentication"])
async def refresh_token_endpoint(refresh_token: str):
    """
    Refresh access token using refresh token
    """
    return await refresh_access_token(refresh_token)

@app.get("/auth/me", tags=["Authentication"])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    Requires: Valid JWT token
    """
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active
    }

# ============================================================================
# PROTECTED ENDPOINTS (WITH AUTHENTICATION)
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Health check - No authentication required"""
    return {
        "service": "Remittance Platform Lakehouse (Authenticated)",
        "version": "2.1.0",
        "status": "operational",
        "authentication": "JWT",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/analytics/summary", tags=["Analytics"])
async def get_analytics_summary(
    current_user: User = Depends(require_any_role)  # All roles can access
):
    """
    Get analytics summary across all domains
    Requires: Any authenticated user (admin, data_engineer, analyst, viewer)
    """
    # Log access for audit
    await log_access(
        user=current_user,
        endpoint="/analytics/summary",
        action="read",
        resource="analytics_summary"
    )
    
    # Return analytics data
    summary = {
        "domains": {
            "agency_banking": {
                "table_count": 12,
                "row_count": 5000000,
                "layers": {
                    "bronze": {"table_count": 3, "row_count": 2000000},
                    "silver": {"table_count": 4, "row_count": 1800000},
                    "gold": {"table_count": 3, "row_count": 1000000},
                    "platinum": {"table_count": 2, "row_count": 200000}
                }
            },
            "ecommerce": {
                "table_count": 12,
                "row_count": 3500000,
                "layers": {
                    "bronze": {"table_count": 3, "row_count": 1500000},
                    "silver": {"table_count": 4, "row_count": 1200000},
                    "gold": {"table_count": 3, "row_count": 700000},
                    "platinum": {"table_count": 2, "row_count": 100000}
                }
            },
            "inventory": {
                "table_count": 12,
                "row_count": 2500000,
                "layers": {
                    "bronze": {"table_count": 3, "row_count": 1000000},
                    "silver": {"table_count": 4, "row_count": 900000},
                    "gold": {"table_count": 3, "row_count": 500000},
                    "platinum": {"table_count": 2, "row_count": 100000}
                }
            },
            "security": {
                "table_count": 12,
                "row_count": 1500000,
                "layers": {
                    "bronze": {"table_count": 3, "row_count": 800000},
                    "silver": {"table_count": 4, "row_count": 500000},
                    "gold": {"table_count": 3, "row_count": 150000},
                    "platinum": {"table_count": 2, "row_count": 50000}
                }
            }
        },
        "total_tables": 48,
        "total_rows": 12500000,
        "accessed_by": current_user.username,
        "user_role": current_user.role.value
    }
    
    return summary

@app.get("/catalog", tags=["Catalog"])
async def get_catalog(
    current_user: User = Depends(require_any_role)  # All roles can view catalog
):
    """
    Get the data catalog
    Requires: Any authenticated user
    """
    await log_access(current_user, "/catalog", "read", "catalog")
    
    return {
        "catalog": {
            "agency_banking": {"bronze": {}, "silver": {}, "gold": {}, "platinum": {}},
            "ecommerce": {"bronze": {}, "silver": {}, "gold": {}, "platinum": {}},
            "inventory": {"bronze": {}, "silver": {}, "gold": {}, "platinum": {}},
            "security": {"bronze": {}, "silver": {}, "gold": {}, "platinum": {}}
        },
        "total_tables": 48,
        "accessed_by": current_user.username
    }

@app.post("/tables/create", tags=["Tables"])
async def create_table(
    table_data: Dict[str, Any],
    current_user: User = Depends(require_data_engineer)  # Only admin and data_engineer
):
    """
    Create a new table in the lakehouse
    Requires: admin or data_engineer role
    """
    await log_access(current_user, "/tables/create", "create", f"table:{table_data.get('name')}")
    
    return {
        "message": "Table created successfully",
        "table": table_data.get("name"),
        "created_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/data/ingest", tags=["Data"])
async def ingest_data(
    ingest_request: Dict[str, Any],
    current_user: User = Depends(require_data_engineer)  # Only admin and data_engineer
):
    """
    Ingest data into a table
    Requires: admin or data_engineer role
    """
    await log_access(current_user, "/data/ingest", "write", f"table:{ingest_request.get('table')}")
    
    return {
        "message": "Data ingested successfully",
        "table": ingest_request.get("table"),
        "rows_ingested": ingest_request.get("row_count", 0),
        "ingested_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/data/query", tags=["Data"])
async def query_data(
    query_request: Dict[str, Any],
    current_user: User = Depends(require_analyst)  # admin, data_engineer, analyst
):
    """
    Query data from the lakehouse
    Requires: admin, data_engineer, or analyst role
    """
    await log_access(current_user, "/data/query", "read", f"table:{query_request.get('table')}")
    
    return {
        "table": query_request.get("table"),
        "rows_returned": 1000,
        "execution_time_ms": 45.2,
        "queried_by": current_user.username,
        "data": []  # Actual data would be here
    }

@app.delete("/tables/{table_name}", tags=["Tables"])
async def delete_table(
    table_name: str,
    current_user: User = Depends(require_admin)  # Only admin can delete
):
    """
    Delete a table from the lakehouse
    Requires: admin role only
    """
    await log_access(current_user, f"/tables/{table_name}", "delete", f"table:{table_name}")
    
    return {
        "message": "Table deleted successfully",
        "table": table_name,
        "deleted_by": current_user.username,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/audit/logs", tags=["Audit"])
async def get_audit_logs(
    current_user: User = Depends(require_admin)  # Only admin can view audit logs
):
    """
    Get audit logs
    Requires: admin role only
    """
    return {
        "message": "Audit logs would be returned here",
        "accessed_by": current_user.username
    }

# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize lakehouse on startup"""
    logger.info("Starting Remittance Platform Lakehouse with Authentication...")
    logger.info("JWT Authentication: Enabled")
    logger.info("RBAC: Enabled (4 roles)")
    logger.info("Lakehouse ready!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8070)

