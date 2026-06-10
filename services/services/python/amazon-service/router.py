import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from . import models
from . import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/listings",
    tags=["amazon-service"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_listing_by_id(db: Session, listing_id: int) -> models.AmazonListing:
    """Helper function to fetch a listing by ID or raise 404."""
    listing = db.query(models.AmazonListing).filter(models.AmazonListing.id == listing_id).first()
    if not listing:
        logger.warning(f"Listing with ID {listing_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amazon Listing not found")
    return listing

def create_activity_log(db: Session, listing_id: int, action: str, details: Optional[str] = None):
    """Helper function to create an activity log entry."""
    log = models.ActivityLog(
        listing_id=listing_id,
        action=action,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info(f"Activity logged for listing {listing_id}: {action}")

# --- CRUD Endpoints ---

@router.post(
    "/",
    response_model=models.AmazonListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Amazon Listing",
    description="Creates a new product listing in the Amazon service database."
)
def create_listing(
    listing: models.AmazonListingCreate,
    db: Session = Depends(config.get_db)
):
    """
    Creates a new Amazon Listing with the provided details.

    - **asin**: Amazon Standard Identification Number (10 characters).
    - **title**: Product title.
    - **price**: Current price (must be greater than 0).
    - **currency**: Currency code (e.g., USD).
    - **seller_id**: Identifier of the seller.
    - **is_prime**: Whether the listing is Prime eligible.
    """
    # Check for existing ASIN
    db_listing = db.query(models.AmazonListing).filter(models.AmazonListing.asin == listing.asin).first()
    if db_listing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ASIN already registered")

    db_listing = models.AmazonListing(**listing.model_dump())
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    create_activity_log(db, db_listing.id, "CREATED", f"Initial listing created with price {db_listing.price}")
    logger.info(f"New listing created: ID {db_listing.id}, ASIN {db_listing.asin}")
    return db_listing

@router.get(
    "/{listing_id}",
    response_model=models.AmazonListingWithLogs,
    summary="Get a specific Amazon Listing with its activity logs",
    description="Retrieves a single Amazon Listing by its primary key ID, including all associated activity logs."
)
def read_listing(
    listing_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Retrieves a single Amazon Listing by ID.

    - **listing_id**: The primary key ID of the listing.
    """
    # Use joinedload to fetch logs in the same query
    listing = db.query(models.AmazonListing).options(joinedload(models.AmazonListing.logs)).filter(models.AmazonListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Amazon Listing not found")
    return listing

@router.get(
    "/",
    response_model=List[models.AmazonListingResponse],
    summary="List all Amazon Listings",
    description="Retrieves a list of all Amazon Listings, with optional filtering and pagination."
)
def list_listings(
    skip: int = Query(0, ge=0, description="Number of items to skip (for pagination)"),
    limit: int = Query(100, le=1000, description="Maximum number of items to return"),
    seller_id: Optional[str] = Query(None, description="Filter by seller ID"),
    is_prime: Optional[bool] = Query(None, description="Filter by Prime eligibility"),
    db: Session = Depends(config.get_db)
):
    """
    Retrieves a list of Amazon Listings.

    - **skip**: The number of records to skip for pagination.
    - **limit**: The maximum number of records to return.
    - **seller_id**: Optional filter to search for listings by a specific seller.
    - **is_prime**: Optional filter to search for Prime eligible listings.
    """
    query = db.query(models.AmazonListing)

    if seller_id:
        query = query.filter(models.AmazonListing.seller_id == seller_id)
    if is_prime is not None:
        query = query.filter(models.AmazonListing.is_prime == is_prime)

    listings = query.offset(skip).limit(limit).all()
    return listings

@router.put(
    "/{listing_id}",
    response_model=models.AmazonListingResponse,
    summary="Update an existing Amazon Listing",
    description="Updates one or more fields of an existing Amazon Listing by its ID."
)
def update_listing(
    listing_id: int,
    listing_update: models.AmazonListingUpdate,
    db: Session = Depends(config.get_db)
):
    """
    Updates an existing Amazon Listing.

    - **listing_id**: The primary key ID of the listing to update.
    - **listing_update**: The fields to update.
    """
    db_listing = get_listing_by_id(db, listing_id)

    update_data = listing_update.model_dump(exclude_unset=True)
    
    # Check for price change to log activity
    price_changed = False
    old_price = db_listing.price
    if "price" in update_data and update_data["price"] != old_price:
        price_changed = True

    for key, value in update_data.items():
        setattr(db_listing, key, value)

    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    if price_changed:
        create_activity_log(db, db_listing.id, "PRICE_UPDATE", f"Price changed from {old_price} to {db_listing.price}")
    else:
        create_activity_log(db, db_listing.id, "UPDATED", f"Listing updated. Fields: {', '.join(update_data.keys())}")

    logger.info(f"Listing updated: ID {db_listing.id}")
    return db_listing

@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Amazon Listing",
    description="Deletes an Amazon Listing by its ID and all associated activity logs."
)
def delete_listing(
    listing_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Deletes an Amazon Listing and its associated activity logs.

    - **listing_id**: The primary key ID of the listing to delete.
    """
    db_listing = get_listing_by_id(db, listing_id)

    # Delete associated activity logs first
    db.query(models.ActivityLog).filter(models.ActivityLog.listing_id == listing_id).delete()
    
    # Delete the listing
    db.delete(db_listing)
    db.commit()

    create_activity_log(db, listing_id, "DELETED", "Listing and all associated logs were removed.")
    logger.info(f"Listing deleted: ID {listing_id}")
    return

# --- Business-Specific Endpoints ---

@router.get(
    "/{listing_id}/logs",
    response_model=List[models.ActivityLogResponse],
    summary="Get activity logs for a specific listing",
    description="Retrieves the history of actions (e.g., price changes, updates) for a single Amazon Listing."
)
def get_listing_logs(
    listing_id: int,
    db: Session = Depends(config.get_db)
):
    """
    Retrieves all activity logs for a given listing ID.

    - **listing_id**: The primary key ID of the listing.
    """
    # Ensure the listing exists
    get_listing_by_id(db, listing_id)
    
    logs = db.query(models.ActivityLog).filter(models.ActivityLog.listing_id == listing_id).order_by(models.ActivityLog.timestamp.desc()).all()
    return logs

@router.patch(
    "/{listing_id}/price",
    response_model=models.AmazonListingResponse,
    summary="Quickly update the price of a listing",
    description="A dedicated endpoint for updating only the price of an Amazon Listing, which automatically logs the price change."
)
def update_listing_price(
    listing_id: int,
    new_price: float = Query(..., gt=0, description="The new price for the listing"),
    db: Session = Depends(config.get_db)
):
    """
    Updates the price of an existing Amazon Listing.

    - **listing_id**: The primary key ID of the listing to update.
    - **new_price**: The new price value.
    """
    db_listing = get_listing_by_id(db, listing_id)
    
    old_price = db_listing.price
    if old_price == new_price:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New price is the same as the current price")

    db_listing.price = new_price
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)

    create_activity_log(db, db_listing.id, "PRICE_UPDATE", f"Price changed from {old_price} to {db_listing.price} via dedicated endpoint")
    logger.info(f"Price updated for listing {db_listing.id}: {old_price} -> {new_price}")
    return db_listing
