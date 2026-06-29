from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
from config import get_db, logger

router = APIRouter(
    prefix="/commissions",
    tags=["commissions"],
    responses={404: {"description": "Not found"}},
)

# --- Utility Functions for Business Logic ---

def get_tier_multiplier(db: Session, tier_name: Optional[str] = None) -> models.CommissionTier:
    """
    Retrieves the commission tier and its multiplier.
    If no tier_name is provided, it attempts to find a default tier or creates one.
    """
    if tier_name:
        tier = db.query(models.CommissionTier).filter(models.CommissionTier.name == tier_name).first()
        if not tier:
            raise HTTPException(status_code=404, detail=f"Commission Tier '{tier_name}' not found.")
        return tier
    
    # Fallback to a default tier
    default_tier_name = "Base Tier"
    tier = db.query(models.CommissionTier).filter(models.CommissionTier.name == default_tier_name).first()
    if not tier:
        # Create a default tier if it doesn't exist
        logger.info(f"Creating default commission tier: {default_tier_name}")
        tier = models.CommissionTier(
            name=default_tier_name,
            description="Default tier for all salespersons.",
            rate_multiplier=1.0
        )
        db.add(tier)
        db.commit()
        db.refresh(tier)
    return tier

def find_best_rule(db: Session, category: str, amount: float, tier_id: Optional[int]) -> Optional[models.CommissionRule]:
    """
    Finds the single best-matching commission rule based on category, amount, and tier.
    Priority: Tier-specific rules > General rules. Within each, highest min_sale_amount first.
    """
    # 1. Search for active, tier-specific rules
    if tier_id:
        tier_rules = db.query(models.CommissionRule).filter(
            models.CommissionRule.is_active == True,
            models.CommissionRule.product_category == category,
            models.CommissionRule.min_sale_amount <= amount,
            models.CommissionRule.tier_id == tier_id
        ).order_by(models.CommissionRule.min_sale_amount.desc()).all()
        if tier_rules:
            return tier_rules[0]

    # 2. Search for active, general rules (tier_id is NULL)
    general_rules = db.query(models.CommissionRule).filter(
        models.CommissionRule.is_active == True,
        models.CommissionRule.product_category == category,
        models.CommissionRule.min_sale_amount <= amount,
        models.CommissionRule.tier_id.is_(None)
    ).order_by(models.CommissionRule.min_sale_amount.desc()).all()
    
    if general_rules:
        return general_rules[0]

    return None

def calculate_commission_amount(sale_amount: float, rule: models.CommissionRule, multiplier: float) -> float:
    """Calculates the commission based on the rule and tier multiplier."""
    if rule.commission_type == models.CommissionType.PERCENTAGE:
        base_commission = sale_amount * rule.commission_value
    elif rule.commission_type == models.CommissionType.FLAT_RATE:
        base_commission = rule.commission_value
    else:
        # Should not happen if enums are used correctly
        raise ValueError(f"Unknown commission type: {rule.commission_type}")
    
    final_commission = base_commission * multiplier
    return round(final_commission, 2)

# --- Core Business Endpoint ---

@router.post("/calculate", response_model=models.CommissionCalculationResult, status_code=status.HTTP_201_CREATED)
def calculate_and_record_commission(
    request: models.CommissionCalculateRequest,
    db: Session = Depends(get_db)
):
    """
    Calculates the commission for a new sale, records the sale, and the resulting commission payment.
    """
    logger.info(f"Processing commission calculation for salesperson {request.salesperson_id} on sale of {request.amount} in category {request.product_category}")

    # 1. Determine the Tier and Multiplier
    try:
        tier = get_tier_multiplier(db, request.tier_name)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error determining tier: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not determine commission tier.")

    # 2. Find the Best Rule
    rule = find_best_rule(db, request.product_category, request.amount, tier.id)
    
    if not rule:
        logger.warning(f"No commission rule found for category {request.product_category} and amount {request.amount}. Recording sale with zero commission.")
        commission_amount = 0.0
        rule_id = None
        rule_name = "No Rule Applied"
    else:
        # 3. Calculate Commission
        commission_amount = calculate_commission_amount(request.amount, rule, tier.rate_multiplier)
        rule_id = rule.id
        rule_name = rule.name
        logger.info(f"Rule '{rule_name}' (ID: {rule_id}) applied. Base commission: {commission_amount / tier.rate_multiplier:.2f}, Multiplier: {tier.rate_multiplier}, Final: {commission_amount:.2f}")

    # 4. Record the Sale
    new_sale = models.Sale(
        salesperson_id=request.salesperson_id,
        amount=request.amount,
        product_category=request.product_category,
        sale_date=datetime.utcnow()
    )
    db.add(new_sale)
    db.flush() # Flush to get the new_sale.id

    new_sale_id = new_sale.id
    
    # 5. Record the Commission Payment (if commission > 0)
    if commission_amount > 0 and rule_id is not None:
        new_payment = models.CommissionPayment(
            sale_id=new_sale_id,
            salesperson_id=request.salesperson_id,
            rule_id=rule_id,
            calculated_amount=commission_amount,
            status=models.CommissionStatus.CALCULATED,
            calculation_date=datetime.utcnow()
        )
        db.add(new_payment)
        db.commit()
        db.refresh(new_sale)
        
        return models.CommissionCalculationResult(
            commission_amount=commission_amount,
            rule_applied_id=rule_id,
            rule_name=rule_name,
            tier_multiplier=tier.rate_multiplier,
            is_new_sale_recorded=True,
            new_sale_id=new_sale_id
        )
    else:
        # Commit the sale even if commission is zero
        db.commit()
        db.refresh(new_sale)
        
        return models.CommissionCalculationResult(
            commission_amount=0.0,
            rule_applied_id=rule_id if rule_id else 0,
            rule_name=rule_name,
            tier_multiplier=tier.rate_multiplier,
            is_new_sale_recorded=True,
            new_sale_id=new_sale_id
        )

# --- CRUD Endpoints for Commission Tiers ---

@router.post("/tiers", response_model=models.CommissionTierRead, status_code=status.HTTP_201_CREATED)
def create_tier(tier: models.CommissionTierCreate, db: Session = Depends(get_db)):
    """Create a new commission tier."""
    db_tier = models.CommissionTier(**tier.dict())
    db.add(db_tier)
    db.commit()
    db.refresh(db_tier)
    return db_tier

@router.get("/tiers", response_model=List[models.CommissionTierRead])
def read_tiers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of all commission tiers."""
    tiers = db.query(models.CommissionTier).offset(skip).limit(limit).all()
    return tiers

@router.get("/tiers/{tier_id}", response_model=models.CommissionTierRead)
def read_tier(tier_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific commission tier by ID."""
    tier = db.query(models.CommissionTier).filter(models.CommissionTier.id == tier_id).first()
    if tier is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    return tier

@router.put("/tiers/{tier_id}", response_model=models.CommissionTierRead)
def update_tier(tier_id: int, tier_update: models.CommissionTierUpdate, db: Session = Depends(get_db)):
    """Update an existing commission tier."""
    db_tier = db.query(models.CommissionTier).filter(models.CommissionTier.id == tier_id).first()
    if db_tier is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    
    update_data = tier_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_tier, key, value)
    
    db.commit()
    db.refresh(db_tier)
    return db_tier

# --- CRUD Endpoints for Commission Rules ---

@router.post("/rules", response_model=models.CommissionRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(rule: models.CommissionRuleCreate, db: Session = Depends(get_db)):
    """Create a new commission rule."""
    if rule.tier_id:
        tier = db.query(models.CommissionTier).filter(models.CommissionTier.id == rule.tier_id).first()
        if not tier:
            raise HTTPException(status_code=404, detail=f"Tier with ID {rule.tier_id} not found.")
            
    db_rule = models.CommissionRule(**rule.dict())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

@router.get("/rules", response_model=List[models.CommissionRuleRead])
def read_rules(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of all commission rules."""
    rules = db.query(models.CommissionRule).offset(skip).limit(limit).all()
    return rules

@router.get("/rules/{rule_id}", response_model=models.CommissionRuleRead)
def read_rule(rule_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific commission rule by ID."""
    rule = db.query(models.CommissionRule).filter(models.CommissionRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@router.put("/rules/{rule_id}", response_model=models.CommissionRuleRead)
def update_rule(rule_id: int, rule_update: models.CommissionRuleUpdate, db: Session = Depends(get_db)):
    """Update an existing commission rule."""
    db_rule = db.query(models.CommissionRule).filter(models.CommissionRule.id == rule_id).first()
    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = rule_update.dict(exclude_unset=True)
    if 'tier_id' in update_data and update_data['tier_id'] is not None:
        tier = db.query(models.CommissionTier).filter(models.CommissionTier.id == update_data['tier_id']).first()
        if not tier:
            raise HTTPException(status_code=404, detail=f"Tier with ID {update_data['tier_id']} not found.")
            
    for key, value in update_data.items():
        setattr(db_rule, key, value)
    
    db.commit()
    db.refresh(db_rule)
    return db_rule

# --- CRUD Endpoints for Sales ---

@router.get("/sales", response_model=List[models.SaleRead])
def read_sales(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of all sales."""
    sales = db.query(models.Sale).offset(skip).limit(limit).all()
    return sales

@router.get("/sales/{sale_id}", response_model=models.SaleRead)
def read_sale(sale_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific sale by ID."""
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if sale is None:
        raise HTTPException(status_code=404, detail="Sale not found")
    return sale

# --- CRUD Endpoints for Commission Payments ---

@router.get("/payments", response_model=List[models.CommissionPaymentRead])
def read_payments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve a list of all commission payments."""
    payments = db.query(models.CommissionPayment).offset(skip).limit(limit).all()
    return payments

@router.get("/payments/{payment_id}", response_model=models.CommissionPaymentRead)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific commission payment by ID."""
    payment = db.query(models.CommissionPayment).filter(models.CommissionPayment.id == payment_id).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@router.put("/payments/{payment_id}", response_model=models.CommissionPaymentRead)
def update_payment_status(payment_id: int, payment_update: models.CommissionPaymentUpdate, db: Session = Depends(get_db)):
    """Update the status of a commission payment (e.g., mark as paid)."""
    db_payment = db.query(models.CommissionPayment).filter(models.CommissionPayment.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    update_data = payment_update.dict(exclude_unset=True)
    
    # Logic to automatically set payment_date if status is set to PAID
    if update_data.get('status') == models.CommissionStatus.PAID and db_payment.status != models.CommissionStatus.PAID:
        db_payment.payment_date = datetime.utcnow()
    
    for key, value in update_data.items():
        setattr(db_payment, key, value)
    
    db.commit()
    db.refresh(db_payment)
    return db_payment

@router.get("/payments/salesperson/{salesperson_id}", response_model=List[models.CommissionPaymentRead])
def read_payments_by_salesperson(salesperson_id: int, db: Session = Depends(get_db)):
    """Retrieve all commission payments for a specific salesperson."""
    payments = db.query(models.CommissionPayment).filter(models.CommissionPayment.salesperson_id == salesperson_id).all()
    return payments
