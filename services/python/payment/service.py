import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---

class PaymentServiceError(HTTPException):
    """Base exception for payment service errors."""
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(status_code=status_code, detail=detail)

class PaymentNotFound(PaymentServiceError):
    def __init__(self, payment_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment with ID {payment_id} not found."
        )

class PaymentMethodNotFound(PaymentServiceError):
    def __init__(self, method_id: int) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment Method with ID {method_id} not found."
        )

class PaymentProcessingError(PaymentServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {detail}"
        )

class InvalidPaymentStatus(PaymentServiceError):
    def __init__(self, current_status: str, required_status: str) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment is in status '{current_status}'. Required status is '{required_status}'."
        )

# --- Payment Methods Service ---

def create_payment_method(db: Session, method_in: schemas.PaymentMethodCreate) -> models.PaymentMethod:
    """Creates a new payment method for a user."""
    logger.info(f"Creating payment method for user_id: {method_in.user_id}")
    
    # Check for existing token to prevent duplicates (basic check)
    existing_method = db.query(models.PaymentMethod).filter(
        models.PaymentMethod.user_id == method_in.user_id,
        models.PaymentMethod.token == method_in.token
    ).first()
    
    if existing_method:
        raise PaymentServiceError(detail="Payment method with this token already exists for this user.", status_code=status.HTTP_409_CONFLICT)

    db_method = models.PaymentMethod(**method_in.model_dump())
    
    # Ensure only one default method per user
    if db_method.is_default:
        db.query(models.PaymentMethod).filter(
            models.PaymentMethod.user_id == method_in.user_id,
            models.PaymentMethod.is_default == True
        ).update({"is_default": False})

    db.add(db_method)
    db.commit()
    db.refresh(db_method)
    logger.info(f"Payment method created with ID: {db_method.id}")
    return db_method

def get_payment_method(db: Session, method_id: int) -> models.PaymentMethod:
    """Retrieves a single payment method by ID."""
    method = db.query(models.PaymentMethod).filter(models.PaymentMethod.id == method_id).first()
    if not method:
        raise PaymentMethodNotFound(method_id)
    return method

def get_payment_methods_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> List[models.PaymentMethod]:
    """Retrieves all payment methods for a given user."""
    return db.query(models.PaymentMethod).filter(models.PaymentMethod.user_id == user_id).offset(skip).limit(limit).all()

def update_payment_method(db: Session, method_id: int, method_update: schemas.PaymentMethodUpdate) -> models.PaymentMethod:
    """Updates an existing payment method."""
    db_method = get_payment_method(db, method_id)
    
    update_data = method_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_method, key, value)

    # Handle default status change
    if 'is_default' in update_data and update_data['is_default']:
        db.query(models.PaymentMethod).filter(
            models.PaymentMethod.user_id == db_method.user_id,
            models.PaymentMethod.is_default == True,
            models.PaymentMethod.id != method_id
        ).update({"is_default": False})

    db.commit()
    db.refresh(db_method)
    logger.info(f"Payment method updated with ID: {db_method.id}")
    return db_method

def delete_payment_method(db: Session, method_id: int) -> None:
    """Deletes a payment method."""
    db_method = get_payment_method(db, method_id)
    db.delete(db_method)
    db.commit()
    logger.info(f"Payment method deleted with ID: {method_id}")

# --- Payments Service ---

def create_payment(db: Session, payment_in: schemas.PaymentCreate) -> models.Payment:
    """Creates a new payment record and attempts to process it."""
    logger.info(f"Initiating payment for external_id: {payment_in.external_id}, amount: {payment_in.amount}")

    # 1. Check for duplicate external_id
    if db.query(models.Payment).filter(models.Payment.external_id == payment_in.external_id).first():
        raise PaymentServiceError(detail=f"Payment with external_id {payment_in.external_id} already exists.", status_code=status.HTTP_409_CONFLICT)

    # 2. Create the initial payment record (Status: PENDING)
    db_payment = models.Payment(**payment_in.model_dump(exclude_none=True))
    db.add(db_payment)
    db.flush() # Flush to get the ID for the transaction

    # 3. Process the payment (Simulated external call)
    try:
        # In a real application, this would call an external payment gateway (e.g., Stripe, PayPal)
        processor_id = f"proc_{db_payment.id}_{db_payment.external_id}" # Simulated processor ID
        
        # Simulate success or failure based on some logic (e.g., amount > 1000 fails)
        if db_payment.amount > 10000:
            raise PaymentProcessingError("Transaction declined by simulated processor due to high amount.")

        # Simulate successful transaction
        transaction_status = "success"
        payment_status = models.PaymentStatus.SUCCESS
        error_code = None
        error_message = None
        
    except PaymentProcessingError as e:
        transaction_status = "failed"
        payment_status = models.PaymentStatus.FAILED
        error_code = "PROC_DECLINED"
        error_message = str(e.detail)
        logger.error(f"Payment processing failed for {db_payment.external_id}: {error_message}")
    except Exception as e:
        transaction_status = "failed"
        payment_status = models.PaymentStatus.FAILED
        processor_id = f"proc_error_{db_payment.id}"
        error_code = "INTERNAL_ERROR"
        error_message = str(e)
        logger.error(f"Internal error during payment processing for {db_payment.external_id}: {error_message}")

    # 4. Create the transaction record
    db_transaction = models.Transaction(
        payment_id=db_payment.id,
        processor_transaction_id=processor_id,
        transaction_type="charge",
        amount=db_payment.amount,
        currency=db_payment.currency,
        status=transaction_status,
        error_code=error_code,
        error_message=error_message
    )
    db.add(db_transaction)

    # 5. Update the payment status
    db_payment.status = payment_status
    
    db.commit()
    db.refresh(db_payment)
    logger.info(f"Payment {db_payment.id} finalized with status: {db_payment.status.value}")
    return db_payment

def get_payment(db: Session, payment_id: int) -> models.Payment:
    """Retrieves a single payment by ID."""
    payment = db.query(models.Payment).filter(models.Payment.id == payment_id).first()
    if not payment:
        raise PaymentNotFound(payment_id)
    return payment

def get_payments(db: Session, skip: int = 0, limit: int = 100) -> List[models.Payment]:
    """Retrieves a list of payments."""
    return db.query(models.Payment).offset(skip).limit(limit).all()

def update_payment_status(db: Session, payment_id: int, status_update: schemas.PaymentUpdate) -> models.Payment:
    """Updates the status of an existing payment."""
    db_payment = get_payment(db, payment_id)
    
    update_data = status_update.model_dump(exclude_unset=True)
    if 'status' in update_data:
        new_status = update_data['status']
        if db_payment.status == models.PaymentStatus.SUCCESS and new_status not in [models.PaymentStatus.REFUNDED, models.PaymentStatus.FAILED]:
            raise InvalidPaymentStatus(db_payment.status.value, "REFUNDED or FAILED")
        
        db_payment.status = new_status
        logger.info(f"Payment {payment_id} status updated to: {new_status.value}")

    if 'description' in update_data:
        db_payment.description = update_data['description']

    db.commit()
    db.refresh(db_payment)
    return db_payment

def refund_payment(db: Session, payment_id: int, refund_amount: float) -> models.Payment:
    """Processes a refund for a payment."""
    db_payment = get_payment(db, payment_id)

    if db_payment.status != models.PaymentStatus.SUCCESS:
        raise InvalidPaymentStatus(db_payment.status.value, "SUCCESS")

    if refund_amount <= 0 or refund_amount > db_payment.amount:
        raise PaymentServiceError(detail="Invalid refund amount.")

    logger.info(f"Initiating refund for payment {payment_id} with amount: {refund_amount}")

    # 1. Process the refund (Simulated external call)
    try:
        # In a real application, this would call an external payment gateway's refund API
        processor_id = f"refund_proc_{db_payment.id}_{db_payment.external_id}" # Simulated processor ID
        
        # Simulate successful refund
        transaction_status = "success"
        
    except Exception as e:
        transaction_status = "failed"
        processor_id = f"refund_error_{db_payment.id}"
        error_code = "REFUND_ERROR"
        error_message = str(e)
        logger.error(f"Refund processing failed for {db_payment.external_id}: {error_message}")
        raise PaymentProcessingError(f"Refund failed: {error_message}")

    # 2. Create the transaction record
    db_transaction = models.Transaction(
        payment_id=db_payment.id,
        processor_transaction_id=processor_id,
        transaction_type="refund",
        amount=-refund_amount, # Negative amount for refund
        currency=db_payment.currency,
        status=transaction_status,
        error_code=error_code if transaction_status == "failed" else None,
        error_message=error_message if transaction_status == "failed" else None
    )
    db.add(db_transaction)

    # 3. Update the payment status if fully refunded (simple logic)
    # A more complex system would track total refunded amount
    if refund_amount == db_payment.amount:
        db_payment.status = models.PaymentStatus.REFUNDED
    
    db.commit()
    db.refresh(db_payment)
    logger.info(f"Refund for payment {db_payment.id} finalized.")
    return db_payment

def delete_payment(db: Session, payment_id: int) -> None:
    """Deletes a payment and its associated transactions."""
    db_payment = get_payment(db, payment_id)
    
    # In a real system, you might only allow deletion of CANCELED or FAILED payments
    if db_payment.status == models.PaymentStatus.SUCCESS:
        raise InvalidPaymentStatus(db_payment.status.value, "CANCELED or FAILED to delete")

    # Delete associated transactions first
    db.query(models.Transaction).filter(models.Transaction.payment_id == payment_id).delete()
    
    # Delete the payment
    db.delete(db_payment)
    db.commit()
    logger.info(f"Payment and associated transactions deleted for ID: {payment_id}")