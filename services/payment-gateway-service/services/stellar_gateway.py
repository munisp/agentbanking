"""
Stellar Gateway Integration
Fast and low-cost cross-border payments
"""

from typing import Dict, Optional
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk.exceptions import NotFoundError, BadRequestError


class StellarGateway:
    """Stellar payment gateway implementation"""
    
    def __init__(
        self,
        horizon_url: str = "https://horizon.stellar.org",
        network_passphrase: str = Network.PUBLIC_NETWORK_PASSPHRASE,
        secret_key: Optional[str] = None
    ):
        self.server = Server(horizon_url=horizon_url)
        self.network_passphrase = network_passphrase
        
        if secret_key:
            self.keypair = Keypair.from_secret(secret_key)
        else:
            self.keypair = None
    
    async def get_balance(self, address: str) -> Dict:
        """
        Get balances for address
        
        Args:
            address: Stellar address (public key)
        """
        try:
            account = self.server.accounts().account_id(address).call()
            
            balances = []
            for balance in account['balances']:
                if balance['asset_type'] == 'native':
                    balances.append({
                        "asset": "XLM",
                        "balance": float(balance['balance']),
                        "asset_type": "native"
                    })
                else:
                    balances.append({
                        "asset": balance.get('asset_code', 'Unknown'),
                        "balance": float(balance['balance']),
                        "asset_type": balance['asset_type'],
                        "asset_issuer": balance.get('asset_issuer')
                    })
            
            return {
                "status": "success",
                "address": address,
                "balances": balances,
                "sequence": account['sequence']
            }
        except NotFoundError:
            return {
                "status": "failed",
                "error": "Account not found"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def send_payment(
        self,
        destination: str,
        amount: float,
        asset_code: str = "XLM",
        asset_issuer: Optional[str] = None,
        memo: Optional[str] = None
    ) -> Dict:
        """
        Send payment
        
        Args:
            destination: Destination address
            amount: Amount to send
            asset_code: Asset code (XLM, USDC, etc.)
            asset_issuer: Asset issuer (required for non-native assets)
            memo: Optional memo
        """
        if not self.keypair:
            return {
                "status": "failed",
                "error": "No secret key configured"
            }
        
        try:
            # Load source account
            source_account = self.server.load_account(self.keypair.public_key)
            
            # Create asset
            if asset_code == "XLM":
                asset = Asset.native()
            else:
                if not asset_issuer:
                    return {
                        "status": "failed",
                        "error": "Asset issuer required for non-native assets"
                    }
                asset = Asset(asset_code, asset_issuer)
            
            # Build transaction
            transaction_builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100
            )
            
            # Add payment operation
            transaction_builder.append_payment_op(
                destination=destination,
                amount=str(amount),
                asset=asset
            )
            
            # Add memo if provided
            if memo:
                from stellar_sdk import TextMemo
                transaction_builder.add_text_memo(memo)
            
            # Build and sign transaction
            transaction = transaction_builder.set_timeout(30).build()
            transaction.sign(self.keypair)
            
            # Submit transaction
            response = self.server.submit_transaction(transaction)
            
            return {
                "status": "success",
                "hash": response['hash'],
                "ledger": response['ledger'],
                "from_address": self.keypair.public_key,
                "to_address": destination,
                "amount": amount,
                "asset": asset_code
            }
        except BadRequestError as e:
            return {
                "status": "failed",
                "error": e.message,
                "extras": e.extras
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def create_trust_line(
        self,
        asset_code: str,
        asset_issuer: str,
        limit: Optional[str] = None
    ) -> Dict:
        """
        Create trust line for asset
        
        Args:
            asset_code: Asset code
            asset_issuer: Asset issuer
            limit: Optional trust line limit
        """
        if not self.keypair:
            return {
                "status": "failed",
                "error": "No secret key configured"
            }
        
        try:
            # Load source account
            source_account = self.server.load_account(self.keypair.public_key)
            
            # Create asset
            asset = Asset(asset_code, asset_issuer)
            
            # Build transaction
            transaction_builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100
            )
            
            # Add change trust operation
            transaction_builder.append_change_trust_op(
                asset=asset,
                limit=limit
            )
            
            # Build and sign transaction
            transaction = transaction_builder.set_timeout(30).build()
            transaction.sign(self.keypair)
            
            # Submit transaction
            response = self.server.submit_transaction(transaction)
            
            return {
                "status": "success",
                "hash": response['hash'],
                "asset_code": asset_code,
                "asset_issuer": asset_issuer
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
            transaction = self.server.transactions().transaction(tx_hash).call()
            
            return {
                "status": "success",
                "hash": transaction['hash'],
                "ledger": transaction['ledger'],
                "created_at": transaction['created_at'],
                "source_account": transaction['source_account'],
                "fee_charged": int(transaction['fee_charged']),
                "operation_count": transaction['operation_count'],
                "successful": transaction['successful'],
                "memo": transaction.get('memo')
            }
        except NotFoundError:
            return {
                "status": "failed",
                "error": "Transaction not found"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_payments(self, address: str, limit: int = 10) -> Dict:
        """
        Get payment history for address
        
        Args:
            address: Stellar address
            limit: Number of payments to return
        """
        try:
            payments = self.server.payments().for_account(address).limit(limit).call()
            
            payment_list = []
            for payment in payments['_embedded']['records']:
                if payment['type'] in ['payment', 'create_account']:
                    payment_list.append({
                        "id": payment['id'],
                        "type": payment['type'],
                        "created_at": payment['created_at'],
                        "transaction_hash": payment['transaction_hash'],
                        "from": payment.get('from'),
                        "to": payment.get('to'),
                        "amount": float(payment.get('amount', 0)),
                        "asset_type": payment.get('asset_type'),
                        "asset_code": payment.get('asset_code')
                    })
            
            return {
                "status": "success",
                "payments": payment_list
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def get_account_info(self, address: str) -> Dict:
        """
        Get account information
        
        Args:
            address: Stellar address
        """
        try:
            account = self.server.accounts().account_id(address).call()
            
            return {
                "status": "success",
                "address": address,
                "sequence": account['sequence'],
                "subentry_count": account['subentry_count'],
                "num_sponsoring": account.get('num_sponsoring', 0),
                "num_sponsored": account.get('num_sponsored', 0),
                "balances": account['balances'],
                "signers": account['signers'],
                "flags": account['flags']
            }
        except NotFoundError:
            return {
                "status": "failed",
                "error": "Account not found"
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def path_payment(
        self,
        destination: str,
        destination_asset_code: str,
        destination_asset_issuer: Optional[str],
        destination_amount: float,
        source_asset_code: str,
        source_asset_issuer: Optional[str],
        max_source_amount: float
    ) -> Dict:
        """
        Send path payment (currency conversion)
        
        Args:
            destination: Destination address
            destination_asset_code: Destination asset code
            destination_asset_issuer: Destination asset issuer
            destination_amount: Destination amount
            source_asset_code: Source asset code
            source_asset_issuer: Source asset issuer
            max_source_amount: Maximum source amount
        """
        if not self.keypair:
            return {
                "status": "failed",
                "error": "No secret key configured"
            }
        
        try:
            # Load source account
            source_account = self.server.load_account(self.keypair.public_key)
            
            # Create assets
            if destination_asset_code == "XLM":
                dest_asset = Asset.native()
            else:
                dest_asset = Asset(destination_asset_code, destination_asset_issuer)
            
            if source_asset_code == "XLM":
                source_asset = Asset.native()
            else:
                source_asset = Asset(source_asset_code, source_asset_issuer)
            
            # Build transaction
            transaction_builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100
            )
            
            # Add path payment operation
            transaction_builder.append_path_payment_strict_receive_op(
                destination=destination,
                send_asset=source_asset,
                send_max=str(max_source_amount),
                dest_asset=dest_asset,
                dest_amount=str(destination_amount),
                path=[]
            )
            
            # Build and sign transaction
            transaction = transaction_builder.set_timeout(30).build()
            transaction.sign(self.keypair)
            
            # Submit transaction
            response = self.server.submit_transaction(transaction)
            
            return {
                "status": "success",
                "hash": response['hash'],
                "ledger": response['ledger']
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def create_wallet(self) -> Dict:
        """Create new Stellar wallet"""
        keypair = Keypair.random()
        return {
            "status": "success",
            "public_key": keypair.public_key,
            "secret_key": keypair.secret
        }
    
    def is_valid_address(self, address: str) -> bool:
        """Check if address is valid"""
        try:
            Keypair.from_public_key(address)
            return True
        except:
            return False
