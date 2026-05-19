import logging
import os
import sys
logging.basicConfig(level=logging.INFO)
import uuid
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json

logger = logging.getLogger(__name__)

class CIPSAccountType(Enum):
    """TigerBeetle account types for CIPS system"""

    CIPS_NOSTRO_USD = 2000
    CIPS_NOSTRO_EUR = 2001
    CIPS_NOSTRO_GBP = 2002
    CIPS_NOSTRO_CNY = 2003
    CIPS_VOSTRO_NGN = 2004
    CIPS_SETTLEMENT = 2005
    CIPS_FX_RESERVE = 2006
    CIPS_CORRESPONDENT_BANK = 2007
    CIPS_CLEARING = 2008
    CIPS_SUSPENSE = 2009

class Currency(Enum):
    """Supported currencies for CIPS"""

    NGN = 566  # Nigerian Naira
    USD = 840  # US Dollar
    EUR = 978  # Euro
    GBP = 826  # British Pound
    CNY = 156  # Chinese Yuan

class CIPSTransferFlags:
    """TigerBeetle transfer flags for CIPS operations"""

    CIPS_CROSS_BORDER = 1 << 3
    CIPS_FX_SETTLEMENT = 1 << 4
    CIPS_CORRESPONDENT = 1 << 5
    CIPS_CLEARING = 1 << 6
    CIPS_NOSTRO_VOSTRO = 1 << 7
    PENDING = 1 << 9
    VOIDED = 1 << 10
    HIGH_PRIORITY = 1 << 13
    REGULATORY_REPORTING = 1 << 14
    AUDIT_REQUIRED = 1 << 15

class CIPSTigerBeetleService:
    """
    CIPS TigerBeetle integration service for cross-border payment processing
    Handles nostro/vostro accounts, FX settlements, and correspondent banking
    """

    
    def __init__(self) -> None:
        self.cluster_id = 0xABCDEF1234567890ABCDEF1234567890
        self.connected = False
        self.client = None
        self.performance_metrics = {
            'total_cross_border_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'total_fx_conversions': 0,
            'average_settlement_time': 0.0,
            'average_latency_ms': 0.0,
            'last_operation_time': None
        }
        
        # Account caches for CIPS operations
        self.nostro_accounts = {}        # currency -> account_id mapping
        self.vostro_accounts = {}        # currency -> account_id mapping
        self.correspondent_accounts = {} # bank_bic -> account_id mapping
        self.system_accounts = {}        # account_type -> account_id mapping
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize TigerBeetle client connection for CIPS"""
        try:
            logger.info("Initializing CIPS TigerBeetle connection...")
            
            # Simulate connection setup for CIPS ledger
            self.client = {
                'cluster_id': self.cluster_id,
                'connected_at': datetime.utcnow(),
                'batch_size_max': 8190,
                'ledger_type': 'CIPS_CROSS_BORDER'
            }
            
            self.connected = True
            logger.info("CIPS TigerBeetle connection established successfully")
            
            # Initialize CIPS system accounts
            self._initialize_cips_accounts()
            
        except Exception as e:
            logger.error(f"Failed to initialize CIPS TigerBeetle connection: {e}")
            self.connected = False
            raise
    
    def _initialize_cips_accounts(self) -> None:
        """Initialize CIPS system accounts (nostro, vostro, clearing, etc.)"""
        try:
            # Initialize nostro accounts (our accounts held at correspondent banks)
            nostro_currencies = [Currency.USD, Currency.EUR, Currency.GBP, Currency.CNY]
            for currency in nostro_currencies:
                account_type = getattr(CIPSAccountType, f'CIPS_NOSTRO_{currency.name}')
                account_id = self._generate_system_account_id(account_type, currency)
                
                if not self._account_exists(account_id):
                    self._create_account(
                        account_id=account_id,
                        user_data=0,
                        account_type=account_type,
                        currency=currency,
                        flags=0
                    )
                
                self.nostro_accounts[currency.name] = account_id
                logger.info(f"Initialized CIPS nostro account for {currency.name}: {account_id}")
            
            # Initialize vostro accounts (correspondent banks' accounts with us)
            vostro_currencies = [Currency.NGN]
            for currency in vostro_currencies:
                account_type = CIPSAccountType.CIPS_VOSTRO_NGN
                account_id = self._generate_system_account_id(account_type, currency)
                
                if not self._account_exists(account_id):
                    self._create_account(
                        account_id=account_id,
                        user_data=0,
                        account_type=account_type,
                        currency=currency,
                        flags=0
                    )
                
                self.vostro_accounts[currency.name] = account_id
                logger.info(f"Initialized CIPS vostro account for {currency.name}: {account_id}")
            
            # Initialize other system accounts
            system_account_types = [
                CIPSAccountType.CIPS_SETTLEMENT,
                CIPSAccountType.CIPS_FX_RESERVE,
                CIPSAccountType.CIPS_CLEARING,
                CIPSAccountType.CIPS_SUSPENSE
            ]
            
            for account_type in system_account_types:
                for currency in [Currency.NGN, Currency.USD, Currency.EUR, Currency.GBP, Currency.CNY]:
                    account_id = self._generate_system_account_id(account_type, currency)
                    
                    if not self._account_exists(account_id):
                        self._create_account(
                            account_id=account_id,
                            user_data=0,
                            account_type=account_type,
                            currency=currency,
                            flags=0
                        )
                    
                    cache_key = f"{account_type.name}_{currency.name}"
                    self.system_accounts[cache_key] = account_id
            
            logger.info("CIPS system accounts initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CIPS system accounts: {e}")
            raise
    
    def process_cross_border_payment(
        self,
        payment_id: str,
        sender_account: str,
        receiver_account: str,
        amount: int,
        source_currency: str,
        target_currency: str,
        fx_rate: float,
        correspondent_banks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process cross-border payment through CIPS with TigerBeetle
        
        This handles the complete cross-border payment flow:
        1. Debit sender's account to nostro account
        2. FX conversion (if needed)
        3. Transfer to correspondent bank
        4. Credit receiver's account
        """
        try:
            if not self.connected:
                raise Exception("CIPS TigerBeetle client not connected")
            
            start_time = time.time()
            transfers = []
            transfer_ids = []
            
            # Get system accounts
            sender_nostro = self._get_nostro_account(source_currency)
            receiver_nostro = self._get_nostro_account(target_currency) if source_currency != target_currency else sender_nostro
            settlement_account = self._get_system_account(CIPSAccountType.CIPS_SETTLEMENT, source_currency)
            
            # Generate transfer IDs
            base_transfer_id = int(time.time() * 1000000)  # Microsecond timestamp
            
            # Step 1: Debit sender account to nostro account
            sender_transfer_id = base_transfer_id + 1
            sender_transfer = {
                'id': sender_transfer_id,
                'debit_account_id': self._generate_customer_account_id(sender_account, source_currency),
                'credit_account_id': sender_nostro,
                'amount': amount,
                'pending_id': 0,
                'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                'code': Currency[source_currency].value,
                'ledger': 2,  # CIPS cross-border ledger
                'flags': CIPSTransferFlags.CIPS_CROSS_BORDER | CIPSTransferFlags.AUDIT_REQUIRED,
                'timestamp': 0
            }
            transfers.append(sender_transfer)
            transfer_ids.append(sender_transfer_id)
            
            # Step 2: FX conversion (if currencies differ)
            if source_currency != target_currency:
                converted_amount = int(amount * fx_rate)
                
                fx_transfer_id = base_transfer_id + 2
                fx_transfer = {
                    'id': fx_transfer_id,
                    'debit_account_id': sender_nostro,
                    'credit_account_id': receiver_nostro,
                    'amount': converted_amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': Currency[target_currency].value,
                    'ledger': 2,  # CIPS cross-border ledger
                    'flags': CIPSTransferFlags.CIPS_FX_SETTLEMENT | CIPSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                transfers.append(fx_transfer)
                transfer_ids.append(fx_transfer_id)
                
                final_amount = converted_amount
            else:
                final_amount = amount
            
            # Step 3: Transfer to correspondent bank
            correspondent_transfer_id = base_transfer_id + 3
            correspondent_account_id = self._get_or_create_correspondent_account(
                correspondent_banks['receiver']['bic'],
                target_currency
            )
            
            correspondent_transfer = {
                'id': correspondent_transfer_id,
                'debit_account_id': receiver_nostro,
                'credit_account_id': correspondent_account_id,
                'amount': final_amount,
                'pending_id': 0,
                'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                'code': Currency[target_currency].value,
                'ledger': 2,  # CIPS cross-border ledger
                'flags': CIPSTransferFlags.CIPS_CORRESPONDENT | CIPSTransferFlags.HIGH_PRIORITY,
                'timestamp': 0
            }
            transfers.append(correspondent_transfer)
            transfer_ids.append(correspondent_transfer_id)
            
            # Step 4: Credit receiver account (final settlement)
            receiver_transfer_id = base_transfer_id + 4
            receiver_transfer = {
                'id': receiver_transfer_id,
                'debit_account_id': correspondent_account_id,
                'credit_account_id': self._generate_customer_account_id(receiver_account, target_currency),
                'amount': final_amount,
                'pending_id': 0,
                'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                'code': Currency[target_currency].value,
                'ledger': 2,  # CIPS cross-border ledger
                'flags': CIPSTransferFlags.CIPS_CROSS_BORDER | CIPSTransferFlags.AUDIT_REQUIRED,
                'timestamp': 0
            }
            transfers.append(receiver_transfer)
            transfer_ids.append(receiver_transfer_id)
            
            # Execute all transfers atomically
            results = self._create_transfers(transfers)
            
            # Check for errors
            if any(result != 'ok' for result in results):
                error_details = [f"Transfer {i}: {result}" for i, result in enumerate(results) if result != 'ok']
                logger.error(f"CIPS cross-border payment failed for {payment_id}: {error_details}")
                
                self._update_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
                
                return {
                    'success': False,
                    'error': 'Cross-border payment execution failed',
                    'details': error_details
                }
            
            # Success
            self._update_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            self.performance_metrics['total_cross_border_operations'] += 1
            
            if source_currency != target_currency:
                self.performance_metrics['total_fx_conversions'] += 1
            
            logger.info(f"Successfully processed CIPS cross-border payment {payment_id}: {amount} {source_currency} -> {final_amount} {target_currency}")
            
            return {
                'success': True,
                'transfer_ids': transfer_ids,
                'amount': amount,
                'converted_amount': final_amount,
                'source_currency': source_currency,
                'target_currency': target_currency,
                'fx_rate': fx_rate,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self._update_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
            logger.error(f"Error processing CIPS cross-border payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reverse_cross_border_payment(
        self,
        payment_id: str,
        original_transfer_ids: List[int],
        reason: str
    ) -> Dict[str, Any]:
        """
        Reverse a cross-border payment by creating offsetting transfers
        """
        try:
            if not self.connected:
                raise Exception("CIPS TigerBeetle client not connected")
            
            start_time = time.time()
            reversal_transfers = []
            reversal_ids = []
            
            # Get original transfers to reverse them
            original_transfers = self._get_transfers(original_transfer_ids)
            
            if not original_transfers:
                return {
                    'success': False,
                    'error': 'Original transfers not found'
                }
            
            # Create reversal transfers (swap debit/credit accounts)
            base_reversal_id = int(time.time() * 1000000)
            
            for i, original_transfer in enumerate(original_transfers):
                reversal_id = base_reversal_id + i + 1
                
                reversal_transfer = {
                    'id': reversal_id,
                    'debit_account_id': original_transfer['credit_account_id'],
                    'credit_account_id': original_transfer['debit_account_id'],
                    'amount': original_transfer['amount'],
                    'pending_id': 0,
                    'user_data': hash(f"{payment_id}_reversal") & 0xFFFFFFFFFFFFFFFF,
                    'code': original_transfer['code'],
                    'ledger': original_transfer['ledger'],
                    'flags': CIPSTransferFlags.VOIDED | CIPSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                
                reversal_transfers.append(reversal_transfer)
                reversal_ids.append(reversal_id)
            
            # Execute reversal transfers
            results = self._create_transfers(reversal_transfers)
            
            # Check for errors
            if any(result != 'ok' for result in results):
                error_details = [f"Reversal {i}: {result}" for i, result in enumerate(results) if result != 'ok']
                logger.error(f"CIPS payment reversal failed for {payment_id}: {error_details}")
                
                return {
                    'success': False,
                    'error': 'Payment reversal failed',
                    'details': error_details
                }
            
            self._update_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            
            logger.info(f"Successfully reversed CIPS cross-border payment {payment_id}")
            
            return {
                'success': True,
                'reversal_id': f"{payment_id}_reversal",
                'reversal_transfer_ids': reversal_ids,
                'reason': reason,
                'reversed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reversing CIPS cross-border payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def complete_settlement(
        self,
        payment_id: str,
        transfer_ids: List[int],
        settlement_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete settlement for a cross-border payment
        """
        try:
            if not self.connected:
                raise Exception("CIPS TigerBeetle client not connected")
            
            # Update settlement metrics
            settlement_time = settlement_info.get('settlement_time_seconds', 300)
            current_avg = self.performance_metrics['average_settlement_time']
            total_ops = self.performance_metrics['total_cross_border_operations']
            
            if total_ops > 0:
                self.performance_metrics['average_settlement_time'] = (
                    (current_avg * (total_ops - 1) + settlement_time) / total_ops
                )
            
            logger.info(f"Completed settlement for CIPS payment {payment_id}")
            
            return {
                'success': True,
                'settlement_completed': True,
                'settlement_time': settlement_time,
                'completed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error completing settlement for payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_nostro_balance(self, currency: str) -> Dict[str, Any]:
        """Get nostro account balance for a specific currency"""
        try:
            if currency not in self.nostro_accounts:
                return {
                    'success': False,
                    'error': f'Nostro account not found for currency: {currency}'
                }
            
            account_id = self.nostro_accounts[currency]
            balance = self._get_account_balance(account_id)
            
            return {
                'success': True,
                'currency': currency,
                'account_id': account_id,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting nostro balance for {currency}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_vostro_balance(self, currency: str) -> Dict[str, Any]:
        """Get vostro account balance for a specific currency"""
        try:
            if currency not in self.vostro_accounts:
                return {
                    'success': False,
                    'error': f'Vostro account not found for currency: {currency}'
                }
            
            account_id = self.vostro_accounts[currency]
            balance = self._get_account_balance(account_id)
            
            return {
                'success': True,
                'currency': currency,
                'account_id': account_id,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting vostro balance for {currency}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get CIPS TigerBeetle service performance metrics"""
        return {
            'connected': self.connected,
            'cluster_id': hex(self.cluster_id),
            'ledger_type': 'CIPS_CROSS_BORDER',
            'metrics': self.performance_metrics.copy(),
            'account_stats': {
                'nostro_accounts': len(self.nostro_accounts),
                'vostro_accounts': len(self.vostro_accounts),
                'correspondent_accounts': len(self.correspondent_accounts),
                'system_accounts': len(self.system_accounts)
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on CIPS TigerBeetle service"""
        try:
            if not self.connected:
                return {
                    'healthy': False,
                    'error': 'Not connected to CIPS TigerBeetle',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Check nostro account balances
            nostro_health = {}
            for currency, account_id in self.nostro_accounts.items():
                try:
                    balance = self._get_account_balance(account_id)
                    nostro_health[currency] = {
                        'account_id': account_id,
                        'balance_available': balance['available_balance'],
                        'status': 'healthy'
                    }
                except Exception as e:
                    nostro_health[currency] = {
                        'account_id': account_id,
                        'status': 'unhealthy',
                        'error': str(e)
                    }
            
            return {
                'healthy': self.connected,
                'connected': self.connected,
                'cluster_id': hex(self.cluster_id),
                'ledger_type': 'CIPS_CROSS_BORDER',
                'nostro_accounts': nostro_health,
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': self.performance_metrics
            }
            
        except Exception as e:
            logger.error(f"CIPS health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    # Private helper methods
    
    def _get_nostro_account(self, currency: str) -> int:
        """Get nostro account ID for currency"""
        if currency not in self.nostro_accounts:
            raise Exception(f"Nostro account not found for currency: {currency}")
        return self.nostro_accounts[currency]
    
    def _get_vostro_account(self, currency: str) -> int:
        """Get vostro account ID for currency"""
        if currency not in self.vostro_accounts:
            raise Exception(f"Vostro account not found for currency: {currency}")
        return self.vostro_accounts[currency]
    
    def _get_system_account(self, account_type: CIPSAccountType, currency: str) -> int:
        """Get system account ID"""

        cache_key = f"{account_type.name}_{currency}"
        if cache_key not in self.system_accounts:
            raise Exception(f"System account not found: {cache_key}")
        return self.system_accounts[cache_key]
    
    def _get_or_create_correspondent_account(self, bank_bic: str, currency: str) -> int:
        """Get or create correspondent bank account"""

        cache_key = f"{bank_bic}_{currency}"
        
        if cache_key in self.correspondent_accounts:
            return self.correspondent_accounts[cache_key]
        
        # Generate account ID for correspondent bank
        account_id = self._generate_correspondent_account_id(bank_bic, currency)
        
        if not self._account_exists(account_id):
            self._create_account(
                account_id=account_id,
                user_data=hash(bank_bic) & 0xFFFFFFFFFFFFFFFF,
                account_type=CIPSAccountType.CIPS_CORRESPONDENT_BANK,
                currency=Currency[currency],
                flags=0
            )
        
        self.correspondent_accounts[cache_key] = account_id
        return account_id
    
    def _generate_customer_account_id(self, account_number: str, currency: str) -> int:
        """Generate account ID for customer account"""

        hash_value = hash(f"customer_{account_number}_{currency}")
        return abs(hash_value) & 0x7FFFFFFFFFFFFFFF
    
    def _generate_correspondent_account_id(self, bank_bic: str, currency: str) -> int:
        """Generate account ID for correspondent bank"""

        hash_value = hash(f"correspondent_{bank_bic}_{currency}")
        return abs(hash_value) & 0x7FFFFFFFFFFFFFFF
    
    def _generate_system_account_id(self, account_type: CIPSAccountType, currency: Currency) -> int:
        """Generate deterministic account ID for system accounts"""

        type_value = account_type.value
        currency_value = currency.value
        combined = (type_value << 32) | currency_value
        return combined & 0x7FFFFFFFFFFFFFFF
    
    def _account_exists(self, account_id: int) -> bool:
        """Check if account exists in TigerBeetle"""
        # Simulate account existence check
        return False  # Always return False to trigger account creation in simulation
    
    def _create_account(
        self,
        account_id: int,
        user_data: int,
        account_type: CIPSAccountType,
        currency: Currency,
        flags: int
    ) -> bool:
        """
Create account in TigerBeetle"""
        try:
            # Simulate account creation
            account_data = {
                'id': account_id,
                'user_data': user_data,
                'ledger': 2,  # CIPS cross-border ledger
                'code': account_type.value,
                'flags': flags,
                'debits_pending': 0,
                'debits_posted': 0,
                'credits_pending': 0,
                'credits_posted': 0,
                'timestamp': 0
            }
            
            logger.debug(f"Created CIPS TigerBeetle account: {account_data}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating CIPS account {account_id}: {e}")
            return False
    
    def _create_transfers(self, transfers: List[Dict[str, Any]]) -> List[str]:
        """Create transfers in TigerBeetle"""
        try:
            # Simulate transfer creation
            results = []
            
            for transfer in transfers:
                # Simulate transfer validation and execution
                if transfer['amount'] <= 0:
                    results.append('invalid_amount')
                elif transfer['debit_account_id'] == transfer['credit_account_id']:
                    results.append('same_account')
                else:
                    results.append('ok')
                    logger.debug(f"Created CIPS TigerBeetle transfer: {transfer}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error creating CIPS transfers: {e}")
            return ['error'] * len(transfers)
    
    def _get_transfers(self, transfer_ids: List[int]) -> List[Dict[str, Any]]:
        """Get transfers by IDs"""
        try:
            # Simulate transfer retrieval
            transfers = []
            
            for transfer_id in transfer_ids:
                # Simulate transfer data
                transfer = {
                    'id': transfer_id,
                    'debit_account_id': 12345,
                    'credit_account_id': 67890,
                    'amount': 100000,
                    'code': Currency.USD.value,
                    'ledger': 2,
                    'flags': CIPSTransferFlags.CIPS_CROSS_BORDER
                }
                transfers.append(transfer)
            
            return transfers
            
        except Exception as e:
            logger.error(f"Error getting transfers: {e}")
            return []
    
    def _get_account_balance(self, account_id: int) -> Dict[str, Any]:
        """Get account balance from TigerBeetle"""
        try:
            # Simulate balance query
            balance_data = {
                'account_id': account_id,
                'debits_pending': 0,
                'debits_posted': 50000,
                'credits_pending': 0,
                'credits_posted': 150000,  # Simulated balance
                'timestamp': int(time.time())
            }
            
            net_balance = balance_data['credits_posted'] - balance_data['debits_posted']
            pending_balance = balance_data['credits_pending'] - balance_data['debits_pending']
            
            return {
                'account_id': account_id,
                'available_balance': net_balance,
                'pending_balance': pending_balance,
                'total_balance': net_balance + pending_balance,
                'debits_posted': balance_data['debits_posted'],
                'credits_posted': balance_data['credits_posted'],
                'debits_pending': balance_data['debits_pending'],
                'credits_pending': balance_data['credits_pending'],
                'last_updated': datetime.fromtimestamp(balance_data['timestamp']).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting account balance for {account_id}: {e}")
            raise
    
    def _update_metrics(self, success: bool, latency_ms: float) -> None:
        """Update performance metrics"""

        self.performance_metrics['total_cross_border_operations'] += 1
        self.performance_metrics['last_operation_time'] = datetime.utcnow().isoformat()
        
        if success:
            self.performance_metrics['successful_operations'] += 1
        else:
            self.performance_metrics['failed_operations'] += 1
        
        # Update average latency (simple moving average)
        current_avg = self.performance_metrics['average_latency_ms']
        total_ops = self.performance_metrics['total_cross_border_operations']
        self.performance_metrics['average_latency_ms'] = (
            (current_avg * (total_ops - 1) + latency_ms) / total_ops
        )

