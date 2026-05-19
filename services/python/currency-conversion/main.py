"""
Currency Conversion Service - Production Implementation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from decimal import Decimal
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Currency Conversion", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ConversionResult(BaseModel):
    from_currency: str
    to_currency: str
    amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    timestamp: datetime

class ConversionRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: Decimal

rates = {
    ("USD", "NGN"): Decimal("1550.00"),
    ("GBP", "NGN"): Decimal("1970.00"),
    ("EUR", "NGN"): Decimal("1680.00"),
    ("NGN", "USD"): Decimal("0.00065"),
}

class CurrencyService:
    @staticmethod
    async def convert(request: ConversionRequest) -> ConversionResult:
        key = (request.from_currency, request.to_currency)
        if key not in rates:
            raise HTTPException(status_code=400, detail="Currency pair not supported")
        
        rate = rates[key]
        converted = request.amount * rate
        
        return ConversionResult(
            from_currency=request.from_currency,
            to_currency=request.to_currency,
            amount=request.amount,
            converted_amount=converted,
            rate=rate,
            timestamp=datetime.utcnow()
        )

@app.post("/api/v1/convert", response_model=ConversionResult)
async def convert(request: ConversionRequest):
    return await CurrencyService.convert(request)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "currency-conversion", "version": "2.0.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8079)
