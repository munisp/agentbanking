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

class PAPSSAccountType(Enum):
    """TigerBeetle account types for PAPSS system"""

    PAPSS_CENTRAL_BANK_NGN = 3000
    PAPSS_CENTRAL_BANK_KES = 3001
    PAPSS_CENTRAL_BANK_GHS = 3002
    PAPSS_CENTRAL_BANK_ZAR = 3003
    PAPSS_CENTRAL_BANK_EGP = 3004
    PAPSS_CENTRAL_BANK_XOF = 3005  # West African CFA Franc
    PAPSS_CENTRAL_BANK_XAF = 3006  # Central African CFA Franc
    PAPSS_REGIONAL_SETTLEMENT = 3007
    PAPSS_MOBILE_MONEY_POOL = 3008
    PAPSS_TRADE_FINANCE_POOL = 3009
    PAPSS_FX_RESERVE = 3010
    PAPSS_CLEARING_HOUSE = 3011
    PAPSS_SUSPENSE = 3012
    PAPSS_CORRIDOR_ECOWAS = 3013
    PAPSS_CORRIDOR_EAC = 3014
    PAPSS_CORRIDOR_SADC = 3015
    PAPSS_CORRIDOR_CEMAC = 3016

class AfricanCurrency(Enum):
    """African currencies supported by PAPSS"""

    NGN = 566  # Nigerian Naira
    GHS = 936  # Ghanaian Cedi
    KES = 404  # Kenyan Shilling
    ZAR = 710  # South African Rand
    EGP = 818  # Egyptian Pound
    MAD = 504  # Moroccan Dirham
    TND = 788  # Tunisian Dinar
    ETB = 230  # Ethiopian Birr
    UGX = 800  # Ugandan Shilling
    TZS = 834  # Tanzanian Shilling
    XOF = 952  # West African CFA Franc
    XAF = 950  # Central African CFA Franc
    BWP = 72   # Botswana Pula
    MUR = 480  # Mauritian Rupee
    RWF = 646  # Rwandan Franc
    USD = 840  # US Dollar

class PAPSSTransferFlags:
    """TigerBeetle transfer flags for PAPSS operations"""

    PAPSS_PAN_AFRICAN = 1 << 3
    PAPSS_REGIONAL_SETTLEMENT = 1 << 4
    PAPSS_MOBILE_MONEY = 1 << 5
    PAPSS_TRADE_FINANCE = 1 << 6
    PAPSS_CENTRAL_BANK = 1 << 7
    PAPSS_CORRIDOR_TRANSFER = 1 << 8
    PENDING = 1 << 9
    VOIDED = 1 << 10
    HIGH_PRIORITY = 1 << 13
    REGULATORY_REPORTING = 1 << 14
    AUDIT_REQUIRED = 1 << 15

class TradeCorridorType(Enum):
    """African trade corridors"""

    ECOWAS = "ECOWAS"
    EAC = "EAC"
    SADC = "SADC"
    CEMAC = "CEMAC"

class PAPSSTigerBeetleService:
    """
    PAPSS TigerBeetle integration service for Pan-African payment processing
    Handles regional settlements, mobile money integration, and trade finance
    """

    
    def __init__(self) -> None:
        self.cluster_id = 0x1234567890ABCDEF1234567890ABCDEF
        self.connected = False
        self.client = None
        self.performance_metrics = {
            'total_pan_african_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'total_mobile_money_transactions': 0,
            'total_trade_finance_transactions': 0,
            'regional_settlement_count': 0,
            'average_settlement_time': 0.0,
            'average_latency_ms': 0.0,
            'last_operation_time': None,
            'corridor_volumes': {
                'ECOWAS': 0,
                'EAC': 0,
                'SADC': 0,
                'CEMAC': 0
            }
        }
        
        # Account caches for PAPSS operations
        self.central_bank_accounts = {}    # country -> account_id mapping
        self.corridor_accounts = {}        # corridor -> account_id mapping
        self.mobile_money_pools = {}       # country -> account_id mapping
        self.system_accounts = {}          # account_type -> account_id mapping
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self) -> None:
        """Initialize TigerBeetle client connection for PAPSS"""
        try:
            logger.info("Initializing PAPSS TigerBeetle connection...")
            
            # Simulate connection setup for PAPSS ledger
            self.client = {
                'cluster_id': self.cluster_id,
                'connected_at': datetime.utcnow(),
                'batch_size_max': 8190,
                'ledger_type': 'PAPSS_PAN_AFRICAN'
            }
            
            self.connected = True
            logger.info("PAPSS TigerBeetle connection established successfully")
            
            # Initialize PAPSS system accounts
            self._initialize_papss_accounts()
            
        except Exception as e:
            logger.error(f"Failed to initialize PAPSS TigerBeetle connection: {e}")
            self.connected = False
            raise
    
    def _initialize_papss_accounts(self) -> None:
        """Initialize PAPSS system accounts (central banks, corridors, pools, etc.)"""
        try:
            # Initialize central bank accounts for major African currencies
            central_bank_currencies = [
                (AfricanCurrency.NGN, PAPSSAccountType.PAPSS_CENTRAL_BANK_NGN),
                (AfricanCurrency.KES, PAPSSAccountType.PAPSS_CENTRAL_BANK_KES),
                (AfricanCurrency.GHS, PAPSSAccountType.PAPSS_CENTRAL_BANK_GHS),
                (AfricanCurrency.ZAR, PAPSSAccountType.PAPSS_CENTRAL_BANK_ZAR),
                (AfricanCurrency.EGP, PAPSSAccountType.PAPSS_CENTRAL_BANK_EGP),
                (AfricanCurrency.XOF, PAPSSAccountType.PAPSS_CENTRAL_BANK_XOF),
                (AfricanCurrency.XAF, PAPSSAccountType.PAPSS_CENTRAL_BANK_XAF)
            ]
            
            for currency, account_type in central_bank_currencies:
                account_id = self._generate_system_account_id(account_type, currency)
                
                if not self._account_exists(account_id):
                    self._create_account(
                        account_id=account_id,
                        user_data=0,
                        account_type=account_type,
                        currency=currency,
                        flags=0
                    )
                
                self.central_bank_accounts[currency.name] = account_id
                logger.info(f"Initialized PAPSS central bank account for {currency.name}: {account_id}")
            
            # Initialize trade corridor accounts
            corridor_types = [
                (TradeCorridorType.ECOWAS, PAPSSAccountType.PAPSS_CORRIDOR_ECOWAS),
                (TradeCorridorType.EAC, PAPSSAccountType.PAPSS_CORRIDOR_EAC),
                (TradeCorridorType.SADC, PAPSSAccountType.PAPSS_CORRIDOR_SADC),
                (TradeCorridorType.CEMAC, PAPSSAccountType.PAPSS_CORRIDOR_CEMAC)
            ]
            
            for corridor, account_type in corridor_types:
                # Create corridor accounts for each major currency
                for currency in [AfricanCurrency.NGN, AfricanCurrency.USD, AfricanCurrency.XOF, AfricanCurrency.XAF]:
                    account_id = self._generate_corridor_account_id(account_type, currency)
                    
                    if not self._account_exists(account_id):
                        self._create_account(
                            account_id=account_id,
                            user_data=hash(corridor.value) & 0xFFFFFFFFFFFFFFFF,
                            account_type=account_type,
                            currency=currency,
                            flags=0
                        )
                    
                    cache_key = f"{corridor.value}_{currency.name}"
                    self.corridor_accounts[cache_key] = account_id
                
                logger.info(f"Initialized PAPSS corridor accounts for {corridor.value}")
            
            # Initialize mobile money pool accounts
            mobile_money_countries = ['NG', 'KE', 'GH', 'UG', 'TZ', 'ZA']
            for country in mobile_money_countries:
                currency = self._get_country_currency(country)
                account_id = self._generate_mobile_money_pool_id(country, currency)
                
                if not self._account_exists(account_id):
                    self._create_account(
                        account_id=account_id,
                        user_data=hash(country) & 0xFFFFFFFFFFFFFFFF,
                        account_type=PAPSSAccountType.PAPSS_MOBILE_MONEY_POOL,
                        currency=currency,
                        flags=0
                    )
                
                self.mobile_money_pools[country] = account_id
                logger.info(f"Initialized mobile money pool for {country}: {account_id}")
            
            # Initialize other system accounts
            system_account_types = [
                PAPSSAccountType.PAPSS_REGIONAL_SETTLEMENT,
                PAPSSAccountType.PAPSS_TRADE_FINANCE_POOL,
                PAPSSAccountType.PAPSS_FX_RESERVE,
                PAPSSAccountType.PAPSS_CLEARING_HOUSE,
                PAPSSAccountType.PAPSS_SUSPENSE
            ]
            
            for account_type in system_account_types:
                for currency in [AfricanCurrency.NGN, AfricanCurrency.KES, AfricanCurrency.GHS, AfricanCurrency.ZAR, AfricanCurrency.XOF, AfricanCurrency.XAF]:
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
            
            logger.info("PAPSS system accounts initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PAPSS system accounts: {e}")
            raise
    
    def process_pan_african_payment(
        self,
        payment_id: str,
        sender_account: str,
        receiver_account: str,
        sender_country: str,
        receiver_country: str,
        amount: int,
        source_currency: str,
        target_currency: str,
        fx_rate: float,
        trade_corridor: str,
        payment_method: str
    ) -> Dict[str, Any]:
        """
        Process Pan-African payment through PAPSS with TigerBeetle
        
        This handles the complete Pan-African payment flow:
        1. Debit sender's account to central bank account
        2. Regional settlement through trade corridor
        3. FX conversion (if needed)
        4. Credit to receiver's central bank
        5. Final credit to receiver's account
        """
        try:
            if not self.connected:
                raise Exception("PAPSS TigerBeetle client not connected")
            
            start_time = time.time()
            transfers = []
            transfer_ids = []
            
            # Get system accounts
            sender_central_bank = self._get_central_bank_account(source_currency)
            receiver_central_bank = self._get_central_bank_account(target_currency) if source_currency != target_currency else sender_central_bank
            corridor_account = self._get_corridor_account(trade_corridor, source_currency)
            
            # Generate transfer IDs
            base_transfer_id = int(time.time() * 1000000)  # Microsecond timestamp
            
            # Step 1: Debit sender account to sender's central bank
            sender_transfer_id = base_transfer_id + 1
            sender_transfer = {
                'id': sender_transfer_id,
                'debit_account_id': self._generate_customer_account_id(sender_account, sender_country, source_currency),
                'credit_account_id': sender_central_bank,
                'amount': amount,
                'pending_id': 0,
                'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                'code': AfricanCurrency[source_currency].value,
                'ledger': 3,  # PAPSS Pan-African ledger
                'flags': PAPSSTransferFlags.PAPSS_PAN_AFRICAN | PAPSSTransferFlags.AUDIT_REQUIRED,
                'timestamp': 0
            }
            transfers.append(sender_transfer)
            transfer_ids.append(sender_transfer_id)
            
            # Step 2: Regional settlement through trade corridor
            corridor_transfer_id = base_transfer_id + 2
            corridor_transfer = {
                'id': corridor_transfer_id,
                'debit_account_id': sender_central_bank,
                'credit_account_id': corridor_account,
                'amount': amount,
                'pending_id': 0,
                'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                'code': AfricanCurrency[source_currency].value,
                'ledger': 3,  # PAPSS Pan-African ledger
                'flags': PAPSSTransferFlags.PAPSS_CORRIDOR_TRANSFER | PAPSSTransferFlags.PAPSS_REGIONAL_SETTLEMENT,
                'timestamp': 0
            }
            transfers.append(corridor_transfer)
            transfer_ids.append(corridor_transfer_id)
            
            # Step 3: FX conversion and transfer to receiver's central bank (if currencies differ)
            if source_currency != target_currency:
                converted_amount = int(amount * fx_rate)
                
                fx_transfer_id = base_transfer_id + 3
                fx_transfer = {
                    'id': fx_transfer_id,
                    'debit_account_id': corridor_account,
                    'credit_account_id': receiver_central_bank,
                    'amount': converted_amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': AfricanCurrency[target_currency].value,
                    'ledger': 3,  # PAPSS Pan-African ledger
                    'flags': PAPSSTransferFlags.PAPSS_REGIONAL_SETTLEMENT | PAPSSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                transfers.append(fx_transfer)
                transfer_ids.append(fx_transfer_id)
                
                final_amount = converted_amount
            else:
                # Same currency transfer through corridor
                same_currency_transfer_id = base_transfer_id + 3
                same_currency_transfer = {
                    'id': same_currency_transfer_id,
                    'debit_account_id': corridor_account,
                    'credit_account_id': receiver_central_bank,
                    'amount': amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': AfricanCurrency[source_currency].value,
                    'ledger': 3,  # PAPSS Pan-African ledger
                    'flags': PAPSSTransferFlags.PAPSS_REGIONAL_SETTLEMENT | PAPSSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                transfers.append(same_currency_transfer)
                transfer_ids.append(same_currency_transfer_id)
                
                final_amount = amount
            
            # Step 4: Handle mobile money if applicable
            if payment_method == 'mobile_money':
                mobile_money_pool = self._get_mobile_money_pool(receiver_country)
                
                mm_transfer_id = base_transfer_id + 4
                mm_transfer = {
                    'id': mm_transfer_id,
                    'debit_account_id': receiver_central_bank,
                    'credit_account_id': mobile_money_pool,
                    'amount': final_amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': AfricanCurrency[target_currency].value,
                    'ledger': 3,  # PAPSS Pan-African ledger
                    'flags': PAPSSTransferFlags.PAPSS_MOBILE_MONEY | PAPSSTransferFlags.HIGH_PRIORITY,
                    'timestamp': 0
                }
                transfers.append(mm_transfer)
                transfer_ids.append(mm_transfer_id)
                
                # Final mobile money credit
                final_transfer_id = base_transfer_id + 5
                final_transfer = {
                    'id': final_transfer_id,
                    'debit_account_id': mobile_money_pool,
                    'credit_account_id': self._generate_mobile_money_account_id(receiver_account, receiver_country),
                    'amount': final_amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': AfricanCurrency[target_currency].value,
                    'ledger': 3,  # PAPSS Pan-African ledger
                    'flags': PAPSSTransferFlags.PAPSS_MOBILE_MONEY | PAPSSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                transfers.append(final_transfer)
                transfer_ids.append(final_transfer_id)
                
            else:
                # Step 5: Credit receiver account (bank transfer)
                receiver_transfer_id = base_transfer_id + 4
                receiver_transfer = {
                    'id': receiver_transfer_id,
                    'debit_account_id': receiver_central_bank,
                    'credit_account_id': self._generate_customer_account_id(receiver_account, receiver_country, target_currency),
                    'amount': final_amount,
                    'pending_id': 0,
                    'user_data': hash(payment_id) & 0xFFFFFFFFFFFFFFFF,
                    'code': AfricanCurrency[target_currency].value,
                    'ledger': 3,  # PAPSS Pan-African ledger
                    'flags': PAPSSTransferFlags.PAPSS_PAN_AFRICAN | PAPSSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                transfers.append(receiver_transfer)
                transfer_ids.append(receiver_transfer_id)
            
            # Execute all transfers atomically
            results = self._create_transfers(transfers)
            
            # Check for errors
            if any(result != 'ok' for result in results):
                error_details = [f"Transfer {i}: {result}" for i, result in enumerate(results) if result != 'ok']
                logger.error(f"PAPSS Pan-African payment failed for {payment_id}: {error_details}")
                
                self._update_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
                
                return {
                    'success': False,
                    'error': 'Pan-African payment execution failed',
                    'details': error_details
                }
            
            # Success - update metrics
            self._update_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            self.performance_metrics['total_pan_african_operations'] += 1
            self.performance_metrics['corridor_volumes'][trade_corridor] += final_amount
            
            if payment_method == 'mobile_money':
                self.performance_metrics['total_mobile_money_transactions'] += 1
            
            if source_currency != target_currency:
                # Track regional FX conversion with detailed metrics
                fx_spread = abs(fx_rate - 1.0) * 100  # Calculate spread percentage
                fx_cost = amount * fx_spread / 100  # Calculate FX cost
                
                fx_metrics = {
                    'conversion_id': f"fx_{payment_id}_{int(time.time())}",
                    'source_currency': source_currency,
                    'target_currency': target_currency,
                    'fx_rate': fx_rate,
                    'fx_spread_percent': fx_spread,
                    'fx_cost': fx_cost,
                    'original_amount': amount,
                    'converted_amount': final_amount,
                    'trade_corridor': trade_corridor,
                    'conversion_timestamp': time.time(),
                    'provider': 'PAPSS_Regional_FX'
                }
                
                logger.info(f"FX Conversion Metrics: {fx_metrics}")
                
                # Store FX metrics for analytics (would integrate with metrics database)
                self._store_fx_conversion_metrics(fx_metrics)
            
            logger.info(f"Successfully processed PAPSS Pan-African payment {payment_id}: {amount} {source_currency} -> {final_amount} {target_currency} via {trade_corridor}")
            
            return {
                'success': True,
                'transfer_ids': transfer_ids,
                'amount': amount,
                'converted_amount': final_amount,
                'source_currency': source_currency,
                'target_currency': target_currency,
                'fx_rate': fx_rate,
                'trade_corridor': trade_corridor,
                'payment_method': payment_method,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self._update_metrics(success=False, latency_ms=(time.time() - start_time) * 1000)
            logger.error(f"Error processing PAPSS Pan-African payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def reverse_pan_african_payment(
        self,
        payment_id: str,
        original_transfer_ids: List[int],
        reason: str
    ) -> Dict[str, Any]:
        """
        Reverse a Pan-African payment by creating offsetting transfers
        """
        try:
            if not self.connected:
                raise Exception("PAPSS TigerBeetle client not connected")
            
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
                    'flags': PAPSSTransferFlags.VOIDED | PAPSSTransferFlags.AUDIT_REQUIRED,
                    'timestamp': 0
                }
                
                reversal_transfers.append(reversal_transfer)
                reversal_ids.append(reversal_id)
            
            # Execute reversal transfers
            results = self._create_transfers(reversal_transfers)
            
            # Check for errors
            if any(result != 'ok' for result in results):
                error_details = [f"Reversal {i}: {result}" for i, result in enumerate(results) if result != 'ok']
                logger.error(f"PAPSS payment reversal failed for {payment_id}: {error_details}")
                
                return {
                    'success': False,
                    'error': 'Payment reversal failed',
                    'details': error_details
                }
            
            self._update_metrics(success=True, latency_ms=(time.time() - start_time) * 1000)
            
            logger.info(f"Successfully reversed PAPSS Pan-African payment {payment_id}")
            
            return {
                'success': True,
                'reversal_id': f"{payment_id}_reversal",
                'reversal_transfer_ids': reversal_ids,
                'reason': reason,
                'reversed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reversing PAPSS Pan-African payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def complete_pan_african_settlement(
        self,
        payment_id: str,
        transfer_ids: List[int],
        settlement_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete settlement for a Pan-African payment
        """
        try:
            if not self.connected:
                raise Exception("PAPSS TigerBeetle client not connected")
            
            # Update settlement metrics
            settlement_time = settlement_info.get('settlement_time_seconds', 180)
            current_avg = self.performance_metrics['average_settlement_time']
            total_ops = self.performance_metrics['total_pan_african_operations']
            
            if total_ops > 0:
                self.performance_metrics['average_settlement_time'] = (
                    (current_avg * (total_ops - 1) + settlement_time) / total_ops
                )
            
            self.performance_metrics['regional_settlement_count'] += 1
            
            logger.info(f"Completed settlement for PAPSS payment {payment_id}")
            
            return {
                'success': True,
                'settlement_completed': True,
                'settlement_time': settlement_time,
                'completed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error completing settlement for PAPSS payment {payment_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_central_bank_balance(self, currency: str) -> Dict[str, Any]:
        """Get central bank account balance for a specific currency"""
        try:
            if currency not in self.central_bank_accounts:
                return {
                    'success': False,
                    'error': f'Central bank account not found for currency: {currency}'
                }
            
            account_id = self.central_bank_accounts[currency]
            balance = self._get_account_balance(account_id)
            
            return {
                'success': True,
                'currency': currency,
                'account_id': account_id,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting central bank balance for {currency}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_corridor_balance(self, corridor: str, currency: str) -> Dict[str, Any]:
        """Get trade corridor account balance"""
        try:
            cache_key = f"{corridor}_{currency}"
            if cache_key not in self.corridor_accounts:
                return {
                    'success': False,
                    'error': f'Corridor account not found: {cache_key}'
                }
            
            account_id = self.corridor_accounts[cache_key]
            balance = self._get_account_balance(account_id)
            
            return {
                'success': True,
                'corridor': corridor,
                'currency': currency,
                'account_id': account_id,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting corridor balance for {corridor}_{currency}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_mobile_money_pool_balance(self, country: str) -> Dict[str, Any]:
        """Get mobile money pool balance for a country"""
        try:
            if country not in self.mobile_money_pools:
                return {
                    'success': False,
                    'error': f'Mobile money pool not found for country: {country}'
                }
            
            account_id = self.mobile_money_pools[country]
            balance = self._get_account_balance(account_id)
            
            return {
                'success': True,
                'country': country,
                'account_id': account_id,
                'balance': balance
            }
            
        except Exception as e:
            logger.error(f"Error getting mobile money pool balance for {country}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get PAPSS TigerBeetle service performance metrics"""
        return {
            'connected': self.connected,
            'cluster_id': hex(self.cluster_id),
            'ledger_type': 'PAPSS_PAN_AFRICAN',
            'metrics': self.performance_metrics.copy(),
            'account_stats': {
                'central_bank_accounts': len(self.central_bank_accounts),
                'corridor_accounts': len(self.corridor_accounts),
                'mobile_money_pools': len(self.mobile_money_pools),
                'system_accounts': len(self.system_accounts)
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on PAPSS TigerBeetle service"""
        try:
            if not self.connected:
                return {
                    'healthy': False,
                    'error': 'Not connected to PAPSS TigerBeetle',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Check central bank account balances
            central_bank_health = {}
            for currency, account_id in self.central_bank_accounts.items():
                try:
                    balance = self._get_account_balance(account_id)
                    central_bank_health[currency] = {
                        'account_id': account_id,
                        'balance_available': balance['available_balance'],
                        'status': 'healthy'
                    }
                except Exception as e:
                    central_bank_health[currency] = {
                        'account_id': account_id,
                        'status': 'unhealthy',
                        'error': str(e)
                    }
            
            # Check corridor account health
            corridor_health = {}
            for corridor_key, account_id in self.corridor_accounts.items():
                try:
                    balance = self._get_account_balance(account_id)
                    corridor_health[corridor_key] = {
                        'account_id': account_id,
                        'balance_available': balance['available_balance'],
                        'status': 'healthy'
                    }
                except Exception as e:
                    corridor_health[corridor_key] = {
                        'account_id': account_id,
                        'status': 'unhealthy',
                        'error': str(e)
                    }
            
            return {
                'healthy': self.connected,
                'connected': self.connected,
                'cluster_id': hex(self.cluster_id),
                'ledger_type': 'PAPSS_PAN_AFRICAN',
                'central_bank_accounts': central_bank_health,
                'corridor_accounts': corridor_health,
                'mobile_money_pools': len(self.mobile_money_pools),
                'timestamp': datetime.utcnow().isoformat(),
                'metrics': self.performance_metrics
            }
            
        except Exception as e:
            logger.error(f"PAPSS health check failed: {e}")
            return {
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    # Private helper methods
    
    def _get_central_bank_account(self, currency: str) -> int:
        """Get central bank account ID for currency"""
        if currency not in self.central_bank_accounts:
            raise Exception(f"Central bank account not found for currency: {currency}")
        return self.central_bank_accounts[currency]
    
    def _get_corridor_account(self, corridor: str, currency: str) -> int:
        """Get trade corridor account ID"""

        cache_key = f"{corridor}_{currency}"
        if cache_key not in self.corridor_accounts:
            raise Exception(f"Corridor account not found: {cache_key}")
        return self.corridor_accounts[cache_key]
    
    def _get_mobile_money_pool(self, country: str) -> int:
        """Get mobile money pool account ID for country"""
        if country not in self.mobile_money_pools:
            raise Exception(f"Mobile money pool not found for country: {country}")
        return self.mobile_money_pools[country]
    
    def _get_system_account(self, account_type: PAPSSAccountType, currency: str) -> int:
        """Get system account ID"""

        cache_key = f"{account_type.name}_{currency}"
        if cache_key not in self.system_accounts:
            raise Exception(f"System account not found: {cache_key}")
        return self.system_accounts[cache_key]
    
    def _get_country_currency(self, country_code: str) -> AfricanCurrency:
        """Get primary currency for a country"""

        country_currencies = {
            'NG': AfricanCurrency.NGN,
            'KE': AfricanCurrency.KES,
            'GH': AfricanCurrency.GHS,
            'ZA': AfricanCurrency.ZAR,
            'EG': AfricanCurrency.EGP,
            'UG': AfricanCurrency.UGX,
            'TZ': AfricanCurrency.TZS,
            'BW': AfricanCurrency.BWP,
            'MU': AfricanCurrency.MUR,
            'RW': AfricanCurrency.RWF
        }
        return country_currencies.get(country_code, AfricanCurrency.NGN)
    
    def _generate_customer_account_id(self, account_number: str, country: str, currency: str) -> int:
        """Generate account ID for customer account"""

        hash_value = hash(f"customer_{account_number}_{country}_{currency}")
        return abs(hash_value) & 0x7FFFFFFFFFFFFFFF
    
    def _generate_mobile_money_account_id(self, phone_number: str, country: str) -> int:
        """Generate account ID for mobile money account"""

        hash_value = hash(f"mobile_money_{phone_number}_{country}")
        return abs(hash_value) & 0x7FFFFFFFFFFFFFFF
    
    def _generate_system_account_id(self, account_type: PAPSSAccountType, currency: AfricanCurrency) -> int:
        """Generate deterministic account ID for system accounts"""

        type_value = account_type.value
        currency_value = currency.value
        combined = (type_value << 32) | currency_value
        return combined & 0x7FFFFFFFFFFFFFFF
    
    def _generate_corridor_account_id(self, account_type: PAPSSAccountType, currency: AfricanCurrency) -> int:
        """Generate account ID for trade corridor accounts"""

        type_value = account_type.value
        currency_value = currency.value
        combined = (type_value << 32) | currency_value
        return combined & 0x7FFFFFFFFFFFFFFF
    
    def _generate_mobile_money_pool_id(self, country: str, currency: AfricanCurrency) -> int:
        """Generate account ID for mobile money pool"""

        hash_value = hash(f"mm_pool_{country}_{currency.name}")
        return abs(hash_value) & 0x7FFFFFFFFFFFFFFF
    
    def _account_exists(self, account_id: int) -> bool:
        """Check if account exists in TigerBeetle"""
        # Simulate account existence check
        return False  # Always return False to trigger account creation in simulation
    
    def _create_account(
        self,
        account_id: int,
        user_data: int,
        account_type: PAPSSAccountType,
        currency: AfricanCurrency,
        flags: int
    ) -> bool:
        """
Create account in TigerBeetle"""
        try:
            # Simulate account creation
            account_data = {
                'id': account_id,
                'user_data': user_data,
                'ledger': 3,  # PAPSS Pan-African ledger
                'code': account_type.value,
                'flags': flags,
                'debits_pending': 0,
                'debits_posted': 0,
                'credits_pending': 0,
                'credits_posted': 0,
                'timestamp': 0
            }
            
            logger.debug(f"Created PAPSS TigerBeetle account: {account_data}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating PAPSS account {account_id}: {e}")
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
                    logger.debug(f"Created PAPSS TigerBeetle transfer: {transfer}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error creating PAPSS transfers: {e}")
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
                    'amount': 500000,
                    'code': AfricanCurrency.NGN.value,
                    'ledger': 3,
                    'flags': PAPSSTransferFlags.PAPSS_PAN_AFRICAN
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
                'debits_posted': 250000,
                'credits_pending': 0,
                'credits_posted': 750000,  # Simulated balance
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

        self.performance_metrics['total_pan_african_operations'] += 1
        self.performance_metrics['last_operation_time'] = datetime.utcnow().isoformat()
        
        if success:
            self.performance_metrics['successful_operations'] += 1
        else:
            self.performance_metrics['failed_operations'] += 1
        
        # Update average latency (simple moving average)
        current_avg = self.performance_metrics['average_latency_ms']
        total_ops = self.performance_metrics['total_pan_african_operations']
        self.performance_metrics['average_latency_ms'] = (
            (current_avg * (total_ops - 1) + latency_ms) / total_ops
        )
    
    def _store_fx_conversion_metrics(self, fx_metrics: Dict[str, Any]) -> None:
        """Store FX conversion metrics for analytics and reporting."""
        try:
            # In production, this would store to a metrics database
            # For now, we log the structured metrics
            logger.info(f"Storing FX metrics: Rate={fx_metrics['fx_rate']:.6f}, "
                       f"Spread={fx_metrics['fx_spread_percent']:.2f}%, "
                       f"Cost=${fx_metrics['fx_cost']:.2f}, "
                       f"Corridor={fx_metrics['trade_corridor']}")
            
            # Update aggregated FX metrics
            if not hasattr(self, 'fx_conversion_metrics'):
                self.fx_conversion_metrics = {
                    'total_conversions': 0,
                    'total_fx_cost': 0.0,
                    'average_spread': 0.0,
                    'conversion_pairs': {},
                    'last_conversion': None
                }
            
            # Update aggregated metrics
            self.fx_conversion_metrics['total_conversions'] += 1
            self.fx_conversion_metrics['total_fx_cost'] += fx_metrics['fx_cost']
            self.fx_conversion_metrics['last_conversion'] = fx_metrics['conversion_timestamp']
            
            # Update average spread
            total_conversions = self.fx_conversion_metrics['total_conversions']
            current_avg_spread = self.fx_conversion_metrics['average_spread']
            self.fx_conversion_metrics['average_spread'] = (
                (current_avg_spread * (total_conversions - 1) + fx_metrics['fx_spread_percent']) / total_conversions
            )
            
            # Track conversion pairs
            pair_key = f"{fx_metrics['source_currency']}-{fx_metrics['target_currency']}"
            if pair_key not in self.fx_conversion_metrics['conversion_pairs']:
                self.fx_conversion_metrics['conversion_pairs'][pair_key] = {
                    'count': 0,
                    'total_volume': 0.0,
                    'avg_rate': 0.0
                }
            
            pair_data = self.fx_conversion_metrics['conversion_pairs'][pair_key]
            pair_data['count'] += 1
            pair_data['total_volume'] += fx_metrics['original_amount']
            pair_data['avg_rate'] = (
                (pair_data['avg_rate'] * (pair_data['count'] - 1) + fx_metrics['fx_rate']) / pair_data['count']
            )
            
            # Example: Store to time-series database for analytics
            # self.metrics_db.store_fx_conversion(fx_metrics)
            
        except Exception as e:
            logger.error(f"Failed to store FX conversion metrics: {e}")

