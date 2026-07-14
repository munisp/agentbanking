from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import json

# Import all necessary components from the generated files
try:
    from . import models, config
except ImportError:
    # Fallback for execution in a single-file context
    import models, config

# Alias for convenience
get_db = config.get_db
get_ml_service = config.get_ml_service
MLService = config.MLService
DecisionStatus = models.DecisionStatus
CaseStatus = models.CaseStatus

router = APIRouter(
    prefix="/fraud",
    tags=["fraud-detection"],
    responses={404: {"description": "Not found"}},
)

# --- Core Fraud Detection Endpoint ---

@router.post(
    "/check_transaction",
    response_model=models.TransactionCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a transaction for real-time fraud detection",
    description="Processes a new transaction through the ML scoring model and rules engine, records the result, and creates a case if manual review is required."
)
def check_transaction(
    transaction_data: models.TransactionCreate,
    db: Session = Depends(get_db),
    ml_service: MLService = Depends(get_ml_service)
):
    """
    Handles the core fraud detection logic.
    1. Scores the transaction using the ML scoring engine.
    2. Applies rules using the rules engine.
    3. Determines the final decision (ALLOW, REVIEW, BLOCK).
    4. Persists the transaction and the check result.
    5. Creates a case if the decision is REVIEW.
    """
    
    # 1. Prepare data for ML/Rules Engine (convert Pydantic to dict)
    transaction_dict = transaction_data.model_dump()
    
    # 2. ML Scoring and Rules Engine
    ml_score = ml_service.score_transaction(transaction_dict)
    rules_triggered = ml_service.apply_rules(transaction_dict)
    
    # 3. Final Decision
    decision, reason = ml_service.get_decision(ml_score, rules_triggered)
    
    # 4. Persist Transaction
    db_transaction = models.Transaction(
        **transaction_dict
    )
    db.add(db_transaction)
    db.flush() # Get the ID before commit
    
    # 5. Persist Fraud Check Result
    rules_triggered_str = ",".join(rules_triggered)
    db_result = models.FraudCheckResult(
        transaction_id=db_transaction.id,
        ml_score=ml_score,
        rules_triggered=rules_triggered_str,
        decision=DecisionStatus(decision),
        reason=reason
    )
    db.add(db_result)
    db.flush() # Get the ID before commit
    
    case_id = None
    # 6. Case Management: Create a case if decision is REVIEW
    if db_result.decision == DecisionStatus.REVIEW:
        db_case = models.Case(
            result_id=db_result.id,
            status=CaseStatus.OPEN
        )
        db.add(db_case)
        db.flush()
        case_id = db_case.id
        
    db.commit()
    db.refresh(db_transaction)
    db.refresh(db_result)
    
    # 7. Return Response
    # Manually convert the rules_triggered string back to a list for the Pydantic response model
    result_read_data = db_result.__dict__.copy()
    result_read_data['rules_triggered'] = rules_triggered
    
    return models.TransactionCheckResponse(
        transaction=models.TransactionRead.model_validate(db_transaction),
        result=models.FraudCheckResultRead.model_validate(result_read_data),
        case_id=case_id
    )

# --- Case Management Endpoints ---

@router.get(
    "/cases",
    response_model=List[models.CaseRead],
    summary="List all fraud cases",
    description="Retrieves a list of fraud cases, optionally filtered by status."
)
def list_cases(
    status: Optional[CaseStatus] = None,
    db: Session = Depends(get_db)
):
    """Retrieves a list of fraud cases."""
    query = db.query(models.Case)
    if status:
        query = query.filter(models.Case.status == status)
    
    return query.all()

@router.get(
    "/cases/{case_id}",
    response_model=models.CaseRead,
    summary="Get a specific fraud case",
    description="Retrieves details for a specific fraud case by ID."
)
def get_case(
    case_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves a specific fraud case."""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case

@router.put(
    "/cases/{case_id}",
    response_model=models.CaseRead,
    summary="Update a fraud case",
    description="Updates the status and/or notes for a specific fraud case."
)
def update_case(
    case_id: int,
    case_update: models.CaseUpdate,
    db: Session = Depends(get_db)
):
    """Updates the status and/or notes for a specific fraud case."""
    db_case = db.query(models.Case).filter(models.Case.id == case_id).first()
    if db_case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Apply updates
    update_data = case_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_case, key, value)
        
    db.commit()
    db.refresh(db_case)
    return db_case

# --- History and Retrieval Endpoints ---

@router.get(
    "/transactions/{transaction_id}",
    response_model=models.TransactionRead,
    summary="Get a transaction by ID",
    description="Retrieves the details of a transaction."
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves a transaction by its ID."""
    db_transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if db_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return db_transaction

@router.get(
    "/results/{transaction_id}",
    response_model=models.FraudCheckResultRead,
    summary="Get fraud check result by Transaction ID",
    description="Retrieves the fraud check result for a given transaction ID."
)
def get_result_by_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Retrieves the fraud check result for a transaction."""
    db_result = db.query(models.FraudCheckResult).filter(models.FraudCheckResult.transaction_id == transaction_id).first()
    if db_result is None:
        raise HTTPException(status_code=404, detail="Fraud check result not found for this transaction")
    
    # Manually convert the rules_triggered string back to a list for the Pydantic response model
    result_read_data = db_result.__dict__.copy()
    result_read_data['rules_triggered'] = [r.strip() for r in db_result.rules_triggered.split(',') if db_result.rules_triggered]
    
    return models.FraudCheckResultRead.model_validate(result_read_data)
