"""
Post-Quantum Cryptography (PQC) Service - Production Implementation.
Uses liboqs (Open Quantum Safe) for real PQC operations.
Falls back to NIST-approved classical algorithms when liboqs is unavailable.
"""
import os
import logging
import secrets
import hashlib
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# Attempt to import liboqs
try:
    import oqs
    LIBOQS_AVAILABLE = True
    logger.info("liboqs available - using real PQC algorithms")
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("liboqs not available - using classical cryptography fallback (install python-oqs for PQC)")

# Fallback: use cryptography library for classical algorithms
try:
    from cryptography.hazmat.primitives.asymmetric import ec, padding
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.error("cryptography library not available - install with: pip install cryptography")


class PQCError(Exception):
    pass


class Kyber768:
    """
    Kyber-768 Key Encapsulation Mechanism (KEM).
    Uses liboqs if available, otherwise falls back to ECDH P-384 (equivalent security level).
    """

    ALGORITHM = "Kyber768"
    FALLBACK_ALGORITHM = "ECDH-P384"

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a Kyber-768 keypair (public_key, secret_key)."""
        if LIBOQS_AVAILABLE:
            with oqs.KeyEncapsulation(self.ALGORITHM) as kem:
                public_key = kem.generate_keypair()
                secret_key = kem.export_secret_key()
                logger.debug(f"Generated {self.ALGORITHM} keypair")
                return public_key, secret_key
        else:
            # Fallback: ECDH P-384
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
            public_key_bytes = private_key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo
            )
            private_key_bytes = private_key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            )
            logger.debug(f"Generated {self.FALLBACK_ALGORITHM} keypair (liboqs fallback)")
            return public_key_bytes, private_key_bytes

    def encapsulate(self, public_key: bytes) -> Tuple[bytes, bytes]:
        """
        Encapsulate a shared secret using the public key.
        Returns (ciphertext, shared_secret).
        """
        if LIBOQS_AVAILABLE:
            with oqs.KeyEncapsulation(self.ALGORITHM) as kem:
                ciphertext, shared_secret = kem.encap_secret(public_key)
                return ciphertext, shared_secret
        else:
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            # Fallback: ECDH key agreement
            peer_public_key = serialization.load_der_public_key(public_key, backend=default_backend())
            ephemeral_private = ec.generate_private_key(ec.SECP384R1(), default_backend())
            shared_key = ephemeral_private.exchange(ec.ECDH(), peer_public_key)
            # Derive shared secret via HKDF
            shared_secret = HKDF(
                algorithm=hashes.SHA384(),
                length=32,
                salt=None,
                info=b"kyber768-fallback",
                backend=default_backend()
            ).derive(shared_key)
            ciphertext = ephemeral_private.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo
            )
            return ciphertext, shared_secret

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate the shared secret using the secret key and ciphertext.
        Returns shared_secret.
        """
        if LIBOQS_AVAILABLE:
            with oqs.KeyEncapsulation(self.ALGORITHM, secret_key=secret_key) as kem:
                shared_secret = kem.decap_secret(ciphertext)
                return shared_secret
        else:
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            # Fallback: ECDH decapsulation
            private_key = serialization.load_der_private_key(secret_key, password=None, backend=default_backend())
            peer_public_key = serialization.load_der_public_key(ciphertext, backend=default_backend())
            shared_key = private_key.exchange(ec.ECDH(), peer_public_key)
            shared_secret = HKDF(
                algorithm=hashes.SHA384(),
                length=32,
                salt=None,
                info=b"kyber768-fallback",
                backend=default_backend()
            ).derive(shared_key)
            return shared_secret


class Dilithium3:
    """
    CRYSTALS-Dilithium3 Digital Signature Scheme.
    Uses liboqs if available, otherwise falls back to ECDSA P-384.
    """

    ALGORITHM = "Dilithium3"
    FALLBACK_ALGORITHM = "ECDSA-P384"

    def generate_keypair(self) -> Tuple[bytes, bytes]:
        """Generate a Dilithium3 keypair (public_key, secret_key)."""
        if LIBOQS_AVAILABLE:
            with oqs.Signature(self.ALGORITHM) as sig:
                public_key = sig.generate_keypair()
                secret_key = sig.export_secret_key()
                return public_key, secret_key
        else:
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
            public_key_bytes = private_key.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo
            )
            private_key_bytes = private_key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption()
            )
            return public_key_bytes, private_key_bytes

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """Sign a message with Dilithium3 secret key."""
        if LIBOQS_AVAILABLE:
            with oqs.Signature(self.ALGORITHM, secret_key=secret_key) as sig:
                return sig.sign(message)
        else:
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            private_key = serialization.load_der_private_key(secret_key, password=None, backend=default_backend())
            signature = private_key.sign(message, ec.ECDSA(hashes.SHA384()))
            return signature

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a Dilithium3 signature."""
        if LIBOQS_AVAILABLE:
            with oqs.Signature(self.ALGORITHM) as sig:
                return sig.verify(message, signature, public_key)
        else:
            if not CRYPTOGRAPHY_AVAILABLE:
                raise PQCError("Neither liboqs nor cryptography library available")
            try:
                pub_key = serialization.load_der_public_key(public_key, backend=default_backend())
                pub_key.verify(signature, message, ec.ECDSA(hashes.SHA384()))
                return True
            except Exception:
                return False


class PQCService:
    """
    Unified Post-Quantum Cryptography service for the platform.
    Provides key generation, encapsulation, signing, and verification.
    """

    def __init__(self):
        self.kyber = Kyber768()
        self.dilithium = Dilithium3()
        self.pqc_available = LIBOQS_AVAILABLE
        logger.info(f"PQCService initialized (liboqs={'available' if LIBOQS_AVAILABLE else 'unavailable - using classical fallback'})")

    def generate_kem_keypair(self) -> Dict[str, bytes]:
        """Generate KEM keypair for key exchange."""
        public_key, secret_key = self.kyber.generate_keypair()
        return {"public_key": public_key, "secret_key": secret_key}

    def encapsulate_key(self, public_key: bytes) -> Dict[str, bytes]:
        """Encapsulate a shared secret."""
        ciphertext, shared_secret = self.kyber.encapsulate(public_key)
        return {"ciphertext": ciphertext, "shared_secret": shared_secret}

    def decapsulate_key(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """Decapsulate a shared secret."""
        return self.kyber.decapsulate(secret_key, ciphertext)

    def generate_signature_keypair(self) -> Dict[str, bytes]:
        """Generate digital signature keypair."""
        public_key, secret_key = self.dilithium.generate_keypair()
        return {"public_key": public_key, "secret_key": secret_key}

    def sign_message(self, message: bytes, secret_key: bytes) -> bytes:
        """Sign a message."""
        return self.dilithium.sign(message, secret_key)

    def verify_signature(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify a message signature."""
        return self.dilithium.verify(message, signature, public_key)

    def get_algorithm_info(self) -> Dict:
        """Return information about active algorithms."""
        return {
            "kem_algorithm": "Kyber768" if LIBOQS_AVAILABLE else "ECDH-P384 (fallback)",
            "signature_algorithm": "Dilithium3" if LIBOQS_AVAILABLE else "ECDSA-P384 (fallback)",
            "pqc_available": LIBOQS_AVAILABLE,
            "security_level": "NIST Level 3" if LIBOQS_AVAILABLE else "Classical 192-bit equivalent",
        }
