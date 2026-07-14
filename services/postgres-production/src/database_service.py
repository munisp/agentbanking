"""
Database Service Layer
Production CRUD operations with proper error handling
"""

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import and_, or_, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import uuid

from models import (
    User, PIXKey, TransferMetadata, AuditLog,
    ComplianceRecord, CDCEvent,
    KYCStatus, PIXKeyType, TransferStatus
)


class UserService:
    """User management service"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def create_user(self, email: str, phone: str, full_name: str,
                   country_code: str, tigerbeetle_account_id: int) -> User:
        """Create new user"""
        with self.db.get_session() as session:
            user = User(
                email=email,
                phone=phone,
                full_name=full_name,
                country_code=country_code,
                tigerbeetle_account_id=tigerbeetle_account_id
            )
            session.add(user)
            session.flush()
            
            # Log audit event
            audit = AuditLog(
                user_id=user.id,
                event_type='USER_CREATED',
                event_category='AUTH',
                action='create_user',
                result='SUCCESS',
                details={'email': email, 'country': country_code}
            )
            session.add(audit)
            
            return user
    
    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID"""
        with self.db.get_session() as session:
            return session.query(User).filter(User.id == user_id).first()
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        with self.db.get_session() as session:
            return session.query(User).filter(User.email == email).first()
    
    def get_user_by_tigerbeetle_id(self, tb_account_id: int) -> Optional[User]:
        """Get user by TigerBeetle account ID"""
        with self.db.get_session() as session:
            return session.query(User).filter(
                User.tigerbeetle_account_id == tb_account_id
            ).first()
    
    def update_kyc_status(self, user_id: uuid.UUID, status: KYCStatus,
                         kyc_data: Optional[Dict] = None) -> User:
        """Update user KYC status"""
        with self.db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            user.kyc_status = status
            if status == KYCStatus.VERIFIED:
                user.kyc_verified_at = datetime.utcnow()
            if kyc_data:
                user.kyc_data = kyc_data
            user.updated_at = datetime.utcnow()
            
            # Log audit event
            audit = AuditLog(
                user_id=user.id,
                event_type='KYC_STATUS_UPDATED',
                event_category='KYC',
                action='update_kyc',
                result='SUCCESS',
                details={'new_status': status.value}
            )
            session.add(audit)
            
            return user
    
    def block_user(self, user_id: uuid.UUID, reason: str) -> User:
        """Block user account"""
        with self.db.get_session() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            user.is_blocked = True
            user.blocked_reason = reason
            user.updated_at = datetime.utcnow()
            
            # Log audit event
            audit = AuditLog(
                user_id=user.id,
                event_type='USER_BLOCKED',
                event_category='COMPLIANCE',
                action='block_user',
                result='SUCCESS',
                details={'reason': reason}
            )
            session.add(audit)
            
            return user


class PIXKeyService:
    """PIX key management service"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def create_pix_key(self, pix_key: str, user_id: uuid.UUID,
                      tigerbeetle_account_id: int, key_type: PIXKeyType,
                      is_primary: bool = False) -> PIXKey:
        """Create new PIX key"""
        with self.db.get_session() as session:
            pix = PIXKey(
                pix_key=pix_key,
                user_id=user_id,
                tigerbeetle_account_id=tigerbeetle_account_id,
                key_type=key_type,
                is_primary=is_primary,
                verified_at=datetime.utcnow()
            )
            session.add(pix)
            
            # Log audit event
            audit = AuditLog(
                user_id=user_id,
                event_type='PIX_KEY_CREATED',
                event_category='TRANSFER',
                action='create_pix_key',
                result='SUCCESS',
                details={'pix_key': pix_key, 'type': key_type.value}
            )
            session.add(audit)
            
            return pix
    
    def resolve_pix_key(self, pix_key: str) -> Optional[PIXKey]:
        """Resolve PIX key to account"""
        with self.db.get_session() as session:
            return session.query(PIXKey).filter(
                and_(
                    PIXKey.pix_key == pix_key,
                    PIXKey.is_active == True
                )
            ).first()
    
    def get_user_pix_keys(self, user_id: uuid.UUID) -> List[PIXKey]:
        """Get all PIX keys for user"""
        with self.db.get_session() as session:
            return session.query(PIXKey).filter(
                and_(
                    PIXKey.user_id == user_id,
                    PIXKey.is_active == True
                )
            ).all()


class TransferMetadataService:
    """Transfer metadata service (NO amounts - those are in TigerBeetle)"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def create_transfer_metadata(self, tigerbeetle_transfer_id: int,
                                user_id: uuid.UUID, from_pix_key: str,
                                to_pix_key: str, currency_code: str,
                                corridor: str, **kwargs) -> TransferMetadata:
        """Create transfer metadata"""
        with self.db.get_session() as session:
            transfer = TransferMetadata(
                tigerbeetle_transfer_id=tigerbeetle_transfer_id,
                user_id=user_id,
                from_pix_key=from_pix_key,
                to_pix_key=to_pix_key,
                currency_code=currency_code,
                corridor=corridor,
                **kwargs
            )
            session.add(transfer)
            
            # Log audit event
            audit = AuditLog(
                user_id=user_id,
                event_type='TRANSFER_CREATED',
                event_category='TRANSFER',
                action='create_transfer',
                result='SUCCESS',
                details={
                    'corridor': corridor,
                    'currency': currency_code,
                    'tb_transfer_id': tigerbeetle_transfer_id
                }
            )
            session.add(audit)
            
            return transfer
    
    def update_transfer_status(self, transfer_id: uuid.UUID,
                              status: TransferStatus) -> TransferMetadata:
        """Update transfer status"""
        with self.db.get_session() as session:
            transfer = session.query(TransferMetadata).filter(
                TransferMetadata.id == transfer_id
            ).first()
            
            if not transfer:
                raise ValueError(f"Transfer {transfer_id} not found")
            
            transfer.status = status
            transfer.updated_at = datetime.utcnow()
            
            if status == TransferStatus.COMPLETED:
                transfer.completed_at = datetime.utcnow()
            
            return transfer
    
    def get_user_transfers(self, user_id: uuid.UUID, limit: int = 50) -> List[TransferMetadata]:
        """Get user transfer history"""
        with self.db.get_session() as session:
            return session.query(TransferMetadata).filter(
                TransferMetadata.user_id == user_id
            ).order_by(desc(TransferMetadata.created_at)).limit(limit).all()


class ComplianceService:
    """Compliance and AML service"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def create_compliance_record(self, entity_type: str, entity_id: uuid.UUID,
                                 check_type: str, status: str, risk_score: int,
                                 **kwargs) -> ComplianceRecord:
        """Create compliance check record"""
        with self.db.get_session() as session:
            record = ComplianceRecord(
                entity_type=entity_type,
                entity_id=entity_id,
                check_type=check_type,
                status=status,
                risk_score=risk_score,
                **kwargs
            )
            session.add(record)
            return record
    
    def get_entity_compliance_records(self, entity_type: str,
                                     entity_id: uuid.UUID) -> List[ComplianceRecord]:
        """Get all compliance records for entity"""
        with self.db.get_session() as session:
            return session.query(ComplianceRecord).filter(
                and_(
                    ComplianceRecord.entity_type == entity_type,
                    ComplianceRecord.entity_id == entity_id
                )
            ).order_by(desc(ComplianceRecord.created_at)).all()


class CDCService:
    """Change Data Capture service for TigerBeetle integration"""
    
    def __init__(self, db_manager) -> None:
        self.db = db_manager
    
    def create_cdc_event(self, event_type: str, tigerbeetle_id: int,
                        event_data: Dict) -> CDCEvent:
        """Create CDC event from TigerBeetle"""
        with self.db.get_session() as session:
            event = CDCEvent(
                event_type=event_type,
                tigerbeetle_id=tigerbeetle_id,
                event_data=event_data
            )
            session.add(event)
            return event
    
    def get_unprocessed_events(self, limit: int = 100) -> List[CDCEvent]:
        """Get unprocessed CDC events"""
        with self.db.get_session() as session:
            return session.query(CDCEvent).filter(
                CDCEvent.processed == False
            ).order_by(CDCEvent.created_at).limit(limit).all()
    
    def mark_event_processed(self, event_id: int, error: Optional[str] = None) -> None:
        """Mark CDC event as processed"""
        with self.db.get_session() as session:
            event = session.query(CDCEvent).filter(CDCEvent.id == event_id).first()
            if event:
                event.processed = True
                event.processed_at = datetime.utcnow()
                if error:
                    event.processing_error = error
                    event.retry_count += 1
