"""
Investment API Endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/investments", tags=["investments"])

class Investment(BaseModel):
    id: int
    product_name: str
    amount_invested: float
    current_value: float
    return_percentage: float
    start_date: str
    status: str
    risk_level: str

class InvestmentListResponse(BaseModel):
    investments: List[Investment]
    total_invested: float
    total_value: float
    total_return: float

class InvestmentCreateRequest(BaseModel):
    product_id: int
    amount: float
    duration_months: int

class InvestmentCreateResponse(BaseModel):
    success: bool
    investment_id: int
    product_name: str
    amount: float
    expected_return: float
    maturity_date: str

@router.get("/", response_model=InvestmentListResponse)
async def list_investments():
    """List user investments."""
    investments = [
        {
            "id": 101,
            "product_name": "Money Market Fund",
            "amount_invested": 500000,
            "current_value": 525000,
            "return_percentage": 5.0,
            "start_date": "2025-10-01",
            "status": "active",
            "risk_level": "low"
        }
    ]
    
    return {
        "investments": investments,
        "total_invested": 500000,
        "total_value": 525000,
        "total_return": 25000
    }

@router.post("/", response_model=InvestmentCreateResponse, status_code=201)
async def create_investment(data: InvestmentCreateRequest):
    """Create new investment."""
    # Validate amount
    # Check wallet balance
    # Deduct amount
    # Create investment record
    
    maturity_date = (datetime.utcnow() + timedelta(days=30 * data.duration_months)).isoformat()
    
    return {
        "success": True,
        "investment_id": 101,
        "product_name": "Money Market Fund",
        "amount": data.amount,
        "expected_return": data.amount * 0.05,  # 5% return
        "maturity_date": maturity_date
    }
