import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from config import get_db
from models import Base, GameSession as GameSessionModel, ActivityLog as ActivityLogModel
from models import GameSessionCreate, GameSessionUpdate, GameSessionResponse, ActivityLogCreate, ActivityLogResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the router
router = APIRouter(
    prefix="/sessions",
    tags=["Game Sessions"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_session_or_404(db: Session, session_id: UUID) -> GameSessionModel:
    """
    Fetches a game session by ID, raising a 404 if not found.
    """
    session = db.query(GameSessionModel).options(joinedload(GameSessionModel.logs)).filter(GameSessionModel.id == session_id).first()
    if not session:
        logger.warning(f"GameSession with ID {session_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game session with ID {session_id} not found"
        )
    return session

# --- CRUD Endpoints for GameSession ---

@router.post(
    "/", 
    response_model=GameSessionResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new game session",
    description="Creates a new game session record in the database."
)
def create_session(session_in: GameSessionCreate, db: Session = Depends(get_db)):
    """
    Create a new game session.
    
    - **user_id**: The ID of the user starting the session.
    - **game_title**: The title of the game.
    - **start_time**: Optional start time (defaults to current time).
    """
    try:
        db_session = GameSessionModel(**session_in.model_dump(exclude_none=True))
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        logger.info(f"Created new GameSession with ID {db_session.id} for user {db_session.user_id}.")
        return db_session
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating game session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the game session."
        )

@router.get(
    "/", 
    response_model=List[GameSessionResponse],
    summary="List all game sessions",
    description="Retrieves a list of all game sessions, with optional filtering and pagination."
)
def list_sessions(
    user_id: UUID | None = None,
    game_title: str | None = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of game sessions.
    
    - **user_id**: Filter sessions by user ID.
    - **game_title**: Filter sessions by game title.
    - **skip**: Number of records to skip (for pagination).
    - **limit**: Maximum number of records to return.
    """
    query = db.query(GameSessionModel).options(joinedload(GameSessionModel.logs))
    
    if user_id:
        query = query.filter(GameSessionModel.user_id == user_id)
    if game_title:
        query = query.filter(GameSessionModel.game_title == game_title)
        
    sessions = query.offset(skip).limit(limit).all()
    return sessions

@router.get(
    "/{session_id}", 
    response_model=GameSessionResponse,
    summary="Get a specific game session",
    description="Retrieves the details of a single game session by its ID, including all associated activity logs."
)
def read_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Get a specific game session by ID.
    """
    return get_session_or_404(db, session_id)

@router.put(
    "/{session_id}", 
    response_model=GameSessionResponse,
    summary="Update an existing game session",
    description="Updates the details of an existing game session. Used primarily to set score, end time, and duration."
)
def update_session(session_id: UUID, session_in: GameSessionUpdate, db: Session = Depends(get_db)):
    """
    Update an existing game session.
    
    - **session_id**: The ID of the session to update.
    - **session_in**: The fields to update (score, end_time, duration_seconds, game_title).
    """
    db_session = get_session_or_404(db, session_id)
    
    update_data = session_in.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_session, key, value)
        
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    logger.info(f"Updated GameSession with ID {session_id}.")
    return db_session

@router.delete(
    "/{session_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a game session",
    description="Deletes a game session and all its associated activity logs."
)
def delete_session(session_id: UUID, db: Session = Depends(get_db)):
    """
    Delete a game session by ID.
    """
    db_session = get_session_or_404(db, session_id)
    
    db.delete(db_session)
    db.commit()
    logger.info(f"Deleted GameSession with ID {session_id}.")
    return {"ok": True}

# --- Business-Specific Endpoint for ActivityLog ---

@router.post(
    "/{session_id}/log", 
    response_model=ActivityLogResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Add an activity log entry to a session",
    description="Records a specific activity (e.g., achievement, level up) within a game session."
)
def add_activity_log(session_id: UUID, log_in: ActivityLogCreate, db: Session = Depends(get_db)):
    """
    Add an activity log entry to a specific game session.
    
    - **session_id**: The ID of the session to log the activity for.
    - **activity_type**: The type of activity (e.g., "ACHIEVEMENT_UNLOCKED").
    - **details**: Optional details about the activity.
    """
    # Check if the session exists
    db_session = get_session_or_404(db, session_id)
    
    try:
        db_log = ActivityLogModel(
            session_id=session_id,
            **log_in.model_dump(exclude_none=True)
        )
        db.add(db_log)
        db.commit()
        db.refresh(db_log)
        logger.info(f"Added activity log '{db_log.activity_type}' to session {session_id}.")
        return db_log
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding activity log to session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while adding the activity log."
        )

# --- Initialization Endpoint (Optional but good practice) ---

@router.post(
    "/initialize_db",
    status_code=status.HTTP_200_OK,
    summary="Initialize Database Tables",
    description="Creates all necessary database tables. Should be run once on application startup."
)
def initialize_db(db: Session = Depends(get_db)):
    """
    Initializes the database tables based on the SQLAlchemy models.
    """
    try:
        # This assumes Base is imported from models.py and bound to the engine in config.py
        from config import engine
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully.")
        return {"message": "Database tables initialized successfully."}
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize database: {e}"
        )
