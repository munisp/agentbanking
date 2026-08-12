"""
KYC Document Verifier — Sprint 78
Automated document verification for agent onboarding
Supports: NIN, BVN, International Passport, Driver's License, Voter's Card

Verification model:
  - Local checks are FORMAT checks only (regex/length). They can never mark
    a document "verified".
  - "verified" requires confirmation from the identity registry
    (IDENTITY_REGISTRY_URL). Without a configured registry, documents stay
    "format_valid" and KYC levels are NOT upgraded.
"""
import json
import time
import hashlib
import re
import os
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional
from enum import Enum

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

logger = logging.getLogger(__name__)

# Identity registry used to actually confirm documents (NIMC/NIBSS/etc).
# When unset, no document can reach "verified" status.
IDENTITY_REGISTRY_URL = os.getenv("IDENTITY_REGISTRY_URL", "")


class DocumentType(Enum):
    NIN = "nin"
    BVN = "bvn"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    VOTERS_CARD = "voters_card"
    UTILITY_BILL = "utility_bill"
    CAC_CERTIFICATE = "cac_certificate"

class VerificationStatus(Enum):
    PENDING = "pending"
    FORMAT_VALID = "format_valid"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    MANUAL_REVIEW = "manual_review"

@dataclass
class KYCDocument:
    doc_id: str
    agent_id: str
    doc_type: str
    doc_number: str
    full_name: str
    date_of_birth: str
    issue_date: str
    expiry_date: Optional[str]
    issuing_authority: str
    country: str
    status: str = "pending"
    confidence_score: float = 0.0
    verification_notes: List[str] = field(default_factory=list)
    verified_at: Optional[float] = None
    submitted_at: float = field(default_factory=time.time)

@dataclass
class KYCProfile:
    agent_id: str
    agent_name: str
    kyc_level: int  # 0=none, 1=basic, 2=enhanced, 3=full
    documents: List[KYCDocument] = field(default_factory=list)
    overall_status: str = "incomplete"
    risk_score: float = 0.0
    last_reviewed: Optional[float] = None

class DocumentValidator:
    """FORMAT validation only. A passing regex means the number is shaped
    correctly — it says nothing about whether the document exists or belongs
    to anyone."""
    NIN_PATTERN = re.compile(r"^\d{11}$")
    BVN_PATTERN = re.compile(r"^\d{11}$")
    PASSPORT_PATTERN = re.compile(r"^[A-Z]\d{8}$")

    @staticmethod
    def validate_nin(number: str) -> tuple:
        if DocumentValidator.NIN_PATTERN.match(number):
            return (True, 0.0, "NIN format valid (11 digits); registry confirmation required for verification")
        return (False, 0.0, "Invalid NIN format (expected 11 digits)")

    @staticmethod
    def validate_bvn(number: str) -> tuple:
        if DocumentValidator.BVN_PATTERN.match(number):
            return (True, 0.0, "BVN format valid (11 digits); registry confirmation required for verification")
        return (False, 0.0, "Invalid BVN format (expected 11 digits)")

    @staticmethod
    def validate_passport(number: str) -> tuple:
        if DocumentValidator.PASSPORT_PATTERN.match(number):
            return (True, 0.0, "Passport format valid; issuing-authority confirmation required for verification")
        return (False, 0.0, "Invalid passport format (expected letter + 8 digits)")

    @staticmethod
    def validate(doc_type: str, number: str) -> tuple:
        validators = {
            "nin": DocumentValidator.validate_nin,
            "bvn": DocumentValidator.validate_bvn,
            "passport": DocumentValidator.validate_passport,
        }
        validator = validators.get(doc_type)
        if validator:
            return validator(number)
        # Fail closed: unknown document types are rejected, never auto-accepted.
        return (False, 0.0, f"Unsupported document type '{doc_type}'; rejected (manual intake required)")

class KYCEngine:
    REQUIRED_DOCS = {
        1: ["nin"],  # Basic KYC
        2: ["nin", "bvn"],  # Enhanced KYC
        3: ["nin", "bvn", "utility_bill", "cac_certificate"],  # Full KYC
    }

    def __init__(self):
        self.profiles: Dict[str, KYCProfile] = {}
        self.documents: Dict[str, KYCDocument] = {}
        self._seed_data()

    def _seed_data(self):
        samples = [
            ("AGT-001", "Adebayo Okonkwo", [
                ("nin", "12345678901", "Adebayo Okonkwo", "1985-03-15", "2020-01-01", None, "NIMC", "NG"),
                ("bvn", "22345678901", "Adebayo Okonkwo", "1985-03-15", "2018-06-01", None, "CBN", "NG"),
            ]),
            ("AGT-002", "Fatima Bello", [
                ("nin", "98765432101", "Fatima Bello", "1990-07-22", "2021-03-15", None, "NIMC", "NG"),
            ]),
            ("AGT-003", "James Mwangi", [
                ("passport", "A12345678", "James Mwangi", "1988-11-10", "2022-01-01", "2032-01-01", "DCI Kenya", "KE"),
            ]),
        ]
        for agent_id, name, docs in samples:
            profile = KYCProfile(agent_id=agent_id, agent_name=name)
            for doc_type, number, full_name, dob, issue, expiry, authority, country in docs:
                doc = self.submit_document(agent_id, doc_type, number, full_name, dob, issue, expiry, authority, country)
                profile.documents.append(doc)
            self._update_profile_status(profile)
            self.profiles[agent_id] = profile

    def _confirm_with_registry(self, doc_type: str, number: str, full_name: str) -> tuple:
        """Confirm the document with the identity registry.

        Returns (verified, note). Any registry failure or absence means NOT
        verified — never a fabricated confirmation.
        """
        if not IDENTITY_REGISTRY_URL:
            return (False, "No identity registry configured (IDENTITY_REGISTRY_URL); "
                           "document remains format_valid only")
        try:
            payload = json.dumps({
                "doc_type": doc_type,
                "doc_number": number,
                "full_name": full_name,
            }).encode()
            req = urllib.request.Request(
                f"{IDENTITY_REGISTRY_URL.rstrip('/')}/verify",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if data.get("verified"):
                return (True, "Identity registry confirmed document")
            return (False, f"Identity registry did not confirm document: "
                           f"{data.get('reason', 'no match')}")
        except Exception as e:
            return (False, f"Identity registry confirmation unavailable: {e}")

    def submit_document(self, agent_id, doc_type, number, full_name, dob, issue_date, expiry_date, authority, country):
        doc_id = hashlib.sha256(f"{agent_id}{doc_type}{number}".encode()).hexdigest()[:12]
        valid, confidence, note = DocumentValidator.validate(doc_type, number)
        notes = [note]
        status = "format_valid" if valid else "rejected"
        verified_at = None
        confidence_score = 0.0

        if valid:
            # "verified" requires real registry confirmation.
            registry_verified, registry_note = self._confirm_with_registry(doc_type, number, full_name)
            notes.append(registry_note)
            if registry_verified:
                status = "verified"
                verified_at = time.time()
                confidence_score = confidence

        doc = KYCDocument(
            doc_id=f"DOC-{doc_id.upper()}",
            agent_id=agent_id,
            doc_type=doc_type,
            doc_number=number,
            full_name=full_name,
            date_of_birth=dob,
            issue_date=issue_date,
            expiry_date=expiry_date,
            issuing_authority=authority,
            country=country,
            status=status,
            confidence_score=confidence_score,
            verification_notes=notes,
            verified_at=verified_at,
        )
        self.documents[doc.doc_id] = doc
        return doc

    def _update_profile_status(self, profile: KYCProfile):
        # Only registry-verified documents count toward KYC level upgrades.
        verified_types = {d.doc_type for d in profile.documents if d.status == "verified"}
        for level in [3, 2, 1]:
            required = set(self.REQUIRED_DOCS[level])
            if required.issubset(verified_types):
                profile.kyc_level = level
                profile.overall_status = "complete" if level >= 2 else "basic"
                break
        else:
            profile.kyc_level = 0
            profile.overall_status = "incomplete"
        profile.risk_score = max(0, 100 - profile.kyc_level * 25 - len(verified_types) * 10)
        profile.last_reviewed = time.time()

    def get_profile(self, agent_id: str) -> Optional[KYCProfile]:
        return self.profiles.get(agent_id)

    def get_all_profiles(self) -> List[KYCProfile]:
        return list(self.profiles.values())

def main():
    engine = KYCEngine()
    print(f"[kyc-document-verifier] Starting with {len(engine.profiles)} agent profiles")
    for profile in engine.get_all_profiles():
        print(f"  {profile.agent_id} ({profile.agent_name}): KYC Level {profile.kyc_level}, Status: {profile.overall_status}, Risk: {profile.risk_score}")
        for doc in profile.documents:
            print(f"    - {doc.doc_type}: {doc.status} (confidence: {doc.confidence_score}%)")
    print(f"[kyc-document-verifier] Total documents: {len(engine.documents)}")

if __name__ == "__main__":
    main()
