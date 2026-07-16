#!/usr/bin/env python3
"""
Comprehensive Database Tests
Tests for all database operations
"""

import pytest
import uuid
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.database import DatabaseManager, DatabaseConfig
from src.database_service import (
    UserService, PIXKeyService, TransferMetadataService,
    ComplianceService, CDCService
)
from src.models import Base, KYCStatus, PIXKeyType, TransferStatus


@pytest.fixture(scope='module')
def db_manager():
    """Create test database manager"""
    # Use test database
    os.environ['POSTGRES_DB'] = 'remittance_test'
    
    manager = DatabaseManager()
    manager.initialize()
    
    # Create all tables
    Base.metadata.create_all(manager.engine)
    
    yield manager
    
    # Cleanup
    Base.metadata.drop_all(manager.engine)
    manager.close()


@pytest.fixture
def user_service(db_manager):
    return UserService(db_manager)


@pytest.fixture
def pix_service(db_manager):
    return PIXKeyService(db_manager)


@pytest.fixture
def transfer_service(db_manager):
    return TransferMetadataService(db_manager)


@pytest.fixture
def compliance_service(db_manager):
    return ComplianceService(db_manager)


@pytest.fixture
def cdc_service(db_manager):
    return CDCService(db_manager)


class TestUserService:
    """Test user management"""
    
    def test_create_user(self, user_service):
        """Test user creation"""
        user = user_service.create_user(
            email='test@example.com',
            phone='+2348012345678',
            full_name='Test User',
            country_code='NGA',
            tigerbeetle_account_id=1000001
        )
        
        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.tigerbeetle_account_id == 1000001
        assert user.kyc_status == KYCStatus.PENDING
        assert user.is_active == True
    
    def test_get_user_by_email(self, user_service):
        """Test get user by email"""
        user = user_service.get_user_by_email('test@example.com')
        
        assert user is not None
        assert user.email == 'test@example.com'
    
    def test_get_user_by_tigerbeetle_id(self, user_service):
        """Test get user by TigerBeetle ID"""
        user = user_service.get_user_by_tigerbeetle_id(1000001)
        
        assert user is not None
        assert user.tigerbeetle_account_id == 1000001
    
    def test_update_kyc_status(self, user_service):
        """Test KYC status update"""
        user = user_service.get_user_by_email('test@example.com')
        
        updated_user = user_service.update_kyc_status(
            user_id=user.id,
            status=KYCStatus.VERIFIED,
            kyc_data={'document_type': 'passport', 'verified': True}
        )
        
        assert updated_user.kyc_status == KYCStatus.VERIFIED
        assert updated_user.kyc_verified_at is not None
        assert updated_user.kyc_data['verified'] == True
    
    def test_block_user(self, user_service):
        """Test user blocking"""
        user = user_service.create_user(
            email='blocked@example.com',
            phone='+2348012345679',
            full_name='Blocked User',
            country_code='NGA',
            tigerbeetle_account_id=1000002
        )
        
        blocked_user = user_service.block_user(
            user_id=user.id,
            reason='Suspicious activity detected'
        )
        
        assert blocked_user.is_blocked == True
        assert blocked_user.blocked_reason == 'Suspicious activity detected'


class TestPIXKeyService:
    """Test PIX key management"""
    
    def test_create_pix_key(self, user_service, pix_service):
        """Test PIX key creation"""
        user = user_service.get_user_by_email('test@example.com')
        
        pix_key = pix_service.create_pix_key(
            pix_key='test@example.com',
            user_id=user.id,
            tigerbeetle_account_id=user.tigerbeetle_account_id,
            key_type=PIXKeyType.EMAIL,
            is_primary=True
        )
        
        assert pix_key.pix_key == 'test@example.com'
        assert pix_key.user_id == user.id
        assert pix_key.key_type == PIXKeyType.EMAIL
        assert pix_key.is_primary == True
        assert pix_key.is_active == True
    
    def test_resolve_pix_key(self, pix_service):
        """Test PIX key resolution"""
        pix = pix_service.resolve_pix_key('test@example.com')
        
        assert pix is not None
        assert pix.pix_key == 'test@example.com'
        assert pix.tigerbeetle_account_id == 1000001
    
    def test_get_user_pix_keys(self, user_service, pix_service):
        """Test get all user PIX keys"""
        user = user_service.get_user_by_email('test@example.com')
        
        # Create another PIX key
        pix_service.create_pix_key(
            pix_key='+2348012345678',
            user_id=user.id,
            tigerbeetle_account_id=user.tigerbeetle_account_id,
            key_type=PIXKeyType.PHONE
        )
        
        pix_keys = pix_service.get_user_pix_keys(user.id)
        
        assert len(pix_keys) >= 2
        assert any(pk.key_type == PIXKeyType.EMAIL for pk in pix_keys)
        assert any(pk.key_type == PIXKeyType.PHONE for pk in pix_keys)


class TestTransferMetadataService:
    """Test transfer metadata management"""
    
    def test_create_transfer_metadata(self, user_service, transfer_service):
        """Test transfer metadata creation"""
        user = user_service.get_user_by_email('test@example.com')
        
        transfer = transfer_service.create_transfer_metadata(
            tigerbeetle_transfer_id=2000001,
            user_id=user.id,
            from_pix_key='test@example.com',
            to_pix_key='recipient@example.com',
            currency_code='NGN',
            corridor='PAPSS',
            description='Test transfer',
            reference_number='REF-001'
        )
        
        assert transfer.id is not None
        assert transfer.tigerbeetle_transfer_id == 2000001
        assert transfer.corridor == 'PAPSS'
        assert transfer.status == TransferStatus.PENDING
    
    def test_update_transfer_status(self, transfer_service):
        """Test transfer status update"""
        # Get the transfer we just created
        with transfer_service.db.get_session() as session:
            from src.models import TransferMetadata
            transfer = session.query(TransferMetadata).filter(
                TransferMetadata.tigerbeetle_transfer_id == 2000001
            ).first()
        
        updated_transfer = transfer_service.update_transfer_status(
            transfer_id=transfer.id,
            status=TransferStatus.COMPLETED
        )
        
        assert updated_transfer.status == TransferStatus.COMPLETED
        assert updated_transfer.completed_at is not None
    
    def test_get_user_transfers(self, user_service, transfer_service):
        """Test get user transfer history"""
        user = user_service.get_user_by_email('test@example.com')
        
        transfers = transfer_service.get_user_transfers(user.id, limit=50)
        
        assert len(transfers) > 0
        assert all(t.user_id == user.id for t in transfers)


class TestComplianceService:
    """Test compliance management"""
    
    def test_create_compliance_record(self, user_service, compliance_service):
        """Test compliance record creation"""
        user = user_service.get_user_by_email('test@example.com')
        
        record = compliance_service.create_compliance_record(
            entity_type='USER',
            entity_id=user.id,
            check_type='AML',
            status='PASS',
            risk_score=15,
            risk_level='LOW',
            findings={'sanctions': 'clear', 'pep': 'negative'}
        )
        
        assert record.id is not None
        assert record.entity_type == 'USER'
        assert record.check_type == 'AML'
        assert record.status == 'PASS'
        assert record.risk_score == 15
    
    def test_get_entity_compliance_records(self, user_service, compliance_service):
        """Test get compliance records for entity"""
        user = user_service.get_user_by_email('test@example.com')
        
        records = compliance_service.get_entity_compliance_records('USER', user.id)
        
        assert len(records) > 0
        assert all(r.entity_id == user.id for r in records)


class TestCDCService:
    """Test CDC integration"""
    
    def test_create_cdc_event(self, cdc_service):
        """Test CDC event creation"""
        event = cdc_service.create_cdc_event(
            event_type='ACCOUNT_CREATED',
            tigerbeetle_id=1000003,
            event_data={
                'account_id': 1000003,
                'email': 'cdc@example.com',
                'country_code': 'NGA'
            }
        )
        
        assert event.id is not None
        assert event.event_type == 'ACCOUNT_CREATED'
        assert event.tigerbeetle_id == 1000003
        assert event.processed == False
    
    def test_get_unprocessed_events(self, cdc_service):
        """Test get unprocessed events"""
        events = cdc_service.get_unprocessed_events(limit=100)
        
        assert len(events) > 0
        assert all(not e.processed for e in events)
    
    def test_mark_event_processed(self, cdc_service):
        """Test mark event as processed"""
        events = cdc_service.get_unprocessed_events(limit=1)
        
        if events:
            event = events[0]
            cdc_service.mark_event_processed(event.id)
            
            # Verify it's marked as processed
            with cdc_service.db.get_session() as session:
                from src.models import CDCEvent
                updated_event = session.query(CDCEvent).filter(
                    CDCEvent.id == event.id
                ).first()
                
                assert updated_event.processed == True
                assert updated_event.processed_at is not None


class TestDatabaseIntegration:
    """Test database integration"""
    
    def test_database_health_check(self, db_manager):
        """Test database health check"""
        assert db_manager.health_check() == True
    
    def test_transaction_rollback(self, db_manager):
        """Test transaction rollback on error"""
        from src.models import User
        
        with pytest.raises(Exception):
            with db_manager.get_session() as session:
                # Create user with duplicate email (should fail)
                user = User(
                    email='test@example.com',  # Duplicate
                    phone='+2348012345680',
                    full_name='Duplicate User',
                    country_code='NGA',
                    tigerbeetle_account_id=1000004
                )
                session.add(user)
                session.flush()
                
                # Force an error
                raise Exception("Simulated error")
        
        # Verify user was not created
        with db_manager.get_session() as session:
            count = session.query(User).filter(
                User.phone == '+2348012345680'
            ).count()
            assert count == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

