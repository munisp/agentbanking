"""
Router for mfa service
Auto-extracted from main.py for unified gateway registration

WARNING (mockware remediation): this is an auto-generated stub artifact. The
REAL MFA service (TOTP/SMS/email enroll/challenge/verify) is implemented in
services/mfa/main.py. This stub defines NO endpoints and must never be
registered in any gateway: if login/token/MFA routes are ever needed here,
they must proxy the real implementation in main.py - a stub that returns
success on authentication endpoints is an auth bypass.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/mfa", tags=["mfa"])

# Intentionally no routes. Do not add ok-fabricating endpoints here.
