import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, update, delete

from .config import get_db
from .models import (
    Base,
    DiscordServer,
    DiscordActivityLog,
    DiscordServerCreate,
    DiscordServerUpdate,
    DiscordServerResponse,
    DiscordActivityLogCreate,
    DiscordActivityLogResponse,
    DiscordServerWithLogsResponse,
)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Router Initialization ---
router = APIRouter(
    prefix="/discord-service",
    tags=["discord-service"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions ---

def get_server_by_id(db: Session, server_id: int) -> DiscordServer:
    """
    Fetches a DiscordServer by its internal ID or raises a 404 error.
    """
    server = db.get(DiscordServer, server_id)
    if not server:
        logger.warning(f"DiscordServer with ID {server_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DiscordServer with ID {server_id} not found",
        )
    return server

# --- CRUD Endpoints for DiscordServer ---

@router.post(
    "/servers",
    response_model=DiscordServerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Discord Server record",
    description="Registers a new Discord server with the service.",
)
def create_server(server: DiscordServerCreate, db: Session = Depends(get_db)):
    """
    Registers a new Discord server in the database.
    
    Raises:
        HTTPException: 409 Conflict if a server with the same external server_id already exists.
    """
    # Check for existing server_id to prevent duplicates
    existing_server = db.scalar(
        select(DiscordServer).where(DiscordServer.server_id == server.server_id)
    )
    if existing_server:
        logger.error(f"Attempted to create duplicate server_id: {server.server_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"DiscordServer with server_id '{server.server_id}' already exists",
        )

    db_server = DiscordServer(**server.model_dump())
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    logger.info(f"Created new DiscordServer with ID: {db_server.id}")
    return db_server

@router.get(
    "/servers",
    response_model=List[DiscordServerResponse],
    summary="List all Discord Server records",
    description="Retrieves a list of all registered Discord servers.",
)
def list_servers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a paginated list of Discord servers.
    """
    servers = db.scalars(
        select(DiscordServer).offset(skip).limit(limit)
    ).all()
    return servers

@router.get(
    "/servers/{server_id}",
    response_model=DiscordServerWithLogsResponse,
    summary="Get a Discord Server record by internal ID",
    description="Retrieves a specific Discord server record, including its activity logs.",
)
def read_server(server_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a Discord server by its internal ID.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    server = db.scalar(
        select(DiscordServer)
        .where(DiscordServer.id == server_id)
    )
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DiscordServer with ID {server_id} not found",
        )
    return server

@router.put(
    "/servers/{server_id}",
    response_model=DiscordServerResponse,
    summary="Update a Discord Server record",
    description="Updates the details of an existing Discord server record.",
)
def update_server(server_id: int, server_update: DiscordServerUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing Discord server record.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    db_server = get_server_by_id(db, server_id)
    
    update_data = server_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_server, key, value)
    
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    logger.info(f"Updated DiscordServer with ID: {server_id}")
    return db_server

@router.delete(
    "/servers/{server_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Discord Server record",
    description="Deletes a Discord server record and all associated activity logs.",
)
def delete_server(server_id: int, db: Session = Depends(get_db)):
    """
    Deletes a Discord server by its internal ID.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    db_server = get_server_by_id(db, server_id)
    
    db.delete(db_server)
    db.commit()
    logger.info(f"Deleted DiscordServer with ID: {server_id}")
    return {"ok": True}

# --- Business-Specific Endpoints ---

@router.post(
    "/servers/{server_id}/log",
    response_model=DiscordActivityLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log an activity for a Discord Server",
    description="Records a new activity log entry associated with a specific Discord server.",
)
def log_activity(server_id: int, log_entry: DiscordActivityLogBase, db: Session = Depends(get_db)):
    """
    Creates a new activity log entry for a given server.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    # Ensure the server exists before logging
    get_server_by_id(db, server_id)
    
    db_log = DiscordActivityLog(
        server_id=server_id,
        log_level=log_entry.log_level,
        message=log_entry.message
    )
    
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    logger.info(f"Logged activity for server ID {server_id}: {log_entry.log_level} - {log_entry.message[:50]}...")
    return db_log

@router.get(
    "/servers/{server_id}/logs",
    response_model=List[DiscordActivityLogResponse],
    summary="List activity logs for a Discord Server",
    description="Retrieves a list of activity logs for a specific Discord server.",
)
def list_server_logs(server_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a paginated list of activity logs for a given server.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    # Ensure the server exists
    get_server_by_id(db, server_id)
    
    logs = db.scalars(
        select(DiscordActivityLog)
        .where(DiscordActivityLog.server_id == server_id)
        .order_by(DiscordActivityLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return logs

@router.post(
    "/servers/{server_id}/toggle-active",
    response_model=DiscordServerResponse,
    summary="Toggle the active status of a Discord Server",
    description="A business-specific endpoint to quickly activate or deactivate the service on a server.",
)
def toggle_server_active_status(server_id: int, db: Session = Depends(get_db)):
    """
    Toggles the `is_active` status of a Discord server.
    
    Raises:
        HTTPException: 404 Not Found if the server does not exist.
    """
    db_server = get_server_by_id(db, server_id)
    
    new_status = not db_server.is_active
    db_server.is_active = new_status
    
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    logger.info(f"Toggled active status for server ID {server_id} to {new_status}")
    
    # Log the action
    db_log = DiscordActivityLog(
        server_id=server_id,
        log_level="INFO",
        message=f"Service status toggled to {'Active' if new_status else 'Inactive'}"
    )
    db.add(db_log)
    db.commit()
    
    return db_server
