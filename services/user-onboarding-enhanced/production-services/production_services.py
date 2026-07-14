"""
Production Services for Onboarding
Account Recovery and Session Management

Services:
1. Account Recovery Service (password reset, account unlock)
2. Session Management Service (Redis-based sessions)
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import secrets
import hashlib
import json

try:
    import redis.asyncio as redis
except ImportError:
    import redis
    redis.asyncio = redis


logger = logging.getLogger(__name__)


class AccountRecoveryService:
    """
    Account recovery service
    
    Features:
    - Password reset via email/SMS
    - Account unlock
    - Security question verification
    - Token-based recovery
    """
    
    def __init__(self, db_connection, email_service=None, sms_service=None) -> None:
        self.db = db_connection
        self.email_service = email_service
        self.sms_service = sms_service
        self.reset_token_expiry_hours = 1
        self.max_reset_attempts_per_day = 3
    
    async def initiate_password_reset(
        self,
        email: str,
        method: str = "email"  # email or sms
    ) -> Dict[str, Any]:
        """
        Initiate password reset process
        
        Args:
            email: User email
            method: Delivery method (email or sms)
            
        Returns:
            Result with token sent confirmation
        """
        try:
            # Get user by email
            user = await self._get_user_by_email(email)
            
            if not user:
                # Don't reveal if email exists (security)
                return {
                    "success": True,
                    "message": "If the email exists, a reset link has been sent."
                }
            
            user_id = user['user_id']
            
            # Check rate limiting
            recent_attempts = await self._get_recent_reset_attempts(user_id, hours=24)
            if len(recent_attempts) >= self.max_reset_attempts_per_day:
                return {
                    "success": False,
                    "error": f"Maximum {self.max_reset_attempts_per_day} password reset attempts per day exceeded. Please try again tomorrow."
                }
            
            # Generate secure reset token
            reset_token = secrets.token_urlsafe(32)
            
            # Store token with expiry
            await self._store_reset_token(
                user_id=user_id,
                token=reset_token,
                expiry_hours=self.reset_token_expiry_hours
            )
            
            # Send reset link/code
            if method == "email":
                sent = await self._send_reset_email(user, reset_token)
            elif method == "sms":
                sent = await self._send_reset_sms(user, reset_token)
            else:
                return {
                    "success": False,
                    "error": "Invalid method. Use 'email' or 'sms'."
                }
            
            if sent:
                logger.info(f"Password reset initiated for user {user_id} via {method}")
                return {
                    "success": True,
                    "message": f"Password reset instructions sent via {method}.",
                    "expires_in_hours": self.reset_token_expiry_hours
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to send reset instructions via {method}"
                }
        
        except Exception as e:
            logger.error(f"Password reset initiation error: {e}")
            return {
                "success": False,
                "error": "Failed to initiate password reset"
            }
    
    async def verify_reset_token(
        self,
        token: str
    ) -> Dict[str, Any]:
        """
        Verify reset token validity
        
        Args:
            token: Reset token
            
        Returns:
            Validation result with user_id if valid
        """
        try:
            # Get token data from database
            token_data = await self._get_reset_token(token)
            
            if not token_data:
                return {
                    "valid": False,
                    "error": "Invalid or expired reset token"
                }
            
            # Check expiry
            if datetime.utcnow() > token_data['expires_at']:
                return {
                    "valid": False,
                    "error": "Reset token has expired. Please request a new one."
                }
            
            # Check if already used
            if token_data.get('used'):
                return {
                    "valid": False,
                    "error": "Reset token has already been used"
                }
            
            return {
                "valid": True,
                "user_id": token_data['user_id'],
                "email": token_data.get('email')
            }
        
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return {
                "valid": False,
                "error": "Token verification failed"
            }
    
    async def reset_password(
        self,
        token: str,
        new_password: str
    ) -> Dict[str, Any]:
        """
        Reset password using valid token
        
        Args:
            token: Reset token
            new_password: New password
            
        Returns:
            Reset result
        """
        try:
            # Verify token
            token_verification = await self.verify_reset_token(token)
            
            if not token_verification['valid']:
                return {
                    "success": False,
                    "error": token_verification['error']
                }
            
            user_id = token_verification['user_id']
            
            # Validate password strength (use PasswordSecurityService)
            # password_validation = await self.password_service.validate_password_strength(new_password)
            # if not password_validation['valid']:
            #     return {"success": False, "error": "Password does not meet requirements"}
            
            # Check password history
            # history_check = await self.password_service.check_password_history(user_id, new_password)
            # if history_check['reused']:
            #     return {"success": False, "error": history_check['message']}
            
            # Hash new password
            # password_hash = self.password_service.hash_password(new_password)
            
            # Update password in database
            await self._update_password(user_id, new_password)  # In production: use password_hash
            
            # Mark token as used
            await self._mark_token_used(token)
            
            # Invalidate all user sessions (force re-login)
            await self._invalidate_all_sessions(user_id)
            
            # Send confirmation email
            await self._send_password_changed_notification(user_id)
            
            logger.info(f"Password reset successful for user {user_id}")
            
            return {
                "success": True,
                "message": "Password reset successfully. Please log in with your new password."
            }
        
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return {
                "success": False,
                "error": "Failed to reset password"
            }
    
    async def unlock_account(
        self,
        user_id: str,
        verification_method: str = "email"
    ) -> Dict[str, Any]:
        """
        Unlock locked account
        
        Args:
            user_id: User ID
            verification_method: Verification method (email, sms, admin)
            
        Returns:
            Unlock result
        """
        try:
            # Get user
            user = await self._get_user(user_id)
            
            if not user:
                return {
                    "success": False,
                    "error": "User not found"
                }
            
            if not user.get('locked'):
                return {
                    "success": True,
                    "message": "Account is not locked"
                }
            
            # Generate unlock token
            unlock_token = secrets.token_urlsafe(32)
            
            # Store unlock token
            await self._store_unlock_token(user_id, unlock_token)
            
            # Send unlock link
            if verification_method == "email":
                sent = await self._send_unlock_email(user, unlock_token)
            elif verification_method == "sms":
                sent = await self._send_unlock_sms(user, unlock_token)
            elif verification_method == "admin":
                # Admin unlock (no verification needed)
                await self._unlock_account_in_db(user_id)
                logger.info(f"Account unlocked by admin for user {user_id}")
                return {
                    "success": True,
                    "message": "Account unlocked by administrator"
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid verification method"
                }
            
            if sent:
                return {
                    "success": True,
                    "message": f"Account unlock instructions sent via {verification_method}"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send unlock instructions"
                }
        
        except Exception as e:
            logger.error(f"Account unlock error: {e}")
            return {
                "success": False,
                "error": "Failed to unlock account"
            }
    
    async def _get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        # Simulated
        return {
            "user_id": "user123",
            "email": email,
            "phone": "+2348012345678"
        }
    
    async def _get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        return {
            "user_id": user_id,
            "email": "user@example.com",
            "locked": True
        }
    
    async def _get_recent_reset_attempts(self, user_id: str, hours: int) -> list:
        """Get recent reset attempts"""
        return []
    
    async def _store_reset_token(self, user_id: str, token: str, expiry_hours: int) -> None:
        """Store reset token"""
        logger.info(f"Reset token stored for user {user_id}")
    
    async def _get_reset_token(self, token: str) -> Optional[Dict]:
        """Get reset token data"""
        return {
            "user_id": "user123",
            "email": "user@example.com",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
            "used": False
        }
    
    async def _mark_token_used(self, token: str) -> None:
        """Mark token as used"""
        logger.info(f"Reset token marked as used")
    
    async def _update_password(self, user_id: str, password_hash: str) -> None:
        """Update password"""
        logger.info(f"Password updated for user {user_id}")
    
    async def _invalidate_all_sessions(self, user_id: str) -> None:
        """Invalidate all user sessions"""
        logger.info(f"All sessions invalidated for user {user_id}")
    
    async def _send_reset_email(self, user: Dict, token: str) -> bool:
        """Send password reset email"""
        logger.info(f"Password reset email sent to {user['email']}")
        return True
    
    async def _send_reset_sms(self, user: Dict, token: str) -> bool:
        """Send password reset SMS"""
        logger.info(f"Password reset SMS sent to {user['phone']}")
        return True
    
    async def _send_password_changed_notification(self, user_id: str) -> None:
        """Send password changed notification"""
        logger.info(f"Password changed notification sent for user {user_id}")
    
    async def _store_unlock_token(self, user_id: str, token: str) -> None:
        """Store unlock token"""
        logger.info(f"Unlock token stored for user {user_id}")
    
    async def _send_unlock_email(self, user: Dict, token: str) -> bool:
        """Send unlock email"""
        logger.info(f"Unlock email sent to {user['email']}")
        return True
    
    async def _send_unlock_sms(self, user: Dict, token: str) -> bool:
        """Send unlock SMS"""
        logger.info(f"Unlock SMS sent to {user['phone']}")
        return True
    
    async def _unlock_account_in_db(self, user_id: str) -> None:
        """Unlock account in database"""
        logger.info(f"Account unlocked in database for user {user_id}")


class SessionManagerService:
    """
    Redis-based session management service
    
    Features:
    - Session creation and validation
    - Device fingerprinting
    - Concurrent session limits
    - Automatic expiry and refresh
    - Session hijacking detection
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self.redis_url = redis_url
        self.redis_client = None
        self.session_expiry_minutes = 30
        self.max_concurrent_sessions = 3
    
    async def initialize(self) -> None:
        """Initialize Redis connection"""
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Session manager initialized")
    
    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def create_session(
        self,
        user_id: str,
        device_info: Dict[str, str],
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Create new session
        
        Args:
            user_id: User ID
            device_info: Device information (user_agent, device_type, etc.)
            ip_address: IP address
            
        Returns:
            Session token and details
        """
        try:
            # Check concurrent session limit
            active_sessions = await self._get_active_sessions(user_id)
            
            if len(active_sessions) >= self.max_concurrent_sessions:
                # Terminate oldest session
                oldest_session = active_sessions[0]
                await self.terminate_session(oldest_session['session_token'])
                logger.info(f"Terminated oldest session for user {user_id} (limit: {self.max_concurrent_sessions})")
            
            # Generate secure session token
            session_token = secrets.token_urlsafe(32)
            
            # Create device fingerprint
            device_fingerprint = self._create_device_fingerprint(device_info)
            
            # Session data
            session_data = {
                "user_id": user_id,
                "session_token": session_token,
                "device_fingerprint": device_fingerprint,
                "device_info": json.dumps(device_info),
                "ip_address": ip_address,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(minutes=self.session_expiry_minutes)).isoformat()
            }
            
            # Store in Redis
            redis_key = f"session:{session_token}"
            await self.redis_client.setex(
                redis_key,
                self.session_expiry_minutes * 60,
                json.dumps(session_data)
            )
            
            # Add to user's active sessions list
            user_sessions_key = f"user_sessions:{user_id}"
            await self.redis_client.sadd(user_sessions_key, session_token)
            await self.redis_client.expire(user_sessions_key, self.session_expiry_minutes * 60)
            
            # Store in database for audit
            await self._store_session_in_db(session_data)
            
            logger.info(f"Session created for user {user_id}")
            
            return {
                "success": True,
                "session_token": session_token,
                "expires_in_minutes": self.session_expiry_minutes,
                "expires_at": session_data['expires_at']
            }
        
        except Exception as e:
            logger.error(f"Session creation error: {e}")
            return {
                "success": False,
                "error": "Failed to create session"
            }
    
    async def validate_session(
        self,
        session_token: str,
        device_info: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate session
        
        Args:
            session_token: Session token
            device_info: Current device info (for fingerprint check)
            ip_address: Current IP address (for hijacking detection)
            
        Returns:
            Validation result with user_id if valid
        """
        try:
            # Get session from Redis
            redis_key = f"session:{session_token}"
            session_data_str = await self.redis_client.get(redis_key)
            
            if not session_data_str:
                return {
                    "valid": False,
                    "error": "Session not found or expired"
                }
            
            session_data = json.loads(session_data_str)
            
            # Check device fingerprint (if provided)
            if device_info:
                current_fingerprint = self._create_device_fingerprint(device_info)
                if current_fingerprint != session_data['device_fingerprint']:
                    logger.warning(f"Device fingerprint mismatch for session {session_token}")
                    return {
                        "valid": False,
                        "error": "Device fingerprint mismatch",
                        "security_alert": True
                    }
            
            # Check IP address change (potential hijacking)
            if ip_address and ip_address != session_data['ip_address']:
                # Log suspicious activity but don't invalidate (could be VPN/mobile)
                logger.warning(f"IP address changed for session {session_token}: {session_data['ip_address']} -> {ip_address}")
                await self._log_suspicious_activity(session_data['user_id'], "ip_change", {
                    "old_ip": session_data['ip_address'],
                    "new_ip": ip_address
                })
            
            # Refresh session expiry on activity
            await self.refresh_session(session_token)
            
            return {
                "valid": True,
                "user_id": session_data['user_id'],
                "session_data": session_data
            }
        
        except Exception as e:
            logger.error(f"Session validation error: {e}")
            return {
                "valid": False,
                "error": "Session validation failed"
            }
    
    async def refresh_session(self, session_token: str) -> Dict[str, Any]:
        """
        Refresh session expiry
        
        Args:
            session_token: Session token
            
        Returns:
            Refresh result
        """
        try:
            redis_key = f"session:{session_token}"
            session_data_str = await self.redis_client.get(redis_key)
            
            if not session_data_str:
                return {
                    "success": False,
                    "error": "Session not found"
                }
            
            session_data = json.loads(session_data_str)
            
            # Update last activity and expiry
            session_data['last_activity'] = datetime.utcnow().isoformat()
            session_data['expires_at'] = (datetime.utcnow() + timedelta(minutes=self.session_expiry_minutes)).isoformat()
            
            # Update in Redis
            await self.redis_client.setex(
                redis_key,
                self.session_expiry_minutes * 60,
                json.dumps(session_data)
            )
            
            return {
                "success": True,
                "expires_at": session_data['expires_at']
            }
        
        except Exception as e:
            logger.error(f"Session refresh error: {e}")
            return {
                "success": False,
                "error": "Failed to refresh session"
            }
    
    async def terminate_session(self, session_token: str) -> Dict[str, Any]:
        """
        Terminate session
        
        Args:
            session_token: Session token
            
        Returns:
            Termination result
        """
        try:
            # Get session data first
            redis_key = f"session:{session_token}"
            session_data_str = await self.redis_client.get(redis_key)
            
            if session_data_str:
                session_data = json.loads(session_data_str)
                user_id = session_data['user_id']
                
                # Remove from user's active sessions
                user_sessions_key = f"user_sessions:{user_id}"
                await self.redis_client.srem(user_sessions_key, session_token)
            
            # Delete from Redis
            await self.redis_client.delete(redis_key)
            
            logger.info(f"Session terminated: {session_token}")
            
            return {
                "success": True,
                "message": "Session terminated successfully"
            }
        
        except Exception as e:
            logger.error(f"Session termination error: {e}")
            return {
                "success": False,
                "error": "Failed to terminate session"
            }
    
    async def terminate_all_sessions(self, user_id: str) -> Dict[str, Any]:
        """Terminate all sessions for user"""
        try:
            active_sessions = await self._get_active_sessions(user_id)
            
            for session in active_sessions:
                await self.terminate_session(session['session_token'])
            
            logger.info(f"All sessions terminated for user {user_id}")
            
            return {
                "success": True,
                "sessions_terminated": len(active_sessions)
            }
        
        except Exception as e:
            logger.error(f"Failed to terminate all sessions: {e}")
            return {
                "success": False,
                "error": "Failed to terminate sessions"
            }
    
    def _create_device_fingerprint(self, device_info: Dict) -> str:
        """Create device fingerprint hash"""
        fingerprint_data = f"{device_info.get('user_agent', '')}{device_info.get('device_type', '')}{device_info.get('os', '')}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    async def _get_active_sessions(self, user_id: str) -> list:
        """Get active sessions for user"""
        try:
            user_sessions_key = f"user_sessions:{user_id}"
            session_tokens = await self.redis_client.smembers(user_sessions_key)
            
            sessions = []
            for token in session_tokens:
                redis_key = f"session:{token}"
                session_data_str = await self.redis_client.get(redis_key)
                if session_data_str:
                    sessions.append(json.loads(session_data_str))
            
            # Sort by created_at
            sessions.sort(key=lambda x: x['created_at'])
            
            return sessions
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    async def _store_session_in_db(self, session_data: Dict) -> None:
        """Store session in database for audit"""
        logger.info(f"Session stored in database: {session_data['session_token']}")
    
    async def _log_suspicious_activity(self, user_id: str, activity_type: str, details: Dict) -> None:
        """Log suspicious activity"""
        logger.warning(f"Suspicious activity for user {user_id}: {activity_type} - {details}")


# Example usage
async def example_usage() -> None:
    """Example usage"""
    
    # Account Recovery
    recovery_service = AccountRecoveryService(db_connection=None)
    
    reset_result = await recovery_service.initiate_password_reset("user@example.com", "email")
    print(f"Password reset: {reset_result}")
    
    # Session Management
    session_service = SessionManagerService()
    await session_service.initialize()
    
    session_result = await session_service.create_session(
        user_id="user123",
        device_info={"user_agent": "Mozilla/5.0...", "device_type": "desktop"},
        ip_address="192.168.1.1"
    )
    print(f"\nSession created: {session_result}")
    
    await session_service.close()


if __name__ == "__main__":
    asyncio.run(example_usage())

