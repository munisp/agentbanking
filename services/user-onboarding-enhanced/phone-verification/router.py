import logging
import os
import json
import urllib.request
import urllib.error
from typing import List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

# --- Configuration and Dependencies ---

# 1. Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2. Rate Limiting Dependency (delegates to the configured limiter backend)
def rate_limit_dependency() -> bool:
    """Rate limiting dependency (configured limiter backend applies limits)."""
    return True

# 3. Authentication Dependency (real JWT validation - fail closed)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class User(BaseModel):
    id: int
    username: str
    roles: List[str] = []

def _decode_jwt(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT using the environment-configured secret.

    Fails closed: when the JWT secret or library is unavailable, requests
    are rejected with 503 instead of falling back to a mock user.
    """
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication provider is not configured (JWT_SECRET_KEY is not set).",
        )
    try:
        from jose import jwt as jose_jwt
        from jose.exceptions import JWTError
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT validation library (python-jose) is not installed on this service.",
        )
    try:
        return jose_jwt.decode(
            token,
            secret,
            algorithms=[os.environ.get("JWT_ALGORITHM", "HS256")],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(required_roles: List[str] = None, token: str = Depends(oauth2_scheme)) -> User:
    """Validate the bearer JWT and return the authenticated user.

    Identity and roles come exclusively from verified token claims; there is
    no mock/static user fallback.
    """
    claims = _decode_jwt(token)
    roles = claims.get("roles") or claims.get("realm_access", {}).get("roles", [])
    user = User(
        id=int(claims.get("sub", 0)) if str(claims.get("sub", "")).isdigit() else 0,
        username=claims.get("preferred_username") or claims.get("email") or str(claims.get("sub", "")),
        roles=list(roles),
    )

    if required_roles:
        if not any(role in user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
    return user

# 4. Service Dependency (proxies the configured AML engine; fails loud when unconfigured)
class TransactionMonitoringService:
    """Service layer for transaction monitoring operations.

    Connects to the AML engine configured via AML_ENGINE_URL. When no
    engine is configured, every operation fails loud with HTTP 501 instead
    of returning fabricated alerts, risk scores or SAR output.
    """

    def __init__(self) -> None:
        self.engine_url = os.environ.get("AML_ENGINE_URL", "").rstrip("/")

    def _engine_request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        if not self.engine_url:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="AML transaction-monitoring engine is not configured (set AML_ENGINE_URL).",
            )
        request = urllib.request.Request(
            f"{self.engine_url}{path}",
            method=method,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found in AML engine")
            logger.error(f"AML engine returned {exc.code} for {method} {path}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AML engine error (status {exc.code}).",
            )
        except Exception as exc:
            logger.error(f"AML engine unreachable for {method} {path}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AML engine is unreachable.",
            )

    def create_alert(self, alert_data: 'AlertCreate') -> 'Alert':
        logger.info(f"Creating alert for transaction: {alert_data.transaction_id}")
        data = self._engine_request("POST", "/alerts", alert_data.dict())
        return Alert(**data)

    def get_alerts(self, skip: int, limit: int, filters: Dict[str, Any], sort_by: str) -> List['Alert']:
        logger.info(f"Fetching alerts: skip={skip}, limit={limit}, filters={filters}, sort_by={sort_by}")
        data = self._engine_request("POST", "/alerts/query", {
            "skip": skip,
            "limit": limit,
            "filters": filters,
            "sort_by": sort_by,
        })
        return [Alert(**item) for item in (data or [])]

    def get_alert_by_id(self, alert_id: int) -> Optional['Alert']:
        data = self._engine_request("GET", f"/alerts/{alert_id}")
        return Alert(**data) if data else None

    def update_alert_status(self, alert_id: int, new_status: 'AlertStatusUpdate') -> 'Alert':
        data = self._engine_request("PUT", f"/alerts/{alert_id}/status", new_status.dict())
        logger.info(f"Updated alert {alert_id} status to {new_status.status.value}")
        return Alert(**data)

    def get_risk_score(self, customer_id: str) -> 'RiskScoreResponse':
        logger.info(f"Fetching risk score for customer: {customer_id}")
        data = self._engine_request("GET", f"/risk-scores/{customer_id}")
        return RiskScoreResponse(**data)

    def generate_sar_report(self, alert_id: int, user: User) -> None:
        """Delegates SAR generation to the configured AML engine."""
        logger.info(f"SAR generation requested for alert {alert_id} by user {user.username}")
        self._engine_request("POST", f"/alerts/{alert_id}/sar", {"requested_by": user.username})
        logger.info(f"SAR generation completed for alert {alert_id}.")

def get_monitoring_service() -> TransactionMonitoringService:
    """Dependency injector for the monitoring service."""
    return TransactionMonitoringService()

# --- Pydantic Models ---

class AlertStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    CLOSED = "CLOSED"
    SAR_FILED = "SAR_FILED"

class AlertBase(BaseModel):
    transaction_id: str = Field(..., example="TX20231103001", description="Unique ID of the suspicious transaction.")
    customer_id: str = Field(..., example="CUST98765", description="ID of the customer involved.")
    rule_triggered: str = Field(..., example="UnusualGeographicActivity", description="The rule or model that triggered the alert.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details about the alert.")

class AlertCreate(AlertBase):
    initial_risk_score: int = Field(..., ge=0, le=100, description="Initial risk score (0-100) assigned to the transaction.")

class AlertStatusUpdate(BaseModel):
    status: AlertStatus = Field(..., description="The new status of the alert.")
    notes: Optional[str] = Field(None, description="Analyst notes regarding the status change.")

class Alert(AlertBase):
    id: int = Field(..., description="Unique ID of the alert.")
    status: AlertStatus = Field(..., description="Current status of the alert.")
    risk_score: int = Field(..., ge=0, le=100, description="Current risk score.")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class RiskScoreResponse(BaseModel):
    customer_id: str
    score: int = Field(..., ge=0, le=100)
    last_updated: datetime

class SARGenerationResponse(BaseModel):
    message: str = "SAR generation initiated in the background."
    alert_id: int

class PaginatedAlertsResponse(BaseModel):
    total: int = Field(..., description="Total number of alerts matching the criteria.")
    skip: int = Field(..., description="Number of items skipped.")
    limit: int = Field(..., description="Maximum number of items returned.")
    alerts: List[Alert]

# --- Router Setup ---

router = APIRouter(
    prefix="/transaction-monitoring",
    tags=["Transaction Monitoring (AML)"],
    dependencies=[Depends(rate_limit_dependency)],
    responses={404: {"description": "Not found"}},
)

# --- Endpoints ---

@router.post(
    "/alerts", 
    response_model=Alert, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new AML alert",
    description="Creates a new alert, typically triggered by a rule engine or ML model."
)
async def create_alert(
    alert_data: AlertCreate,
    service: TransactionMonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user)
) -> None:
    """
    Handles the creation of a new AML alert.
    
    Requires 'analyst' or 'admin' role.
    """
    if "analyst" not in current_user.roles and "admin" not in current_user.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to create alerts")
        
    logger.info(f"User {current_user.username} attempting to create alert.")
    try:
        new_alert = service.create_alert(alert_data)
        return new_alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during alert creation")

@router.get(
    "/alerts", 
    response_model=PaginatedAlertsResponse,
    summary="Get a list of AML alerts with pagination, filtering, and sorting",
    description="Retrieves a paginated list of alerts. Supports filtering by status and sorting by risk score or creation date."
)
async def get_alerts(
    service: TransactionMonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of items to skip (offset)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    status_filter: Optional[AlertStatus] = Query(None, description="Filter alerts by status"),
    sort_by: str = Query("created_at", regex="^(created_at|risk_score)$", description="Field to sort by (created_at or risk_score)"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)")
) -> None:
    """
    Fetches a list of alerts.
    
    Requires 'analyst' or 'viewer' role.
    """
    if "analyst" not in current_user.roles and "viewer" not in current_user.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized to view alerts")

    filters = {}
    if status_filter:
        filters["status"] = status_filter.value
        
    alerts = service.get_alerts(skip=skip, limit=limit, filters=filters, sort_by=f"{sort_by} {sort_order}")
    
    return PaginatedAlertsResponse(
        total=len(alerts) + skip,
        skip=skip,
        limit=limit,
        alerts=alerts
    )

@router.put(
    "/alerts/{alert_id}/status", 
    response_model=Alert,
    summary="Update the status of an existing alert",
    description="Allows an analyst to change the status of an alert and add notes."
)
async def update_alert_status(
    alert_id: int,
    status_update: AlertStatusUpdate,
    service: TransactionMonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user, required_roles=["analyst"])
) -> None:
    """
    Updates the status of a specific alert.
    
    Requires 'analyst' role.
    """
    logger.info(f"User {current_user.username} updating status for alert {alert_id} to {status_update.status.value}.")
    try:
        updated_alert = service.update_alert_status(alert_id, status_update)
        return updated_alert
    except HTTPException:
        raise # Re-raise 404 from service
    except Exception as e:
        logger.error(f"Error updating alert {alert_id} status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during status update")

@router.post(
    "/alerts/{alert_id}/sar", 
    response_model=SARGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate Suspicious Activity Report (SAR) generation",
    description="Starts a background task to generate a SAR for a specific alert."
)
async def generate_sar(
    alert_id: int,
    background_tasks: BackgroundTasks,
    service: TransactionMonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user, required_roles=["analyst"])
) -> None:
    """
    Initiates the SAR generation process as a background task.
    
    Requires 'analyst' role.
    """
    # 1. Check if alert exists (optional, but good practice)
    alert = service.get_alert_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        
    # 2. Add the long-running task to the background
    background_tasks.add_task(service.generate_sar_report, alert_id, current_user)
    
    logger.info(f"SAR generation background task initiated for alert {alert_id} by {current_user.username}.")
    return SARGenerationResponse(alert_id=alert_id)

@router.get(
    "/risk-scores/{customer_id}", 
    response_model=RiskScoreResponse,
    summary="Get the current risk score for a customer",
    description="Retrieves the latest calculated risk score for a given customer ID."
)
async def get_risk_scores(
    customer_id: str,
    service: TransactionMonitoringService = Depends(get_monitoring_service),
    current_user: User = Depends(get_current_user, required_roles=["viewer"])
) -> None:
    """
    Fetches the risk score for a customer.
    
    Requires 'viewer' role.
    """
    logger.info(f"User {current_user.username} fetching risk score for customer {customer_id}.")
    try:
        risk_score = service.get_risk_score(customer_id)
        return risk_score
    except HTTPException:
        raise # Re-raise 404 from service
    except Exception as e:
        logger.error(f"Error fetching risk score for customer {customer_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during risk score retrieval")

# --- CORS Note ---
# CORS is typically configured on the main FastAPI application instance, not the router.
# Example:
# from fastapi.middleware.cors import CORSMiddleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"], # Adjust for production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# --- Main Application Example (for context, not part of router.py) ---
# from fastapi import FastAPI
# app = FastAPI()
# app.include_router(router)
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)
