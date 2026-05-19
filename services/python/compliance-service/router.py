"""
router.py: FastAPI router with all API endpoints and business logic for compliance-service.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

# Import models and configuration
from config import get_db
from models import (
    ComplianceRule, ComplianceRuleCreate, ComplianceRuleUpdate, ComplianceRuleRead,
    ComplianceCheck, ComplianceCheckCreate, ComplianceCheckUpdate, ComplianceCheckRead,
    Violation, ViolationRead, ViolationResolve,
    CheckStatus, RuleSeverity
)

router = APIRouter(
    prefix="/compliance",
    tags=["compliance"],
    responses={404: {"description": "Not found"}},
)

# --- Helper Functions (Business Logic) ---

async def _create_violation(db: AsyncSession, check: ComplianceCheck, rule: ComplianceRule) -> Violation:
    """
    Internal function to create a Violation record based on a failed check.
    """
    violation = Violation(
        check_id=check.id,
        rule_id=rule.id,
        entity_id=check.entity_id,
        entity_type=check.entity_type,
        violation_timestamp=datetime.utcnow(),
        is_resolved=False,
    )
    db.add(violation)
    await db.commit()
    await db.refresh(violation)
    return violation

# --- ComplianceRule Endpoints ---

@router.post("/rules", response_model=ComplianceRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(rule_in: ComplianceRuleCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new compliance rule.
    """
    # Check if a rule with the same name already exists
    result = await db.execute(select(ComplianceRule).filter(ComplianceRule.name == rule_in.name))
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Compliance rule with name '{rule_in.name}' already exists."
        )

    rule = ComplianceRule(**rule_in.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.get("/rules", response_model=List[ComplianceRuleRead])
async def read_rules(skip: int = 0, limit: int = 100, is_active: Optional[bool] = None, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a list of compliance rules. Can filter by active status.
    """
    query = select(ComplianceRule).offset(skip).limit(limit).order_by(ComplianceRule.id)
    if is_active is not None:
        query = query.filter(ComplianceRule.is_active == is_active)
        
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/rules/{rule_id}", response_model=ComplianceRuleRead)
async def read_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a specific compliance rule by ID.
    """
    rule = await db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found")
    return rule

@router.put("/rules/{rule_id}", response_model=ComplianceRuleRead)
async def update_rule(rule_id: int, rule_in: ComplianceRuleUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update an existing compliance rule.
    """
    rule = await db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found")

    update_data = rule_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    rule.updated_at = datetime.utcnow() # Manually update timestamp if not using ORM event listeners
    
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete a compliance rule by ID. This will cascade delete associated checks and violations.
    """
    rule = await db.get(ComplianceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance rule not found")
    
    await db.delete(rule)
    await db.commit()
    return {"ok": True}

# --- ComplianceCheck Endpoints ---

@router.post("/checks", response_model=ComplianceCheckRead, status_code=status.HTTP_201_CREATED)
async def initiate_check(check_in: ComplianceCheckCreate, db: AsyncSession = Depends(get_db)):
    """
    Initiate a new compliance check. The status is set to PENDING initially.
    """
    rule = await db.get(ComplianceRule, check_in.rule_id)
    if not rule or not rule.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule not found or is not active."
        )

    check = ComplianceCheck(**check_in.model_dump(), status=CheckStatus.PENDING)
    db.add(check)
    await db.commit()
    
    # Refresh with rule relationship for the response model
    await db.execute(select(ComplianceCheck).filter(ComplianceCheck.id == check.id).options(selectinload(ComplianceCheck.rule)))
    await db.refresh(check)
    return check

@router.put("/checks/{check_id}", response_model=ComplianceCheckRead)
async def complete_check(check_id: int, check_update: ComplianceCheckUpdate, db: AsyncSession = Depends(get_db)):
    """
    Complete a compliance check by updating its status and details.
    If the status is FAIL, a Violation record is automatically created.
    """
    # 1. Fetch the check and rule
    result = await db.execute(
        select(ComplianceCheck)
        .filter(ComplianceCheck.id == check_id)
        .options(selectinload(ComplianceCheck.rule))
    )
    check = result.scalars().first()
    
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Compliance check not found.")

    # 2. Update the check record
    check.status = check_update.status
    check.details = check_update.details
    check.check_timestamp = datetime.utcnow() # Update timestamp to completion time

    # 3. Business Logic: Handle failure
    if check.status == CheckStatus.FAIL:
        # Check if a violation already exists for this check
        violation_result = await db.execute(select(Violation).filter(Violation.check_id == check_id))
        existing_violation = violation_result.scalars().first()
        
        if not existing_violation:
            # Create a new violation record
            await _create_violation(db, check, check.rule)
        else:
            # If a violation exists, ensure it's marked as unresolved (in case of re-check)
            existing_violation.is_resolved = False
            existing_violation.resolution_details = None
            existing_violation.resolution_timestamp = None
            db.add(existing_violation)
            
    # 4. Handle success (if a previous violation existed, it should be resolved)
    elif check.status == CheckStatus.PASS:
        violation_result = await db.execute(select(Violation).filter(Violation.check_id == check_id, Violation.is_resolved == False))
        unresolved_violation = violation_result.scalars().first()
        
        if unresolved_violation:
            # Automatically resolve the violation if the re-check passes
            unresolved_violation.is_resolved = True
            unresolved_violation.resolution_details = "Automatically resolved by subsequent successful compliance check."
            unresolved_violation.resolution_timestamp = datetime.utcnow()
            db.add(unresolved_violation)

    await db.commit()
    await db.refresh(check)
    return check

@router.get("/checks", response_model=List[ComplianceCheckRead])
async def read_checks(
    skip: int = 0, 
    limit: int = 100, 
    status_filter: Optional[CheckStatus] = None, 
    entity_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a list of compliance checks. Can filter by status and entity ID.
    """
    query = select(ComplianceCheck).options(selectinload(ComplianceCheck.rule)).offset(skip).limit(limit).order_by(ComplianceCheck.check_timestamp.desc())
    
    if status_filter:
        query = query.filter(ComplianceCheck.status == status_filter)
    if entity_id:
        query = query.filter(ComplianceCheck.entity_id == entity_id)
        
    result = await db.execute(query)
    return result.unique().scalars().all()

# --- Violation Endpoints ---

@router.get("/violations", response_model=List[ViolationRead])
async def read_violations(
    skip: int = 0, 
    limit: int = 100, 
    is_resolved: Optional[bool] = False, 
    severity: Optional[RuleSeverity] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a list of compliance violations. Filters by resolution status and rule severity.
    """
    query = select(Violation).options(
        selectinload(Violation.rule),
        selectinload(Violation.check).selectinload(ComplianceCheck.rule)
    ).offset(skip).limit(limit).order_by(Violation.violation_timestamp.desc())
    
    if is_resolved is not None:
        query = query.filter(Violation.is_resolved == is_resolved)
        
    if severity:
        # Join with ComplianceRule to filter by severity
        query = query.join(ComplianceRule).filter(ComplianceRule.severity == severity)
        
    result = await db.execute(query)
    return result.unique().scalars().all()

@router.get("/violations/{violation_id}", response_model=ViolationRead)
async def read_violation(violation_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a specific violation by ID.
    """
    result = await db.execute(
        select(Violation)
        .filter(Violation.id == violation_id)
        .options(
            selectinload(Violation.rule),
            selectinload(Violation.check).selectinload(ComplianceCheck.rule)
        )
    )
    violation = result.unique().scalars().first()
    
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
    return violation

@router.put("/violations/{violation_id}/resolve", response_model=ViolationRead)
async def resolve_violation(violation_id: int, resolution_in: ViolationResolve, db: AsyncSession = Depends(get_db)):
    """
    Manually resolve an existing violation.
    """
    result = await db.execute(
        select(Violation)
        .filter(Violation.id == violation_id)
        .options(
            selectinload(Violation.rule),
            selectinload(Violation.check).selectinload(ComplianceCheck.rule)
        )
    )
    violation = result.unique().scalars().first()
    
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")
        
    if violation.is_resolved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Violation is already resolved.")

    violation.is_resolved = resolution_in.is_resolved
    violation.resolution_details = resolution_in.resolution_details
    violation.resolution_timestamp = datetime.utcnow()
    
    await db.commit()
    await db.refresh(violation)
    return violation
