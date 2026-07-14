"""
Polygon (MATIC) Gateway Integration
Low-cost Ethereum-compatible blockchain for fast transactions
"""

from typing import Dict, Optional
from web3 import Web3
from eth_account import Account
from decimal import Decimal


class PolygonGateway:
    """Polygon payment gateway implementation"""
    
    def __init__(
        self,
        rpc_url: str,
        chain_id: int = 137,  # 137 for mainnet, 80001 for Mumbai testnet
        private_key: Optional[str] = None
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        
        if private_key:
            self.account = Account.from_key(private_key)
        else:
            self.account = None
        
        # USDC contract on Polygon
        self.usdc_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        # USDT contract on Polygon
        self.usdt_address = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
        
        # ERC20 ABI (minimal)
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            }
        ]
    
    def _to_wei(self, amount: float, decimals: int = 18) -> int:
        """Convert amount to wei"""
        return int(amount * (10 ** decimals))
    
    def _from_wei(self, amount: int, decimals: int = 18) -> float:
        """Convert wei to amount"""
        return float(amount) / (10 ** decimals)
    
    async def get_balance(self, address: str, token: str = "MATIC") -> Dict:
        """
        Get balance for address
        
        Args:
            address: Wallet address
            token: Token symbol (MATIC, USDC, USDT, or contract address)
        """
        try:
            if token == "MATIC":
                balance_wei = self.w3.eth.get_balance(address)
                balance = self._from_wei(balance_wei, 18)
                return {
                    "status": "success",
                    "balance": balance,
                    "token": "MATIC",
                    "address": address
                }
            else:
                # Get token contract address
                if token == "USDC":
                    token_address = self.usdc_address
                    decimals = 6
                elif token == "USDT":
                    token_address = self.usdt_address
                    decimals = 6
                else:
                    token_address = token
                    # Get decimals from contract
                    contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
                    decimals = contract.functions.decimals().call()
                
                # Get balance
                contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
                balance_raw = contract.functions.balanceOf(address).call()
                balance = self._from_wei(balance_raw, decimals)
                
                return {
                    "status": "success",
                    "balance": balance,
                    "token": token,
                    "address": address,
                    "token_address": token_address
                }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_matic(
        self,
        to_address: str,
        amount: float,
        gas_price_gwei: Optional[float] = None
    ) -> Dict:
        """
        Send MATIC
        
        Args:
            to_address: Recipient address
            amount: Amount in MATIC
            gas_price_gwei: Gas price in Gwei (optional)
        """
        if not self.account:
            return {
                "status": "failed",
                "error": "No private key configured"
            }
        
        try:
            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Get gas price
            if gas_price_gwei:
                gas_price = self.w3.to_wei(gas_price_gwei, 'gwei')
            else:
                gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = {
                'nonce': nonce,
                'to': to_address,
                'value': self._to_wei(amount, 18),
                'gas': 21000,
                'gasPrice': gas_price,
                'chainId': self.chain_id
            }
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return {
                "status": "success",
                "tx_hash": tx_hash.hex(),
                "from_address": self.account.address,
                "to_address": to_address,
                "amount": amount,
                "token": "MATIC"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_token(
        self,
        to_address: str,
        amount: float,
        token: str = "USDC",
        gas_price_gwei: Optional[float] = None
    ) -> Dict:
        """
        Send ERC20 token
        
        Args:
            to_address: Recipient address
            amount: Amount in tokens
            token: Token symbol (USDC, USDT, or contract address)
            gas_price_gwei: Gas price in Gwei (optional)
        """
        if not self.account:
            return {
                "status": "failed",
                "error": "No private key configured"
            }
        
        try:
            # Get token contract address and decimals
            if token == "USDC":
                token_address = self.usdc_address
                decimals = 6
            elif token == "USDT":
                token_address = self.usdt_address
                decimals = 6
            else:
                token_address = token
                contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
                decimals = contract.functions.decimals().call()
            
            # Get contract
            contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
            
            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            
            # Get gas price
            if gas_price_gwei:
                gas_price = self.w3.to_wei(gas_price_gwei, 'gwei')
            else:
                gas_price = self.w3.eth.gas_price
            
            # Build transaction
            transaction = contract.functions.transfer(
                to_address,
                self._to_wei(amount, decimals)
            ).build_transaction({
                'nonce': nonce,
                'gasPrice': gas_price,
                'chainId': self.chain_id
            })
            
            # Estimate gas
            transaction['gas'] = self.w3.eth.estimate_gas(transaction)
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            return {
                "status": "success",
                "tx_hash": tx_hash.hex(),
                "from_address": self.account.address,
                "to_address": to_address,
                "amount": amount,
                "token": token,
                "token_address": token_address
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_transaction(self, tx_hash: str) -> Dict:
        """
        Get transaction details
        
        Args:
            tx_hash: Transaction hash
        """
        try:
            tx = self.w3.eth.get_transaction(tx_hash)
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            return {
                "status": "success",
                "tx_hash": tx_hash,
                "from_address": tx['from'],
                "to_address": tx['to'],
                "value": self._from_wei(tx['value'], 18),
                "gas_used": receipt['gasUsed'],
                "gas_price": self._from_wei(tx['gasPrice'], 9),  # Gwei
                "block_number": receipt['blockNumber'],
                "confirmations": self.w3.eth.block_number - receipt['blockNumber'],
                "success": receipt['status'] == 1
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def wait_for_confirmation(self, tx_hash: str, confirmations: int = 12) -> Dict:
        """
        Wait for transaction confirmation
        
        Args:
            tx_hash: Transaction hash
            confirmations: Number of confirmations to wait for
        """
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            current_block = self.w3.eth.block_number
            tx_block = receipt['blockNumber']
            current_confirmations = current_block - tx_block
            
            return {
                "status": "success",
                "tx_hash": tx_hash,
                "confirmed": current_confirmations >= confirmations,
                "confirmations": current_confirmations,
                "success": receipt['status'] == 1
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def estimate_gas_fee(self, to_address: str, amount: float, token: str = "MATIC") -> Dict:
        """
        Estimate gas fee for transaction
        
        Args:
            to_address: Recipient address
            amount: Amount to send
            token: Token symbol (MATIC, USDC, USDT)
        """
        try:
            gas_price = self.w3.eth.gas_price
            
            if token == "MATIC":
                gas_limit = 21000
            else:
                # Estimate gas for token transfer
                if token == "USDC":
                    token_address = self.usdc_address
                    decimals = 6
                elif token == "USDT":
                    token_address = self.usdt_address
                    decimals = 6
                else:
                    return {
                        "status": "failed",
                        "error": "Unsupported token"
                    }
                
                contract = self.w3.eth.contract(address=token_address, abi=self.erc20_abi)
                gas_limit = contract.functions.transfer(
                    to_address,
                    self._to_wei(amount, decimals)
                ).estimate_gas({'from': self.account.address if self.account else to_address})
            
            gas_fee_wei = gas_price * gas_limit
            gas_fee_matic = self._from_wei(gas_fee_wei, 18)
            gas_price_gwei = self._from_wei(gas_price, 9)
            
            return {
                "status": "success",
                "gas_limit": gas_limit,
                "gas_price_gwei": gas_price_gwei,
                "gas_fee_matic": gas_fee_matic,
                "gas_fee_usd": gas_fee_matic * 0.5  # Approximate MATIC price
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def create_wallet(self) -> Dict:
        """Create new Polygon wallet"""
        account = Account.create()
        return {
            "status": "success",
            "address": account.address,
            "private_key": account.key.hex()
        }
    
    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid"""
        return self.w3.is_address(address)
