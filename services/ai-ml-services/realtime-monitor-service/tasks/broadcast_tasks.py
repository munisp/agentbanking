"""
Background Tasks for Broadcasting Real-time Updates
Nigerian Remittance Platform
"""

import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from websocket.connection_manager import manager
from services.realtime_monitor_service import RealtimeMonitorService
from db.session import SessionLocal
import logging

logger = logging.getLogger(__name__)


class BroadcastTasks:
    """Background tasks for broadcasting updates"""

    def __init__(self):
        self.running = False
        self.tasks = []

    async def start(self):
        """Start all background tasks"""
        if self.running:
            logger.warning("Broadcast tasks already running")
            return
        
        self.running = True
        logger.info("Starting broadcast tasks...")
        
        # Start individual tasks
        self.tasks = [
            asyncio.create_task(self._broadcast_metrics_loop()),
            asyncio.create_task(self._broadcast_active_transactions_loop()),
            asyncio.create_task(self._monitor_new_transactions_loop()),
            asyncio.create_task(self._monitor_new_alerts_loop())
        ]
        
        logger.info(f"Started {len(self.tasks)} broadcast tasks")

    async def stop(self):
        """Stop all background tasks"""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping broadcast tasks...")
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks = []
        logger.info("All broadcast tasks stopped")

    async def _broadcast_metrics_loop(self):
        """Broadcast dashboard metrics every 5 seconds"""
        try:
            while self.running:
                try:
                    # Get metrics
                    db = SessionLocal()
                    try:
                        service = RealtimeMonitorService(db)
                        metrics = service.get_dashboard_metrics()
                        
                        # Broadcast to all connected clients
                        await manager.broadcast_to_dashboard(
                            "metrics_update",
                            metrics.dict()
                        )
                    finally:
                        db.close()
                    
                    # Wait 5 seconds
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error broadcasting metrics: {e}")
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Metrics broadcast task cancelled")

    async def _broadcast_active_transactions_loop(self):
        """Broadcast active transactions every 3 seconds"""
        try:
            while self.running:
                try:
                    # Get active transactions
                    db = SessionLocal()
                    try:
                        service = RealtimeMonitorService(db)
                        transactions, total = service.get_active_transactions(page=1, page_size=50)
                        
                        # Convert to dict
                        transactions_data = [
                            {
                                "id": txn.id,
                                "amount": txn.amount,
                                "currency": txn.currency,
                                "status": txn.status.value,
                                "type": txn.type.value,
                                "sender": txn.sender.to_dict() if txn.sender else None,
                                "recipient": txn.recipient.to_dict() if txn.recipient else None,
                                "payment_method": txn.payment_method,
                                "reference": txn.reference,
                                "created_at": txn.created_at.isoformat() if txn.created_at else None
                            }
                            for txn in transactions
                        ]
                        
                        # Broadcast to all connected clients
                        await manager.broadcast_to_dashboard(
                            "active_transactions_update",
                            {
                                "transactions": transactions_data,
                                "total": total
                            }
                        )
                    finally:
                        db.close()
                    
                    # Wait 3 seconds
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Error broadcasting active transactions: {e}")
                    await asyncio.sleep(3)
        except asyncio.CancelledError:
            logger.info("Active transactions broadcast task cancelled")

    async def _monitor_new_transactions_loop(self):
        """Monitor and broadcast new transactions"""
        try:
            last_check = datetime.utcnow()
            
            while self.running:
                try:
                    # Get new transactions since last check
                    db = SessionLocal()
                    try:
                        from models.transaction import Transaction
                        
                        new_transactions = db.query(Transaction).filter(
                            Transaction.created_at > last_check
                        ).all()
                        
                        # Broadcast each new transaction
                        for txn in new_transactions:
                            await manager.broadcast_to_dashboard(
                                "transaction_update",
                                {
                                    "id": txn.id,
                                    "amount": txn.amount,
                                    "currency": txn.currency,
                                    "status": txn.status.value,
                                    "type": txn.type.value,
                                    "sender": txn.sender.to_dict() if txn.sender else None,
                                    "recipient": txn.recipient.to_dict() if txn.recipient else None,
                                    "payment_method": txn.payment_method,
                                    "reference": txn.reference,
                                    "created_at": txn.created_at.isoformat() if txn.created_at else None
                                }
                            )
                        
                        # Update last check time
                        last_check = datetime.utcnow()
                    finally:
                        db.close()
                    
                    # Wait 1 second
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error monitoring new transactions: {e}")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("New transactions monitor task cancelled")

    async def _monitor_new_alerts_loop(self):
        """Monitor and broadcast new alerts"""
        try:
            last_check = datetime.utcnow()
            
            while self.running:
                try:
                    # Get new alerts since last check
                    db = SessionLocal()
                    try:
                        from models.alert import Alert
                        
                        new_alerts = db.query(Alert).filter(
                            Alert.timestamp > last_check
                        ).all()
                        
                        # Broadcast each new alert
                        for alert in new_alerts:
                            await manager.broadcast_to_dashboard(
                                "alert",
                                {
                                    "id": alert.id,
                                    "type": alert.type.value,
                                    "severity": alert.severity.value,
                                    "title": alert.title,
                                    "message": alert.message,
                                    "acknowledged": alert.acknowledged,
                                    "timestamp": alert.timestamp.isoformat() if alert.timestamp else None
                                }
                            )
                        
                        # Update last check time
                        last_check = datetime.utcnow()
                    finally:
                        db.close()
                    
                    # Wait 2 seconds
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error monitoring new alerts: {e}")
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.info("New alerts monitor task cancelled")


# Global broadcast tasks instance
broadcast_tasks = BroadcastTasks()
