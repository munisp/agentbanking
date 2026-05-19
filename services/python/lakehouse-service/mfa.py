"""
Multi-Factor Authentication (MFA) Implementation
Supports TOTP (Time-based One-Time Password) using pyotp
"""

import pyotp
import qrcode
import io
import base64
import hashlib
import secrets
from typing import Optional, List, Tuple
from datetime import datetime

from pydantic import BaseModel

# ============================================================================
# MODELS
# ============================================================================

class MFASetupResponse(BaseModel):
    """Response for MFA setup"""
    secret: str
    qr_code_data_url: str  # Base64 encoded QR code image
    backup_codes: List[str]
    manual_entry_key: str  # For manual entry in authenticator apps

class MFAVerifyRequest(BaseModel):
    """Request to verify MFA code"""
    code: str
    use_backup_code: bool = False

# ============================================================================
# MFA MANAGER
# ============================================================================

class MFAManager:
    """Manager for Multi-Factor Authentication operations"""
    
    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate backup codes for MFA recovery
        Returns list of plain codes and their hashes
        """
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(code)
        return codes
    
    @staticmethod
    def hash_backup_codes(codes: List[str]) -> List[str]:
        """Hash backup codes for storage"""
        return [hashlib.sha256(code.encode()).hexdigest() for code in codes]
    
    @staticmethod
    def format_backup_codes(codes: List[str]) -> List[str]:
        """Format backup codes for display (XXXX-XXXX)"""
        return [f"{code[:4]}-{code[4:]}" for code in codes]
    
    @staticmethod
    def generate_qr_code(
        secret: str,
        username: str,
        issuer: str = "Remittance Platform Lakehouse"
    ) -> str:
        """
        Generate QR code for TOTP setup
        Returns base64-encoded PNG image data URL
        """
        # Create TOTP URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=username,
            issuer_name=issuer
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
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Return as data URL
        return f"data:image/png;base64,{img_base64}"
    
    @staticmethod
    def setup_mfa(username: str, issuer: str = "Remittance Platform Lakehouse") -> MFASetupResponse:
        """
        Set up MFA for a user
        Returns secret, QR code, and backup codes
        """
        # Generate secret
        secret = MFAManager.generate_secret()
        
        # Generate QR code
        qr_code_data_url = MFAManager.generate_qr_code(secret, username, issuer)
        
        # Generate backup codes
        backup_codes = MFAManager.generate_backup_codes(10)
        formatted_codes = MFAManager.format_backup_codes(backup_codes)
        
        # Format secret for manual entry (groups of 4)
        manual_entry_key = ' '.join([secret[i:i+4] for i in range(0, len(secret), 4)])
        
        return MFASetupResponse(
            secret=secret,
            qr_code_data_url=qr_code_data_url,
            backup_codes=formatted_codes,
            manual_entry_key=manual_entry_key
        )
    
    @staticmethod
    def verify_totp_code(secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verify a TOTP code
        
        Args:
            secret: The TOTP secret
            code: The 6-digit code to verify
            valid_window: Number of time steps to check before/after current (default 1 = ±30 seconds)
        
        Returns:
            True if code is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=valid_window)
        except Exception:
            return False
    
    @staticmethod
    def get_current_totp_code(secret: str) -> str:
        """
        Get current TOTP code (for testing/debugging only)
        DO NOT expose this in production API
        """
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    @staticmethod
    def get_time_remaining() -> int:
        """
        Get seconds remaining until next TOTP code
        Useful for UI countdown
        """
        return 30 - (int(datetime.now().timestamp()) % 30)

# ============================================================================
# MFA VERIFICATION WITH RATE LIMITING
# ============================================================================

class MFAVerifier:
    """MFA verification with rate limiting and attempt tracking"""
    
    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
    
    async def verify_code(
        self,
        user_id: str,
        secret: str,
        code: str,
        backup_codes: Optional[List[str]] = None,
        use_backup_code: bool = False,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify MFA code with rate limiting
        
        Returns:
            (success: bool, error_message: Optional[str])
        """
        from database import MFAAttemptsDatabase, UserDatabase
        
        # Check rate limiting
        recent_failed = await MFAAttemptsDatabase.get_recent_failed_attempts(
            user_id,
            self.window_minutes
        )
        
        if recent_failed >= self.max_attempts:
            return False, f"Too many failed attempts. Please try again in {self.window_minutes} minutes."
        
        # Verify code
        success = False
        
        if use_backup_code and backup_codes:
            # Verify backup code
            success = await UserDatabase.use_backup_code(user_id, code)
            if not success:
                await MFAAttemptsDatabase.log_mfa_attempt(user_id, code, False, ip_address)
                return False, "Invalid backup code"
        else:
            # Verify TOTP code
            success = MFAManager.verify_totp_code(secret, code)
            if not success:
                await MFAAttemptsDatabase.log_mfa_attempt(user_id, code, False, ip_address)
                remaining_attempts = self.max_attempts - recent_failed - 1
                return False, f"Invalid code. {remaining_attempts} attempts remaining."
        
        # Log successful attempt
        await MFAAttemptsDatabase.log_mfa_attempt(user_id, code, True, ip_address)
        
        return True, None

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_mfa_setup():
    """Example of setting up MFA for a user"""
    
    # Setup MFA
    username = "admin@example.com"
    mfa_setup = MFAManager.setup_mfa(username)
    
    print("=== MFA Setup ===")
    print(f"Secret: {mfa_setup.secret}")
    print(f"Manual Entry Key: {mfa_setup.manual_entry_key}")
    print(f"\nBackup Codes (save these securely!):")
    for i, code in enumerate(mfa_setup.backup_codes, 1):
        print(f"  {i}. {code}")
    print(f"\nQR Code: {mfa_setup.qr_code_data_url[:50]}...")
    
    # Simulate verification
    print("\n=== Verification ===")
    current_code = MFAManager.get_current_totp_code(mfa_setup.secret)
    print(f"Current TOTP code: {current_code}")
    
    is_valid = MFAManager.verify_totp_code(mfa_setup.secret, current_code)
    print(f"Verification result: {is_valid}")
    
    # Time remaining
    time_remaining = MFAManager.get_time_remaining()
    print(f"Time remaining: {time_remaining} seconds")

if __name__ == "__main__":
    example_mfa_setup()

