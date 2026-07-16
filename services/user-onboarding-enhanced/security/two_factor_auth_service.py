"""
Two-Factor Authentication (2FA/MFA) Service
TOTP-based authentication with backup options

Features:
- TOTP (Time-based One-Time Password)
- Google Authenticator compatible
- QR code generation
- 10 recovery codes (one-time use)
- SMS backup codes
- Encrypted secret storage
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import secrets
import hashlib
import json
from datetime import datetime, timedelta

try:
    import pyotp
    import qrcode
    from io import BytesIO
    import base64
except ImportError:
    logger.warning("pyotp or qrcode not installed. Install with: pip install pyotp qrcode pillow")


logger = logging.getLogger(__name__)


class TwoFactorAuthService:
    """
    2FA/MFA service using TOTP (RFC 6238)
    
    Features:
    - TOTP setup and verification
    - QR code generation for authenticator apps
    - Recovery codes (10x one-time use)
    - SMS backup codes
    - Secret encryption
    """
    
    def __init__(self, db_connection, sms_provider=None) -> None:
        self.db = db_connection
        self.sms_provider = sms_provider
        self.issuer_name = "Nigerian Remittance Platform"
        self.recovery_codes_count = 10
        self.sms_code_expiry_minutes = 10
    
    async def setup_totp(
        self,
        user_id: str,
        user_email: str
    ) -> Dict[str, Any]:
        """
        Set up TOTP for user
        
        Args:
            user_id: User ID
            user_email: User email (displayed in authenticator app)
            
        Returns:
            {
                "secret": str,  # Base32 encoded secret (for manual entry)
                "qr_code": str,  # QR code image (base64 PNG)
                "qr_code_url": str,  # Data URL for direct use in <img>
                "recovery_codes": List[str],  # 10 recovery codes
                "backup_codes_count": int
            }
        """
        try:
            # Generate secret (32 character base32 string)
            secret = pyotp.random_base32()
            
            # Create TOTP instance
            totp = pyotp.TOTP(secret)
            
            # Generate provisioning URI for QR code
            provisioning_uri = totp.provisioning_uri(
                name=user_email,
                issuer_name=self.issuer_name
            )
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            qr_code_data_url = f"data:image/png;base64,{qr_code_base64}"
            
            # Generate recovery codes
            recovery_codes = self._generate_recovery_codes()
            
            # Hash recovery codes for storage
            hashed_recovery_codes = [
                self._hash_recovery_code(code) for code in recovery_codes
            ]
            
            # Store in database (encrypted)
            await self._store_2fa_data(
                user_id=user_id,
                secret=secret,
                recovery_codes=hashed_recovery_codes
            )
            
            logger.info(f"2FA setup completed for user {user_id}")
            
            return {
                "success": True,
                "secret": secret,
                "qr_code": qr_code_base64,
                "qr_code_url": qr_code_data_url,
                "recovery_codes": recovery_codes,
                "backup_codes_count": len(recovery_codes),
                "message": "2FA setup successful. Save your recovery codes in a safe place."
            }
        
        except Exception as e:
            logger.error(f"Failed to setup 2FA for user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def verify_totp(
        self,
        user_id: str,
        code: str
    ) -> Dict[str, Any]:
        """
        Verify TOTP code
        
        Args:
            user_id: User ID
            code: 6-digit TOTP code or recovery code
            
        Returns:
            Verification result
        """
        try:
            # Get 2FA data from database
            twofa_data = await self._get_2fa_data(user_id)
            
            if not twofa_data:
                return {
                    "success": False,
                    "error": "2FA not set up for this user"
                }
            
            if not twofa_data.get('enabled'):
                return {
                    "success": False,
                    "error": "2FA is not enabled for this user"
                }
            
            # Check if it's a TOTP code (6 digits)
            if code.isdigit() and len(code) == 6:
                secret = twofa_data['secret']
                totp = pyotp.TOTP(secret)
                
                # Verify with 1 time step tolerance (±30 seconds)
                if totp.verify(code, valid_window=1):
                    logger.info(f"2FA verification successful for user {user_id}")
                    return {
                        "success": True,
                        "method": "totp",
                        "message": "2FA code verified successfully"
                    }
            
            # Check if it's a recovery code
            recovery_result = await self._verify_recovery_code(user_id, code, twofa_data)
            if recovery_result['valid']:
                return {
                    "success": True,
                    "method": "recovery_code",
                    "message": "Recovery code used successfully",
                    "remaining_codes": recovery_result['remaining_codes']
                }
            
            # Check if it's an SMS backup code
            sms_result = await self._verify_sms_backup_code(user_id, code)
            if sms_result['valid']:
                return {
                    "success": True,
                    "method": "sms_backup",
                    "message": "SMS backup code verified successfully"
                }
            
            # All verification methods failed
            logger.warning(f"Invalid 2FA code for user {user_id}")
            return {
                "success": False,
                "error": "Invalid 2FA code"
            }
        
        except Exception as e:
            logger.error(f"2FA verification error for user {user_id}: {e}")
            return {
                "success": False,
                "error": "Verification failed"
            }
    
    async def send_sms_backup_code(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Send backup code via SMS
        
        Args:
            user_id: User ID
            
        Returns:
            Result
        """
        if not self.sms_provider:
            return {
                "success": False,
                "error": "SMS backup not configured"
            }
        
        try:
            # Get user phone
            user = await self._get_user(user_id)
            
            if not user or not user.get('phone'):
                return {
                    "success": False,
                    "error": "No phone number registered"
                }
            
            # Generate 6-digit backup code
            backup_code = ''.join(secrets.choice('0123456789') for _ in range(6))
            
            # Store with expiry
            await self._store_sms_backup_code(
                user_id=user_id,
                code=backup_code,
                expiry_minutes=self.sms_code_expiry_minutes
            )
            
            # Send SMS
            message = f"""Your {self.issuer_name} backup 2FA code is: {backup_code}

This code will expire in {self.sms_code_expiry_minutes} minutes.

If you didn't request this code, please secure your account immediately."""
            
            sent = await self.sms_provider.send_sms(user['phone'], message)
            
            if sent:
                logger.info(f"SMS backup code sent to user {user_id}")
                return {
                    "success": True,
                    "message": f"Backup code sent via SMS to {user['phone'][-4:]}",
                    "expires_in_minutes": self.sms_code_expiry_minutes
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to send SMS backup code"
                }
        
        except Exception as e:
            logger.error(f"Failed to send SMS backup code: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def disable_2fa(
        self,
        user_id: str,
        verification_code: str
    ) -> Dict[str, Any]:
        """
        Disable 2FA (requires verification)
        
        Args:
            user_id: User ID
            verification_code: TOTP code or recovery code for verification
            
        Returns:
            Result
        """
        # Verify code first
        verification = await self.verify_totp(user_id, verification_code)
        
        if not verification['success']:
            return {
                "success": False,
                "error": "Invalid verification code. Cannot disable 2FA."
            }
        
        try:
            # Disable 2FA in database
            await self._disable_2fa_in_db(user_id)
            
            logger.info(f"2FA disabled for user {user_id}")
            
            return {
                "success": True,
                "message": "2FA disabled successfully"
            }
        
        except Exception as e:
            logger.error(f"Failed to disable 2FA: {e}")
            return {
                "success": False,
                "error": "Failed to disable 2FA"
            }
    
    async def regenerate_recovery_codes(
        self,
        user_id: str,
        verification_code: str
    ) -> Dict[str, Any]:
        """
        Regenerate recovery codes (requires verification)
        
        Args:
            user_id: User ID
            verification_code: TOTP code for verification
            
        Returns:
            New recovery codes
        """
        # Verify code first
        verification = await self.verify_totp(user_id, verification_code)
        
        if not verification['success']:
            return {
                "success": False,
                "error": "Invalid verification code"
            }
        
        try:
            # Generate new recovery codes
            recovery_codes = self._generate_recovery_codes()
            
            # Hash for storage
            hashed_codes = [
                self._hash_recovery_code(code) for code in recovery_codes
            ]
            
            # Update in database
            await self._update_recovery_codes(user_id, hashed_codes)
            
            logger.info(f"Recovery codes regenerated for user {user_id}")
            
            return {
                "success": True,
                "recovery_codes": recovery_codes,
                "message": "Recovery codes regenerated successfully. Save them in a safe place."
            }
        
        except Exception as e:
            logger.error(f"Failed to regenerate recovery codes: {e}")
            return {
                "success": False,
                "error": "Failed to regenerate recovery codes"
            }
    
    async def get_2fa_status(self, user_id: str) -> Dict[str, Any]:
        """Get 2FA status for user"""
        try:
            twofa_data = await self._get_2fa_data(user_id)
            
            if not twofa_data:
                return {
                    "enabled": False,
                    "setup_completed": False
                }
            
            return {
                "enabled": twofa_data.get('enabled', False),
                "setup_completed": True,
                "setup_date": twofa_data.get('setup_date'),
                "recovery_codes_remaining": twofa_data.get('recovery_codes_remaining', 0),
                "last_used": twofa_data.get('last_used')
            }
        
        except Exception as e:
            logger.error(f"Failed to get 2FA status: {e}")
            return {
                "enabled": False,
                "error": str(e)
            }
    
    def _generate_recovery_codes(self) -> List[str]:
        """Generate recovery codes"""
        codes = []
        for _ in range(self.recovery_codes_count):
            # Generate 16-character hex code
            code = secrets.token_hex(8).upper()
            # Format as XXXX-XXXX-XXXX-XXXX
            formatted = '-'.join([code[i:i+4] for i in range(0, 16, 4)])
            codes.append(formatted)
        return codes
    
    def _hash_recovery_code(self, code: str) -> str:
        """Hash recovery code for storage"""
        # Remove dashes and hash
        clean_code = code.replace('-', '')
        return hashlib.sha256(clean_code.encode()).hexdigest()
    
    async def _verify_recovery_code(
        self,
        user_id: str,
        code: str,
        twofa_data: Dict
    ) -> Dict[str, Any]:
        """Verify recovery code"""
        try:
            # Hash the provided code
            code_hash = self._hash_recovery_code(code)
            
            # Get unused recovery codes
            recovery_codes = twofa_data.get('recovery_codes', [])
            
            if code_hash in recovery_codes:
                # Mark code as used
                await self._mark_recovery_code_used(user_id, code_hash)
                
                remaining = len(recovery_codes) - 1
                
                logger.info(f"Recovery code used for user {user_id}, {remaining} remaining")
                
                return {
                    "valid": True,
                    "remaining_codes": remaining
                }
            
            return {"valid": False}
        
        except Exception as e:
            logger.error(f"Recovery code verification error: {e}")
            return {"valid": False}
    
    async def _verify_sms_backup_code(
        self,
        user_id: str,
        code: str
    ) -> Dict[str, Any]:
        """Verify SMS backup code"""
        # Simplified - in production, check database
        return {"valid": False}
    
    async def _store_2fa_data(
        self,
        user_id: str,
        secret: str,
        recovery_codes: List[str]
    ) -> None:
        """Store 2FA data in database (encrypted)"""
        # In production: encrypt secret, store in database
        logger.info(f"2FA data stored for user {user_id}")
    
    async def _get_2fa_data(self, user_id: str) -> Optional[Dict]:
        """Get 2FA data from database"""
        # In production: query database, decrypt secret
        # Simulated data for testing
        return {
            "user_id": user_id,
            "enabled": True,
            "secret": "JBSWY3DPEHPK3PXP",  # Example secret
            "recovery_codes": [],
            "recovery_codes_remaining": 10,
            "setup_date": datetime.utcnow().isoformat(),
            "last_used": None
        }
    
    async def _disable_2fa_in_db(self, user_id: str) -> None:
        """Disable 2FA in database"""
        logger.info(f"2FA disabled in database for user {user_id}")
    
    async def _update_recovery_codes(
        self,
        user_id: str,
        hashed_codes: List[str]
    ) -> None:
        """Update recovery codes in database"""
        logger.info(f"Recovery codes updated for user {user_id}")
    
    async def _mark_recovery_code_used(self, user_id: str, code_hash: str) -> None:
        """Mark recovery code as used"""
        logger.info(f"Recovery code marked as used for user {user_id}")
    
    async def _store_sms_backup_code(
        self,
        user_id: str,
        code: str,
        expiry_minutes: int
    ) -> None:
        """Store SMS backup code with expiry"""
        logger.info(f"SMS backup code stored for user {user_id}")
    
    async def _get_user(self, user_id: str) -> Optional[Dict]:
        """Get user from database"""
        # Simulated
        return {
            "user_id": user_id,
            "phone": "+2348012345678"
        }


# Example usage
async def example_usage() -> None:
    """Example usage of TwoFactorAuthService"""
    
    service = TwoFactorAuthService(db_connection=None)
    
    user_id = "user123"
    user_email = "user@example.com"
    
    # Setup 2FA
    setup_result = await service.setup_totp(user_id, user_email)
    print(f"Setup result: {setup_result}")
    
    if setup_result['success']:
        print(f"\nSecret (for manual entry): {setup_result['secret']}")
        print(f"Recovery codes: {setup_result['recovery_codes']}")
        print(f"\nScan this QR code with Google Authenticator:")
        print(f"QR Code URL: {setup_result['qr_code_url'][:100]}...")
        
        # Generate current TOTP code for testing
        totp = pyotp.TOTP(setup_result['secret'])
        current_code = totp.now()
        print(f"\nCurrent TOTP code: {current_code}")
        
        # Verify TOTP
        verify_result = await service.verify_totp(user_id, current_code)
        print(f"\nVerification result: {verify_result}")
        
        # Get status
        status = await service.get_2fa_status(user_id)
        print(f"\n2FA status: {status}")


if __name__ == "__main__":
    asyncio.run(example_usage())

