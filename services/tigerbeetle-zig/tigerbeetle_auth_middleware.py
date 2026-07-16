"""
TigerBeetle Sync Authentication and mTLS Middleware
Production-grade security for sync endpoints
"""

import hashlib
import hmac
import json
import logging
import os
import ssl
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

class SecurityConfig:
    """Security configuration for TigerBeetle sync"""
    
    def __init__(self):
        # JWT Configuration
        self.jwt_secret = os.getenv("TIGERBEETLE_JWT_SECRET", self._generate_default_secret())
        self.jwt_algorithm = os.getenv("TIGERBEETLE_JWT_ALGORITHM", "HS256")
        self.jwt_expiry_minutes = int(os.getenv("TIGERBEETLE_JWT_EXPIRY_MINUTES", "60"))
        
        # API Key Configuration
        self.api_key = os.getenv("TIGERBEETLE_API_KEY")
        self.api_key_header = os.getenv("TIGERBEETLE_API_KEY_HEADER", "X-TigerBeetle-API-Key")
        
        # mTLS Configuration
        self.mtls_enabled = os.getenv("TIGERBEETLE_MTLS_ENABLED", "false").lower() == "true"
        self.ca_cert_path = os.getenv("TIGERBEETLE_CA_CERT_PATH", "/etc/tigerbeetle/ca.crt")
        self.server_cert_path = os.getenv("TIGERBEETLE_SERVER_CERT_PATH", "/etc/tigerbeetle/server.crt")
        self.server_key_path = os.getenv("TIGERBEETLE_SERVER_KEY_PATH", "/etc/tigerbeetle/server.key")
        self.client_cert_required = os.getenv("TIGERBEETLE_CLIENT_CERT_REQUIRED", "true").lower() == "true"
        
        # HMAC Configuration for webhook/sync verification
        self.hmac_secret = os.getenv("TIGERBEETLE_HMAC_SECRET", self._generate_default_secret())
        
        # Rate Limiting
        self.rate_limit_requests = int(os.getenv("TIGERBEETLE_RATE_LIMIT_REQUESTS", "100"))
        self.rate_limit_window_seconds = int(os.getenv("TIGERBEETLE_RATE_LIMIT_WINDOW", "60"))
        
        # Allowed Edge IDs (comma-separated)
        self.allowed_edge_ids = os.getenv("TIGERBEETLE_ALLOWED_EDGE_IDS", "").split(",")
        self.allowed_edge_ids = [e.strip() for e in self.allowed_edge_ids if e.strip()]
    
    def _generate_default_secret(self) -> str:
        """Generate a default secret (for development only)"""
        import secrets
        return secrets.token_hex(32)


# Global config instance
security_config = SecurityConfig()


# =============================================================================
# JWT TOKEN MANAGEMENT
# =============================================================================

class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: str  # Subject (edge_id or service_id)
    iss: str  # Issuer
    aud: str  # Audience
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    permissions: list  # List of permissions
    edge_id: Optional[str] = None
    service_type: Optional[str] = None


class JWTManager:
    """JWT token management for TigerBeetle sync"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def create_token(
        self,
        subject: str,
        permissions: list,
        edge_id: Optional[str] = None,
        service_type: Optional[str] = None,
        expiry_minutes: Optional[int] = None
    ) -> str:
        """Create a JWT token"""
        now = datetime.utcnow()
        expiry = now + timedelta(minutes=expiry_minutes or self.config.jwt_expiry_minutes)
        
        payload = {
            "sub": subject,
            "iss": "tigerbeetle-zig-primary",
            "aud": "tigerbeetle-sync",
            "exp": int(expiry.timestamp()),
            "iat": int(now.timestamp()),
            "permissions": permissions,
            "edge_id": edge_id,
            "service_type": service_type,
        }
        
        return jwt.encode(payload, self.config.jwt_secret, algorithm=self.config.jwt_algorithm)
    
    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm],
                audience="tigerbeetle-sync"
            )
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    
    def create_edge_token(self, edge_id: str) -> str:
        """Create a token for an edge instance"""
        permissions = [
            "sync:read",
            "sync:write",
            "accounts:read",
            "accounts:write",
            "transfers:read",
            "transfers:write",
        ]
        return self.create_token(
            subject=f"edge:{edge_id}",
            permissions=permissions,
            edge_id=edge_id,
            service_type="edge"
        )
    
    def create_service_token(self, service_id: str, permissions: list) -> str:
        """Create a token for a service"""
        return self.create_token(
            subject=f"service:{service_id}",
            permissions=permissions,
            service_type="service"
        )


# Global JWT manager
jwt_manager = JWTManager(security_config)


# =============================================================================
# API KEY AUTHENTICATION
# =============================================================================

api_key_header = APIKeyHeader(name=security_config.api_key_header, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> bool:
    """Verify API key"""
    if not security_config.api_key:
        # API key not configured, skip validation
        return True
    
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if not hmac.compare_digest(api_key, security_config.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return True


# =============================================================================
# JWT BEARER AUTHENTICATION
# =============================================================================

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_jwt_token(request: Request) -> Optional[TokenPayload]:
    """Verify JWT token from Authorization header"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    return jwt_manager.verify_token(token)


# =============================================================================
# HMAC SIGNATURE VERIFICATION
# =============================================================================

class HMACVerifier:
    """HMAC signature verification for sync requests"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def sign_payload(self, payload: bytes, timestamp: int) -> str:
        """Sign a payload with HMAC"""
        message = f"{timestamp}.{payload.decode()}"
        signature = hmac.new(
            self.config.hmac_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        timestamp: int,
        max_age_seconds: int = 300
    ) -> bool:
        """Verify HMAC signature"""
        # Check timestamp freshness
        current_time = int(time.time())
        if abs(current_time - timestamp) > max_age_seconds:
            logger.warning(f"Signature timestamp too old: {timestamp}")
            return False
        
        # Compute expected signature
        expected_signature = self.sign_payload(payload, timestamp)
        
        # Compare signatures
        return hmac.compare_digest(signature, expected_signature)


# Global HMAC verifier
hmac_verifier = HMACVerifier(security_config)


async def verify_hmac_signature(request: Request) -> bool:
    """Verify HMAC signature from request headers"""
    signature = request.headers.get("X-TigerBeetle-Signature")
    timestamp_str = request.headers.get("X-TigerBeetle-Timestamp")
    
    if not signature or not timestamp_str:
        # HMAC not provided, allow if other auth is present
        return True
    
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp")
    
    body = await request.body()
    
    if not hmac_verifier.verify_signature(body, signature, timestamp):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    return True


# =============================================================================
# mTLS CONFIGURATION
# =============================================================================

class MTLSConfig:
    """mTLS configuration helper"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context for mTLS"""
        if not self.config.mtls_enabled:
            return None
        
        try:
            # Create SSL context
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            
            # Load server certificate and key
            context.load_cert_chain(
                certfile=self.config.server_cert_path,
                keyfile=self.config.server_key_path
            )
            
            # Load CA certificate for client verification
            if self.config.client_cert_required:
                context.verify_mode = ssl.CERT_REQUIRED
                context.load_verify_locations(cafile=self.config.ca_cert_path)
            else:
                context.verify_mode = ssl.CERT_OPTIONAL
                if os.path.exists(self.config.ca_cert_path):
                    context.load_verify_locations(cafile=self.config.ca_cert_path)
            
            # Set minimum TLS version
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            logger.info("mTLS SSL context created successfully")
            return context
            
        except Exception as e:
            logger.error(f"Failed to create SSL context: {e}")
            return None
    
    def verify_client_certificate(self, cert_der: bytes) -> Tuple[bool, Optional[str]]:
        """Verify client certificate and extract edge ID"""
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            
            # Check certificate validity
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False, None
            
            # Extract common name (edge ID)
            common_name = None
            for attribute in cert.subject:
                if attribute.oid == NameOID.COMMON_NAME:
                    common_name = attribute.value
                    break
            
            # Verify edge ID is allowed
            if common_name and security_config.allowed_edge_ids:
                if common_name not in security_config.allowed_edge_ids:
                    logger.warning(f"Edge ID not allowed: {common_name}")
                    return False, None
            
            return True, common_name
            
        except Exception as e:
            logger.error(f"Certificate verification failed: {e}")
            return False, None


# Global mTLS config
mtls_config = MTLSConfig(security_config)


# =============================================================================
# COMBINED AUTHENTICATION DEPENDENCY
# =============================================================================

class AuthResult(BaseModel):
    """Authentication result"""
    authenticated: bool
    auth_method: str
    edge_id: Optional[str] = None
    service_id: Optional[str] = None
    permissions: list = []


async def authenticate_sync_request(request: Request) -> AuthResult:
    """
    Combined authentication for sync requests
    Supports: JWT, API Key, HMAC, mTLS
    """
    # Try JWT authentication first
    token_payload = await verify_jwt_token(request)
    if token_payload:
        return AuthResult(
            authenticated=True,
            auth_method="jwt",
            edge_id=token_payload.edge_id,
            service_id=token_payload.sub,
            permissions=token_payload.permissions
        )
    
    # Try API key authentication
    api_key = request.headers.get(security_config.api_key_header)
    if api_key and security_config.api_key:
        if hmac.compare_digest(api_key, security_config.api_key):
            return AuthResult(
                authenticated=True,
                auth_method="api_key",
                permissions=["sync:read", "sync:write"]
            )
    
    # Try HMAC signature authentication
    signature = request.headers.get("X-TigerBeetle-Signature")
    timestamp_str = request.headers.get("X-TigerBeetle-Timestamp")
    edge_id = request.headers.get("X-TigerBeetle-Edge-ID")
    
    if signature and timestamp_str:
        try:
            timestamp = int(timestamp_str)
            body = await request.body()
            
            if hmac_verifier.verify_signature(body, signature, timestamp):
                return AuthResult(
                    authenticated=True,
                    auth_method="hmac",
                    edge_id=edge_id,
                    permissions=["sync:read", "sync:write"]
                )
        except Exception as e:
            logger.warning(f"HMAC verification failed: {e}")
    
    # Check mTLS client certificate
    if security_config.mtls_enabled:
        client_cert = request.scope.get("transport", {}).get("peercert")
        if client_cert:
            valid, cert_edge_id = mtls_config.verify_client_certificate(client_cert)
            if valid:
                return AuthResult(
                    authenticated=True,
                    auth_method="mtls",
                    edge_id=cert_edge_id,
                    permissions=["sync:read", "sync:write"]
                )
    
    # No authentication provided
    # In development mode, allow unauthenticated requests
    if os.getenv("TIGERBEETLE_DEV_MODE", "false").lower() == "true":
        logger.warning("Allowing unauthenticated request in dev mode")
        return AuthResult(
            authenticated=True,
            auth_method="dev_mode",
            permissions=["sync:read", "sync:write"]
        )
    
    raise HTTPException(status_code=401, detail="Authentication required")


def require_permission(permission: str):
    """Decorator to require a specific permission"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, auth: AuthResult = Depends(authenticate_sync_request), **kwargs):
            if permission not in auth.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission} required"
                )
            return await func(*args, auth=auth, **kwargs)
        return wrapper
    return decorator


# =============================================================================
# RATE LIMITING
# =============================================================================

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed"""
        now = time.time()
        window_start = now - self.config.rate_limit_window_seconds
        
        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                t for t in self.requests[client_id] if t > window_start
            ]
        else:
            self.requests[client_id] = []
        
        # Check limit
        if len(self.requests[client_id]) >= self.config.rate_limit_requests:
            return False
        
        # Record request
        self.requests[client_id].append(now)
        return True


# Global rate limiter
rate_limiter = RateLimiter(security_config)


async def check_rate_limit(request: Request, auth: AuthResult = Depends(authenticate_sync_request)):
    """Check rate limit for request"""
    client_id = auth.edge_id or auth.service_id or request.client.host
    
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return auth


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def generate_edge_credentials(edge_id: str) -> Dict[str, str]:
    """Generate credentials for a new edge instance"""
    token = jwt_manager.create_edge_token(edge_id)
    
    # Generate HMAC key for this edge
    edge_hmac_key = hmac.new(
        security_config.hmac_secret.encode(),
        edge_id.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "edge_id": edge_id,
        "jwt_token": token,
        "hmac_key": edge_hmac_key,
        "api_endpoint": os.getenv("TIGERBEETLE_ZIG_ENDPOINT", "http://localhost:8030"),
    }


def create_signed_request_headers(
    edge_id: str,
    payload: bytes,
    token: Optional[str] = None
) -> Dict[str, str]:
    """Create headers for a signed sync request"""
    timestamp = int(time.time())
    signature = hmac_verifier.sign_payload(payload, timestamp)
    
    headers = {
        "X-TigerBeetle-Edge-ID": edge_id,
        "X-TigerBeetle-Timestamp": str(timestamp),
        "X-TigerBeetle-Signature": signature,
        "Content-Type": "application/json",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    return headers
