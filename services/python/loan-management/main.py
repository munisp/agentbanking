"""
Loan Management Service
End-to-end loan lifecycle management

Features:
- Loan application processing
- Credit scoring integration
- Loan disbursement
- Repayment tracking
- Collections management
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum
import asyncpg
import os
import logging
from decimal import Decimal

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/loans")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Loan Management Service", version="1.0.0")
db_pool = None

class LoanStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISBURSED = "disbursed"
    REPAYING = "repaying"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"

class LoanApplication(BaseModel):
    user_id: str
    amount: Decimal
    tenure_months: int
    purpose: str
    monthly_income: Decimal

class LoanResponse(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    interest_rate: Decimal
    tenure_months: int
    monthly_payment: Decimal
    status: LoanStatus
    created_at: datetime

@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(100) NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                interest_rate DECIMAL(5,2) NOT NULL,
                tenure_months INT NOT NULL,
                monthly_payment DECIMAL(15,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                disbursed_at TIMESTAMP,
                purpose TEXT
            );
        """)
    logger.info("Loan Management Service started")

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

def calculate_monthly_payment(principal: Decimal, rate: Decimal, months: int) -> Decimal:
    """Calculate monthly loan payment"""
    monthly_rate = rate / Decimal(12) / Decimal(100)
    payment = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    return payment.quantize(Decimal('0.01'))

@app.post("/applications", response_model=LoanResponse)
async def apply_for_loan(application: LoanApplication):
    """Submit loan application"""
    
    # Simple credit scoring
    if application.monthly_income < application.amount / Decimal(6):
        raise HTTPException(status_code=400, detail="Insufficient income for loan amount")
    
    # Calculate interest rate based on tenure
    interest_rate = Decimal(15) if application.tenure_months <= 6 else Decimal(18)
    monthly_payment = calculate_monthly_payment(application.amount, interest_rate, application.tenure_months)
    
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO loans (user_id, amount, interest_rate, tenure_months, monthly_payment, purpose, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'approved') RETURNING *
        """, application.user_id, application.amount, interest_rate, application.tenure_months,
            monthly_payment, application.purpose)
        
        return LoanResponse(**dict(row))

@app.get("/loans/{loan_id}", response_model=LoanResponse)
async def get_loan(loan_id: str):
    """Get loan details"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM loans WHERE id = $1", loan_id)
        if not row:
            raise HTTPException(status_code=404, detail="Loan not found")
        return LoanResponse(**dict(row))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "loan-management"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8106)
