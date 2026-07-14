#!/usr/bin/env python3
"""
CIPS PostgreSQL Integration
Complete database layer for CIPS transactions
Version: 1.0.0
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CIPSPostgresIntegration:
    """PostgreSQL integration for CIPS transactions"""
    
    def __init__(self, config: Optional[Dict] = None) -> None:
        """
        Initialize PostgreSQL connection pool
        
        Args:
            config: Database configuration dictionary
        """
        if config is None:
            config = {
                "host": os.getenv("CIPS_POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("CIPS_POSTGRES_PORT", "5432")),
                "database": os.getenv("CIPS_POSTGRES_DATABASE", "cips_remittance"),
                "user": os.getenv("CIPS_POSTGRES_USER", "cips_user"),
                "password": os.getenv("CIPS_POSTGRES_PASSWORD", ""),
                "min_conn": 2,
                "max_conn": int(os.getenv("CIPS_DB_POOL_SIZE", "20"))
            }
        
        self.config = config
        self.connection_pool = None
        self._initialize_pool()
        self._create_tables()
        
        logger.info(f"CIPS PostgreSQL integration initialized: {config['host']}:{config['port']}/{config['database']}")
    
    def _initialize_pool(self) -> None:
        """Initialize connection pool"""
        try:
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                self.config["min_conn"],
                self.config["max_conn"],
                host=self.config["host"],
                port=self.config["port"],
                database=self.config["database"],
                user=self.config["user"],
                password=self.config["password"],
                cursor_factory=RealDictCursor
            )
            logger.info("Connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {str(e)}")
            raise
    
    def _get_connection(self) -> None:
        """Get connection from pool"""
        return self.connection_pool.getconn()
    
    def _return_connection(self, conn) -> None:
        """Return connection to pool"""
        self.connection_pool.putconn(conn)
    
    def _create_tables(self) -> None:
        """Create database tables if they don't exist"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Transfers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_transfers (
                    id BIGSERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255) UNIQUE NOT NULL,
                    message_id VARCHAR(255) UNIQUE NOT NULL,
                    instruction_id VARCHAR(255) NOT NULL,
                    end_to_end_id VARCHAR(255) NOT NULL,
                    transaction_id VARCHAR(255) NOT NULL,
                    
                    -- Parties
                    debtor_name VARCHAR(255) NOT NULL,
                    debtor_account VARCHAR(255) NOT NULL,
                    debtor_agent_bic VARCHAR(11) NOT NULL,
                    creditor_name VARCHAR(255) NOT NULL,
                    creditor_account VARCHAR(255) NOT NULL,
                    creditor_agent_bic VARCHAR(11) NOT NULL,
                    
                    -- Amount
                    currency VARCHAR(3) NOT NULL,
                    amount DECIMAL(20, 2) NOT NULL,
                    
                    -- Status
                    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
                    cips_status VARCHAR(50),
                    status_reason VARCHAR(255),
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    settled_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Additional info
                    remittance_info TEXT,
                    correspondent_bank_bic VARCHAR(11),
                    metadata JSONB,
                    
                    INDEX idx_transfer_id (transfer_id),
                    INDEX idx_message_id (message_id),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at),
                    INDEX idx_debtor_account (debtor_account),
                    INDEX idx_creditor_account (creditor_account)
                )
            """)
            
            # ISO 20022 Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_iso20022_messages (
                    id BIGSERIAL PRIMARY KEY,
                    message_id VARCHAR(255) UNIQUE NOT NULL,
                    message_type VARCHAR(50) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    transfer_id VARCHAR(255),
                    
                    -- Message content
                    xml_content TEXT NOT NULL,
                    parsed_data JSONB,
                    
                    -- Status
                    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
                    error_message TEXT,
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP WITH TIME ZONE,
                    
                    FOREIGN KEY (transfer_id) REFERENCES cips_transfers(transfer_id),
                    INDEX idx_message_type (message_type),
                    INDEX idx_direction (direction),
                    INDEX idx_status (status),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            # Settlement table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_settlements (
                    id BIGSERIAL PRIMARY KEY,
                    settlement_id VARCHAR(255) UNIQUE NOT NULL,
                    settlement_date DATE NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    
                    -- Amounts
                    total_debits DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    total_credits DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    net_position DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    
                    -- Counts
                    debit_count INTEGER NOT NULL DEFAULT 0,
                    credit_count INTEGER NOT NULL DEFAULT 0,
                    
                    -- Status
                    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
                    settled_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    INDEX idx_settlement_date (settlement_date),
                    INDEX idx_currency (currency),
                    INDEX idx_status (status)
                )
            """)
            
            # Compliance checks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_compliance_checks (
                    id BIGSERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255) NOT NULL,
                    check_type VARCHAR(50) NOT NULL,
                    check_result VARCHAR(50) NOT NULL,
                    risk_score DECIMAL(5, 2),
                    details JSONB,
                    checked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    FOREIGN KEY (transfer_id) REFERENCES cips_transfers(transfer_id),
                    INDEX idx_transfer_id (transfer_id),
                    INDEX idx_check_type (check_type),
                    INDEX idx_check_result (check_result),
                    INDEX idx_checked_at (checked_at)
                )
            """)
            
            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_audit_log (
                    id BIGSERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255),
                    action VARCHAR(100) NOT NULL,
                    actor VARCHAR(255),
                    details JSONB,
                    ip_address INET,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    INDEX idx_transfer_id (transfer_id),
                    INDEX idx_action (action),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_statistics (
                    id BIGSERIAL PRIMARY KEY,
                    stat_date DATE NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    
                    -- Volume
                    total_transfers INTEGER NOT NULL DEFAULT 0,
                    successful_transfers INTEGER NOT NULL DEFAULT 0,
                    failed_transfers INTEGER NOT NULL DEFAULT 0,
                    
                    -- Amounts
                    total_amount DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    average_amount DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    min_amount DECIMAL(20, 2),
                    max_amount DECIMAL(20, 2),
                    
                    -- Performance
                    average_processing_time_ms INTEGER,
                    p95_processing_time_ms INTEGER,
                    p99_processing_time_ms INTEGER,
                    
                    -- Timestamps
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE (stat_date, currency),
                    INDEX idx_stat_date (stat_date),
                    INDEX idx_currency (currency)
                )
            """)
            
            # Errors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cips_errors (
                    id BIGSERIAL PRIMARY KEY,
                    transfer_id VARCHAR(255),
                    message_id VARCHAR(255),
                    error_code VARCHAR(50) NOT NULL,
                    error_message TEXT NOT NULL,
                    error_details JSONB,
                    stack_trace TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    
                    INDEX idx_transfer_id (transfer_id),
                    INDEX idx_error_code (error_code),
                    INDEX idx_created_at (created_at)
                )
            """)
            
            conn.commit()
            logger.info("Database tables created successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create tables: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def create_transfer(self, transfer_data: Dict) -> str:
        """Create a new transfer record"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_transfers (
                    transfer_id, message_id, instruction_id, end_to_end_id, transaction_id,
                    debtor_name, debtor_account, debtor_agent_bic,
                    creditor_name, creditor_account, creditor_agent_bic,
                    currency, amount, status, remittance_info,
                    correspondent_bank_bic, metadata
                ) VALUES (
                    %(transfer_id)s, %(message_id)s, %(instruction_id)s, %(end_to_end_id)s, %(transaction_id)s,
                    %(debtor_name)s, %(debtor_account)s, %(debtor_agent_bic)s,
                    %(creditor_name)s, %(creditor_account)s, %(creditor_agent_bic)s,
                    %(currency)s, %(amount)s, %(status)s, %(remittance_info)s,
                    %(correspondent_bank_bic)s, %(metadata)s
                )
                RETURNING transfer_id
            """, transfer_data)
            
            result = cursor.fetchone()
            conn.commit()
            
            transfer_id = result["transfer_id"]
            logger.info(f"Transfer created: {transfer_id}")
            
            # Log audit
            self._log_audit(transfer_id, "TRANSFER_CREATED", transfer_data)
            
            return transfer_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create transfer: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def update_transfer_status(self, transfer_id: str, status: str, cips_status: Optional[str] = None, status_reason: Optional[str] = None) -> None:
        """Update transfer status"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE cips_transfers
                SET status = %s, cips_status = %s, status_reason = %s, updated_at = CURRENT_TIMESTAMP
                WHERE transfer_id = %s
            """, (status, cips_status, status_reason, transfer_id))
            
            conn.commit()
            logger.info(f"Transfer status updated: {transfer_id} -> {status}")
            
            # Log audit
            self._log_audit(transfer_id, "STATUS_UPDATED", {"status": status, "cips_status": cips_status})
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update transfer status: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_transfer(self, transfer_id: str) -> Optional[Dict]:
        """Get transfer by ID"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM cips_transfers WHERE transfer_id = %s
            """, (transfer_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
            
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def save_iso20022_message(self, message_data: Dict) -> None:
        """Save ISO 20022 message"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_iso20022_messages (
                    message_id, message_type, direction, transfer_id,
                    xml_content, parsed_data, status
                ) VALUES (
                    %(message_id)s, %(message_type)s, %(direction)s, %(transfer_id)s,
                    %(xml_content)s, %(parsed_data)s, %(status)s
                )
            """, message_data)
            
            conn.commit()
            logger.info(f"ISO 20022 message saved: {message_data['message_id']}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save ISO 20022 message: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def record_compliance_check(self, check_data: Dict) -> None:
        """Record compliance check"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_compliance_checks (
                    transfer_id, check_type, check_result, risk_score, details
                ) VALUES (
                    %(transfer_id)s, %(check_type)s, %(check_result)s, %(risk_score)s, %(details)s
                )
            """, check_data)
            
            conn.commit()
            logger.info(f"Compliance check recorded: {check_data['transfer_id']} - {check_data['check_type']}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to record compliance check: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def _log_audit(self, transfer_id: str, action: str, details: Dict) -> None:
        """Log audit entry"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_audit_log (transfer_id, action, details)
                VALUES (%s, %s, %s)
            """, (transfer_id, action, json.dumps(details)))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to log audit: {str(e)}")
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def get_daily_statistics(self, date: str, currency: str) -> Optional[Dict]:
        """Get daily statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM cips_statistics
                WHERE stat_date = %s AND currency = %s
            """, (date, currency))
            
            result = cursor.fetchone()
            return dict(result) if result else None
            
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def update_statistics(self, date: str, currency: str, stats: Dict) -> None:
        """Update daily statistics"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_statistics (
                    stat_date, currency, total_transfers, successful_transfers, failed_transfers,
                    total_amount, average_amount, min_amount, max_amount
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (stat_date, currency)
                DO UPDATE SET
                    total_transfers = cips_statistics.total_transfers + EXCLUDED.total_transfers,
                    successful_transfers = cips_statistics.successful_transfers + EXCLUDED.successful_transfers,
                    failed_transfers = cips_statistics.failed_transfers + EXCLUDED.failed_transfers,
                    total_amount = cips_statistics.total_amount + EXCLUDED.total_amount,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                date, currency,
                stats.get("total_transfers", 0),
                stats.get("successful_transfers", 0),
                stats.get("failed_transfers", 0),
                stats.get("total_amount", 0),
                stats.get("average_amount", 0),
                stats.get("min_amount"),
                stats.get("max_amount")
            ))
            
            conn.commit()
            logger.info(f"Statistics updated: {date} - {currency}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update statistics: {str(e)}")
            raise
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def log_error(self, error_data: Dict) -> None:
        """Log error"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO cips_errors (
                    transfer_id, message_id, error_code, error_message, error_details, stack_trace
                ) VALUES (
                    %(transfer_id)s, %(message_id)s, %(error_code)s, %(error_message)s, %(error_details)s, %(stack_trace)s
                )
            """, error_data)
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")
        finally:
            cursor.close()
            self._return_connection(conn)
    
    def close(self) -> None:
        """Close connection pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Connection pool closed")


# Example usage
if __name__ == "__main__":
    # Initialize
    db = CIPSPostgresIntegration()
    
    # Create transfer
    transfer_data = {
        "transfer_id": "TXN123456789",
        "message_id": "MSG123456789",
        "instruction_id": "INST123456789",
        "end_to_end_id": "E2E123456789",
        "transaction_id": "TX123456789",
        "debtor_name": "Test Sender",
        "debtor_account": "1234567890",
        "debtor_agent_bic": "CITIUS33",
        "creditor_name": "Test Receiver",
        "creditor_account": "9876543210",
        "creditor_agent_bic": "BKCHCNBJ",
        "currency": "USD",
        "amount": Decimal("10000.00"),
        "status": "PENDING",
        "remittance_info": "Test payment",
        "correspondent_bank_bic": "CITIUS33",
        "metadata": json.dumps({"test": True})
    }
    
    transfer_id = db.create_transfer(transfer_data)
    print(f"Transfer created: {transfer_id}")
    
    # Update status
    db.update_transfer_status(transfer_id, "SUCCESS", "ACCP")
    
    # Get transfer
    transfer = db.get_transfer(transfer_id)
    print(f"Transfer: {json.dumps(transfer, indent=2, default=str)}")
    
    # Close
    db.close()

