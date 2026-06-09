from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from . import schemas
from .database import get_db_session
from .service import (
    TenantService, TransactionService, FraudRuleService, FraudReportService,
    ItemNotFound, DuplicateItem, ServiceException,
    get_tenant_service, get_transaction_service, get_fraud_rule_service, get_fraud_report_service
)

router = APIRouter(
    prefix="/api/v1",
    tags=["fraud-detection"],
    responses={404: {"description": "Not found"}},
)

# --- Exception Handling Helper ---

def handle_service_exception(e: ServiceException) -> None:
    """Maps service exceptions to appropriate HTTP exceptions."""
    if isinstance(e, ItemNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) from e
    elif isinstance(e, DuplicateItem):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {e}"
        ) from e

# --- Tenants Endpoints ---

@router.post("/tenants", response_model=schemas.Tenant, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant: schemas.TenantCreate,
    service: TenantService = Depends(get_tenant_service)
) -> None:
    """Create a new tenant."""
    try:
        return await service.create(tenant)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/tenants/{tenant_id}", response_model=schemas.Tenant)
async def read_tenant(
    tenant_id: int,
    service: TenantService = Depends(get_tenant_service)
) -> None:
    """Retrieve a tenant by ID."""
    try:
        return await service.get_by_id(tenant_id)
    except ItemNotFound as e:
        handle_service_exception(e)

@router.get("/tenants", response_model=List[schemas.Tenant])
async def list_tenants(
    skip: int = 0,
    limit: int = 100,
    service: TenantService = Depends(get_tenant_service)
) -> None:
    """List all tenants."""
    return await service.get_all(skip=skip, limit=limit)

@router.put("/tenants/{tenant_id}", response_model=schemas.Tenant)
async def update_tenant(
    tenant_id: int,
    tenant: schemas.TenantUpdate,
    service: TenantService = Depends(get_tenant_service)
) -> None:
    """Update an existing tenant."""
    try:
        return await service.update(tenant_id, tenant)
    except ServiceException as e:
        handle_service_exception(e)

@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: int,
    service: TenantService = Depends(get_tenant_service)
) -> Dict[str, Any]:
    """Delete a tenant by ID."""
    try:
        await service.delete(tenant_id)
        return {"ok": True}
    except ItemNotFound as e:
        handle_service_exception(e)

# --- Fraud Rules Endpoints ---

@router.post("/rules", response_model=schemas.FraudRule, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule: schemas.FraudRuleCreate,
    service: FraudRuleService = Depends(get_fraud_rule_service)
) -> None:
    """Create a new fraud rule."""
    try:
        return await service.create(rule)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/rules/{rule_id}", response_model=schemas.FraudRule)
async def read_rule(
    rule_id: int,
    service: FraudRuleService = Depends(get_fraud_rule_service)
) -> None:
    """Retrieve a fraud rule by ID."""
    try:
        return await service.get_by_id(rule_id)
    except ItemNotFound as e:
        handle_service_exception(e)

@router.get("/rules", response_model=List[schemas.FraudRule])
async def list_rules(
    skip: int = 0,
    limit: int = 100,
    service: FraudRuleService = Depends(get_fraud_rule_service)
) -> None:
    """List all fraud rules."""
    return await service.get_all(skip=skip, limit=limit)

@router.put("/rules/{rule_id}", response_model=schemas.FraudRule)
async def update_rule(
    rule_id: int,
    rule: schemas.FraudRuleUpdate,
    service: FraudRuleService = Depends(get_fraud_rule_service)
) -> None:
    """Update an existing fraud rule."""
    try:
        return await service.update(rule_id, rule)
    except ServiceException as e:
        handle_service_exception(e)

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    service: FraudRuleService = Depends(get_fraud_rule_service)
) -> Dict[str, Any]:
    """Delete a fraud rule by ID."""
    try:
        await service.delete(rule_id)
        return {"ok": True}
    except ItemNotFound as e:
        handle_service_exception(e)

# --- Transactions Endpoints ---

@router.post("/transactions/process", response_model=schemas.Transaction, status_code=status.HTTP_201_CREATED)
async def process_transaction(
    transaction: schemas.TransactionCreate,
    service: TransactionService = Depends(get_transaction_service)
) -> None:
    """
    Process a new transaction for fraud detection.
    Runs rule-based and ML-based checks, and determines the final transaction status.
    """
    try:
        return await service.process_transaction(transaction)
    except ServiceException as e:
        handle_service_exception(e)

@router.get("/transactions/{transaction_id}", response_model=schemas.Transaction)
async def read_transaction(
    transaction_id: int,
    service: TransactionService = Depends(get_transaction_service)
) -> None:
    """Retrieve a transaction by ID."""
    try:
        return await service.get_by_id(transaction_id)
    except ItemNotFound as e:
        handle_service_exception(e)

@router.get("/transactions", response_model=List[schemas.Transaction])
async def list_transactions(
    skip: int = 0,
    limit: int = 100,
    service: TransactionService = Depends(get_transaction_service)
) -> None:
    """List all transactions."""
    return await service.get_all(skip=skip, limit=limit)

# --- Fraud Reports Endpoints (Read-Only for simplicity) ---

@router.get("/reports/{report_id}", response_model=schemas.FraudReport)
async def read_report(
    report_id: int,
    service: FraudReportService = Depends(get_fraud_report_service)
) -> None:
    """Retrieve a fraud report by ID."""
    try:
        return await service.get_by_id(report_id)
    except ItemNotFound as e:
        handle_service_exception(e)

@router.get("/reports", response_model=List[schemas.FraudReport])
async def list_reports(
    skip: int = 0,
    limit: int = 100,
    service: FraudReportService = Depends(get_fraud_report_service)
) -> None:
    """List all fraud reports."""
    return await service.get_all(skip=skip, limit=limit)