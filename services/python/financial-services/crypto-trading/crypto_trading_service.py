"""
Cryptocurrency Trading Service
Buy, sell, and trade cryptocurrencies
"""

from typing import Dict


class CryptoTradingService:
    """Crypto trading"""
    
    def __init__(self):
        self.prices = {
            "BTC": 45000.00,
            "ETH": 3000.00,
            "USDT": 1.00,
            "USDC": 1.00
        }
    
    async def get_price(self, symbol: str) -> Dict:
        """Get crypto price"""
        try:
            price = self.prices.get(symbol.upper())
            if not price:
                return {"status": "failed", "error": "Symbol not found"}
            
            return {
                "status": "success",
                "symbol": symbol.upper(),
                "price": price,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def buy_crypto(self, user_id: str, symbol: str, amount_usd: float) -> Dict:
        """Buy cryptocurrency"""
        try:
            price = self.prices.get(symbol.upper(), 0)
            if price == 0:
                return {"status": "failed", "error": "Symbol not found"}
            
            crypto_amount = amount_usd / price
            
            trade = {
                "trade_id": f"TRADE-{secrets.token_hex(8)}",
                "user_id": user_id,
                "type": "buy",
                "symbol": symbol.upper(),
                "amount_usd": amount_usd,
                "crypto_amount": crypto_amount,
                "price": price,
                "status": "completed",
                "executed_at": datetime.now().isoformat()
            }
            
            return {"status": "success", "trade": trade}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def sell_crypto(self, user_id: str, symbol: str, crypto_amount: float) -> Dict:
        """Sell cryptocurrency"""
        try:
            price = self.prices.get(symbol.upper(), 0)
            if price == 0:
                return {"status": "failed", "error": "Symbol not found"}
            
            amount_usd = crypto_amount * price
            
            trade = {
                "trade_id": f"TRADE-{secrets.token_hex(8)}",
                "user_id": user_id,
                "type": "sell",
                "symbol": symbol.upper(),
                "crypto_amount": crypto_amount,
                "amount_usd": amount_usd,
                "price": price,
                "status": "completed",
                "executed_at": datetime.now().isoformat()
            }
            
            return {"status": "success", "trade": trade}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
