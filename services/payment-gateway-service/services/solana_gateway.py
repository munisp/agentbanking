"""
Solana Pay Gateway Integration
Fast and low-cost payments on Solana blockchain
"""

import base58
from typing import Dict, Optional
import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from solders.message import Message


class SolanaGateway:
    """Solana Pay gateway implementation"""
    
    def __init__(
        self,
        rpc_url: str = "https://api.mainnet-beta.solana.com",
        private_key: Optional[str] = None
    ):
        self.rpc_url = rpc_url
        
        if private_key:
            self.keypair = Keypair.from_base58_string(private_key)
        else:
            self.keypair = None
        
        # USDC SPL Token address on Solana
        self.usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        # USDT SPL Token address on Solana
        self.usdt_mint = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    
    async def _rpc_call(self, method: str, params: list) -> Dict:
        """Make RPC call to Solana node"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.rpc_url, json=payload)
            return response.json()
    
    def _lamports_to_sol(self, lamports: int) -> float:
        """Convert lamports to SOL"""
        return lamports / 1_000_000_000
    
    def _sol_to_lamports(self, sol: float) -> int:
        """Convert SOL to lamports"""
        return int(sol * 1_000_000_000)
    
    async def get_balance(self, address: str, token: str = "SOL") -> Dict:
        """
        Get balance for address
        
        Args:
            address: Wallet address
            token: Token symbol (SOL, USDC, USDT, or mint address)
        """
        try:
            if token == "SOL":
                result = await self._rpc_call("getBalance", [address])
                
                if "result" in result:
                    lamports = result["result"]["value"]
                    balance = self._lamports_to_sol(lamports)
                    
                    return {
                        "status": "success",
                        "balance": balance,
                        "token": "SOL",
                        "address": address
                    }
                else:
                    return {
                        "status": "failed",
                        "error": result.get("error", {}).get("message", "Failed to get balance")
                    }
            else:
                # Get SPL token balance
                if token == "USDC":
                    mint_address = self.usdc_mint
                elif token == "USDT":
                    mint_address = self.usdt_mint
                else:
                    mint_address = token
                
                result = await self._rpc_call("getTokenAccountsByOwner", [
                    address,
                    {"mint": mint_address},
                    {"encoding": "jsonParsed"}
                ])
                
                if "result" in result and result["result"]["value"]:
                    token_account = result["result"]["value"][0]
                    balance_data = token_account["account"]["data"]["parsed"]["info"]["tokenAmount"]
                    balance = float(balance_data["uiAmount"])
                    
                    return {
                        "status": "success",
                        "balance": balance,
                        "token": token,
                        "address": address,
                        "mint_address": mint_address
                    }
                else:
                    return {
                        "status": "success",
                        "balance": 0.0,
                        "token": token,
                        "address": address
                    }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_sol(
        self,
        to_address: str,
        amount: float
    ) -> Dict:
        """
        Send SOL
        
        Args:
            to_address: Recipient address
            amount: Amount in SOL
        """
        if not self.keypair:
            return {
                "status": "failed",
                "error": "No private key configured"
            }
        
        try:
            # Get recent blockhash
            blockhash_result = await self._rpc_call("getLatestBlockhash", [])
            blockhash = blockhash_result["result"]["value"]["blockhash"]
            
            # Create transfer instruction
            from_pubkey = self.keypair.pubkey()
            to_pubkey = Pubkey.from_string(to_address)
            lamports = self._sol_to_lamports(amount)
            
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )
            
            # Create transaction
            message = Message.new_with_blockhash(
                [transfer_ix],
                from_pubkey,
                blockhash
            )
            transaction = Transaction([self.keypair], message, blockhash)
            
            # Serialize and encode transaction
            serialized_tx = base58.b58encode(bytes(transaction)).decode('utf-8')
            
            # Send transaction
            result = await self._rpc_call("sendTransaction", [
                serialized_tx,
                {"encoding": "base58"}
            ])
            
            if "result" in result:
                return {
                    "status": "success",
                    "signature": result["result"],
                    "from_address": str(from_pubkey),
                    "to_address": to_address,
                    "amount": amount,
                    "token": "SOL"
                }
            else:
                return {
                    "status": "failed",
                    "error": result.get("error", {}).get("message", "Transaction failed")
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_transaction(self, signature: str) -> Dict:
        """
        Get transaction details
        
        Args:
            signature: Transaction signature
        """
        try:
            result = await self._rpc_call("getTransaction", [
                signature,
                {"encoding": "jsonParsed"}
            ])
            
            if "result" in result and result["result"]:
                tx_data = result["result"]
                meta = tx_data.get("meta", {})
                
                return {
                    "status": "success",
                    "signature": signature,
                    "block_time": tx_data.get("blockTime"),
                    "slot": tx_data.get("slot"),
                    "success": meta.get("err") is None,
                    "fee": self._lamports_to_sol(meta.get("fee", 0))
                }
            else:
                return {
                    "status": "failed",
                    "error": "Transaction not found"
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def confirm_transaction(self, signature: str) -> Dict:
        """
        Confirm transaction status
        
        Args:
            signature: Transaction signature
        """
        try:
            result = await self._rpc_call("getSignatureStatuses", [[signature]])
            
            if "result" in result and result["result"]["value"]:
                status = result["result"]["value"][0]
                
                if status:
                    return {
                        "status": "success",
                        "signature": signature,
                        "confirmed": status.get("confirmationStatus") in ["confirmed", "finalized"],
                        "confirmation_status": status.get("confirmationStatus"),
                        "confirmations": status.get("confirmations"),
                        "success": status.get("err") is None
                    }
                else:
                    return {
                        "status": "pending",
                        "signature": signature,
                        "confirmed": False
                    }
            else:
                return {
                    "status": "failed",
                    "error": "Could not get transaction status"
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_recent_transactions(self, address: str, limit: int = 10) -> Dict:
        """
        Get recent transactions for address
        
        Args:
            address: Wallet address
            limit: Number of transactions to return
        """
        try:
            result = await self._rpc_call("getSignaturesForAddress", [
                address,
                {"limit": limit}
            ])
            
            if "result" in result:
                transactions = []
                for tx in result["result"]:
                    transactions.append({
                        "signature": tx.get("signature"),
                        "block_time": tx.get("blockTime"),
                        "slot": tx.get("slot"),
                        "success": tx.get("err") is None,
                        "memo": tx.get("memo")
                    })
                
                return {
                    "status": "success",
                    "transactions": transactions
                }
            else:
                return {
                    "status": "failed",
                    "error": "Failed to get transactions"
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def estimate_fee(self) -> Dict:
        """Estimate transaction fee"""
        try:
            result = await self._rpc_call("getFees", [])
            
            if "result" in result:
                fee_calculator = result["result"]["value"]["feeCalculator"]
                lamports_per_signature = fee_calculator.get("lamportsPerSignature", 5000)
                fee_sol = self._lamports_to_sol(lamports_per_signature)
                
                return {
                    "status": "success",
                    "fee_lamports": lamports_per_signature,
                    "fee_sol": fee_sol,
                    "fee_usd": fee_sol * 20  # Approximate SOL price
                }
            else:
                return {
                    "status": "failed",
                    "error": "Failed to get fee estimate"
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def create_wallet(self) -> Dict:
        """Create new Solana wallet"""
        keypair = Keypair()
        return {
            "status": "success",
            "address": str(keypair.pubkey()),
            "private_key": base58.b58encode(bytes(keypair)).decode('utf-8')
        }
    
    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid"""
        try:
            Pubkey.from_string(address)
            return True
        except:
            return False
    
    async def create_payment_request(
        self,
        recipient: str,
        amount: float,
        label: str,
        message: str,
        memo: Optional[str] = None
    ) -> Dict:
        """
        Create Solana Pay payment request URL
        
        Args:
            recipient: Recipient address
            amount: Amount in SOL
            label: Label for the payment
            message: Message for the payment
            memo: Optional memo
        """
        try:
            # Build Solana Pay URL
            url = f"solana:{recipient}"
            params = []
            
            if amount:
                params.append(f"amount={amount}")
            if label:
                params.append(f"label={label}")
            if message:
                params.append(f"message={message}")
            if memo:
                params.append(f"memo={memo}")
            
            if params:
                url += "?" + "&".join(params)
            
            return {
                "status": "success",
                "payment_url": url,
                "recipient": recipient,
                "amount": amount
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
