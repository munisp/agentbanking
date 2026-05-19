"""
FastAPI router for the rule-engine service.
Handles CRUD operations for rules and rule execution simulation.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from . import models
from .config import get_db, settings

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/rules",
    tags=["rules"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions ---

def log_activity(db: Session, rule_id: int, activity_type: str, details: Optional[dict] = None, user_id: Optional[str] = "system"):
    """Creates an activity log entry."""
    log_entry = models.ActivityLogCreate(
        rule_id=rule_id,
        activity_type=activity_type,
        details=details,
        user_id=user_id
    )
    db_log = models.ActivityLog(**log_entry.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

def get_rule_by_id(db: Session, rule_id: int) -> models.Rule:
    """Helper function to fetch a rule by ID or raise 404."""
    rule = db.query(models.Rule).filter(models.Rule.id == rule_id).first()
    if not rule:
        logger.warning(f"Rule with ID {rule_id} not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rule with ID {rule_id} not found")
    return rule

# --- CRUD Endpoints for Rule ---

@router.post("/", response_model=models.RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(rule: models.RuleCreate, db: Session = Depends(get_db)):
    """
    Creates a new rule in the rule engine.
    """
    logger.info(f"Attempting to create new rule: {rule.name} for tenant {rule.tenant_id}")
    try:
        db_rule = models.Rule(**rule.model_dump())
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        
        # Log creation activity
        log_activity(db, db_rule.id, "RULE_CREATED", {"name": db_rule.name, "tenant_id": db_rule.tenant_id})
        
        logger.info(f"Rule created successfully with ID: {db_rule.id}")
        return db_rule
    except IntegrityError:
        db.rollback()
        detail = f"Rule with name '{rule.name}' already exists for tenant '{rule.tenant_id}'."
        logger.error(f"Integrity error during rule creation: {detail}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during rule creation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during rule creation")

@router.get("/", response_model=List[models.RuleResponse])
def list_rules(
    tenant_id: Optional[str] = None,
    status_filter: Optional[models.RuleStatus] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieves a list of rules, with optional filtering by tenant_id and status.
    Supports pagination via skip and limit parameters.
    """
    query = db.query(models.Rule)
    
    if tenant_id:
        query = query.filter(models.Rule.tenant_id == tenant_id)
    
    if status_filter:
        query = query.filter(models.Rule.status == status_filter.value)
        
    rules = query.offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(rules)} rules (skip={skip}, limit={limit}, tenant_id={tenant_id}, status={status_filter}).")
    return rules

@router.get("/{rule_id}", response_model=models.RuleWithLogsResponse)
def read_rule(rule_id: int, db: Session = Depends(get_db)):
    """
    Retrieves a single rule by its ID, including its activity log history.
    """
    rule = get_rule_by_id(db, rule_id)
    logger.info(f"Retrieved rule with ID: {rule_id}.")
    return rule

@router.put("/{rule_id}", response_model=models.RuleResponse)
def update_rule(rule_id: int, rule_update: models.RuleUpdate, db: Session = Depends(get_db)):
    """
    Updates an existing rule by its ID. Only provided fields are updated.
    """
    db_rule = get_rule_by_id(db, rule_id)
    
    update_data = rule_update.model_dump(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    # Check for name conflict if name is being updated
    if 'name' in update_data and update_data['name'] != db_rule.name:
        existing_rule = db.query(models.Rule).filter(
            models.Rule.tenant_id == db_rule.tenant_id,
            models.Rule.name == update_data['name']
        ).first()
        if existing_rule and existing_rule.id != rule_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Rule with name '{update_data['name']}' already exists for tenant '{db_rule.tenant_id}'.")

    for key, value in update_data.items():
        setattr(db_rule, key, value)

    db.commit()
    db.refresh(db_rule)
    
    # Log update activity
    log_activity(db, db_rule.id, "RULE_UPDATED", {"changes": update_data})
    
    logger.info(f"Rule with ID {rule_id} updated successfully.")
    return db_rule

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """
    Deletes a rule by its ID.
    """
    db_rule = get_rule_by_id(db, rule_id)
    
    # Note: Depending on the database setup, related ActivityLogs might be automatically
    # deleted (CASCADE) or need manual deletion. Assuming CASCADE for simplicity.
    
    db.delete(db_rule)
    db.commit()
    
    # Log deletion activity (log before actual delete if possible, or log to a separate system)
    # For simplicity, we log it here assuming the log table is independent or handled.
    # In a real system, this log might happen outside the main transaction.
    # We skip logging here to avoid foreign key issues on the ActivityLog table.
    
    logger.info(f"Rule with ID {rule_id} deleted successfully.")
    return

# --- Business Logic Endpoints ---

class RuleExecutionRequest(models.BaseModel):
    """Schema for a rule execution request."""
    tenant_id: str = Field(..., description="The tenant ID for which the rules should be executed.")
    event_data: dict = Field(..., description="The event data payload to be evaluated against the rules.")
    user_id: Optional[str] = Field(None, description="The user ID associated with the event.")

class RuleExecutionResponse(models.BaseModel):
    """Schema for a rule execution response."""
    tenant_id: str
    event_id: str = Field(..., description="A unique ID for the processed event.")
    matched_rules: List[int] = Field(..., description="List of IDs of rules that matched the event data.")
    actions_taken: List[dict] = Field(..., description="List of actions executed as a result of rule matches.")
    decision: str = Field(..., description="The final decision based on rule execution (e.g., 'ALLOW', 'FLAG', 'DENY').")

@router.post("/execute", response_model=RuleExecutionResponse)
def execute_rules(request: RuleExecutionRequest, db: Session = Depends(get_db)):
    """
    Evaluates the execution of active rules for a given tenant against an event payload.
    
    This endpoint represents the core business logic of the rule engine.
    In a real-world scenario, this would involve complex rule parsing and evaluation.
    """
    logger.info(f"Executing rules for tenant: {request.tenant_id} with event data keys: {list(request.event_data.keys())}")
    
    # 1. Fetch all active rules for the tenant
    active_rules = db.query(models.Rule).filter(
        models.Rule.tenant_id == request.tenant_id,
        models.Rule.status == models.RuleStatus.ACTIVE.value,
        models.Rule.is_enabled == True
    ).order_by(models.Rule.priority).all()
    
    matched_rules = []
    actions_taken = []
    final_decision = "ALLOW"
    
    # 2. Simulate rule evaluation and action execution
    for rule in active_rules:
        # Rule evaluation via configured engine
        # For demonstration, we'll match a rule if the event_data contains a specific key.
        is_match = "amount" in request.event_data and request.event_data.get("amount", 0) > 1000
        
        if is_match:
            matched_rules.append(rule.id)
            actions_taken.append({"rule_id": rule.id, "action": rule.action_json})
            
            # Simple decision logic: if any rule matches, flag the transaction
            final_decision = "FLAG"
            
            # Log rule execution activity
            log_activity(
                db, 
                rule.id, 
                "RULE_FIRED", 
                {"event_data_keys": list(request.event_data.keys()), "decision": final_decision},
                user_id=request.user_id
            )
            
            logger.debug(f"Rule {rule.id} matched and fired.")

    # 3. Generate a unique event ID
    event_id = f"evt-{hash(str(request.event_data))}"
    
    logger.info(f"Rule execution complete for event {event_id}. Decision: {final_decision}. Matched rules: {matched_rules}")
    
    return RuleExecutionResponse(
        tenant_id=request.tenant_id,
        event_id=event_id,
        matched_rules=matched_rules,
        actions_taken=actions_taken,
        decision=final_decision
    )
