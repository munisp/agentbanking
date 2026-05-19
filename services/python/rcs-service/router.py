import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from . import models
from .config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rcs-campaigns",
    tags=["RCS Campaigns"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def log_activity(
    db: Session, 
    campaign_id: int, 
    activity_type: str, 
    details: Optional[str] = None, 
    user_id: Optional[str] = "system"
):
    """
    Logs an activity for a specific RCS Campaign.
    """
    log_entry = models.RCSCampaignActivityLog(
        campaign_id=campaign_id,
        activity_type=activity_type,
        details=details,
        user_id=user_id
    )
    db.add(log_entry)
    # Note: The log will be committed with the main transaction

# --- CRUD Endpoints ---

@router.post(
    "/", 
    response_model=models.RCSCampaignResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new RCS Campaign"
)
def create_campaign(
    campaign: models.RCSCampaignCreate, 
    db: Session = Depends(get_db)
):
    """
    Creates a new RCS Campaign in the database.
    
    Raises:
    - 409 Conflict: If a campaign with the same name already exists.
    """
    logger.info(f"Attempting to create new campaign: {campaign.name}")
    
    db_campaign = models.RCSCampaign(**campaign.model_dump())
    
    try:
        db.add(db_campaign)
        db.flush() # Flush to get the ID before commit
        
        # Log creation activity
        log_activity(db, db_campaign.id, "created", f"Campaign created with initial status: {db_campaign.status}")
        
        db.commit()
        db.refresh(db_campaign)
        logger.info(f"Campaign created successfully with ID: {db_campaign.id}")
        return db_campaign
    except IntegrityError:
        db.rollback()
        logger.warning(f"Creation failed: Campaign name '{campaign.name}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign with name '{campaign.name}' already exists."
        )

@router.get(
    "/{campaign_id}", 
    response_model=models.RCSCampaignResponse,
    summary="Get a specific RCS Campaign by ID"
)
def read_campaign(
    campaign_id: int, 
    db: Session = Depends(get_db)
):
    """
    Retrieves a single RCS Campaign by its unique ID.
    
    Raises:
    - 404 Not Found: If no campaign with the given ID exists.
    """
    db_campaign = db.get(models.RCSCampaign, campaign_id)
    if db_campaign is None:
        logger.warning(f"Read failed: Campaign ID {campaign_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="RCS Campaign not found"
        )
    return db_campaign

@router.get(
    "/", 
    response_model=List[models.RCSCampaignResponse],
    summary="List all RCS Campaigns"
)
def list_campaigns(
    skip: int = 0, 
    limit: int = 100, 
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of RCS Campaigns with optional filtering and pagination.
    """
    stmt = select(models.RCSCampaign)
    
    if status_filter:
        stmt = stmt.where(models.RCSCampaign.status == status_filter)
        
    campaigns = db.scalars(stmt.offset(skip).limit(limit)).all()
    return campaigns

@router.put(
    "/{campaign_id}", 
    response_model=models.RCSCampaignResponse,
    summary="Update an existing RCS Campaign"
)
def update_campaign(
    campaign_id: int, 
    campaign_update: models.RCSCampaignUpdate, 
    db: Session = Depends(get_db)
):
    """
    Updates an existing RCS Campaign with the provided data.
    
    Raises:
    - 404 Not Found: If no campaign with the given ID exists.
    - 409 Conflict: If the new name conflicts with an existing campaign.
    """
    db_campaign = db.get(models.RCSCampaign, campaign_id)
    if db_campaign is None:
        logger.warning(f"Update failed: Campaign ID {campaign_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="RCS Campaign not found"
        )

    update_data = campaign_update.model_dump(exclude_unset=True)
    
    # Check for name uniqueness if name is being updated
    if "name" in update_data and update_data["name"] != db_campaign.name:
        existing_campaign = db.scalar(
            select(models.RCSCampaign).where(models.RCSCampaign.name == update_data["name"])
        )
        if existing_campaign and existing_campaign.id != campaign_id:
            logger.warning(f"Update failed: Campaign name '{update_data['name']}' already exists.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Campaign with name '{update_data['name']}' already exists."
            )

    # Apply updates
    for key, value in update_data.items():
        setattr(db_campaign, key, value)

    try:
        db.add(db_campaign)
        
        # Log update activity
        log_activity(db, campaign_id, "updated", f"Campaign details updated. Fields changed: {', '.join(update_data.keys())}")
        
        db.commit()
        db.refresh(db_campaign)
        logger.info(f"Campaign ID {campaign_id} updated successfully.")
        return db_campaign
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Update failed due to integrity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database integrity error during update."
        )

@router.delete(
    "/{campaign_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an RCS Campaign"
)
def delete_campaign(
    campaign_id: int, 
    db: Session = Depends(get_db)
):
    """
    Deletes an RCS Campaign by its ID.
    
    Raises:
    - 404 Not Found: If no campaign with the given ID exists.
    """
    db_campaign = db.get(models.RCSCampaign, campaign_id)
    if db_campaign is None:
        logger.warning(f"Delete failed: Campaign ID {campaign_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="RCS Campaign not found"
        )

    db.delete(db_campaign)
    
    # Log deletion activity (log must be added before commit, but the campaign object is still valid)
    # Note: Since activity logs are cascade-deleted, this log is for external tracking, 
    # but for this simple implementation, we'll just commit the delete.
    # In a real system, we might log to a separate, non-cascading table.
    # For now, we'll rely on the cascade delete to keep the DB clean.
    
    db.commit()
    logger.info(f"Campaign ID {campaign_id} deleted successfully.")
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{campaign_id}/launch",
    response_model=models.RCSCampaignResponse,
    summary="Launch an RCS Campaign (Change status to 'active')"
)
def launch_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Changes the status of a campaign to 'active', simulating a launch.
    
    Raises:
    - 404 Not Found: If no campaign with the given ID exists.
    - 400 Bad Request: If the campaign is already active or completed.
    """
    db_campaign = db.get(models.RCSCampaign, campaign_id)
    if db_campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="RCS Campaign not found"
        )

    if db_campaign.status in ["active", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign is already in status '{db_campaign.status}' and cannot be launched."
        )

    # Business logic for launching (e.g., validation, external API calls) would go here
    
    db_campaign.status = "active"
    db.add(db_campaign)
    
    log_activity(db, campaign_id, "status_change", "Campaign status changed to 'active' (Launched)")
    
    db.commit()
    db.refresh(db_campaign)
    logger.info(f"Campaign ID {campaign_id} launched (status set to 'active').")
    return db_campaign

@router.post(
    "/{campaign_id}/archive",
    response_model=models.RCSCampaignResponse,
    summary="Archive an RCS Campaign"
)
def archive_campaign(
    campaign_id: int,
    db: Session = Depends(get_db)
):
    """
    Sets the `is_archived` flag to True for a campaign.
    
    Raises:
    - 404 Not Found: If no campaign with the given ID exists.
    """
    db_campaign = db.get(models.RCSCampaign, campaign_id)
    if db_campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="RCS Campaign not found"
        )

    if db_campaign.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign is already archived."
        )

    db_campaign.is_archived = True
    db.add(db_campaign)
    
    log_activity(db, campaign_id, "archived", "Campaign marked as archived.")
    
    db.commit()
    db.refresh(db_campaign)
    logger.info(f"Campaign ID {campaign_id} archived.")
    return db_campaign
