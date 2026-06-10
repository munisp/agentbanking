import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .config import get_db
from .models import (
    UssdSession, UssdSessionLog,
    UssdSessionCreate, UssdSessionUpdate, UssdSessionResponse,
    UssdSessionLogResponse, UssdCallbackRequest, UssdCallbackResponse
)

# Configure logging
logger = logging.getLogger(__name__)
router = APIRouter()

# --- Internal Helper Functions ---

def _log_activity(db: Session, session_id: uuid.UUID, log_type: str, message: str, details: dict = None):
    """
    Internal function to create an activity log entry for a session.
    """
    log_entry = UssdSessionLog(
        session_id=session_id,
        log_type=log_type,
        message=message,
        details=details if details is not None else {}
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

def _process_ussd_logic(session: UssdSession, user_input: str) -> (str, str, str):
    """
    Processes the core USSD menu logic.
    
    In a real application, this would be a complex state machine or a dedicated
    business logic service.
    
    Returns: (response_text, gateway_status, internal_status)
    """
    session.last_input = user_input
    
    if session.current_menu_level == "MAIN_MENU":
        if user_input == "":
            # Initial request
            response_text = "Welcome to USSD Service.\n1. Check Balance\n2. Mini Statement\n3. Exit"
            session.current_menu_level = "MAIN_MENU_WAIT"
            gateway_status = "CON"
            internal_status = "ACTIVE"
        elif user_input == "1":
            response_text = "Your balance is $100.00. Thank you."
            session.current_menu_level = "BALANCE_CHECKED"
            session.status = "COMPLETED"
            gateway_status = "END"
            internal_status = "COMPLETED"
        elif user_input == "2":
            response_text = "Last 3 transactions: $5, $10, $20. Thank you."
            session.current_menu_level = "STATEMENT_CHECKED"
            session.status = "COMPLETED"
            gateway_status = "END"
            internal_status = "COMPLETED"
        elif user_input == "3":
            response_text = "Thank you for using our service. Goodbye."
            session.current_menu_level = "EXITED"
            session.status = "CANCELED"
            gateway_status = "END"
            internal_status = "CANCELED"
        else:
            response_text = "Invalid option. Please try again.\n1. Check Balance\n2. Mini Statement\n3. Exit"
            gateway_status = "CON"
            internal_status = "ACTIVE"
            
    else:
        # Fallback for any other state (e.g., waiting for input in a sub-menu)
        response_text = "Session error or timeout. Please dial again."
        session.current_menu_level = "ERROR"
        session.status = "CANCELED"
        gateway_status = "END"
        internal_status = "CANCELED"

    session.session_data["menu_history"] = session.session_data.get("menu_history", []) + [session.current_menu_level]
    
    return response_text, gateway_status, internal_status

# --- Business-Specific Endpoint (Core USSD Logic) ---

@router.post("/callback", response_model=UssdCallbackResponse, status_code=status.HTTP_200_OK, tags=["USSD"])
def ussd_callback(request: UssdCallbackRequest, db: Session = Depends(get_db)):
    """
    Handles incoming USSD requests from the gateway.
    This is the main business logic endpoint.
    """
    logger.info(f"Received USSD callback for session: {request.session_id}")
    
    # 1. Find or Create Session
    session = db.query(UssdSession).filter(UssdSession.session_id == request.session_id).first()
    
    is_new_session = False
    if not session:
        is_new_session = True
        # Create a new session
        session_data = UssdSessionCreate(
            session_id=request.session_id,
            phone_number=request.phone_number,
            service_code=request.service_code,
            last_input=request.text if request.text else None,
            session_data={"start_time": str(uuid.uuid4())}
        )
        session = UssdSession(**session_data.model_dump())
        db.add(session)
        try:
            db.commit()
            db.refresh(session)
        except IntegrityError:
            db.rollback()
            logger.error(f"Integrity error creating session {request.session_id}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not create USSD session.")
        
        _log_activity(db, session.id, "REQUEST", "New session started", request.model_dump())
    else:
        # Existing session
        if session.status != "ACTIVE":
            # Session is already completed or canceled, but gateway sent another request
            logger.warning(f"Request for non-active session: {request.session_id}. Status: {session.status}")
            response_text = "Your session has expired or been completed. Please dial again."
            return UssdCallbackResponse(
                session_id=request.session_id,
                response_text=response_text,
                session_status="END",
                internal_status=session.status
            )
        
        _log_activity(db, session.id, "REQUEST", "Input received", request.model_dump())

    # 2. Process USSD Logic
    user_input = request.text.strip()
    response_text, gateway_status, internal_status = _process_ussd_logic(session, user_input)
    
    # 3. Update Session State
    session.status = internal_status
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # 4. Log Response
    response_details = {
        "response_text": response_text,
        "session_status": gateway_status,
        "internal_status": internal_status
    }
    _log_activity(db, session.id, "RESPONSE", f"Sending response: {gateway_status}", response_details)

    # 5. Return Response to Gateway
    return UssdCallbackResponse(
        session_id=request.session_id,
        response_text=response_text,
        session_status=gateway_status,
        internal_status=internal_status
    )

# --- CRUD Endpoints for UssdSession ---

@router.post("/sessions", response_model=UssdSessionResponse, status_code=status.HTTP_201_CREATED, tags=["Sessions"])
def create_session(session_in: UssdSessionCreate, db: Session = Depends(get_db)):
    """
    Manually create a new USSD session (e.g., for testing or administrative purposes).
    """
    try:
        session = UssdSession(**session_in.model_dump())
        db.add(session)
        db.commit()
        db.refresh(session)
        _log_activity(db, session.id, "ADMIN", "Session manually created", session_in.model_dump())
        return session
    except IntegrityError:
        db.rollback()
        logger.error(f"Attempt to create duplicate session_id: {session_in.session_id}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session with this session_id already exists.")

@router.get("/sessions", response_model=List[UssdSessionResponse], tags=["Sessions"])
def list_sessions(
    skip: int = 0, 
    limit: int = 100, 
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of USSD sessions with optional filtering by status.
    """
    query = db.query(UssdSession)
    if status_filter:
        query = query.filter(UssdSession.status == status_filter.upper())
        
    sessions = query.offset(skip).limit(limit).all()
    return sessions

@router.get("/sessions/{session_id}", response_model=UssdSessionResponse, tags=["Sessions"])
def get_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieve a specific USSD session by its internal ID.
    """
    session = db.query(UssdSession).filter(UssdSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session

@router.put("/sessions/{session_id}", response_model=UssdSessionResponse, tags=["Sessions"])
def update_session(session_id: uuid.UUID, session_in: UssdSessionUpdate, db: Session = Depends(get_db)):
    """
    Update an existing USSD session by its internal ID.
    """
    session = db.query(UssdSession).filter(UssdSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    update_data = session_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(session, key, value)

    db.add(session)
    db.commit()
    db.refresh(session)
    _log_activity(db, session.id, "ADMIN", "Session manually updated", update_data)
    return session

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Sessions"])
def delete_session(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Delete a USSD session by its internal ID.
    """
    session = db.query(UssdSession).filter(UssdSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    db.delete(session)
    db.commit()
    logger.info(f"Session {session_id} deleted.")
    return

# --- Additional Business-Specific Endpoints (Logs) ---

@router.get("/sessions/{session_id}/logs", response_model=List[UssdSessionLogResponse], tags=["Sessions", "Logs"])
def get_session_logs(session_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieve all activity logs for a specific USSD session, ordered by timestamp.
    """
    session = db.query(UssdSession).filter(UssdSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
    logs = db.query(UssdSessionLog).filter(UssdSessionLog.session_id == session_id).order_by(UssdSessionLog.timestamp).all()
    return logs

@router.get("/logs", response_model=List[UssdSessionLogResponse], tags=["Logs"])
def list_all_logs(
    skip: int = 0, 
    limit: int = 100, 
    log_type_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of all USSD session logs with optional filtering by log type.
    """
    query = db.query(UssdSessionLog)
    if log_type_filter:
        query = query.filter(UssdSessionLog.log_type == log_type_filter.upper())
        
    logs = query.order_by(UssdSessionLog.timestamp.desc()).offset(skip).limit(limit).all()
    return logs
