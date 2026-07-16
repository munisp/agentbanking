from fastapi import APIRouter, Depends, HTTPException, responses, Header, Query
from sqlalchemy.orm import Session
from database import get_session
from utils import create_logger
from services import TransactionService
from schemas import Context, Pagination

transaction_router = APIRouter()

logger = create_logger(__name__)


@transaction_router.get("/metrics")
def fetch_transaction_metrics(
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Fetch transactions route handler."""

    context = Context(
        tenant_id=tenant_id,
    )

    try:
        transaction_service = TransactionService(db)

        metrics = transaction_service.fetch_transaction_metrics(context)

        return responses.JSONResponse(
            content={"message": "success", "metrics": metrics}, status_code=200
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_transaction_metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch transaction metrics failed.")


@transaction_router.get("/account/{id}")
def fetch_customer_transactions(
    id: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Fetch transactions route handler."""

    context = Context(
        tenant_id=tenant_id,
    )

    pagination = Pagination(limit=limit, page=page)

    try:
        transaction_service = TransactionService(db)

        transactions = transaction_service.fetch_account_transactions(
            id, context, pagination
        )

        return responses.JSONResponse(
            content={
                "message": "success",
                "transactions": [t.to_dict() for t in transactions],
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch transactions failed.")


@transaction_router.get("/account-number/{account_number}")
def fetch_customer_account_number_transactions(
    account_number: str,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Fetch transactions route handler."""

    context = Context(
        tenant_id=tenant_id,
    )

    pagination = Pagination(limit=limit, page=page)

    try:
        transaction_service = TransactionService(db)

        transactions = transaction_service.fetch_account_number_transactions(
            account_number, context, pagination
        )

        return responses.JSONResponse(
            content={
                "message": "success",
                "transactions": [t.to_dict() for t in transactions],
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch transactions failed.")


@transaction_router.get("/")
def fetch_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Fetch transactions route handler."""

    context = Context(tenant_id=tenant_id)

    pagination = Pagination(limit=limit, page=page)

    try:
        transaction_service = TransactionService(db)

        transactions = transaction_service.fetch_transactions(context, pagination)

        return responses.JSONResponse(
            content={
                "message": "success",
                "transactions": [t.to_dict() for t in transactions],
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch transactions failed.")


@transaction_router.get("/{id}")
def fetch_transaction_by_id(
    id: str,
    db: Session = Depends(get_session),
    tenant_id: str = Header(..., alias="x-tenant-id"),
):
    """Fetch transaction by id route handler."""

    context = Context(tenant_id=tenant_id)

    try:
        transaction_service = TransactionService(db)

        transaction = transaction_service.fetch_transaction_by_id(id, context)

        return responses.JSONResponse(
            content={
                "message": "success",
                "transaction": transaction.to_dict() if transaction else None,
            },
            status_code=200,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during fetch_transaction_by_id: {str(e)}")
        raise HTTPException(status_code=500, detail="Fetch transaction failed.")
