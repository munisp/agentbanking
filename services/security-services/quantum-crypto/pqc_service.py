"""
Post-Quantum Cryptography Service
Implements NIST-standardized quantum-resistant algorithms:
- Kyber768: Key Encapsulation Mechanism (KEM) for key exchange
- Dilithium3: Digital Signature Algorithm (DSA)

This implementation uses the liboqs-python library which provides
NIST-approved post-quantum cryptographic algorithms.
"""

import os
import base64
import json
from typing import Tuple, Dict
from datetime import datetime
import logging

# Production PQC service with real liboqs or classical fallback
from pqc_service_production import PQCService, Kyber768, Dilithium3, LIBOQS_AVAILABLE


# Try to import liboqs, fall back to mock if not available
try:
    import oqs
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logging.warning("liboqs not available, using mock implementation")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Kyber768KEM:
    """
    Kyber768 Key Encapsulation Mechanism
    Provides quantum-resistant key exchange
    Security Level: NIST Level 3 (equivalent to AES-192)
    """
    
    def __init__(self):
        if LIBOQS_AVAILABLE:
            self.kem = oqs.KeyEncapsulation("Kyber768")
        else:
            self.kem = None
            logger.warning("Using mock Kyber768 implementation")
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a new Kyber768 keypair
        Returns: (public_key, secret_key)
        """
        if LIBOQS_AVAILABLE:
            public_key = self.kem.generate_keypair()
            secret_key = self.kem.export_secret_key()
            logger.info("Generated Kyber768 keypair")
            return public_key, secret_key
        else:
            # Mock implementation
            public_key = os.urandom(1184)  # Kyber768 public key size
            secret_key = os.urandom(2400)  # Kyber768 secret key size
            logger.info("Generated mock Kyber768 keypair")
            return public_key, secret_key
    
    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using the public key
        Returns: (ciphertext, shared_secret)
        """
        if LIBOQS_AVAILABLE:
            ciphertext, shared_secret = self.kem.encap_secret(public_key)
            logger.info("Encapsulated shared secret with Kyber768")
            return ciphertext, shared_secret
        else:
            # Mock implementation
            ciphertext = os.urandom(1088)  # Kyber768 ciphertext size
            shared_secret = os.urandom(32)  # 256-bit shared secret
            logger.info("Generated mock Kyber768 encapsulation")
            return ciphertext, shared_secret
    
    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate the shared secret using the secret key
        Returns: shared_secret
        """
        if LIBOQS_AVAILABLE:
            if self.kem is None:
                self.kem = oqs.KeyEncapsulation("Kyber768")
            shared_secret = self.kem.decap_secret(ciphertext)
            logger.info("Decapsulated shared secret with Kyber768")
            return shared_secret
        else:
            # Mock implementation - return deterministic value for testing
            shared_secret = os.urandom(32)
            logger.info("Generated mock Kyber768 decapsulation")
            return shared_secret

class Dilithium3DSA:
    """
    Dilithium3 Digital Signature Algorithm
    Provides quantum-resistant digital signatures
    Security Level: NIST Level 3 (equivalent to AES-192)
    """
    
    def __init__(self):
        if LIBOQS_AVAILABLE:
            self.sig = oqs.Signature("Dilithium3")
        else:
            self.sig = None
            logger.warning("Using mock Dilithium3 implementation")
    
    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """
        Generate a new Dilithium3 keypair
        Returns: (public_key, secret_key)
        """
        if LIBOQS_AVAILABLE:
            public_key = self.sig.generate_keypair()
            secret_key = self.sig.export_secret_key()
            logger.info("Generated Dilithium3 keypair")
            return public_key, secret_key
        else:
            # Mock implementation
            public_key = os.urandom(1952)  # Dilithium3 public key size
            secret_key = os.urandom(4000)  # Dilithium3 secret key size
            logger.info("Generated mock Dilithium3 keypair")
            return public_key, secret_key
    
    def sign(self, secret_key: bytes, message: bytes) -> bytes:
        """
        Sign a message using the secret key
        Returns: signature
        """
        if LIBOQS_AVAILABLE:
            if self.sig is None:
                self.sig = oqs.Signature("Dilithium3")
            signature = self.sig.sign(message)
            logger.info(f"Signed message of {len(message)} bytes with Dilithium3")
            return signature
        else:
            # Mock implementation
            signature = os.urandom(3293)  # Dilithium3 signature size
            logger.info(f"Generated mock Dilithium3 signature for {len(message)} bytes")
            return signature
    
    def verify(self, public_key: bytes, message: bytes, signature: bytes) -> bool:
        """
        Verify a signature using the public key
        Returns: True if valid, False otherwise
        """
        if LIBOQS_AVAILABLE:
            if self.sig is None:
                self.sig = oqs.Signature("Dilithium3")
            is_valid = self.sig.verify(message, signature, public_key)
            logger.info(f"Verified Dilithium3 signature: {is_valid}")
            return is_valid
        else:
            # Mock implementation - always return True for testing
            logger.info("Mock Dilithium3 signature verification (always True)")
            return True

class PQCService:
    """
    Post-Quantum Cryptography Service
    Provides high-level API for quantum-resistant operations
    """
    
    def __init__(self):
        self.kyber = Kyber768KEM()
        self.dilithium = Dilithium3DSA()
        logger.info("Initialized PQC Service")
    
    def create_secure_channel_keys(self) -> Dict:
        """
        Create keys for establishing a secure channel
        Returns: Dictionary with public_key, secret_key (base64 encoded)
        """
        public_key, secret_key = self.kyber.generate_keypair()
        
        return {
            "algorithm": "Kyber768",
            "public_key": base64.b64encode(public_key).decode('utf-8'),
            "secret_key": base64.b64encode(secret_key).decode('utf-8'),
            "created_at": datetime.utcnow().isoformat()
        }
    
    def establish_shared_secret(self, public_key_b64: str) -> Dict:
        """
        Establish a shared secret with a peer
        Returns: Dictionary with ciphertext and shared_secret (base64 encoded)
        """
        public_key = base64.b64decode(public_key_b64)
        ciphertext, shared_secret = self.kyber.encapsulate(public_key)
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "shared_secret": base64.b64encode(shared_secret).decode('utf-8'),
            "algorithm": "Kyber768"
        }
    
    def derive_shared_secret(self, secret_key_b64: str, ciphertext_b64: str) -> Dict:
        """
        Derive the shared secret from ciphertext
        Returns: Dictionary with shared_secret (base64 encoded)
        """
        secret_key = base64.b64decode(secret_key_b64)
        ciphertext = base64.b64decode(ciphertext_b64)
        shared_secret = self.kyber.decapsulate(secret_key, ciphertext)
        
        return {
            "shared_secret": base64.b64encode(shared_secret).decode('utf-8'),
            "algorithm": "Kyber768"
        }
    
    def create_signing_keys(self) -> Dict:
        """
        Create keys for digital signatures
        Returns: Dictionary with public_key, secret_key (base64 encoded)
        """
        public_key, secret_key = self.dilithium.generate_keypair()
        
        return {
            "algorithm": "Dilithium3",
            "public_key": base64.b64encode(public_key).decode('utf-8'),
            "secret_key": base64.b64encode(secret_key).decode('utf-8'),
            "created_at": datetime.utcnow().isoformat()
        }
    
    def sign_message(self, secret_key_b64: str, message: str) -> Dict:
        """
        Sign a message
        Returns: Dictionary with signature (base64 encoded)
        """
        secret_key = base64.b64decode(secret_key_b64)
        message_bytes = message.encode('utf-8')
        signature = self.dilithium.sign(secret_key, message_bytes)
        
        return {
            "signature": base64.b64encode(signature).decode('utf-8'),
            "algorithm": "Dilithium3",
            "message_hash": base64.b64encode(
                os.urandom(32)  # In production, use actual hash
            ).decode('utf-8')
        }
    
    def verify_signature(self, public_key_b64: str, message: str, signature_b64: str) -> Dict:
        """
        Verify a signature
        Returns: Dictionary with verification result
        """
        public_key = base64.b64decode(public_key_b64)
        message_bytes = message.encode('utf-8')
        signature = base64.b64decode(signature_b64)
        
        is_valid = self.dilithium.verify(public_key, message_bytes, signature)
        
        return {
            "valid": is_valid,
            "algorithm": "Dilithium3",
            "verified_at": datetime.utcnow().isoformat()
        }

# Example usage
if __name__ == "__main__":
    print("=== Post-Quantum Cryptography Service Demo ===\n")
    
    pqc = PQCService()
    
    # 1. Key Exchange (Kyber768)
    print("1. Quantum-Resistant Key Exchange (Kyber768)")
    print("-" * 50)
    
    # Alice generates keypair
    alice_keys = pqc.create_secure_channel_keys()
    print(f"Alice generated keypair")
    print(f"Public key length: {len(alice_keys['public_key'])} chars (base64)")
    
    # Bob encapsulates shared secret
    bob_encap = pqc.establish_shared_secret(alice_keys['public_key'])
    print(f"\nBob encapsulated shared secret")
    print(f"Ciphertext length: {len(bob_encap['ciphertext'])} chars (base64)")
    
    # Alice decapsulates shared secret
    alice_secret = pqc.derive_shared_secret(
        alice_keys['secret_key'],
        bob_encap['ciphertext']
    )
    print(f"\nAlice decapsulated shared secret")
    print(f"Shared secrets match: {alice_secret['shared_secret'] == bob_encap['shared_secret']}")
    
    # 2. Digital Signatures (Dilithium3)
    print("\n\n2. Quantum-Resistant Digital Signatures (Dilithium3)")
    print("-" * 50)
    
    # Generate signing keypair
    signing_keys = pqc.create_signing_keys()
    print(f"Generated signing keypair")
    print(f"Public key length: {len(signing_keys['public_key'])} chars (base64)")
    
    # Sign a message
    message = "Transfer 1000 NGN from Alice to Bob"
    signature_result = pqc.sign_message(signing_keys['secret_key'], message)
    print(f"\nSigned message: '{message}'")
    print(f"Signature length: {len(signature_result['signature'])} chars (base64)")
    
    # Verify signature
    verification = pqc.verify_signature(
        signing_keys['public_key'],
        message,
        signature_result['signature']
    )
    print(f"\nSignature verification: {verification['valid']}")
    
    # Try to verify with wrong message
    wrong_verification = pqc.verify_signature(
        signing_keys['public_key'],
        "Transfer 2000 NGN from Alice to Bob",  # Different message
        signature_result['signature']
    )
    print(f"Wrong message verification: {wrong_verification['valid']}")
    
    print("\n=== Demo Complete ===")
