from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from . import schemas, service, database, models
from .config import settings

# --- Dependencies ---

def get_db() -> None:
    """Dependency for database session."""
    yield from database.get_db()

def verify_api_key(x_api_key: str = Header(..., alias=settings.API_KEY_HEADER)) -> None:
    """Basic API Key security dependency."""
    if x_api_key != settings.API_KEY_VALUE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return x_api_key

# --- Routers ---

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    dependencies=[Depends(verify_api_key)],
    responses={404: {"description": "Not found"}},
)

method_router = APIRouter(
    prefix="/methods",
    tags=["Payment Methods"],
    dependencies=[Depends(verify_api_key)],
    responses={404: {"description": "Not found"}},
)

# --- Payment Methods Endpoints ---

@method_router.post(
    "/", 
    response_model=schemas.PaymentMethodRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment method"
)
def create_method(
    method: schemas.PaymentMethodCreate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Registers a new tokenized payment method for a user.
    """
    try:
        return service.create_payment_method(db=db, method_in=method)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@method_router.get(
    "/{method_id}", 
    response_model=schemas.PaymentMethodRead,
    summary="Get a payment method by ID"
)
def read_method(
    method_id: int, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves details of a specific payment method.
    """
    try:
        return service.get_payment_method(db=db, method_id=method_id)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@method_router.get(
    "/user/{user_id}", 
    response_model=List[schemas.PaymentMethodRead],
    summary="List payment methods for a user"
)
def list_methods_by_user(
    user_id: int,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves a list of all payment methods associated with a given user ID.
    """
    return service.get_payment_methods_by_user(db=db, user_id=user_id, skip=skip, limit=limit)

@method_router.patch(
    "/{method_id}", 
    response_model=schemas.PaymentMethodRead,
    summary="Update a payment method"
)
def update_method(
    method_id: int, 
    method_update: schemas.PaymentMethodUpdate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Updates details of an existing payment method, such as setting it as default.
    """
    try:
        return service.update_payment_method(db=db, method_id=method_id, method_update=method_update)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@method_router.delete(
    "/{method_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment method"
)
def delete_method(
    method_id: int, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deletes a payment method from the system.
    """
    try:
        service.delete_payment_method(db=db, method_id=method_id)
        return {"ok": True}
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# --- Payment Endpoints ---

@router.post(
    "/", 
    response_model=schemas.PaymentRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create and process a new payment"
)
def create_payment_route(
    payment: schemas.PaymentCreate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Initiates a new payment. This endpoint creates the payment record and
    simulates the processing of the transaction.
    """
    try:
        return service.create_payment(db=db, payment_in=payment)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get(
    "/{payment_id}", 
    response_model=schemas.PaymentRead,
    summary="Get a payment by ID"
)
def read_payment(
    payment_id: int, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves the full details of a payment, including associated transactions.
    """
    try:
        return service.get_payment(db=db, payment_id=payment_id)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get(
    "/", 
    response_model=List[schemas.PaymentRead],
    summary="List all payments"
)
def list_payments(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
) -> None:
    """
    Retrieves a paginated list of all payments.
    """
    return service.get_payments(db=db, skip=skip, limit=limit)

@router.patch(
    "/{payment_id}/status", 
    response_model=schemas.PaymentRead,
    summary="Update payment status (e.g., for webhooks)"
)
def update_payment_status_route(
    payment_id: int, 
    status_update: schemas.PaymentUpdate, 
    db: Session = Depends(get_db)
) -> None:
    """
    Updates the status of a payment. This is typically used by webhooks
    from the payment processor.
    """
    try:
        return service.update_payment_status(db=db, payment_id=payment_id, status_update=status_update)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.post(
    "/{payment_id}/refund", 
    response_model=schemas.PaymentRead,
    summary="Process a refund for a payment"
)
def refund_payment_route(
    payment_id: int, 
    refund_amount: float, 
    db: Session = Depends(get_db)
) -> None:
    """
    Initiates a refund for a successful payment.
    """
    try:
        return service.refund_payment(db=db, payment_id=payment_id, refund_amount=refund_amount)
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.delete(
    "/{payment_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a payment"
)
def delete_payment_route(
    payment_id: int, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deletes a payment and its associated transactions. Only allowed for
    CANCELED or FAILED payments.
    """
    try:
        service.delete_payment(db=db, payment_id=payment_id)
        return {"ok": True}
    except service.PaymentServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

# Combine routers
router.include_router(method_router)