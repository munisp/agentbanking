"""
CIPS TigerBeetle Service
High-performance ledger service for CIPS (Cross-Border Interbank Payment System) integration

Features:
- Account creation and management for CIPS participants
- Transfer processing with ACID guarantees  
- Balance queries and transaction history
- Settlement reconciliation
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from decimal import Decimal
import asyncio
import os
import aiohttp

logger = logging.getLogger(__name__)


class CipsTigerbeetleService:
    """
    TigerBeetle ledger service for CIPS integration
    
    Provides high-performance, ACID-compliant ledger operations for
    Cross-Border Interbank Payment System (CIPS) transactions
    """
    
    def __init__(self, tigerbeetle_address: str = None) -> None:
        """Initialize CIPS TigerBeetle service"""
        self.tigerbeetle_address = tigerbeetle_address or os.getenv(
            'TIGERBEETLE_ADDRESS',
            'http://localhost:3000'
        )
        self.ledger_id = 2  # Ledger ID for CIPS
        self.currency_code_cny = 156  # ISO 4217 code for CNY
        logger.info(f"Initialized CIPS TigerBeetle service at {self.tigerbeetle_address}")
    
    async def create_account(
        self,
        participant_id: str,
        account_type: str = "SETTLEMENT",
        currency: str = "CNY"
    ) -> Dict[str, Any]:
        """Create CIPS participant account in TigerBeetle"""
        try:
            account_id = int(uuid.uuid4().hex[:32], 16)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tigerbeetle_address}/accounts",
                    json={
                        "id": str(account_id),
                        "ledger": self.ledger_id,
                        "code": self.currency_code_cny,
                        "user_data": participant_id,
                        "flags": 0
                    }
                ) as response:
                    if response.status == 201:
                        return {
                            "success": True,
                            "account_id": account_id,
                            "participant_id": participant_id,
                            "currency": currency
                        }
                    else:
                        error = await response.text()
                        return {"success": False, "error": error}
        except Exception as e:
            logger.error(f"Error creating CIPS account: {e}")
            return {"success": False, "error": str(e)}
    
    async def process_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
        transfer_id: str = None
    ) -> Dict[str, Any]:
        """Process CIPS transfer between accounts"""
        try:
            if not transfer_id:
                transfer_id = f"cips_{uuid.uuid4().hex[:20]}"
            
            amount_fen = int(amount * 100)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.tigerbeetle_address}/transfers",
                    json={
                        "id": str(int(uuid.uuid4().hex[:32], 16)),
                        "debit_account_id": str(from_account_id),
                        "credit_account_id": str(to_account_id),
                        "ledger": self.ledger_id,
                        "code": self.currency_code_cny,
                        "amount": amount_fen,
                        "user_data": transfer_id,
                        "flags": 0
                    }
                ) as response:
                    if response.status == 201:
                        return {
                            "success": True,
                            "transfer_id": transfer_id,
                            "amount": float(amount),
                            "currency": "CNY",
                            "status": "COMPLETED"
                        }
                    else:
                        error = await response.text()
                        return {"success": False, "error": error}
        except Exception as e:
            logger.error(f"Error processing CIPS transfer: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_balance(self, account_id: int) -> Dict[str, Any]:
        """Get account balance from TigerBeetle"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.tigerbeetle_address}/accounts/{account_id}"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        balance_cny = Decimal(data.get('balance', 0)) / 100
                        
                        return {
                            "success": True,
                            "account_id": account_id,
                            "balance": float(balance_cny),
                            "currency": "CNY"
                        }
                    else:
                        error = await response.text()
                        return {"success": False, "error": error}
        except Exception as e:
            logger.error(f"Error querying balance: {e}")
            return {"success": False, "error": str(e)}


def get_instance() -> None:
    """Get module instance"""
    return CipsTigerbeetleService()

