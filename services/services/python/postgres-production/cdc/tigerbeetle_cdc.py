"""
TigerBeetle CDC Integration
Real-time synchronization from TigerBeetle to PostgreSQL
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TigerBeetleCDC:
    """Change Data Capture from TigerBeetle to PostgreSQL"""
    
    def __init__(self, db_manager, tigerbeetle_client) -> None:
        self.db = db_manager
        self.tb_client = tigerbeetle_client
        self.running = False
    
    async def start(self) -> None:
        """Start CDC processing"""
        self.running = True
        logger.info("🔄 Starting TigerBeetle CDC...")
        
        while self.running:
            try:
                await self.process_events()
                await asyncio.sleep(1)  # Poll every second
            except Exception as e:
                logger.error(f"❌ CDC error: {e}")
                await asyncio.sleep(5)
    
    async def process_events(self) -> None:
        """Process pending CDC events"""
        from src.database_service import CDCService
        
        cdc_service = CDCService(self.db)
        events = cdc_service.get_unprocessed_events(limit=100)
        
        for event in events:
            try:
                await self.process_event(event)
                cdc_service.mark_event_processed(event.id)
                logger.info(f"✅ Processed CDC event {event.id}: {event.event_type}")
            except Exception as e:
                logger.error(f"❌ Failed to process event {event.id}: {e}")
                cdc_service.mark_event_processed(event.id, error=str(e))
    
    async def process_event(self, event) -> None:
        """Process individual CDC event"""
        if event.event_type == 'ACCOUNT_CREATED':
            await self.handle_account_created(event.event_data)
        elif event.event_type == 'TRANSFER_COMPLETED':
            await self.handle_transfer_completed(event.event_data)
        elif event.event_type == 'ACCOUNT_BALANCE_UPDATED':
            await self.handle_balance_updated(event.event_data)
    
    async def handle_account_created(self, data: Dict[str, Any]) -> None:
        """Handle TigerBeetle account creation"""
        from src.database_service import UserService
        
        user_service = UserService(self.db)
        
        # Check if user already exists
        existing = user_service.get_user_by_tigerbeetle_id(data['account_id'])
        if existing:
            logger.info(f"User already exists for TB account {data['account_id']}")
            return
        
        # Create user from TigerBeetle data
        user = user_service.create_user(
            email=data.get('email', f"user_{data['account_id']}@example.com"),
            phone=data.get('phone'),
            full_name=data.get('name', 'Unknown'),
            country_code=data.get('country_code', 'NGA'),
            tigerbeetle_account_id=data['account_id']
        )
        
        logger.info(f"✅ Created user {user.id} from TB account {data['account_id']}")
    
    async def handle_transfer_completed(self, data: Dict[str, Any]) -> None:
        """Handle TigerBeetle transfer completion"""
        from src.database_service import TransferMetadataService
        
        transfer_service = TransferMetadataService(self.db)
        
        # Create transfer metadata
        transfer = transfer_service.create_transfer_metadata(
            tigerbeetle_transfer_id=data['transfer_id'],
            user_id=data.get('user_id'),
            from_pix_key=data.get('from_pix_key'),
            to_pix_key=data.get('to_pix_key'),
            currency_code=data.get('currency', 'NGN'),
            corridor=data.get('corridor', 'PAPSS'),
            status='COMPLETED',
            reference_number=data.get('reference'),
            metadata=data.get('metadata', {})
        )
        
        logger.info(f"✅ Created transfer metadata {transfer.id} for TB transfer {data['transfer_id']}")
    
    async def handle_balance_updated(self, data: Dict[str, Any]) -> None:
        """Handle balance updates (logged only, balances stay in TigerBeetle)"""
        logger.info(f"💰 Balance updated for TB account {data['account_id']}")
        # No action needed - balances are queried from TigerBeetle directly
    
    def stop(self) -> None:
        """Stop CDC processing"""
        self.running = False
        logger.info("🛑 Stopping TigerBeetle CDC...")


async def main() -> None:
    """CDC main entry point"""
    from config.database import DatabaseManager
    
    db_manager = DatabaseManager()
    db_manager.initialize()
    
    # Initialize TigerBeetle client (placeholder - replace with actual client)
    tb_client = None
    
    cdc = TigerBeetleCDC(db_manager, tb_client)
    
    try:
        await cdc.start()
    except KeyboardInterrupt:
        cdc.stop()
    finally:
        db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
