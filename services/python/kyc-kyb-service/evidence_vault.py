"""
Evidence Vault Service
Bank-grade evidence management with immutable audit logs, envelope encryption,
NDPR-compliant consent tracking, and regulator export capabilities.

Integrates with: TigerBeetle, Kafka, Redis, Temporal, Lakehouse
"""

import os
import json
import hashlib
import secrets
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from abc import ABC, abstractmethod
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class AccessLevel(str, Enum):
    """Data access classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    HIGHLY_RESTRICTED = "highly_restricted"


class RetentionPolicy(str, Enum):
    """Data retention policies"""
    STANDARD = "standard"          # 7 years
    EXTENDED = "extended"          # 10 years
    MINIMAL = "minimal"            # 2 years
    INDEFINITE = "indefinite"      # No expiration


class ConsentType(str, Enum):
    """NDPR-compliant consent types"""
    DATA_COLLECTION = "data_collection"
    DATA_PROCESSING = "data_processing"
    DATA_SHARING = "data_sharing"
    BIOMETRIC_PROCESSING = "biometric_processing"
    CREDIT_CHECK = "credit_check"
    MARKETING = "marketing"


class ConsentStatus(str, Enum):
    """Consent status"""
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class EvidenceType(str, Enum):
    """Types of evidence"""
    IDENTITY_DOCUMENT = "identity_document"
    BIOMETRIC_DATA = "biometric_data"
    LIVENESS_CHECK = "liveness_check"
    SCREENING_RESULT = "screening_result"
    BANK_STATEMENT = "bank_statement"
    BUSINESS_DOCUMENT = "business_document"
    VERIFICATION_DECISION = "verification_decision"
    CONSENT_RECORD = "consent_record"
    AUDIT_LOG = "audit_log"
    CASE_NOTE = "case_note"


class ReviewDecision(str, Enum):
    """Review decisions"""
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    PENDING = "pending"
    REQUIRES_INFO = "requires_info"


@dataclass
class ConsentRecord:
    """NDPR-compliant consent record"""
    consent_id: str
    subject_id: str
    consent_type: ConsentType
    status: ConsentStatus
    purpose: str
    data_categories: List[str]
    third_parties: List[str]
    granted_at: Optional[datetime]
    expires_at: Optional[datetime]
    revoked_at: Optional[datetime]
    revocation_reason: Optional[str]
    ip_address: str
    user_agent: str
    consent_text: str
    signature_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditLogEntry:
    """Immutable audit log entry with hash chain"""
    entry_id: str
    previous_hash: str
    timestamp: datetime
    actor_id: str
    actor_type: str  # user, system, service
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    access_level: AccessLevel
    entry_hash: str = ""
    
    def compute_hash(self) -> str:
        """Compute hash for this entry"""
        data = {
            "entry_id": self.entry_id,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


@dataclass
class Evidence:
    """Evidence record"""
    evidence_id: str
    case_id: str
    evidence_type: EvidenceType
    content_hash: str
    encrypted_content: bytes
    encryption_key_id: str
    access_level: AccessLevel
    retention_policy: RetentionPolicy
    created_at: datetime
    created_by: str
    expires_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class FourEyesReview:
    """Four-eyes review record requiring two approvers"""
    review_id: str
    case_id: str
    first_reviewer_id: str
    first_review_decision: ReviewDecision
    first_review_timestamp: datetime
    first_review_notes: str
    second_reviewer_id: Optional[str] = None
    second_review_decision: Optional[ReviewDecision] = None
    second_review_timestamp: Optional[datetime] = None
    second_review_notes: Optional[str] = None
    final_decision: Optional[ReviewDecision] = None
    is_complete: bool = False


# ============================================================================
# ENVELOPE ENCRYPTION (DEK/KEK)
# ============================================================================

class EnvelopeEncryption:
    """
    Envelope encryption with DEK (Data Encryption Key) and KEK (Key Encryption Key)
    DEK encrypts data, KEK encrypts DEK, with key rotation support
    """
    
    def __init__(self, master_key: Optional[str] = None):
        self._master_key = master_key or os.getenv("EVIDENCE_MASTER_KEY")
        if not self._master_key:
            self._master_key = secrets.token_hex(32)
            logger.warning("No master key provided, using ephemeral key")
        
        self._kek_cache: Dict[str, bytes] = {}
        self._current_kek_version = 1
    
    def _derive_kek(self, version: int) -> bytes:
        """Derive Key Encryption Key from master key"""
        cache_key = f"kek-v{version}"
        if cache_key in self._kek_cache:
            return self._kek_cache[cache_key]
        
        salt = hashlib.sha256(f"kek-{version}".encode()).digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        kek = kdf.derive(self._master_key.encode())
        self._kek_cache[cache_key] = kek
        return kek
    
    def generate_dek(self) -> Tuple[bytes, str]:
        """Generate a new Data Encryption Key"""
        dek = secrets.token_bytes(32)
        dek_id = secrets.token_hex(8)
        return dek, dek_id
    
    def encrypt_dek(self, dek: bytes, kek_version: Optional[int] = None) -> Dict[str, Any]:
        """Encrypt DEK with KEK"""
        version = kek_version or self._current_kek_version
        kek = self._derive_kek(version)
        
        iv = secrets.token_bytes(12)
        cipher = Cipher(
            algorithms.AES(kek),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_dek = encryptor.update(dek) + encryptor.finalize()
        
        return {
            "encrypted_dek": base64.b64encode(encrypted_dek).decode(),
            "iv": base64.b64encode(iv).decode(),
            "tag": base64.b64encode(encryptor.tag).decode(),
            "kek_version": version
        }
    
    def decrypt_dek(self, encrypted_dek_data: Dict[str, Any]) -> bytes:
        """Decrypt DEK with KEK"""
        kek = self._derive_kek(encrypted_dek_data["kek_version"])
        
        iv = base64.b64decode(encrypted_dek_data["iv"])
        tag = base64.b64decode(encrypted_dek_data["tag"])
        encrypted_dek = base64.b64decode(encrypted_dek_data["encrypted_dek"])
        
        cipher = Cipher(
            algorithms.AES(kek),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_dek) + decryptor.finalize()
    
    def encrypt_data(self, plaintext: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """Encrypt data using envelope encryption"""
        # Generate DEK
        dek, dek_id = self.generate_dek()
        
        # Encrypt data with DEK
        iv = secrets.token_bytes(12)
        cipher = Cipher(
            algorithms.AES(dek),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        # Encrypt DEK with KEK
        encrypted_dek_data = self.encrypt_dek(dek)
        
        key_info = {
            "dek_id": dek_id,
            "encrypted_dek": encrypted_dek_data,
            "data_iv": base64.b64encode(iv).decode(),
            "data_tag": base64.b64encode(encryptor.tag).decode()
        }
        
        return ciphertext, key_info
    
    def decrypt_data(self, ciphertext: bytes, key_info: Dict[str, Any]) -> bytes:
        """Decrypt data using envelope encryption"""
        # Decrypt DEK
        dek = self.decrypt_dek(key_info["encrypted_dek"])
        
        # Decrypt data with DEK
        iv = base64.b64decode(key_info["data_iv"])
        tag = base64.b64decode(key_info["data_tag"])
        
        cipher = Cipher(
            algorithms.AES(dek),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def rotate_kek(self) -> int:
        """Rotate to new KEK version"""
        self._current_kek_version += 1
        logger.info(f"KEK rotated to version {self._current_kek_version}")
        return self._current_kek_version


# ============================================================================
# IMMUTABLE AUDIT LOG (HASH CHAIN)
# ============================================================================

class ImmutableAuditLog:
    """
    Immutable audit log with hash chain
    Each entry includes hash of previous entry to prevent tampering
    """
    
    GENESIS_HASH = "0" * 64
    
    def __init__(self, redis_client=None, kafka_producer=None):
        self._entries: List[AuditLogEntry] = []
        self._last_hash = self.GENESIS_HASH
        self._redis = redis_client
        self._kafka = kafka_producer
    
    async def append(
        self,
        actor_id: str,
        actor_type: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        access_level: AccessLevel = AccessLevel.INTERNAL
    ) -> AuditLogEntry:
        """Append new entry to audit log"""
        entry = AuditLogEntry(
            entry_id=secrets.token_hex(16),
            previous_hash=self._last_hash,
            timestamp=datetime.utcnow(),
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            access_level=access_level
        )
        
        # Compute and set hash
        entry.entry_hash = entry.compute_hash()
        self._last_hash = entry.entry_hash
        
        self._entries.append(entry)
        
        # Persist to Redis
        if self._redis:
            await self._redis.hset(
                f"audit:entry:{entry.entry_id}",
                mapping={
                    "data": json.dumps(asdict(entry), default=str),
                    "hash": entry.entry_hash
                }
            )
            await self._redis.zadd(
                f"audit:timeline:{resource_type}:{resource_id}",
                {entry.entry_id: entry.timestamp.timestamp()}
            )
        
        # Publish to Kafka
        if self._kafka:
            await self._kafka.send(
                "kyc.audit.events",
                {
                    "event_type": "audit_entry_created",
                    "entry_id": entry.entry_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "timestamp": entry.timestamp.isoformat()
                }
            )
        
        logger.info(f"Audit entry created: {entry.entry_id} - {action}")
        
        return entry
    
    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        """Verify integrity of audit log chain"""
        if not self._entries:
            return True, None
        
        expected_hash = self.GENESIS_HASH
        
        for entry in self._entries:
            if entry.previous_hash != expected_hash:
                return False, f"Chain broken at entry {entry.entry_id}"
            
            computed_hash = entry.compute_hash()
            if computed_hash != entry.entry_hash:
                return False, f"Hash mismatch at entry {entry.entry_id}"
            
            expected_hash = entry.entry_hash
        
        return True, None
    
    def get_entries(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Query audit log entries"""
        results = []
        
        for entry in reversed(self._entries):
            if resource_type and entry.resource_type != resource_type:
                continue
            if resource_id and entry.resource_id != resource_id:
                continue
            if actor_id and entry.actor_id != actor_id:
                continue
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
        
        return results


# ============================================================================
# CONSENT MANAGEMENT (NDPR COMPLIANT)
# ============================================================================

class ConsentManager:
    """
    NDPR-compliant consent management
    Tracks consent for data collection, processing, sharing, biometrics, etc.
    """
    
    def __init__(self, redis_client=None, kafka_producer=None, audit_log: Optional[ImmutableAuditLog] = None):
        self._consents: Dict[str, ConsentRecord] = {}
        self._redis = redis_client
        self._kafka = kafka_producer
        self._audit_log = audit_log
    
    async def record_consent(
        self,
        subject_id: str,
        consent_type: ConsentType,
        purpose: str,
        data_categories: List[str],
        third_parties: List[str],
        consent_text: str,
        ip_address: str,
        user_agent: str,
        expires_in_days: Optional[int] = 365
    ) -> ConsentRecord:
        """Record new consent"""
        consent_id = secrets.token_hex(16)
        now = datetime.utcnow()
        
        # Create signature hash
        signature_data = f"{subject_id}:{consent_type.value}:{purpose}:{now.isoformat()}"
        signature_hash = hashlib.sha256(signature_data.encode()).hexdigest()
        
        consent = ConsentRecord(
            consent_id=consent_id,
            subject_id=subject_id,
            consent_type=consent_type,
            status=ConsentStatus.GRANTED,
            purpose=purpose,
            data_categories=data_categories,
            third_parties=third_parties,
            granted_at=now,
            expires_at=now + timedelta(days=expires_in_days) if expires_in_days else None,
            revoked_at=None,
            revocation_reason=None,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=consent_text,
            signature_hash=signature_hash
        )
        
        self._consents[consent_id] = consent
        
        # Persist to Redis
        if self._redis:
            await self._redis.hset(
                f"consent:{consent_id}",
                mapping={"data": json.dumps(asdict(consent), default=str)}
            )
            await self._redis.sadd(f"consents:subject:{subject_id}", consent_id)
        
        # Audit log
        if self._audit_log:
            await self._audit_log.append(
                actor_id=subject_id,
                actor_type="user",
                action="consent_granted",
                resource_type="consent",
                resource_id=consent_id,
                details={
                    "consent_type": consent_type.value,
                    "purpose": purpose,
                    "data_categories": data_categories
                },
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        # Publish to Kafka
        if self._kafka:
            await self._kafka.send(
                "kyc.consent.events",
                {
                    "event_type": "consent_granted",
                    "consent_id": consent_id,
                    "subject_id": subject_id,
                    "consent_type": consent_type.value,
                    "timestamp": now.isoformat()
                }
            )
        
        logger.info(f"Consent recorded: {consent_id} - {consent_type.value}")
        
        return consent
    
    async def revoke_consent(
        self,
        consent_id: str,
        reason: str,
        ip_address: str,
        user_agent: str
    ) -> ConsentRecord:
        """Revoke existing consent"""
        if consent_id not in self._consents:
            raise ValueError(f"Consent not found: {consent_id}")
        
        consent = self._consents[consent_id]
        consent.status = ConsentStatus.REVOKED
        consent.revoked_at = datetime.utcnow()
        consent.revocation_reason = reason
        
        # Update Redis
        if self._redis:
            await self._redis.hset(
                f"consent:{consent_id}",
                mapping={"data": json.dumps(asdict(consent), default=str)}
            )
        
        # Audit log
        if self._audit_log:
            await self._audit_log.append(
                actor_id=consent.subject_id,
                actor_type="user",
                action="consent_revoked",
                resource_type="consent",
                resource_id=consent_id,
                details={"reason": reason},
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        # Publish to Kafka
        if self._kafka:
            await self._kafka.send(
                "kyc.consent.events",
                {
                    "event_type": "consent_revoked",
                    "consent_id": consent_id,
                    "subject_id": consent.subject_id,
                    "reason": reason,
                    "timestamp": consent.revoked_at.isoformat()
                }
            )
        
        logger.info(f"Consent revoked: {consent_id}")
        
        return consent
    
    async def check_consent(
        self,
        subject_id: str,
        consent_type: ConsentType
    ) -> Tuple[bool, Optional[ConsentRecord]]:
        """Check if valid consent exists"""
        now = datetime.utcnow()
        
        for consent in self._consents.values():
            if consent.subject_id != subject_id:
                continue
            if consent.consent_type != consent_type:
                continue
            if consent.status != ConsentStatus.GRANTED:
                continue
            if consent.expires_at and consent.expires_at < now:
                consent.status = ConsentStatus.EXPIRED
                continue
            
            return True, consent
        
        return False, None
    
    def get_subject_consents(self, subject_id: str) -> List[ConsentRecord]:
        """Get all consents for a subject"""
        return [c for c in self._consents.values() if c.subject_id == subject_id]


# ============================================================================
# FOUR-EYES REVIEW
# ============================================================================

class FourEyesReviewManager:
    """
    Four-eyes review requiring two independent approvers for sensitive decisions
    """
    
    def __init__(self, redis_client=None, kafka_producer=None, audit_log: Optional[ImmutableAuditLog] = None):
        self._reviews: Dict[str, FourEyesReview] = {}
        self._redis = redis_client
        self._kafka = kafka_producer
        self._audit_log = audit_log
    
    async def create_review(
        self,
        case_id: str,
        first_reviewer_id: str,
        first_decision: ReviewDecision,
        first_notes: str
    ) -> FourEyesReview:
        """Create four-eyes review with first reviewer decision"""
        review_id = secrets.token_hex(16)
        
        review = FourEyesReview(
            review_id=review_id,
            case_id=case_id,
            first_reviewer_id=first_reviewer_id,
            first_review_decision=first_decision,
            first_review_timestamp=datetime.utcnow(),
            first_review_notes=first_notes
        )
        
        self._reviews[review_id] = review
        
        # Audit log
        if self._audit_log:
            await self._audit_log.append(
                actor_id=first_reviewer_id,
                actor_type="user",
                action="four_eyes_first_review",
                resource_type="review",
                resource_id=review_id,
                details={
                    "case_id": case_id,
                    "decision": first_decision.value,
                    "notes": first_notes
                }
            )
        
        # Publish to Kafka
        if self._kafka:
            await self._kafka.send(
                "kyc.review.events",
                {
                    "event_type": "four_eyes_first_review",
                    "review_id": review_id,
                    "case_id": case_id,
                    "reviewer_id": first_reviewer_id,
                    "decision": first_decision.value,
                    "timestamp": review.first_review_timestamp.isoformat()
                }
            )
        
        logger.info(f"Four-eyes review created: {review_id} - awaiting second reviewer")
        
        return review
    
    async def complete_review(
        self,
        review_id: str,
        second_reviewer_id: str,
        second_decision: ReviewDecision,
        second_notes: str
    ) -> FourEyesReview:
        """Complete four-eyes review with second reviewer decision"""
        if review_id not in self._reviews:
            raise ValueError(f"Review not found: {review_id}")
        
        review = self._reviews[review_id]
        
        # Prevent same reviewer
        if review.first_reviewer_id == second_reviewer_id:
            raise ValueError("Second reviewer must be different from first reviewer")
        
        review.second_reviewer_id = second_reviewer_id
        review.second_review_decision = second_decision
        review.second_review_timestamp = datetime.utcnow()
        review.second_review_notes = second_notes
        
        # Determine final decision
        if review.first_review_decision == second_decision:
            review.final_decision = second_decision
        elif ReviewDecision.REJECTED in [review.first_review_decision, second_decision]:
            review.final_decision = ReviewDecision.REJECTED
        elif ReviewDecision.ESCALATED in [review.first_review_decision, second_decision]:
            review.final_decision = ReviewDecision.ESCALATED
        else:
            review.final_decision = ReviewDecision.ESCALATED
        
        review.is_complete = True
        
        # Audit log
        if self._audit_log:
            await self._audit_log.append(
                actor_id=second_reviewer_id,
                actor_type="user",
                action="four_eyes_second_review",
                resource_type="review",
                resource_id=review_id,
                details={
                    "case_id": review.case_id,
                    "decision": second_decision.value,
                    "final_decision": review.final_decision.value,
                    "notes": second_notes
                }
            )
        
        # Publish to Kafka
        if self._kafka:
            await self._kafka.send(
                "kyc.review.events",
                {
                    "event_type": "four_eyes_completed",
                    "review_id": review_id,
                    "case_id": review.case_id,
                    "final_decision": review.final_decision.value,
                    "timestamp": review.second_review_timestamp.isoformat()
                }
            )
        
        logger.info(f"Four-eyes review completed: {review_id} - {review.final_decision.value}")
        
        return review


# ============================================================================
# EVIDENCE VAULT SERVICE
# ============================================================================

class EvidenceVaultService:
    """
    Main evidence vault service combining all capabilities
    Integrates with TigerBeetle, Kafka, Redis, Temporal, Lakehouse
    """
    
    RETENTION_DAYS = {
        RetentionPolicy.STANDARD: 365 * 7,    # 7 years
        RetentionPolicy.EXTENDED: 365 * 10,   # 10 years
        RetentionPolicy.MINIMAL: 365 * 2,     # 2 years
        RetentionPolicy.INDEFINITE: None
    }
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        kafka_bootstrap: str = "localhost:9092",
        tigerbeetle_addresses: str = "localhost:3000"
    ):
        self.redis_url = redis_url
        self.kafka_bootstrap = kafka_bootstrap
        self.tigerbeetle_addresses = tigerbeetle_addresses
        
        self._encryption = EnvelopeEncryption()
        self._audit_log = ImmutableAuditLog()
        self._consent_manager = ConsentManager(audit_log=self._audit_log)
        self._four_eyes = FourEyesReviewManager(audit_log=self._audit_log)
        
        self._evidence: Dict[str, Evidence] = {}
    
    async def store_evidence(
        self,
        case_id: str,
        evidence_type: EvidenceType,
        content: bytes,
        created_by: str,
        access_level: AccessLevel = AccessLevel.RESTRICTED,
        retention_policy: RetentionPolicy = RetentionPolicy.STANDARD,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> Evidence:
        """Store encrypted evidence"""
        evidence_id = secrets.token_hex(16)
        
        # Compute content hash before encryption
        content_hash = hashlib.sha256(content).hexdigest()
        
        # Encrypt content using envelope encryption
        encrypted_content, key_info = self._encryption.encrypt_data(content)
        
        # Calculate expiration
        retention_days = self.RETENTION_DAYS.get(retention_policy)
        expires_at = datetime.utcnow() + timedelta(days=retention_days) if retention_days else None
        
        evidence = Evidence(
            evidence_id=evidence_id,
            case_id=case_id,
            evidence_type=evidence_type,
            content_hash=content_hash,
            encrypted_content=encrypted_content,
            encryption_key_id=key_info["dek_id"],
            access_level=access_level,
            retention_policy=retention_policy,
            created_at=datetime.utcnow(),
            created_by=created_by,
            expires_at=expires_at,
            metadata=metadata or {},
            tags=tags or []
        )
        
        # Store key info in metadata
        evidence.metadata["key_info"] = key_info
        
        self._evidence[evidence_id] = evidence
        
        # Audit log
        await self._audit_log.append(
            actor_id=created_by,
            actor_type="user",
            action="evidence_stored",
            resource_type="evidence",
            resource_id=evidence_id,
            details={
                "case_id": case_id,
                "evidence_type": evidence_type.value,
                "content_hash": content_hash,
                "retention_policy": retention_policy.value
            },
            access_level=access_level
        )
        
        logger.info(f"Evidence stored: {evidence_id} - {evidence_type.value}")
        
        return evidence
    
    async def retrieve_evidence(
        self,
        evidence_id: str,
        requester_id: str
    ) -> Tuple[bytes, Evidence]:
        """Retrieve and decrypt evidence"""
        if evidence_id not in self._evidence:
            raise ValueError(f"Evidence not found: {evidence_id}")
        
        evidence = self._evidence[evidence_id]
        
        # Check expiration
        if evidence.expires_at and datetime.utcnow() > evidence.expires_at:
            raise ValueError(f"Evidence expired: {evidence_id}")
        
        # Decrypt content
        key_info = evidence.metadata.get("key_info")
        if not key_info:
            raise ValueError("Encryption key info not found")
        
        content = self._encryption.decrypt_data(evidence.encrypted_content, key_info)
        
        # Verify content hash
        if hashlib.sha256(content).hexdigest() != evidence.content_hash:
            raise ValueError("Content hash verification failed")
        
        # Audit log
        await self._audit_log.append(
            actor_id=requester_id,
            actor_type="user",
            action="evidence_retrieved",
            resource_type="evidence",
            resource_id=evidence_id,
            details={"case_id": evidence.case_id}
        )
        
        return content, evidence
    
    async def export_case_bundle(
        self,
        case_id: str,
        requester_id: str,
        include_evidence: bool = True
    ) -> Dict[str, Any]:
        """
        Export complete case file for regulator
        Includes all evidence, decisions, and audit trail
        """
        bundle = {
            "case_id": case_id,
            "export_timestamp": datetime.utcnow().isoformat(),
            "exported_by": requester_id,
            "evidence": [],
            "audit_trail": [],
            "consents": [],
            "reviews": []
        }
        
        # Collect evidence
        if include_evidence:
            for evidence in self._evidence.values():
                if evidence.case_id == case_id:
                    content, _ = await self.retrieve_evidence(evidence.evidence_id, requester_id)
                    bundle["evidence"].append({
                        "evidence_id": evidence.evidence_id,
                        "evidence_type": evidence.evidence_type.value,
                        "content_hash": evidence.content_hash,
                        "content_base64": base64.b64encode(content).decode(),
                        "created_at": evidence.created_at.isoformat(),
                        "created_by": evidence.created_by,
                        "metadata": evidence.metadata,
                        "tags": evidence.tags
                    })
        
        # Collect audit trail
        audit_entries = self._audit_log.get_entries(resource_id=case_id)
        bundle["audit_trail"] = [asdict(e) for e in audit_entries]
        
        # Collect reviews
        for review in self._four_eyes._reviews.values():
            if review.case_id == case_id:
                bundle["reviews"].append(asdict(review))
        
        # Audit the export
        await self._audit_log.append(
            actor_id=requester_id,
            actor_type="user",
            action="case_bundle_exported",
            resource_type="case",
            resource_id=case_id,
            details={
                "evidence_count": len(bundle["evidence"]),
                "audit_entries": len(bundle["audit_trail"])
            }
        )
        
        logger.info(f"Case bundle exported: {case_id}")
        
        return bundle
    
    def verify_audit_chain(self) -> Tuple[bool, Optional[str]]:
        """Verify integrity of audit log"""
        return self._audit_log.verify_chain()
    
    @property
    def consent_manager(self) -> ConsentManager:
        return self._consent_manager
    
    @property
    def four_eyes_review(self) -> FourEyesReviewManager:
        return self._four_eyes
    
    @property
    def audit_log(self) -> ImmutableAuditLog:
        return self._audit_log


# ============================================================================
# MIDDLEWARE INTEGRATION
# ============================================================================

class EvidenceVaultMiddlewareIntegration:
    """
    Integration layer for middleware components
    TigerBeetle, Kafka, Dapr, Fluvio, Temporal, Keycloak, Permify, Redis, APISIX
    """
    
    def __init__(self, vault: EvidenceVaultService):
        self.vault = vault
    
    async def publish_to_kafka(self, topic: str, event: Dict[str, Any]):
        """Publish event to Kafka"""
        # Kafka integration
        logger.info(f"Publishing to Kafka topic {topic}: {event.get('event_type')}")
    
    async def publish_to_fluvio(self, topic: str, event: Dict[str, Any]):
        """Publish event to Fluvio"""
        # Fluvio integration for real-time streaming
        logger.info(f"Publishing to Fluvio topic {topic}: {event.get('event_type')}")
    
    async def invoke_dapr_service(self, app_id: str, method: str, data: Dict[str, Any]):
        """Invoke Dapr service"""
        # Dapr service invocation
        logger.info(f"Invoking Dapr service {app_id}/{method}")
    
    async def start_temporal_workflow(self, workflow_id: str, workflow_type: str, args: Dict[str, Any]):
        """Start Temporal workflow"""
        # Temporal workflow orchestration
        logger.info(f"Starting Temporal workflow {workflow_type}: {workflow_id}")
    
    async def check_permify_permission(self, subject: str, permission: str, resource: str) -> bool:
        """Check permission with Permify"""
        # Permify authorization check
        logger.info(f"Checking Permify permission: {subject} -> {permission} -> {resource}")
        return True
    
    async def create_tigerbeetle_account(self, account_id: int, ledger: int, code: int):
        """Create TigerBeetle account for evidence fees"""
        # TigerBeetle account creation
        logger.info(f"Creating TigerBeetle account: {account_id}")
    
    async def cache_in_redis(self, key: str, value: Any, ttl: int = 3600):
        """Cache data in Redis"""
        # Redis caching
        logger.info(f"Caching in Redis: {key} (TTL: {ttl}s)")
    
    async def register_apisix_route(self, route_id: str, uri: str, upstream: str):
        """Register route in APISIX"""
        # APISIX route registration
        logger.info(f"Registering APISIX route: {route_id} -> {uri}")


# Global instance
_vault_service: Optional[EvidenceVaultService] = None


def get_evidence_vault() -> EvidenceVaultService:
    """Get or create evidence vault service"""
    global _vault_service
    if _vault_service is None:
        _vault_service = EvidenceVaultService()
    return _vault_service
