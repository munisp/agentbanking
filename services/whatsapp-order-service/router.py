import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from . import models
from .config import get_db, logger

# --- Router Initialization ---
router = APIRouter(
    prefix="/orders",
    tags=["whatsapp-orders"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Database Operations) ---

def create_activity_log(db: Session, order_id: uuid.UUID, activity_type: str, description: str):
    """Creates a new activity log entry for a given order."""
    activity = models.WhatsAppOrderActivity(
        order_id=order_id,
        activity_type=activity_type,
        description=description,
    )
    db.add(activity)
    # Note: The activity will be committed with the main transaction.

def get_order_by_id(db: Session, order_id: uuid.UUID):
    """Retrieves a WhatsAppOrder by its ID, including activities."""
    return db.query(models.WhatsAppOrder).options(joinedload(models.WhatsAppOrder.activities)).filter(models.WhatsAppOrder.id == order_id).first()

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.WhatsAppOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new WhatsApp Order",
    description="Creates a new order initiated via WhatsApp, logging the creation activity."
)
def create_whatsapp_order(
    order: models.WhatsAppOrderCreate, db: Session = Depends(get_db)
):
    """
    Handles the creation of a new WhatsApp order.
    """
    logger.info(f"Attempting to create new order for user: {order.whatsapp_user_id}")
    
    db_order = models.WhatsAppOrder(**order.model_dump())
    
    # Log the creation activity
    create_activity_log(
        db, 
        db_order.id, 
        "ORDER_CREATED", 
        f"Order created with total amount {db_order.total_amount} {db_order.currency}."
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    logger.info(f"Successfully created order with ID: {db_order.id}")
    return db_order

@router.get(
    "/{order_id}",
    response_model=models.WhatsAppOrderResponse,
    summary="Get a specific WhatsApp Order",
    description="Retrieves the details of a single WhatsApp order by its unique ID, including its activity history."
)
def read_whatsapp_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves a single WhatsApp order by ID.
    """
    db_order = get_order_by_id(db, order_id)
    if db_order is None:
        logger.warning(f"Order not found with ID: {order_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp Order not found")
    return db_order

@router.get(
    "/",
    response_model=List[models.WhatsAppOrderResponse],
    summary="List all WhatsApp Orders",
    description="Retrieves a list of all WhatsApp orders, with optional pagination and filtering by user ID or status."
)
def list_whatsapp_orders(
    whatsapp_user_id: Optional[str] = None,
    status_filter: Optional[models.OrderStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Lists WhatsApp orders with optional filtering and pagination.
    """
    query = db.query(models.WhatsAppOrder)
    
    if whatsapp_user_id:
        query = query.filter(models.WhatsAppOrder.whatsapp_user_id == whatsapp_user_id)
    
    if status_filter:
        query = query.filter(models.WhatsAppOrder.order_status == status_filter)
        
    orders = query.offset(skip).limit(limit).all()
    
    return orders

@router.put(
    "/{order_id}",
    response_model=models.WhatsAppOrderResponse,
    summary="Update a WhatsApp Order",
    description="Updates the details of an existing WhatsApp order. Note: Use the dedicated PATCH endpoint for status changes."
)
def update_whatsapp_order(
    order_id: uuid.UUID,
    order_update: models.WhatsAppOrderUpdate,
    db: Session = Depends(get_db),
):
    """
    Updates an existing WhatsApp order.
    """
    db_order = get_order_by_id(db, order_id)
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp Order not found")

    update_data = order_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    update_description_parts = []
    for key, value in update_data.items():
        setattr(db_order, key, value)
        update_description_parts.append(f"{key} updated to {value}")

    # Log the update activity
    create_activity_log(
        db, 
        order_id, 
        "ORDER_UPDATED", 
        "General order details updated: " + ", ".join(update_description_parts)
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    logger.info(f"Successfully updated order with ID: {order_id}")
    return db_order

@router.delete(
    "/{order_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a WhatsApp Order",
    description="Deletes a WhatsApp order by its unique ID. This action is irreversible."
)
def delete_whatsapp_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Deletes a WhatsApp order.
    """
    db_order = db.query(models.WhatsAppOrder).filter(models.WhatsAppOrder.id == order_id).first()
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp Order not found")

    db.delete(db_order)
    db.commit()
    
    logger.info(f"Successfully deleted order with ID: {order_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.patch(
    "/{order_id}/status",
    response_model=models.WhatsAppOrderResponse,
    summary="Update Order Status",
    description="Updates the status of a WhatsApp order and logs the status change activity."
)
def update_order_status(
    order_id: uuid.UUID,
    new_status: models.OrderStatus,
    db: Session = Depends(get_db),
):
    """
    Updates the status of an order and logs the change.
    """
    db_order = get_order_by_id(db, order_id)
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="WhatsApp Order not found")

    old_status = db_order.order_status
    if old_status == new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order is already in status: {new_status}")

    db_order.order_status = new_status
    
    # Log the status change activity
    create_activity_log(
        db, 
        order_id, 
        "STATUS_CHANGE", 
        f"Order status changed from {old_status.value} to {new_status.value}."
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    logger.info(f"Order {order_id} status changed to: {new_status.value}")
    return db_order
