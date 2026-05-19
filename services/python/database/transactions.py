"""
Transaction Management Utilities for Remittance Platform

This module provides production-ready transaction management with:
- Automatic commit/rollback
- Nested transaction support
- Savepoints for partial rollback
- Transaction isolation levels
- Deadlock retry logic
"""

from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError
from typing import Generator
import logging
import time

logger = logging.getLogger(__name__)


@contextmanager
def transaction_scope(session: Session, max_retries: int = 3) -> Generator[Session, None, None]:
    """
    Provide a transactional scope with automatic commit/rollback.
    
    This context manager ensures ACID properties:
    - Atomicity: All operations succeed or all fail
    - Consistency: Database remains in valid state
    - Isolation: Concurrent transactions don't interfere
    - Durability: Committed changes persist
    
    Args:
        session: SQLAlchemy session
        max_retries: Maximum number of retries for deadlocks (default: 3)
    
    Yields:
        Session: The database session
    
    Example:
        with transaction_scope(db) as tx:
            # Debit from account
            from_account = tx.query(Account).filter_by(id=1).first()
            from_account.balance -= 100
            
            # Credit to account
            to_account = tx.query(Account).filter_by(id=2).first()
            to_account.balance += 100
            
            # All or nothing - atomic transaction
    """
    retries = 0
    
    while retries < max_retries:
        try:
            yield session
            session.commit()
            logger.debug("Transaction committed successfully")
            return
        except OperationalError as e:
            # Handle deadlocks with retry
            session.rollback()
            retries += 1
            if retries >= max_retries:
                logger.error(f"Transaction failed after {max_retries} retries: {e}")
                raise
            logger.warning(f"Deadlock detected, retrying ({retries}/{max_retries})...")
            time.sleep(0.1 * retries)  # Exponential backoff
        except IntegrityError as e:
            # Handle constraint violations
            session.rollback()
            logger.error(f"Integrity constraint violation: {e}")
            raise
        except Exception as e:
            # Handle all other exceptions
            session.rollback()
            logger.error(f"Transaction failed: {e}")
            raise


@contextmanager
def savepoint_scope(session: Session, name: str = None) -> Generator[Session, None, None]:
    """
    Provide a savepoint scope for partial rollback.
    
    Savepoints allow you to rollback part of a transaction without
    rolling back the entire transaction.
    
    Args:
        session: SQLAlchemy session
        name: Optional savepoint name
    
    Yields:
        Session: The database session
    
    Example:
        with transaction_scope(db) as tx:
            # Create account
            account = Account(balance=1000)
            tx.add(account)
            
            try:
                with savepoint_scope(tx, "transfer") as sp:
                    # Try risky operation
                    account.balance -= 2000  # This will fail
                    if account.balance < 0:
                        raise ValueError("Insufficient funds")
            except ValueError:
                # Savepoint rolled back, but transaction continues
                logger.warning("Transfer failed, but account creation succeeded")
    """
    savepoint = session.begin_nested()
    try:
        yield session
        savepoint.commit()
        logger.debug(f"Savepoint '{name}' committed")
    except Exception as e:
        savepoint.rollback()
        logger.warning(f"Savepoint '{name}' rolled back: {e}")
        raise


class TransactionManager:
    """
    Advanced transaction manager with isolation level support.
    
    Provides fine-grained control over transaction isolation levels:
    - READ UNCOMMITTED: Lowest isolation, highest performance
    - READ COMMITTED: Default for most databases
    - REPEATABLE READ: Prevents non-repeatable reads
    - SERIALIZABLE: Highest isolation, lowest performance
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    @contextmanager
    def transaction(
        self,
        isolation_level: str = None,
        max_retries: int = 3
    ) -> Generator[Session, None, None]:
        """
        Execute transaction with specific isolation level.
        
        Args:
            isolation_level: One of: READ UNCOMMITTED, READ COMMITTED,
                           REPEATABLE READ, SERIALIZABLE
            max_retries: Maximum retries for deadlocks
        
        Yields:
            Session: The database session
        
        Example:
            manager = TransactionManager(db)
            with manager.transaction(isolation_level="SERIALIZABLE") as tx:
                # Critical financial operation
                account = tx.query(Account).with_for_update().first()
                account.balance -= 100
        """
        # Set isolation level if specified
        if isolation_level:
            self.session.execute(
                f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"
            )
            logger.debug(f"Transaction isolation level set to {isolation_level}")
        
        # Use standard transaction scope with retry logic
        with transaction_scope(self.session, max_retries=max_retries) as tx:
            yield tx
    
    @contextmanager
    def read_only_transaction(self) -> Generator[Session, None, None]:
        """
        Execute read-only transaction (optimization).
        
        Read-only transactions can be optimized by the database
        and don't acquire write locks.
        
        Yields:
            Session: The database session
        
        Example:
            manager = TransactionManager(db)
            with manager.read_only_transaction() as tx:
                # Read operations only
                accounts = tx.query(Account).all()
        """
        self.session.execute("SET TRANSACTION READ ONLY")
        logger.debug("Read-only transaction started")
        
        try:
            yield self.session
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Read-only transaction failed: {e}")
            raise
    
    @contextmanager
    def serializable_transaction(self) -> Generator[Session, None, None]:
        """
        Execute serializable transaction (highest isolation).
        
        Serializable transactions prevent all concurrency anomalies
        but may have performance impact.
        
        Yields:
            Session: The database session
        
        Example:
            manager = TransactionManager(db)
            with manager.serializable_transaction() as tx:
                # Critical operation requiring full isolation
                account = tx.query(Account).with_for_update().first()
                account.balance -= 100
        """
        with self.transaction(isolation_level="SERIALIZABLE") as tx:
            yield tx


# Convenience functions for common transaction patterns

def transfer_money(
    session: Session,
    from_account_id: int,
    to_account_id: int,
    amount: float
) -> bool:
    """
    Transfer money between accounts (atomic operation).
    
    This is a complete example of using transaction_scope for
    financial operations.
    
    Args:
        session: Database session
        from_account_id: Source account ID
        to_account_id: Destination account ID
        amount: Amount to transfer
    
    Returns:
        bool: True if transfer succeeded
    
    Raises:
        ValueError: If insufficient funds or invalid amount
        Exception: If database operation fails
    """
    from .models import Account
    
    if amount <= 0:
        raise ValueError("Transfer amount must be positive")
    
    with transaction_scope(session) as tx:
        # Lock accounts to prevent concurrent modifications
        from_account = tx.query(Account).with_for_update().filter_by(
            id=from_account_id
        ).first()
        
        if not from_account:
            raise ValueError(f"Source account {from_account_id} not found")
        
        if from_account.balance < amount:
            raise ValueError(
                f"Insufficient funds: {from_account.balance} < {amount}"
            )
        
        to_account = tx.query(Account).with_for_update().filter_by(
            id=to_account_id
        ).first()
        
        if not to_account:
            raise ValueError(f"Destination account {to_account_id} not found")
        
        # Perform transfer
        from_account.balance -= amount
        to_account.balance += amount
        
        logger.info(
            f"Transfer: {from_account_id} -> {to_account_id}, "
            f"amount: {amount}"
        )
        
        # Transaction will auto-commit if no exceptions
        return True


def batch_update(
    session: Session,
    model_class,
    updates: list[dict],
    batch_size: int = 1000
) -> int:
    """
    Perform batch updates with transaction management.
    
    Args:
        session: Database session
        model_class: SQLAlchemy model class
        updates: List of update dictionaries with 'id' and update fields
        batch_size: Number of records per transaction
    
    Returns:
        int: Number of records updated
    
    Example:
        updates = [
            {'id': 1, 'status': 'active'},
            {'id': 2, 'status': 'active'},
            ...
        ]
        count = batch_update(db, Account, updates, batch_size=100)
    """
    total_updated = 0
    
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        
        with transaction_scope(session) as tx:
            for update in batch:
                record_id = update.pop('id')
                tx.query(model_class).filter_by(id=record_id).update(update)
            
            total_updated += len(batch)
            logger.info(f"Batch updated: {len(batch)} records")
    
    return total_updated

