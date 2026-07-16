"""
PAPSS PostgreSQL Integration
Database layer for PAPSS payments, settlements, and audit trails
"""

import psycopg2
from psycopg2 import pool, extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
import logging
import json
import os

logger = logging.getLogger(__name__)


class PAPSSPostgresIntegration:
    """PostgreSQL integration for PAPSS payments"""
    
    def __init__(self, database_url: str = None) -> None:
        """Initialize PostgreSQL connection pool"""
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.connection_pool = None
        self._initialize_connection_pool()
        self._initialize_schema()
    
    def _initialize_connection_pool(self) -> None:
        """Initialize PostgreSQL connection pool"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=5,
                maxconn=20,
                dsn=self.database_url
            )
            logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise
    
    def _get_connection(self) -> None:
        """Get connection from pool"""
        return self.connection_pool.getconn()
    
    def _return_connection(self, conn) -> None:
        """Return connection to pool"""
        self.connection_pool.putconn(conn)
    
    def _initialize_schema(self) -> None:
        """Initialize database schema"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Create payments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_payments (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(100) UNIQUE NOT NULL,
                    sender_country VARCHAR(2) NOT NULL,
                    sender_bank_code VARCHAR(20) NOT NULL,
                    sender_account VARCHAR(50) NOT NULL,
                    sender_name VARCHAR(200) NOT NULL,
                    sender_phone VARCHAR(20),
                    receiver_country VARCHAR(2) NOT NULL,
                    receiver_bank_code VARCHAR(20) NOT NULL,
                    receiver_account VARCHAR(50) NOT NULL,
                    receiver_name VARCHAR(200) NOT NULL,
                    receiver_phone VARCHAR(20),
                    amount DECIMAL(20, 2) NOT NULL,
                    source_currency VARCHAR(3) NOT NULL,
                    target_currency VARCHAR(3) NOT NULL,
                    exchange_rate DECIMAL(20, 6),
                    target_amount DECIMAL(20, 2),
                    payment_type VARCHAR(50) NOT NULL,
                    payment_method VARCHAR(50) NOT NULL,
                    trade_corridor VARCHAR(20),
                    purpose_code VARCHAR(10),
                    reference VARCHAR(200),
                    instructions TEXT,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    tigerbeetle_transfer_ids JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    failed_at TIMESTAMP,
                    error_message TEXT,
                    metadata JSONB
                );
                
                CREATE INDEX IF NOT EXISTS idx_payment_id ON papss_payments(payment_id);
                CREATE INDEX IF NOT EXISTS idx_sender_account ON papss_payments(sender_account);
                CREATE INDEX IF NOT EXISTS idx_receiver_account ON papss_payments(receiver_account);
                CREATE INDEX IF NOT EXISTS idx_status ON papss_payments(status);
                CREATE INDEX IF NOT EXISTS idx_created_at ON papss_payments(created_at);
                CREATE INDEX IF NOT EXISTS idx_trade_corridor ON papss_payments(trade_corridor);
                CREATE INDEX IF NOT EXISTS idx_currencies ON papss_payments(source_currency, target_currency);
            """)
            
            # Create settlements table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_settlements (
                    id SERIAL PRIMARY KEY,
                    settlement_id VARCHAR(100) UNIQUE NOT NULL,
                    trade_corridor VARCHAR(20) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    total_amount DECIMAL(20, 2) NOT NULL,
                    transaction_count INTEGER NOT NULL,
                    settlement_date DATE NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    payment_ids JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    metadata JSONB
                );
                
                CREATE INDEX IF NOT EXISTS idx_settlement_id ON papss_settlements(settlement_id);
                CREATE INDEX IF NOT EXISTS idx_settlement_date ON papss_settlements(settlement_date);
                CREATE INDEX IF NOT EXISTS idx_settlement_status ON papss_settlements(status);
            """)
            
            # Create mobile money transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_mobile_money (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(100) NOT NULL,
                    sender_operator VARCHAR(50) NOT NULL,
                    sender_phone VARCHAR(20) NOT NULL,
                    receiver_operator VARCHAR(50) NOT NULL,
                    receiver_phone VARCHAR(20) NOT NULL,
                    amount DECIMAL(20, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'pending',
                    operator_reference VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (payment_id) REFERENCES papss_payments(payment_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_mm_payment_id ON papss_mobile_money(payment_id);
                CREATE INDEX IF NOT EXISTS idx_mm_sender_phone ON papss_mobile_money(sender_phone);
                CREATE INDEX IF NOT EXISTS idx_mm_receiver_phone ON papss_mobile_money(receiver_phone);
            """)
            
            # Create compliance records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_compliance (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(100) NOT NULL,
                    check_type VARCHAR(50) NOT NULL,
                    check_result VARCHAR(50) NOT NULL,
                    risk_score DECIMAL(5, 2),
                    sanctions_check BOOLEAN DEFAULT FALSE,
                    pep_check BOOLEAN DEFAULT FALSE,
                    aml_check BOOLEAN DEFAULT FALSE,
                    details JSONB,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (payment_id) REFERENCES papss_payments(payment_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_compliance_payment_id ON papss_compliance(payment_id);
                CREATE INDEX IF NOT EXISTS idx_compliance_result ON papss_compliance(check_result);
            """)
            
            # Create FX rates table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_fx_rates (
                    id SERIAL PRIMARY KEY,
                    source_currency VARCHAR(3) NOT NULL,
                    target_currency VARCHAR(3) NOT NULL,
                    rate DECIMAL(20, 6) NOT NULL,
                    provider VARCHAR(50),
                    valid_from TIMESTAMP NOT NULL,
                    valid_until TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_fx_currencies ON papss_fx_rates(source_currency, target_currency);
                CREATE INDEX IF NOT EXISTS idx_fx_valid_from ON papss_fx_rates(valid_from);
            """)
            
            # Create audit trail table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_audit_trail (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(100) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    actor VARCHAR(200),
                    details JSONB,
                    ip_address VARCHAR(50),
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_audit_payment_id ON papss_audit_trail(payment_id);
                CREATE INDEX IF NOT EXISTS idx_audit_created_at ON papss_audit_trail(created_at);
            """)
            
            # Create statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papss_statistics (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    trade_corridor VARCHAR(20),
                    currency VARCHAR(3),
                    total_payments INTEGER DEFAULT 0,
                    total_amount DECIMAL(20, 2) DEFAULT 0,
                    successful_payments INTEGER DEFAULT 0,
                    failed_payments INTEGER DEFAULT 0,
                    avg_processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, trade_corridor, currency)
                );
                
                CREATE INDEX IF NOT EXISTS idx_stats_date ON papss_statistics(date);
                CREATE INDEX IF NOT EXISTS idx_stats_corridor ON papss_statistics(trade_corridor);
            """)
            
            conn.commit()
            logger.info("Database schema initialized successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to initialize schema: {e}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def create_payment(self, payment_data: Dict[str, Any]) -> int:
        """Create a new PAPSS payment record"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO papss_payments (
                    payment_id, sender_country, sender_bank_code, sender_account, sender_name, sender_phone,
                    receiver_country, receiver_bank_code, receiver_account, receiver_name, receiver_phone,
                    amount, source_currency, target_currency, exchange_rate, target_amount,
                    payment_type, payment_method, trade_corridor, purpose_code, reference, instructions,
                    status, metadata
                ) VALUES (
                    %(payment_id)s, %(sender_country)s, %(sender_bank_code)s, %(sender_account)s, %(sender_name)s, %(sender_phone)s,
                    %(receiver_country)s, %(receiver_bank_code)s, %(receiver_account)s, %(receiver_name)s, %(receiver_phone)s,
                    %(amount)s, %(source_currency)s, %(target_currency)s, %(exchange_rate)s, %(target_amount)s,
                    %(payment_type)s, %(payment_method)s, %(trade_corridor)s, %(purpose_code)s, %(reference)s, %(instructions)s,
                    %(status)s, %(metadata)s
                ) RETURNING id
            """, payment_data)
            
            payment_id = cursor.fetchone()[0]
            conn.commit()
            
            # Log audit trail
            self._log_audit_trail(payment_data['payment_id'], 'payment_created', payment_data)
            
            logger.info(f"Payment created: {payment_data['payment_id']}")
            return payment_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create payment: {e}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def update_payment_status(self, payment_id: str, status: str, error_message: str = None) -> None:
        """Update payment status"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            update_fields = {
                'status': status,
                'updated_at': datetime.now()
            }
            
            if status == 'completed':
                update_fields['completed_at'] = datetime.now()
            elif status == 'failed':
                update_fields['failed_at'] = datetime.now()
                update_fields['error_message'] = error_message
            
            cursor.execute("""
                UPDATE papss_payments
                SET status = %(status)s, updated_at = %(updated_at)s,
                    completed_at = %(completed_at)s, failed_at = %(failed_at)s, error_message = %(error_message)s
                WHERE payment_id = %(payment_id)s
            """, {**update_fields, 'payment_id': payment_id, 'completed_at': update_fields.get('completed_at'),
                  'failed_at': update_fields.get('failed_at'), 'error_message': error_message})
            
            conn.commit()
            
            # Log audit trail
            self._log_audit_trail(payment_id, f'status_changed_to_{status}', {'status': status, 'error': error_message})
            
            logger.info(f"Payment {payment_id} status updated to {status}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update payment status: {e}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("SELECT * FROM papss_payments WHERE payment_id = %s", (payment_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_payments_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get payments by status"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                "SELECT * FROM papss_payments WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def create_settlement(self, settlement_data: Dict[str, Any]) -> int:
        """Create a new settlement record"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO papss_settlements (
                    settlement_id, trade_corridor, currency, total_amount, transaction_count,
                    settlement_date, status, payment_ids, metadata
                ) VALUES (
                    %(settlement_id)s, %(trade_corridor)s, %(currency)s, %(total_amount)s, %(transaction_count)s,
                    %(settlement_date)s, %(status)s, %(payment_ids)s, %(metadata)s
                ) RETURNING id
            """, settlement_data)
            
            settlement_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Settlement created: {settlement_data['settlement_id']}")
            return settlement_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create settlement: {e}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def store_fx_rate(self, source_currency: str, target_currency: str, rate: Decimal,
                      provider: str, valid_duration_minutes: int = 60) -> None:
        """Store FX rate"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            valid_from = datetime.now()
            valid_until = valid_from + timedelta(minutes=valid_duration_minutes)
            
            cursor.execute("""
                INSERT INTO papss_fx_rates (
                    source_currency, target_currency, rate, provider, valid_from, valid_until
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (source_currency, target_currency, rate, provider, valid_from, valid_until))
            
            conn.commit()
            logger.info(f"FX rate stored: {source_currency}/{target_currency} = {rate}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to store FX rate: {e}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_latest_fx_rate(self, source_currency: str, target_currency: str) -> Optional[Decimal]:
        """Get latest FX rate"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT rate FROM papss_fx_rates
                WHERE source_currency = %s AND target_currency = %s
                  AND valid_from <= NOW() AND valid_until >= NOW()
                ORDER BY created_at DESC
                LIMIT 1
            """, (source_currency, target_currency))
            
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def _log_audit_trail(self, payment_id: str, action: str, details: Dict[str, Any]) -> None:
        """Log audit trail"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO papss_audit_trail (payment_id, action, details)
                VALUES (%s, %s, %s)
            """, (payment_id, action, json.dumps(details)))
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to log audit trail: {e}")
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_statistics(self, start_date: datetime, end_date: datetime,
                      trade_corridor: str = None) -> List[Dict[str, Any]]:
        """Get payment statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            query = """
                SELECT * FROM papss_statistics
                WHERE date BETWEEN %s AND %s
            """
            params = [start_date, end_date]
            
            if trade_corridor:
                query += " AND trade_corridor = %s"
                params.append(trade_corridor)
            
            query += " ORDER BY date DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def close(self) -> None:
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("PostgreSQL connection pool closed")


# Example usage
if __name__ == '__main__':
    db = PAPSSPostgresIntegration()
    
    # Create test payment
    payment_data = {
        'payment_id': 'PAPSS-TEST-001',
        'sender_country': 'NG',
        'sender_bank_code': 'NRPNNGLA',
        'sender_account': '1234567890',
        'sender_name': 'Test Sender',
        'sender_phone': '+234801234567',
        'receiver_country': 'KE',
        'receiver_bank_code': 'CBKEKENX',
        'receiver_account': '9876543210',
        'receiver_name': 'Test Receiver',
        'receiver_phone': '+254701234567',
        'amount': Decimal('500000'),
        'source_currency': 'NGN',
        'target_currency': 'KES',
        'exchange_rate': Decimal('0.32'),
        'target_amount': Decimal('160000'),
        'payment_type': 'personal',
        'payment_method': 'bank_transfer',
        'trade_corridor': 'EAC',
        'purpose_code': 'FAMI',
        'reference': 'Test payment',
        'instructions': 'Test instructions',
        'status': 'pending',
        'metadata': json.dumps({'test': True})
    }
    
    payment_id = db.create_payment(payment_data)
    print(f"Created payment with ID: {payment_id}")
    
    # Get payment
    payment = db.get_payment('PAPSS-TEST-001')
    print(f"Retrieved payment: {payment}")
    
    db.close()

