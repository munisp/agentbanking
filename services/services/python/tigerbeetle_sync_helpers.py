"""
TigerBeetle Sync Helper Functions
Provides real implementations to replace placeholders and mocks
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import asyncpg

class TigerBeetleSyncHelpers:
    """Helper functions for TigerBeetle synchronization"""
    
    @staticmethod
    async def get_customer_id_from_account(tigerbeetle_id: int, conn: asyncpg.Connection) -> Optional[str]:
        """
        Retrieve actual customer ID from account mapping
        
        Args:
            tigerbeetle_id: TigerBeetle account ID
            conn: Database connection
            
        Returns:
            Customer ID if found, None otherwise
        """
        try:
            # First check if there's an existing mapping
            result = await conn.fetchrow("""
                SELECT customer_id 
                FROM account_customer_mapping 
                WHERE tigerbeetle_account_id = $1
            """, tigerbeetle_id)
            
            if result:
                return result['customer_id']
            
            # Check in account_metadata table
            result = await conn.fetchrow("""
                SELECT customer_id 
                FROM account_metadata 
                WHERE id = $1 AND customer_id IS NOT NULL AND customer_id != ''
            """, tigerbeetle_id)
            
            if result and result['customer_id'] and not result['customer_id'].startswith('customer_'):
                return result['customer_id']
            
            # Check in customers table by linking through transactions
            result = await conn.fetchrow("""
                SELECT DISTINCT c.id as customer_id
                FROM customers c
                JOIN transactions t ON t.customer_id = c.id
                WHERE t.tigerbeetle_account_id = $1
                LIMIT 1
            """, tigerbeetle_id)
            
            if result:
                # Create mapping for future use
                await conn.execute("""
                    INSERT INTO account_customer_mapping (tigerbeetle_account_id, customer_id, created_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (tigerbeetle_account_id) DO UPDATE SET customer_id = $2
                """, tigerbeetle_id, result['customer_id'])
                return result['customer_id']
            
            return None
            
        except Exception as e:
            print(f"Error getting customer ID: {e}")
            return None
    
    @staticmethod
    async def generate_account_number(tigerbeetle_id: int, conn: asyncpg.Connection) -> str:
        """
        Generate or retrieve actual account number
        
        Args:
            tigerbeetle_id: TigerBeetle account ID
            conn: Database connection
            
        Returns:
            Account number (existing or newly generated)
        """
        try:
            # Check if account number already exists
            result = await conn.fetchrow("""
                SELECT account_number 
                FROM account_metadata 
                WHERE id = $1 AND account_number IS NOT NULL AND account_number != ''
            """, tigerbeetle_id)
            
            if result and result['account_number'] and not result['account_number'].startswith('acc_'):
                return result['account_number']
            
            # Generate new account number using Nigerian banking format
            # Format: BBBBBBBBBBCC where B=base number, C=check digits
            base_number = str(tigerbeetle_id).zfill(10)
            
            # Calculate check digits using Luhn algorithm
            check_digits = TigerBeetleSyncHelpers._calculate_check_digits(base_number)
            account_number = f"{base_number}{check_digits}"
            
            # Update account metadata with generated number
            await conn.execute("""
                UPDATE account_metadata 
                SET account_number = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, account_number, tigerbeetle_id)
            
            return account_number
            
        except Exception as e:
            print(f"Error generating account number: {e}")
            # Fallback to formatted ID
            return f"ACC{str(tigerbeetle_id).zfill(12)}"
    
    @staticmethod
    def _calculate_check_digits(number_str: str) -> str:
        """Calculate check digits using Luhn algorithm"""
        def luhn_checksum(card_number):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_number)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        
        check_digit = (10 - luhn_checksum(number_str)) % 10
        return str(check_digit) + str((int(number_str[-1]) + check_digit) % 10)
    
    @staticmethod
    async def get_payment_reference(tigerbeetle_id: int, conn: asyncpg.Connection) -> str:
        """
        Generate or retrieve payment reference for transfer
        
        Args:
            tigerbeetle_id: TigerBeetle transfer ID
            conn: Database connection
            
        Returns:
            Payment reference
        """
        try:
            # Check if reference already exists
            result = await conn.fetchrow("""
                SELECT payment_reference 
                FROM transfer_metadata 
                WHERE id = $1 AND payment_reference IS NOT NULL
            """, tigerbeetle_id)
            
            if result and result['payment_reference'] and not result['payment_reference'].startswith('transfer_'):
                return result['payment_reference']
            
            # Generate new reference
            # Format: TXN-YYYYMMDD-XXXXXXXX
            timestamp = datetime.now().strftime('%Y%m%d')
            unique_id = str(uuid.uuid4())[:8].upper()
            reference = f"TXN-{timestamp}-{unique_id}"
            
            # Update transfer metadata
            await conn.execute("""
                UPDATE transfer_metadata 
                SET payment_reference = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, reference, tigerbeetle_id)
            
            return reference
            
        except Exception as e:
            print(f"Error generating payment reference: {e}")
            return f"TXN-{datetime.now().strftime('%Y%m%d')}-{str(tigerbeetle_id).zfill(8)}"
    
    @staticmethod
    async def get_transfer_description(transfer_data: Dict[str, Any], conn: asyncpg.Connection) -> str:
        """
        Generate meaningful transfer description
        
        Args:
            transfer_data: Transfer data from TigerBeetle
            conn: Database connection
            
        Returns:
            Transfer description
        """
        try:
            tigerbeetle_id = transfer_data.get('id')
            amount = transfer_data.get('amount', 0) / 100  # Convert from cents
            
            # Try to get description from metadata
            result = await conn.fetchrow("""
                SELECT description 
                FROM transfer_metadata 
                WHERE id = $1 AND description IS NOT NULL
            """, tigerbeetle_id)
            
            if result and result['description'] and result['description'] != 'TigerBeetle transfer':
                return result['description']
            
            # Get account information for better description
            debit_account = transfer_data.get('debit_account_id')
            credit_account = transfer_data.get('credit_account_id')
            
            # Get customer names if available
            debit_info = await conn.fetchrow("""
                SELECT c.name as customer_name, am.account_number
                FROM account_metadata am
                LEFT JOIN account_customer_mapping acm ON acm.tigerbeetle_account_id = am.id
                LEFT JOIN customers c ON c.id = acm.customer_id
                WHERE am.id = $1
            """, debit_account)
            
            credit_info = await conn.fetchrow("""
                SELECT c.name as customer_name, am.account_number
                FROM account_metadata am
                LEFT JOIN account_customer_mapping acm ON acm.tigerbeetle_account_id = am.id
                LEFT JOIN customers c ON c.id = acm.customer_id
                WHERE am.id = $1
            """, credit_account)
            
            # Build description
            if debit_info and credit_info:
                description = f"Transfer of NGN {amount:,.2f} from {debit_info['account_number']} to {credit_info['account_number']}"
            else:
                description = f"Transfer of NGN {amount:,.2f} (ID: {tigerbeetle_id})"
            
            # Update metadata
            await conn.execute("""
                UPDATE transfer_metadata 
                SET description = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            """, description, tigerbeetle_id)
            
            return description
            
        except Exception as e:
            print(f"Error generating transfer description: {e}")
            amount = transfer_data.get('amount', 0) / 100
            return f"Transfer of NGN {amount:,.2f}"
    
    @staticmethod
    async def ensure_sync_tables_exist(conn: asyncpg.Connection):
        """Ensure all required sync tables exist"""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS account_customer_mapping (
                tigerbeetle_account_id BIGINT PRIMARY KEY,
                customer_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_acm_customer_id ON account_customer_mapping(customer_id);
            
            CREATE TABLE IF NOT EXISTS sync_state (
                service_name VARCHAR(255) PRIMARY KEY,
                last_sync_time TIMESTAMP NOT NULL,
                sync_count BIGINT DEFAULT 0,
                error_count BIGINT DEFAULT 0,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS account_sync_log (
                id SERIAL PRIMARY KEY,
                tigerbeetle_id BIGINT NOT NULL,
                sync_type VARCHAR(50) NOT NULL,
                sync_direction VARCHAR(20) NOT NULL,
                sync_status VARCHAR(20) NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_asl_tigerbeetle_id ON account_sync_log(tigerbeetle_id);
            CREATE INDEX IF NOT EXISTS idx_asl_created_at ON account_sync_log(created_at);
            
            CREATE TABLE IF NOT EXISTS transfer_sync_log (
                id SERIAL PRIMARY KEY,
                tigerbeetle_id BIGINT NOT NULL,
                sync_type VARCHAR(50) NOT NULL,
                sync_direction VARCHAR(20) NOT NULL,
                sync_status VARCHAR(20) NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tsl_tigerbeetle_id ON transfer_sync_log(tigerbeetle_id);
            CREATE INDEX IF NOT EXISTS idx_tsl_created_at ON transfer_sync_log(created_at);
        """)

