"""
Interest Calculation Service - Production Implementation
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal
from datetime import datetime
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Interest Calculation", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class InterestCalculation(BaseModel):
    principal: Decimal
    rate: Decimal
    days: int
    interest: Decimal
    total: Decimal
    timestamp: datetime

class CalculateRequest(BaseModel):
    principal: Decimal
    rate: Decimal
    days: int

class InterestService:
    @staticmethod
    async def calculate(request: CalculateRequest) -> InterestCalculation:
        interest = (request.principal * request.rate * request.days) / (Decimal("365") * Decimal("100"))
        total = request.principal + interest
        
        result = InterestCalculation(
            principal=request.principal,
            rate=request.rate,
            days=request.days,
            interest=interest,
            total=total,
            timestamp=datetime.utcnow()
        )
        logger.info(f"Calculated interest: {interest}")
        return result

@app.post("/api/v1/calculate", response_model=InterestCalculation)
async def calculate(request: CalculateRequest):
    return await InterestService.calculate(request)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "interest-calculation", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8084)
