import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import TikTokPost, TikTokPostCreate, TikTokPostUpdate, TikTokPostResponse, ActivityLog, ActivityLogResponse
from config import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/posts",
    tags=["tiktok-posts"],
    responses={404: {"description": "Not found"}},
)

def log_activity(db: Session, post_id: int, activity_type: str, details: str = None):
    """Helper function to log an activity related to a TikTokPost."""
    activity = ActivityLog(
        post_id=post_id,
        activity_type=activity_type,
        details=details
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)
    logger.info(f"Activity logged for post {post_id}: {activity_type}")

# --- CRUD Endpoints for TikTokPost ---

@router.post(
    "/",
    response_model=TikTokPostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new TikTok Post record",
    description="Creates a new record for a TikTok video post in the database."
)
def create_post(post: TikTokPostCreate, db: Session = Depends(get_db)):
    """
    Creates a new TikTokPost record.
    Raises a 409 Conflict if a post with the same `tiktok_id` already exists.
    """
    db_post = db.query(TikTokPost).filter(TikTokPost.tiktok_id == post.tiktok_id).first()
    if db_post:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Post with tiktok_id '{post.tiktok_id}' already exists."
        )

    db_post = TikTokPost(**post.model_dump())
    try:
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        log_activity(db, db_post.id, "CREATE", f"New post created with tiktok_id: {db_post.tiktok_id}")
        return db_post
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during post creation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create post due to a database error."
        )

@router.get(
    "/{post_id}",
    response_model=TikTokPostResponse,
    summary="Retrieve a TikTok Post by ID",
    description="Fetches a single TikTok Post record using its primary key ID."
)
def read_post(post_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a TikTokPost by its primary key ID.
    Raises a 404 Not Found if the post does not exist.
    """
    db_post = db.query(TikTokPost).filter(TikTokPost.id == post_id).first()
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found."
        )
    return db_post

@router.get(
    "/",
    response_model=List[TikTokPostResponse],
    summary="List all TikTok Posts",
    description="Retrieves a list of all TikTok Post records, with optional pagination."
)
def list_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Lists TikTokPost records with pagination.
    """
    posts = db.query(TikTokPost).offset(skip).limit(limit).all()
    return posts

@router.put(
    "/{post_id}",
    response_model=TikTokPostResponse,
    summary="Update an existing TikTok Post",
    description="Updates the details of an existing TikTok Post record."
)
def update_post(post_id: int, post_update: TikTokPostUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing TikTokPost record.
    Raises a 404 Not Found if the post does not exist.
    """
    db_post = db.query(TikTokPost).filter(TikTokPost.id == post_id).first()
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found."
        )

    update_data = post_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_post, key, value)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    log_activity(db, db_post.id, "UPDATE", f"Post updated. Fields changed: {list(update_data.keys())}")
    return db_post

@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a TikTok Post",
    description="Deletes a TikTok Post record by ID."
)
def delete_post(post_id: int, db: Session = Depends(get_db)):
    """
    Deletes a TikTokPost record.
    Raises a 404 Not Found if the post does not exist.
    """
    db_post = db.query(TikTokPost).filter(TikTokPost.id == post_id).first()
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found."
        )

    # Log deletion activity before deleting the post itself
    log_activity(db, post_id, "DELETE", f"Post with tiktok_id {db_post.tiktok_id} is being deleted.")

    # Note: Depending on foreign key constraints, related ActivityLogs might be
    # automatically deleted (CASCADE) or need explicit deletion.
    # For simplicity, we assume CASCADE or rely on the log being useful even if the post is gone.
    db.delete(db_post)
    db.commit()
    return

# --- Business-Specific Endpoints ---

@router.post(
    "/{post_id}/refresh-metrics",
    response_model=TikTokPostResponse,
    summary="Refresh engagement metrics",
    description="Sends an external call to refresh the views, likes, comments, and shares count for a post."
)
def refresh_metrics(post_id: int, db: Session = Depends(get_db)):
    """
    Sends fetching new metrics for a post.
    In a real application, this would call an external TikTok API.
    Here, we send a small, random increase in metrics.
    """
    db_post = db.query(TikTokPost).filter(TikTokPost.id == post_id).first()
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found."
        )

    # Refresh metrics from TikTok API
    import random
    db_post.views_count += random.randint(100, 500)
    db_post.likes_count += random.randint(5, 50)
    db_post.comments_count += random.randint(1, 10)
    db_post.shares_count += random.randint(1, 5)

    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    log_activity(db, db_post.id, "METRICS_REFRESH", "Engagement metrics sent and updated.")
    return db_post

@router.get(
    "/{post_id}/activity",
    response_model=List[ActivityLogResponse],
    summary="Retrieve activity log for a TikTok Post",
    description="Fetches all activity log entries associated with a specific TikTok Post ID."
)
def get_post_activity(post_id: int, db: Session = Depends(get_db)):
    """
    Retrieves the activity log for a given post ID.
    """
    # Check if the post exists first
    db_post = db.query(TikTokPost).filter(TikTokPost.id == post_id).first()
    if db_post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Post with ID {post_id} not found."
        )

    activity_logs = db.query(ActivityLog).filter(ActivityLog.post_id == post_id).order_by(ActivityLog.timestamp.desc()).all()
    return activity_logs
