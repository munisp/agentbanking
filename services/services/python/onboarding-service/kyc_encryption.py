"""
KYC/KYB Data Encryption Service
AES-256 encryption for audit trails, PII data, and sensitive documents
"""

import os
import base64
import hashlib
import secrets
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, Union, List
from dataclasses import dataclass
from enum import Enum
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import hmac

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    AES_256_GCM = "aes-256-gcm"
    AES_256_CBC = "aes-256-cbc"
    FERNET = "fernet"


class DataClassification(str, Enum):
    """Data classification levels for encryption"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, financial data
    TOP_SECRET = "top_secret"  # Encryption keys, credentials


@dataclass
class EncryptedData:
    """Encrypted data container"""
    ciphertext: bytes
    iv: bytes
    tag: Optional[bytes]
    algorithm: EncryptionAlgorithm
    key_id: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ciphertext": base64.b64encode(self.ciphertext).decode(),
            "iv": base64.b64encode(self.iv).decode(),
            "tag": base64.b64encode(self.tag).decode() if self.tag else None,
            "algorithm": self.algorithm.value,
            "key_id": self.key_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EncryptedData":
        return cls(
            ciphertext=base64.b64decode(data["ciphertext"]),
            iv=base64.b64decode(data["iv"]),
            tag=base64.b64decode(data["tag"]) if data.get("tag") else None,
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            key_id=data["key_id"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class KeyManager:
    """
    Secure key management for KYC encryption
    In production, integrate with HSM or cloud KMS (AWS KMS, Azure Key Vault, etc.)
    """
    
    def __init__(self, master_key: Optional[str] = None):
        self._master_key = master_key or os.getenv("KYC_MASTER_KEY")
        if not self._master_key:
            raise RuntimeError(
                "KYC_MASTER_KEY environment variable is required. "
                "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        
        self._key_cache: Dict[str, bytes] = {}
        self._key_versions: Dict[str, int] = {}
        self._current_key_id = "kyc-key-v1"
    
    def derive_key(self, key_id: str, salt: Optional[bytes] = None) -> bytes:
        """Derive encryption key using PBKDF2"""
        if key_id in self._key_cache:
            return self._key_cache[key_id]
        
        if salt is None:
            salt = hashlib.sha256(key_id.encode()).digest()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(self._master_key.encode())
        self._key_cache[key_id] = key
        
        return key
    
    def get_current_key_id(self) -> str:
        return self._current_key_id
    
    def rotate_key(self) -> str:
        """Rotate to a new key version"""
        version = self._key_versions.get(self._current_key_id, 1) + 1
        new_key_id = f"kyc-key-v{version}"
        self._key_versions[new_key_id] = version
        self._current_key_id = new_key_id
        logger.info(f"Key rotated to {new_key_id}")
        return new_key_id
    
    def generate_data_key(self) -> tuple[bytes, bytes]:
        """Generate a data encryption key (DEK) encrypted with master key"""
        dek = secrets.token_bytes(32)
        
        # Encrypt DEK with master key
        master_key = self.derive_key(self._current_key_id)
        cipher = Cipher(
            algorithms.AES(master_key),
            modes.GCM(secrets.token_bytes(12)),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_dek = encryptor.update(dek) + encryptor.finalize()
        
        return dek, encrypted_dek


class AES256Encryptor:
    """
    AES-256 encryption implementation for KYC data
    Supports both GCM (authenticated) and CBC modes
    """
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
    
    def encrypt_gcm(self, plaintext: bytes, key_id: Optional[str] = None) -> EncryptedData:
        """
        Encrypt using AES-256-GCM (authenticated encryption)
        Recommended for most use cases
        """
        key_id = key_id or self.key_manager.get_current_key_id()
        key = self.key_manager.derive_key(key_id)
        
        iv = secrets.token_bytes(12)  # 96 bits for GCM
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            tag=encryptor.tag,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
            key_id=key_id,
            timestamp=datetime.utcnow()
        )
    
    def decrypt_gcm(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt AES-256-GCM encrypted data"""
        key = self.key_manager.derive_key(encrypted_data.key_id)
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(encrypted_data.iv, encrypted_data.tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        return decryptor.update(encrypted_data.ciphertext) + decryptor.finalize()
    
    def encrypt_cbc(self, plaintext: bytes, key_id: Optional[str] = None) -> EncryptedData:
        """
        Encrypt using AES-256-CBC with PKCS7 padding
        Use when GCM is not available
        """
        key_id = key_id or self.key_manager.get_current_key_id()
        key = self.key_manager.derive_key(key_id)
        
        iv = secrets.token_bytes(16)  # 128 bits for CBC
        
        # Apply PKCS7 padding
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(plaintext) + padder.finalize()
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()
        
        # Generate HMAC for integrity
        hmac_key = self.key_manager.derive_key(f"{key_id}-hmac")
        tag = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            tag=tag,
            algorithm=EncryptionAlgorithm.AES_256_CBC,
            key_id=key_id,
            timestamp=datetime.utcnow()
        )
    
    def decrypt_cbc(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt AES-256-CBC encrypted data"""
        key = self.key_manager.derive_key(encrypted_data.key_id)
        
        # Verify HMAC
        hmac_key = self.key_manager.derive_key(f"{encrypted_data.key_id}-hmac")
        expected_tag = hmac.new(
            hmac_key, 
            encrypted_data.iv + encrypted_data.ciphertext, 
            hashlib.sha256
        ).digest()
        
        if not hmac.compare_digest(encrypted_data.tag, expected_tag):
            raise ValueError("HMAC verification failed - data may be tampered")
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(encrypted_data.iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        padded_data = decryptor.update(encrypted_data.ciphertext) + decryptor.finalize()
        
        # Remove PKCS7 padding
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
    
    def encrypt(self, plaintext: bytes, algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM) -> EncryptedData:
        """Encrypt data using specified algorithm"""
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self.encrypt_gcm(plaintext)
        elif algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self.encrypt_cbc(plaintext)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def decrypt(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt data based on algorithm used"""
        if encrypted_data.algorithm == EncryptionAlgorithm.AES_256_GCM:
            return self.decrypt_gcm(encrypted_data)
        elif encrypted_data.algorithm == EncryptionAlgorithm.AES_256_CBC:
            return self.decrypt_cbc(encrypted_data)
        else:
            raise ValueError(f"Unsupported algorithm: {encrypted_data.algorithm}")


class PIIEncryptor:
    """
    Specialized encryptor for PII (Personally Identifiable Information)
    Provides field-level encryption for sensitive data
    """
    
    PII_FIELDS = [
        "nin", "bvn", "ssn", "passport_number", "drivers_license",
        "date_of_birth", "phone_number", "email", "address",
        "bank_account", "credit_card", "tax_id", "biometric_data",
        "face_encoding", "fingerprint", "signature"
    ]
    
    def __init__(self, encryptor: AES256Encryptor):
        self.encryptor = encryptor
    
    def encrypt_pii_field(self, field_name: str, value: str) -> Dict[str, Any]:
        """Encrypt a single PII field"""
        if not value:
            return {"encrypted": False, "value": value}
        
        encrypted = self.encryptor.encrypt_gcm(value.encode())
        
        return {
            "encrypted": True,
            "field": field_name,
            "data": encrypted.to_dict()
        }
    
    def decrypt_pii_field(self, encrypted_field: Dict[str, Any]) -> str:
        """Decrypt a single PII field"""
        if not encrypted_field.get("encrypted"):
            return encrypted_field.get("value", "")
        
        encrypted_data = EncryptedData.from_dict(encrypted_field["data"])
        decrypted = self.encryptor.decrypt(encrypted_data)
        
        return decrypted.decode()
    
    def encrypt_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt all PII fields in a document
        Preserves non-PII fields as-is
        """
        encrypted_doc = {}
        
        for key, value in document.items():
            if key.lower() in self.PII_FIELDS:
                if isinstance(value, str):
                    encrypted_doc[key] = self.encrypt_pii_field(key, value)
                elif isinstance(value, dict):
                    encrypted_doc[key] = self.encrypt_document(value)
                else:
                    encrypted_doc[key] = value
            elif isinstance(value, dict):
                encrypted_doc[key] = self.encrypt_document(value)
            elif isinstance(value, list):
                encrypted_doc[key] = [
                    self.encrypt_document(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                encrypted_doc[key] = value
        
        return encrypted_doc
    
    def decrypt_document(self, encrypted_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt all encrypted PII fields in a document"""
        decrypted_doc = {}
        
        for key, value in encrypted_doc.items():
            if isinstance(value, dict):
                if value.get("encrypted"):
                    decrypted_doc[key] = self.decrypt_pii_field(value)
                else:
                    decrypted_doc[key] = self.decrypt_document(value)
            elif isinstance(value, list):
                decrypted_doc[key] = [
                    self.decrypt_document(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                decrypted_doc[key] = value
        
        return decrypted_doc


class AuditTrailEncryptor:
    """
    Encrypted audit trail for KYC/KYB operations
    Ensures compliance with data protection regulations
    """
    
    def __init__(self, encryptor: AES256Encryptor, db_url: Optional[str] = None):
        self.encryptor = encryptor
        self._audit_log: List[Dict[str, Any]] = []
        self._db_url = db_url or os.getenv("DATABASE_URL")
    
    def log_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """
        Log an encrypted audit event
        Returns the audit event ID
        """
        event_id = secrets.token_hex(16)
        
        audit_entry = {
            "event_id": event_id,
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Encrypt the audit entry
        plaintext = json.dumps(audit_entry).encode()
        encrypted = self.encryptor.encrypt_gcm(plaintext)
        
        encrypted_entry = {
            "event_id": event_id,
            "encrypted_data": encrypted.to_dict(),
            "timestamp": audit_entry["timestamp"]
        }
        
        self._audit_log.append(encrypted_entry)
        self._persist_entry(encrypted_entry)
        
        logger.info(f"Audit event logged: {event_id} - {event_type}/{action}")
        
        return event_id
    
    def _persist_entry(self, entry: Dict[str, Any]) -> None:
        """Persist audit entry to database if configured"""
        if not self._db_url:
            return
        try:
            import asyncpg
            import asyncio

            async def _insert():
                conn = await asyncpg.connect(self._db_url)
                try:
                    await conn.execute(
                        "INSERT INTO kyc_audit_log (event_id, encrypted_data, created_at) "
                        "VALUES ($1, $2, NOW()) ON CONFLICT (event_id) DO NOTHING",
                        entry["event_id"],
                        json.dumps(entry["encrypted_data"]),
                    )
                finally:
                    await conn.close()

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_insert())
            except RuntimeError:
                asyncio.run(_insert())
        except Exception as exc:
            logger.warning(f"Failed to persist audit entry {entry['event_id']}: {exc}")
    
    def get_audit_entry(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve and decrypt an audit entry"""
        for entry in self._audit_log:
            if entry["event_id"] == event_id:
                encrypted_data = EncryptedData.from_dict(entry["encrypted_data"])
                decrypted = self.encryptor.decrypt(encrypted_data)
                return json.loads(decrypted.decode())
        
        return None
    
    def get_audit_trail(
        self,
        user_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve and decrypt audit trail with optional filters
        """
        results = []
        
        for entry in self._audit_log:
            # Check time filters
            entry_time = datetime.fromisoformat(entry["timestamp"])
            
            if start_time and entry_time < start_time:
                continue
            if end_time and entry_time > end_time:
                continue
            
            # Decrypt entry
            encrypted_data = EncryptedData.from_dict(entry["encrypted_data"])
            decrypted = self.encryptor.decrypt(encrypted_data)
            audit_entry = json.loads(decrypted.decode())
            
            # Apply filters
            if user_id and audit_entry["user_id"] != user_id:
                continue
            if resource_id and audit_entry["resource_id"] != resource_id:
                continue
            
            results.append(audit_entry)
        
        return results
    
    def export_audit_trail(self, output_path: str) -> int:
        """
        Export encrypted audit trail to file
        Returns number of entries exported
        """
        with open(output_path, 'w') as f:
            json.dump(self._audit_log, f, indent=2)
        
        return len(self._audit_log)
    
    def import_audit_trail(self, input_path: str) -> int:
        """
        Import encrypted audit trail from file
        Returns number of entries imported
        """
        with open(input_path, 'r') as f:
            imported = json.load(f)
        
        self._audit_log.extend(imported)
        
        return len(imported)


class KYCEncryptionService:
    """
    Main KYC encryption service combining all encryption capabilities
    """
    
    def __init__(self, master_key: Optional[str] = None):
        self.key_manager = KeyManager(master_key)
        self.encryptor = AES256Encryptor(self.key_manager)
        self.pii_encryptor = PIIEncryptor(self.encryptor)
        self.audit_trail = AuditTrailEncryptor(self.encryptor)
    
    def encrypt_kyc_data(self, kyc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt KYC verification data"""
        return self.pii_encryptor.encrypt_document(kyc_data)
    
    def decrypt_kyc_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt KYC verification data"""
        return self.pii_encryptor.decrypt_document(encrypted_data)
    
    def encrypt_kyb_data(self, kyb_data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt KYB verification data"""
        return self.pii_encryptor.encrypt_document(kyb_data)
    
    def decrypt_kyb_data(self, encrypted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt KYB verification data"""
        return self.pii_encryptor.decrypt_document(encrypted_data)
    
    def encrypt_document_image(self, image_data: bytes) -> EncryptedData:
        """Encrypt document image"""
        return self.encryptor.encrypt_gcm(image_data)
    
    def decrypt_document_image(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt document image"""
        return self.encryptor.decrypt(encrypted_data)
    
    def log_kyc_event(
        self,
        user_id: str,
        action: str,
        verification_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Log KYC audit event"""
        return self.audit_trail.log_event(
            event_type="kyc",
            user_id=user_id,
            action=action,
            resource_type="kyc_verification",
            resource_id=verification_id,
            details=details,
            ip_address=ip_address
        )
    
    def log_kyb_event(
        self,
        user_id: str,
        action: str,
        business_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """Log KYB audit event"""
        return self.audit_trail.log_event(
            event_type="kyb",
            user_id=user_id,
            action=action,
            resource_type="kyb_verification",
            resource_id=business_id,
            details=details,
            ip_address=ip_address
        )
    
    def get_kyc_audit_trail(
        self,
        verification_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get audit trail for KYC verification"""
        return self.audit_trail.get_audit_trail(
            resource_id=verification_id,
            start_time=start_time,
            end_time=end_time
        )
    
    def rotate_encryption_key(self) -> str:
        """Rotate encryption key"""
        return self.key_manager.rotate_key()


# Global encryption service instance
_encryption_service: Optional[KYCEncryptionService] = None


def get_encryption_service() -> KYCEncryptionService:
    """Get or create encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = KYCEncryptionService()
    return _encryption_service
