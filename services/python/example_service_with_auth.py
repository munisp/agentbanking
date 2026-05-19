import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Example Service with Keycloak Authentication
Remittance Platform V11.0

This example demonstrates how to integrate Keycloak authentication
into existing FastAPI microservices.

Author: Manus AI
Date: November 11, 2025
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("agent-banking-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List
import logging
import os
import httpx
import uuid as uuid_mod

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://database-service:8080")
KEYCLOAK_ADMIN_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080") + "/admin/realms/remittance"
TEMPORAL_URL = os.getenv("TEMPORAL_URL", "http://temporal:7233")

# Import Keycloak authentication
from shared.keycloak_auth import (
    KeycloakAuth,
    require_auth,
    require_role,
    require_any_role,
    get_user_id,
    get_username,
    get_email,
    get_roles
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Remittance Platform Service",
    description="Example service with Keycloak authentication",
    version="1.0.0"
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize Keycloak auth
auth = KeycloakAuth(
    server_url="http://keycloak:8080",
    realm="remittance",
    client_id="remittance-api"
)


# ============================================================================
# Models
# ============================================================================

class UserProfile(BaseModel):
    """User profile model."""
    user_id: str
    username: str
    email: Optional[str]
    roles: List[str]
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class TransactionRequest(BaseModel):
    """Transaction request model."""
    amount: float
    customer_id: str
    transaction_type: str
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    """Transaction response model."""
    transaction_id: str
    status: str
    amount: float
    message: str


# ============================================================================
# Public Endpoints (No Authentication Required)
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "remittance-service"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Remittance Platform Service",
        "version": "1.0.0",
        "authentication": "Keycloak OAuth 2.0 / OpenID Connect"
    }


# ============================================================================
# Protected Endpoints (Authentication Required)
# ============================================================================

@app.get("/api/v1/profile", response_model=UserProfile)
@require_auth
async def get_profile(user: dict = Depends(auth.get_current_user)):
    """
    Get current user profile.
    
    Requires: Authentication
    """
    return UserProfile(
        user_id=get_user_id(user),
        username=get_username(user),
        email=get_email(user),
        roles=get_roles(user),
        first_name=user.get("given_name"),
        last_name=user.get("family_name")
    )


@app.get("/api/v1/transactions/history")
@require_auth
async def get_transaction_history(
    limit: int = 10,
    offset: int = 0,
    user: dict = Depends(auth.get_current_user)
):
    """
    Get transaction history for current user.
    
    Requires: Authentication
    """
    user_id = get_user_id(user)
    username = get_username(user)
    
    logger.info(f"Fetching transaction history for user: {username} (ID: {user_id})")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{DATABASE_SERVICE_URL}/api/v1/transactions",
                params={"user_id": user_id, "limit": limit, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "user_id": user_id,
                "username": username,
                "transactions": data.get("items", []),
                "total": data.get("total", 0),
                "limit": limit,
                "offset": offset,
            }
        except httpx.HTTPError as exc:
            logger.error(f"Failed to fetch transactions: {exc}")
            raise HTTPException(status_code=502, detail="Transaction service unavailable")


# ============================================================================
# Role-Based Endpoints
# ============================================================================

@app.post("/api/v1/transactions/cash-in", response_model=TransactionResponse)
@require_any_role("agent", "super_agent", "admin")
async def cash_in(
    request: TransactionRequest,
    user: dict = Depends(auth.get_current_user)
):
    """
    Process cash-in transaction.
    
    Requires: agent, super_agent, or admin role
    """
    user_id = get_user_id(user)
    username = get_username(user)
    
    logger.info(f"Cash-in transaction initiated by {username}: {request.amount}")
    
    txn_id = str(uuid_mod.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{TEMPORAL_URL}/api/v1/workflows/cash-in",
                json={
                    "transaction_id": txn_id,
                    "agent_id": user_id,
                    "customer_id": request.customer_id,
                    "amount": request.amount,
                    "type": request.transaction_type,
                    "description": request.description,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return TransactionResponse(
                transaction_id=txn_id,
                status=result.get("status", "completed"),
                amount=request.amount,
                message=f"Cash-in of {request.amount} completed successfully",
            )
        except httpx.HTTPError as exc:
            logger.error(f"Cash-in workflow failed: {exc}")
            raise HTTPException(status_code=502, detail="Transaction processing failed")


@app.post("/api/v1/transactions/cash-out", response_model=TransactionResponse)
@require_any_role("agent", "super_agent", "admin")
async def cash_out(
    request: TransactionRequest,
    user: dict = Depends(auth.get_current_user)
):
    """
    Process cash-out transaction.
    
    Requires: agent, super_agent, or admin role
    """
    user_id = get_user_id(user)
    username = get_username(user)
    
    logger.info(f"Cash-out transaction initiated by {username}: {request.amount}")
    
    txn_id = str(uuid_mod.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{TEMPORAL_URL}/api/v1/workflows/cash-out",
                json={
                    "transaction_id": txn_id,
                    "agent_id": user_id,
                    "customer_id": request.customer_id,
                    "amount": request.amount,
                    "type": request.transaction_type,
                    "description": request.description,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return TransactionResponse(
                transaction_id=txn_id,
                status=result.get("status", "completed"),
                amount=request.amount,
                message=f"Cash-out of {request.amount} completed successfully",
            )
        except httpx.HTTPError as exc:
            logger.error(f"Cash-out workflow failed: {exc}")
            raise HTTPException(status_code=502, detail="Transaction processing failed")


@app.get("/api/v1/agents/hierarchy")
@require_any_role("super_agent", "admin")
async def get_agent_hierarchy(user: dict = Depends(auth.get_current_user)):
    """
    Get agent hierarchy tree.
    
    Requires: super_agent or admin role
    """
    user_id = get_user_id(user)
    username = get_username(user)
    
    logger.info(f"Agent hierarchy requested by {username}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{DATABASE_SERVICE_URL}/api/v1/agents/{user_id}/hierarchy",
            )
            resp.raise_for_status()
            hierarchy = resp.json()
            return {
                "agent_id": user_id,
                "username": username,
                "level": hierarchy.get("level", 1),
                "downline": hierarchy.get("downline", []),
                "total_downline": hierarchy.get("total_downline", 0),
            }
        except httpx.HTTPError as exc:
            logger.error(f"Failed to fetch hierarchy: {exc}")
            raise HTTPException(status_code=502, detail="Hierarchy service unavailable")


@app.post("/api/v1/agents/recruit")
@require_any_role("agent", "super_agent", "admin")
async def recruit_agent(
    email: str,
    first_name: str,
    last_name: str,
    user: dict = Depends(auth.get_current_user)
):
    """
    Recruit a new agent.
    
    Requires: agent, super_agent, or admin role
    """
    recruiter_id = get_user_id(user)
    recruiter_username = get_username(user)
    
    logger.info(f"Agent recruitment initiated by {recruiter_username}: {email}")
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            kc_resp = await client.post(
                f"{KEYCLOAK_ADMIN_URL}/users",
                json={
                    "username": email,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": False,
                    "requiredActions": ["VERIFY_EMAIL", "UPDATE_PASSWORD"],
                },
            )
            kc_resp.raise_for_status()
            db_resp = await client.post(
                f"{DATABASE_SERVICE_URL}/api/v1/agents",
                json={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "recruiter_id": recruiter_id,
                    "status": "pending_verification",
                },
            )
            db_resp.raise_for_status()
            return {
                "message": "Agent recruitment initiated",
                "recruiter_id": recruiter_id,
                "recruiter_username": recruiter_username,
                "new_agent_email": email,
                "status": "pending_verification",
            }
        except httpx.HTTPError as exc:
            logger.error(f"Agent recruitment failed: {exc}")
            raise HTTPException(status_code=502, detail="Recruitment service unavailable")


# ============================================================================
# Admin-Only Endpoints
# ============================================================================

@app.get("/api/v1/admin/users")
@require_role("admin")
async def list_users(
    limit: int = 10,
    offset: int = 0,
    user: dict = Depends(auth.get_current_user)
):
    """
    List all users (admin only).
    
    Requires: admin role
    """
    admin_username = get_username(user)
    
    logger.info(f"User list requested by admin: {admin_username}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{KEYCLOAK_ADMIN_URL}/users",
                params={"first": offset, "max": limit},
            )
            resp.raise_for_status()
            kc_users = resp.json()
            users = []
            for u in kc_users:
                role_resp = await client.get(
                    f"{KEYCLOAK_ADMIN_URL}/users/{u['id']}/role-mappings/realm",
                )
                roles = [r["name"] for r in role_resp.json()] if role_resp.status_code == 200 else []
                users.append({
                    "user_id": u["id"],
                    "username": u.get("username", ""),
                    "email": u.get("email", ""),
                    "roles": roles,
                    "status": "active" if u.get("enabled") else "disabled",
                })
            return {"users": users, "total": len(users), "limit": limit, "offset": offset}
        except httpx.HTTPError as exc:
            logger.error(f"Failed to list users: {exc}")
            raise HTTPException(status_code=502, detail="User service unavailable")


@app.post("/api/v1/admin/users/{user_id}/roles")
@require_role("admin")
async def assign_role(
    user_id: str,
    role: str,
    user: dict = Depends(auth.get_current_user)
):
    """
    Assign role to user (admin only).
    
    Requires: admin role
    """
    admin_username = get_username(user)
    
    logger.info(f"Role assignment by admin {admin_username}: user={user_id}, role={role}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            roles_resp = await client.get(f"{KEYCLOAK_ADMIN_URL}/roles/{role}")
            roles_resp.raise_for_status()
            role_repr = roles_resp.json()
            resp = await client.post(
                f"{KEYCLOAK_ADMIN_URL}/users/{user_id}/role-mappings/realm",
                json=[role_repr],
            )
            resp.raise_for_status()
            return {
                "message": f"Role '{role}' assigned to user '{user_id}'",
                "assigned_by": admin_username,
            }
        except httpx.HTTPError as exc:
            logger.error(f"Role assignment failed: {exc}")
            raise HTTPException(status_code=502, detail="Role assignment failed")


# ============================================================================
# Application Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Remittance Platform Service starting up...")
    logger.info(f"Keycloak server: {auth.server_url}")
    logger.info(f"Keycloak realm: {auth.realm}")
    logger.info(f"Client ID: {auth.client_id}")
    logger.info("Service ready to accept requests")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Remittance Platform Service shutting down...")


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "example_service_with_auth:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

