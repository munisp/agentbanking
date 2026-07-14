"""
PostgreSQL Database Connection and Models
Handles database operations for user authentication
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

import asyncpg
from asyncpg import Pool, Connection
import bcrypt

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/lakehouse_db"
)

# Connection pool
db_pool: Optional[Pool] = None

# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    DATA_ENGINEER = "data_engineer"
    ANALYST = "analyst"
    VIEWER = "viewer"

class MFAMethod(str, Enum):
    TOTP = "totp"
    SMS = "sms"
    EMAIL = "email"

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

async def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60
    )
    print(f"✓ Database pool initialized")

async def close_db_pool():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        print(f"✓ Database pool closed")

async def get_db() -> Connection:
    """Get database connection from pool"""
    if not db_pool:
        await init_db_pool()
    return await db_pool.acquire()

async def release_db(conn: Connection):
    """Release database connection back to pool"""
    await db_pool.release(conn)

# ============================================================================
# USER OPERATIONS
# ============================================================================

class UserDatabase:
    """Database operations for users"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    @staticmethod
    async def create_user(
        username: str,
        email: str,
        password: str,
        role: UserRole = UserRole.VIEWER,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new user"""
        conn = await get_db()
        try:
            hashed_password = UserDatabase.hash_password(password)
            
            user = await conn.fetchrow("""
                INSERT INTO users (username, email, hashed_password, role, first_name, last_name)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING user_id, username, email, role, is_active, created_at
            """, username, email, hashed_password, role.value, first_name, last_name)
            
            return dict(user)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        conn = await get_db()
        try:
            user = await conn.fetchrow("""
                SELECT user_id, username, email, hashed_password, role, is_active,
                       mfa_enabled, mfa_method, mfa_secret, mfa_backup_codes,
                       first_name, last_name, phone, department,
                       created_at, updated_at, last_login, password_changed_at,
                       failed_login_attempts, locked_until
                FROM users
                WHERE username = $1
            """, username)
            
            return dict(user) if user else None
        finally:
            await release_db(conn)
    
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        conn = await get_db()
        try:
            user = await conn.fetchrow("""
                SELECT user_id, username, email, role, is_active,
                       mfa_enabled, mfa_method, first_name, last_name,
                       created_at, last_login
                FROM users
                WHERE user_id = $1
            """, user_id)
            
            return dict(user) if user else None
        finally:
            await release_db(conn)
    
    @staticmethod
    async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username and password"""
        user = await UserDatabase.get_user_by_username(username)
        
        if not user:
            return None
        
        # Check if account is locked
        if user.get('locked_until') and user['locked_until'] > datetime.utcnow():
            return None
        
        # Verify password
        if not UserDatabase.verify_password(password, user['hashed_password']):
            # Increment failed login attempts
            await UserDatabase.increment_failed_login(username)
            return None
        
        # Check if user is active
        if not user.get('is_active', False):
            return None
        
        # Reset failed login attempts on success
        await UserDatabase.reset_failed_login(username)
        
        # Update last login
        await UserDatabase.update_last_login(username)
        
        return user
    
    @staticmethod
    async def update_last_login(username: str):
        """Update user's last login timestamp"""
        conn = await get_db()
        try:
            await conn.execute("""
                UPDATE users
                SET last_login = $1
                WHERE username = $2
            """, datetime.utcnow(), username)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def increment_failed_login(username: str):
        """Increment failed login attempts and lock account if needed"""
        conn = await get_db()
        try:
            # Increment counter
            result = await conn.fetchrow("""
                UPDATE users
                SET failed_login_attempts = failed_login_attempts + 1
                WHERE username = $1
                RETURNING failed_login_attempts
            """, username)
            
            # Lock account after 5 failed attempts
            if result and result['failed_login_attempts'] >= 5:
                lock_until = datetime.utcnow() + timedelta(minutes=30)
                await conn.execute("""
                    UPDATE users
                    SET locked_until = $1
                    WHERE username = $2
                """, lock_until, username)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def reset_failed_login(username: str):
        """Reset failed login attempts"""
        conn = await get_db()
        try:
            await conn.execute("""
                UPDATE users
                SET failed_login_attempts = 0,
                    locked_until = NULL
                WHERE username = $1
            """, username)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def enable_mfa(
        user_id: str,
        mfa_secret: str,
        mfa_method: MFAMethod = MFAMethod.TOTP,
        backup_codes: Optional[List[str]] = None
    ):
        """Enable MFA for user"""
        conn = await get_db()
        try:
            await conn.execute("""
                UPDATE users
                SET mfa_enabled = TRUE,
                    mfa_method = $1,
                    mfa_secret = $2,
                    mfa_backup_codes = $3
                WHERE user_id = $4
            """, mfa_method.value, mfa_secret, backup_codes or [], user_id)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def disable_mfa(user_id: str):
        """Disable MFA for user"""
        conn = await get_db()
        try:
            await conn.execute("""
                UPDATE users
                SET mfa_enabled = FALSE,
                    mfa_secret = NULL,
                    mfa_backup_codes = NULL
                WHERE user_id = $4
            """, user_id)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def use_backup_code(user_id: str, code: str) -> bool:
        """Use a backup code and remove it from the list"""
        conn = await get_db()
        try:
            user = await conn.fetchrow("""
                SELECT mfa_backup_codes
                FROM users
                WHERE user_id = $1
            """, user_id)
            
            if not user or not user['mfa_backup_codes']:
                return False
            
            backup_codes = user['mfa_backup_codes']
            
            # Hash the provided code and check if it exists
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            if code_hash not in backup_codes:
                return False
            
            # Remove the used code
            backup_codes.remove(code_hash)
            
            await conn.execute("""
                UPDATE users
                SET mfa_backup_codes = $1
                WHERE user_id = $2
            """, backup_codes, user_id)
            
            return True
        finally:
            await release_db(conn)

# ============================================================================
# REFRESH TOKEN OPERATIONS
# ============================================================================

class RefreshTokenDatabase:
    """Database operations for refresh tokens"""
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash token using SHA256"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    @staticmethod
    async def store_refresh_token(
        user_id: str,
        token: str,
        expires_at: datetime,
        device_name: Optional[str] = None,
        device_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Store refresh token in database"""
        conn = await get_db()
        try:
            token_hash = RefreshTokenDatabase.hash_token(token)
            
            result = await conn.fetchrow("""
                INSERT INTO refresh_tokens 
                (user_id, token_hash, expires_at, device_name, device_type, ip_address, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING token_id
            """, user_id, token_hash, expires_at, device_name, device_type, ip_address, user_agent)
            
            return str(result['token_id'])
        finally:
            await release_db(conn)
    
    @staticmethod
    async def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify refresh token and return associated user"""
        conn = await get_db()
        try:
            token_hash = RefreshTokenDatabase.hash_token(token)
            
            result = await conn.fetchrow("""
                SELECT rt.token_id, rt.user_id, rt.expires_at, rt.is_revoked,
                       u.username, u.email, u.role
                FROM refresh_tokens rt
                JOIN users u ON rt.user_id = u.user_id
                WHERE rt.token_hash = $1
                AND rt.is_revoked = FALSE
                AND rt.expires_at > $2
            """, token_hash, datetime.utcnow())
            
            if result:
                # Update last_used_at
                await conn.execute("""
                    UPDATE refresh_tokens
                    SET last_used_at = $1
                    WHERE token_id = $2
                """, datetime.utcnow(), result['token_id'])
            
            return dict(result) if result else None
        finally:
            await release_db(conn)
    
    @staticmethod
    async def revoke_refresh_token(token: str, reason: str = "User logout"):
        """Revoke a refresh token"""
        conn = await get_db()
        try:
            token_hash = RefreshTokenDatabase.hash_token(token)
            
            await conn.execute("""
                UPDATE refresh_tokens
                SET is_revoked = TRUE,
                    revoked_at = $1,
                    revoked_reason = $2
                WHERE token_hash = $3
            """, datetime.utcnow(), reason, token_hash)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def revoke_all_user_tokens(user_id: str, reason: str = "Logout all devices"):
        """Revoke all refresh tokens for a user"""
        conn = await get_db()
        try:
            await conn.execute("""
                UPDATE refresh_tokens
                SET is_revoked = TRUE,
                    revoked_at = $1,
                    revoked_reason = $2
                WHERE user_id = $3
                AND is_revoked = FALSE
            """, datetime.utcnow(), reason, user_id)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def cleanup_expired_tokens() -> int:
        """Clean up expired tokens"""
        conn = await get_db()
        try:
            result = await conn.execute("""
                DELETE FROM refresh_tokens
                WHERE expires_at < $1
                AND is_revoked = FALSE
            """, datetime.utcnow())
            
            return int(result.split()[-1])  # Extract count from "DELETE n"
        finally:
            await release_db(conn)

# ============================================================================
# AUDIT LOG OPERATIONS
# ============================================================================

class AuditLogDatabase:
    """Database operations for audit logs"""
    
    @staticmethod
    async def log_action(
        user_id: Optional[str],
        username: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an action to audit log"""
        conn = await get_db()
        try:
            await conn.execute("""
                INSERT INTO audit_logs 
                (user_id, username, action, resource_type, resource_id, endpoint,
                 method, status_code, ip_address, user_agent, success, error_message, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, user_id, username, action, resource_type, resource_id, endpoint,
                method, status_code, ip_address, user_agent, success, error_message, metadata or {})
        finally:
            await release_db(conn)
    
    @staticmethod
    async def get_user_audit_logs(
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get audit logs for a user"""
        conn = await get_db()
        try:
            rows = await conn.fetch("""
                SELECT * FROM audit_logs
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """, user_id, limit, offset)
            
            return [dict(row) for row in rows]
        finally:
            await release_db(conn)
    
    @staticmethod
    async def cleanup_old_logs(days: int = 90) -> int:
        """Clean up old audit logs"""
        conn = await get_db()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = await conn.execute("""
                DELETE FROM audit_logs
                WHERE created_at < $1
            """, cutoff_date)
            
            return int(result.split()[-1])
        finally:
            await release_db(conn)

# ============================================================================
# MFA ATTEMPTS OPERATIONS
# ============================================================================

class MFAAttemptsDatabase:
    """Database operations for MFA attempts"""
    
    @staticmethod
    async def log_mfa_attempt(
        user_id: str,
        code_entered: str,
        success: bool,
        ip_address: Optional[str] = None
    ):
        """Log an MFA attempt"""
        conn = await get_db()
        try:
            await conn.execute("""
                INSERT INTO mfa_attempts (user_id, code_entered, success, ip_address)
                VALUES ($1, $2, $3, $4)
            """, user_id, code_entered, success, ip_address)
        finally:
            await release_db(conn)
    
    @staticmethod
    async def get_recent_failed_attempts(user_id: str, minutes: int = 15) -> int:
        """Get count of recent failed MFA attempts"""
        conn = await get_db()
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
            result = await conn.fetchrow("""
                SELECT COUNT(*) as count
                FROM mfa_attempts
                WHERE user_id = $1
                AND success = FALSE
                AND created_at > $2
            """, user_id, cutoff_time)
            
            return result['count'] if result else 0
        finally:
            await release_db(conn)

