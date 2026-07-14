import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from . import models, config
from .models import Product, ActivityLog
from .models import ProductCreate, ProductUpdate, ProductResponse, ActivityLogResponse

# --- Configuration and Setup ---

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def log_activity(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int,
    details: Optional[str] = None,
    product_id: Optional[int] = None,
    user_id: Optional[str] = "system",
):
    """
    Creates an entry in the activity log table.
    """
    log_entry = ActivityLog(
        service_name=config.get_settings().SERVICE_NAME,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details,
        product_id=product_id,
        user_id=user_id,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    logger.info(f"Activity logged: {action} on {entity_type}:{entity_id}")


def get_product_or_404(db: Session, product_id: int) -> Product:
    """
    Helper function to fetch a product by ID or raise a 404 error.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        logger.warning(f"Product with ID {product_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    return product

# --- Product CRUD Endpoints ---

@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    description="Creates a new product entry in the database.",
)
def create_product(
    product: ProductCreate, db: Session = Depends(config.get_db)
):
    """
    Creates a new product with the provided details.
    """
    logger.info(f"Attempting to create new product: {product.name}")
    
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    log_activity(
        db,
        action="CREATE",
        entity_type="Product",
        entity_id=db_product.id,
        details=f"Product '{db_product.name}' created.",
        product_id=db_product.id,
    )
    
    logger.info(f"Product created successfully with ID: {db_product.id}")
    return db_product


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a product by ID",
    description="Retrieves the details of a single product by its unique ID.",
)
def read_product(
    product_id: int, db: Session = Depends(config.get_db)
):
    """
    Retrieves a product by its ID. Raises 404 if not found.
    """
    return get_product_or_404(db, product_id)


@router.get(
    "/",
    response_model=List[ProductResponse],
    summary="List all products",
    description="Retrieves a list of all products, with optional pagination and filtering.",
)
def list_products(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(config.get_db),
):
    """
    Lists products, allowing for skipping, limiting, and filtering by active status.
    """
    query = db.query(Product)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
        
    products = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(products)} products (skip={skip}, limit={limit}, active={is_active}).")
    return products


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update an existing product",
    description="Updates the details of an existing product by its ID.",
)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: Session = Depends(config.get_db),
):
    """
    Updates an existing product. Only provided fields are modified.
    """
    db_product = get_product_or_404(db, product_id)
    
    update_data = product_in.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )

    for key, value in update_data.items():
        setattr(db_product, key, value)

    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    log_activity(
        db,
        action="UPDATE",
        entity_type="Product",
        entity_id=db_product.id,
        details=f"Product '{db_product.name}' updated with fields: {', '.join(update_data.keys())}.",
        product_id=db_product.id,
    )
    
    logger.info(f"Product ID {product_id} updated successfully.")
    return db_product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product",
    description="Deletes a product by its ID. Note: This is a hard delete.",
)
def delete_product(
    product_id: int, db: Session = Depends(config.get_db)
):
    """
    Deletes a product from the database.
    """
    db_product = get_product_or_404(db, product_id)
    product_name = db_product.name
    
    db.delete(db_product)
    db.commit()
    
    log_activity(
        db,
        action="DELETE",
        entity_type="Product",
        entity_id=product_id,
        details=f"Product '{product_name}' deleted.",
        product_id=product_id,
    )
    
    logger.info(f"Product ID {product_id} deleted successfully.")
    return


# --- Business-Specific Endpoints ---

class StockUpdate(models.BaseModel):
    """Schema for updating product stock."""
    quantity_change: int = Field(..., description="The amount to add (positive) or subtract (negative) from the current stock.")


@router.patch(
    "/{product_id}/stock",
    response_model=ProductResponse,
    summary="Update product stock quantity",
    description="Adjusts the stock quantity of a product by a specified amount.",
)
def update_product_stock(
    product_id: int,
    stock_update: StockUpdate,
    db: Session = Depends(config.get_db),
):
    """
    Updates the stock quantity of a product. Ensures stock does not drop below zero.
    """
    db_product = get_product_or_404(db, product_id)
    
    new_stock = db_product.stock_quantity + stock_update.quantity_change
    
    if new_stock < 0:
        logger.error(f"Stock update failed for product {product_id}: resulting stock {new_stock} is negative.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stock change of {stock_update.quantity_change} would result in negative stock ({new_stock}). Operation aborted.",
        )

    old_stock = db_product.stock_quantity
    db_product.stock_quantity = new_stock
    
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    log_activity(
        db,
        action="STOCK_CHANGE",
        entity_type="Product",
        entity_id=db_product.id,
        details=f"Stock changed from {old_stock} to {new_stock}. Change: {stock_update.quantity_change}.",
        product_id=db_product.id,
    )
    
    logger.info(f"Product ID {product_id} stock updated from {old_stock} to {new_stock}.")
    return db_product


# --- Activity Log Endpoints ---

@router.get(
    "/logs",
    response_model=List[ActivityLogResponse],
    summary="List all activity logs",
    description="Retrieves a list of all service activity logs, ordered by creation time.",
    tags=["activity-logs"],
)
def list_activity_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(config.get_db),
):
    """
    Lists activity logs with pagination.
    """
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    logger.info(f"Retrieved {len(logs)} activity logs.")
    return logs
