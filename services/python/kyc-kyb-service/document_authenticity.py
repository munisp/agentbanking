"""
Document Authenticity Service
Advanced document verification with MRZ validation, barcode/QR decoding,
font consistency checking, compression artifact analysis, and cross-field validation.

Integrates with: Redis for caching, Kafka for events, Lakehouse for analytics
"""

import os
import re
import json
import logging
import secrets
import hashlib
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import base64

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class DocumentType(str, Enum):
    """Document types"""
    PASSPORT = "passport"
    NATIONAL_ID = "national_id"
    DRIVERS_LICENSE = "drivers_license"
    VOTERS_CARD = "voters_card"
    RESIDENCE_PERMIT = "residence_permit"
    VISA = "visa"
    CAC_CERTIFICATE = "cac_certificate"


class AuthenticityCheckType(str, Enum):
    """Types of authenticity checks"""
    MRZ_VALIDATION = "mrz_validation"
    BARCODE_QR = "barcode_qr"
    FONT_CONSISTENCY = "font_consistency"
    COMPRESSION_ARTIFACTS = "compression_artifacts"
    EDGE_DETECTION = "edge_detection"
    PHOTO_TAMPERING = "photo_tampering"
    CROSS_FIELD_CONSISTENCY = "cross_field_consistency"
    DATE_VALIDITY = "date_validity"
    SECURITY_FEATURES = "security_features"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CheckResult(str, Enum):
    """Check result"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    INCONCLUSIVE = "inconclusive"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MRZData:
    """Parsed MRZ data"""
    document_type: str
    country_code: str
    surname: str
    given_names: str
    document_number: str
    nationality: str
    date_of_birth: str
    sex: str
    expiry_date: str
    personal_number: Optional[str] = None
    check_digits_valid: bool = False
    raw_mrz: str = ""


@dataclass
class BarcodeData:
    """Parsed barcode/QR data"""
    barcode_type: str  # QR, PDF417, Code128, etc.
    raw_data: str
    parsed_fields: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = False


@dataclass
class AuthenticityCheck:
    """Single authenticity check result"""
    check_type: AuthenticityCheckType
    result: CheckResult
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class DocumentAuthenticityResult:
    """Complete document authenticity result"""
    document_id: str
    document_type: DocumentType
    overall_result: CheckResult
    overall_confidence: float
    risk_level: RiskLevel
    checks: List[AuthenticityCheck]
    mrz_data: Optional[MRZData] = None
    barcode_data: Optional[BarcodeData] = None
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# MRZ VALIDATOR
# ============================================================================

class MRZValidator:
    """
    Machine Readable Zone (MRZ) validation
    Supports TD1 (ID cards), TD2 (some IDs), TD3 (passports)
    """
    
    # MRZ character weights for check digit calculation
    WEIGHTS = [7, 3, 1]
    
    # Character values for check digit
    CHAR_VALUES = {
        '<': 0, '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
        '6': 6, '7': 7, '8': 8, '9': 9, 'A': 10, 'B': 11, 'C': 12,
        'D': 13, 'E': 14, 'F': 15, 'G': 16, 'H': 17, 'I': 18, 'J': 19,
        'K': 20, 'L': 21, 'M': 22, 'N': 23, 'O': 24, 'P': 25, 'Q': 26,
        'R': 27, 'S': 28, 'T': 29, 'U': 30, 'V': 31, 'W': 32, 'X': 33,
        'Y': 34, 'Z': 35
    }
    
    def parse_mrz(self, mrz_lines: List[str]) -> Tuple[Optional[MRZData], List[str]]:
        """Parse MRZ and return data with any errors"""
        errors = []
        
        # Clean lines
        lines = [line.strip().upper() for line in mrz_lines if line.strip()]
        
        if len(lines) == 2 and len(lines[0]) == 44:
            # TD3 format (passport)
            return self._parse_td3(lines, errors)
        elif len(lines) == 3 and len(lines[0]) == 30:
            # TD1 format (ID card)
            return self._parse_td1(lines, errors)
        elif len(lines) == 2 and len(lines[0]) == 36:
            # TD2 format
            return self._parse_td2(lines, errors)
        else:
            errors.append(f"Unknown MRZ format: {len(lines)} lines")
            return None, errors
    
    def _parse_td3(self, lines: List[str], errors: List[str]) -> Tuple[Optional[MRZData], List[str]]:
        """Parse TD3 (passport) MRZ"""
        line1, line2 = lines
        
        # Line 1: P<COUNTRY_CODE<SURNAME<<GIVEN_NAMES
        doc_type = line1[0:2].replace('<', '')
        country_code = line1[2:5]
        names = line1[5:].split('<<')
        surname = names[0].replace('<', ' ').strip()
        given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ""
        
        # Line 2: Document number, nationality, DOB, sex, expiry, personal number
        doc_number = line2[0:9].replace('<', '')
        doc_check = line2[9]
        nationality = line2[10:13]
        dob = line2[13:19]
        dob_check = line2[19]
        sex = line2[20]
        expiry = line2[21:27]
        expiry_check = line2[27]
        personal_number = line2[28:42].replace('<', '')
        personal_check = line2[42]
        composite_check = line2[43]
        
        # Validate check digits
        check_digits_valid = True
        
        if not self._validate_check_digit(line2[0:9], doc_check):
            errors.append("Document number check digit invalid")
            check_digits_valid = False
        
        if not self._validate_check_digit(dob, dob_check):
            errors.append("Date of birth check digit invalid")
            check_digits_valid = False
        
        if not self._validate_check_digit(expiry, expiry_check):
            errors.append("Expiry date check digit invalid")
            check_digits_valid = False
        
        # Composite check
        composite_data = line2[0:10] + line2[13:20] + line2[21:43]
        if not self._validate_check_digit(composite_data, composite_check):
            errors.append("Composite check digit invalid")
            check_digits_valid = False
        
        return MRZData(
            document_type=doc_type,
            country_code=country_code,
            surname=surname,
            given_names=given_names,
            document_number=doc_number,
            nationality=nationality,
            date_of_birth=self._format_date(dob),
            sex=sex,
            expiry_date=self._format_date(expiry),
            personal_number=personal_number if personal_number else None,
            check_digits_valid=check_digits_valid,
            raw_mrz="\n".join(lines)
        ), errors
    
    def _parse_td1(self, lines: List[str], errors: List[str]) -> Tuple[Optional[MRZData], List[str]]:
        """Parse TD1 (ID card) MRZ"""
        line1, line2, line3 = lines
        
        # Line 1: Document type, country, document number
        doc_type = line1[0:2].replace('<', '')
        country_code = line1[2:5]
        doc_number = line1[5:14].replace('<', '')
        doc_check = line1[14]
        
        # Line 2: DOB, sex, expiry, nationality
        dob = line2[0:6]
        dob_check = line2[6]
        sex = line2[7]
        expiry = line2[8:14]
        expiry_check = line2[14]
        nationality = line2[15:18]
        
        # Line 3: Names
        names = line3.split('<<')
        surname = names[0].replace('<', ' ').strip()
        given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ""
        
        # Validate check digits
        check_digits_valid = True
        
        if not self._validate_check_digit(line1[5:14], doc_check):
            errors.append("Document number check digit invalid")
            check_digits_valid = False
        
        if not self._validate_check_digit(dob, dob_check):
            errors.append("Date of birth check digit invalid")
            check_digits_valid = False
        
        if not self._validate_check_digit(expiry, expiry_check):
            errors.append("Expiry date check digit invalid")
            check_digits_valid = False
        
        return MRZData(
            document_type=doc_type,
            country_code=country_code,
            surname=surname,
            given_names=given_names,
            document_number=doc_number,
            nationality=nationality,
            date_of_birth=self._format_date(dob),
            sex=sex,
            expiry_date=self._format_date(expiry),
            check_digits_valid=check_digits_valid,
            raw_mrz="\n".join(lines)
        ), errors
    
    def _parse_td2(self, lines: List[str], errors: List[str]) -> Tuple[Optional[MRZData], List[str]]:
        """Parse TD2 MRZ"""
        line1, line2 = lines
        
        # Similar to TD3 but shorter
        doc_type = line1[0:2].replace('<', '')
        country_code = line1[2:5]
        names = line1[5:].split('<<')
        surname = names[0].replace('<', ' ').strip()
        given_names = names[1].replace('<', ' ').strip() if len(names) > 1 else ""
        
        doc_number = line2[0:9].replace('<', '')
        doc_check = line2[9]
        nationality = line2[10:13]
        dob = line2[13:19]
        dob_check = line2[19]
        sex = line2[20]
        expiry = line2[21:27]
        expiry_check = line2[27]
        
        check_digits_valid = True
        
        if not self._validate_check_digit(line2[0:9], doc_check):
            errors.append("Document number check digit invalid")
            check_digits_valid = False
        
        return MRZData(
            document_type=doc_type,
            country_code=country_code,
            surname=surname,
            given_names=given_names,
            document_number=doc_number,
            nationality=nationality,
            date_of_birth=self._format_date(dob),
            sex=sex,
            expiry_date=self._format_date(expiry),
            check_digits_valid=check_digits_valid,
            raw_mrz="\n".join(lines)
        ), errors
    
    def _validate_check_digit(self, data: str, check_digit: str) -> bool:
        """Validate MRZ check digit"""
        if check_digit == '<':
            check_digit = '0'
        
        try:
            expected = int(check_digit)
        except ValueError:
            return False
        
        total = 0
        for i, char in enumerate(data):
            value = self.CHAR_VALUES.get(char, 0)
            weight = self.WEIGHTS[i % 3]
            total += value * weight
        
        return (total % 10) == expected
    
    def _format_date(self, date_str: str) -> str:
        """Format MRZ date (YYMMDD) to ISO format"""
        if len(date_str) != 6:
            return date_str
        
        year = int(date_str[0:2])
        month = date_str[2:4]
        day = date_str[4:6]
        
        # Determine century
        current_year = datetime.now().year % 100
        if year > current_year + 10:
            year += 1900
        else:
            year += 2000
        
        return f"{year}-{month}-{day}"


# ============================================================================
# BARCODE/QR DECODER
# ============================================================================

class BarcodeQRDecoder:
    """
    Barcode and QR code decoding for identity documents
    Supports PDF417 (driver's licenses), QR codes, Code128, etc.
    """
    
    def decode_barcode(self, barcode_data: str, barcode_type: str) -> BarcodeData:
        """Decode barcode data"""
        parsed_fields = {}
        is_valid = False
        
        if barcode_type.upper() == "PDF417":
            parsed_fields, is_valid = self._parse_pdf417(barcode_data)
        elif barcode_type.upper() in ["QR", "QRCODE"]:
            parsed_fields, is_valid = self._parse_qr(barcode_data)
        elif barcode_type.upper() == "CODE128":
            parsed_fields, is_valid = self._parse_code128(barcode_data)
        else:
            # Generic parsing
            parsed_fields = {"raw": barcode_data}
            is_valid = len(barcode_data) > 0
        
        return BarcodeData(
            barcode_type=barcode_type,
            raw_data=barcode_data,
            parsed_fields=parsed_fields,
            is_valid=is_valid
        )
    
    def _parse_pdf417(self, data: str) -> Tuple[Dict[str, Any], bool]:
        """Parse PDF417 barcode (common in driver's licenses)"""
        fields = {}
        
        # AAMVA format parsing (US/Canada driver's licenses)
        # Format: @\n followed by field codes
        
        if data.startswith("@"):
            lines = data.split("\n")
            
            for line in lines:
                if len(line) >= 3:
                    code = line[0:3]
                    value = line[3:].strip()
                    
                    # Common AAMVA field codes
                    field_map = {
                        "DAA": "full_name",
                        "DAB": "last_name",
                        "DAC": "first_name",
                        "DAD": "middle_name",
                        "DAG": "street_address",
                        "DAI": "city",
                        "DAJ": "state",
                        "DAK": "postal_code",
                        "DAQ": "license_number",
                        "DBB": "date_of_birth",
                        "DBC": "sex",
                        "DBD": "issue_date",
                        "DBA": "expiry_date",
                        "DAY": "suffix",
                        "DAU": "height",
                        "DAW": "weight",
                        "DAZ": "hair_color",
                        "DCS": "last_name",
                        "DCT": "first_name",
                    }
                    
                    if code in field_map:
                        fields[field_map[code]] = value
        
        is_valid = len(fields) > 0
        
        return fields, is_valid
    
    def _parse_qr(self, data: str) -> Tuple[Dict[str, Any], bool]:
        """Parse QR code data"""
        fields = {}
        
        # Try JSON parsing
        try:
            fields = json.loads(data)
            return fields, True
        except json.JSONDecodeError:
            pass
        
        # Try URL parsing
        if data.startswith("http"):
            fields = {"url": data}
            return fields, True
        
        # Try key-value parsing
        if "=" in data:
            for pair in data.split("&"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    fields[key] = value
            return fields, len(fields) > 0
        
        # Raw data
        fields = {"raw": data}
        return fields, len(data) > 0
    
    def _parse_code128(self, data: str) -> Tuple[Dict[str, Any], bool]:
        """Parse Code128 barcode"""
        # Code128 is typically just alphanumeric data
        fields = {"value": data}
        return fields, len(data) > 0


# ============================================================================
# FONT CONSISTENCY ANALYZER
# ============================================================================

class FontConsistencyAnalyzer:
    """
    Analyze font consistency across document text
    Detects potential text alterations
    """
    
    def analyze_fonts(self, text_regions: List[Dict[str, Any]]) -> AuthenticityCheck:
        """Analyze font consistency across text regions"""
        issues = []
        details = {}
        
        if not text_regions:
            return AuthenticityCheck(
                check_type=AuthenticityCheckType.FONT_CONSISTENCY,
                result=CheckResult.INCONCLUSIVE,
                confidence=0.0,
                details={"reason": "No text regions provided"},
                issues=["No text regions to analyze"]
            )
        
        # Extract font characteristics
        fonts = []
        for region in text_regions:
            font_info = {
                "font_family": region.get("font_family", "unknown"),
                "font_size": region.get("font_size", 0),
                "font_weight": region.get("font_weight", "normal"),
                "font_style": region.get("font_style", "normal"),
                "text": region.get("text", ""),
                "position": region.get("position", {})
            }
            fonts.append(font_info)
        
        # Check for font family consistency
        font_families = set(f["font_family"] for f in fonts if f["font_family"] != "unknown")
        if len(font_families) > 2:
            issues.append(f"Multiple font families detected: {font_families}")
        
        # Check for unusual font size variations
        font_sizes = [f["font_size"] for f in fonts if f["font_size"] > 0]
        if font_sizes:
            avg_size = sum(font_sizes) / len(font_sizes)
            size_variance = sum((s - avg_size) ** 2 for s in font_sizes) / len(font_sizes)
            
            if size_variance > 100:  # High variance threshold
                issues.append("Unusual font size variation detected")
            
            details["avg_font_size"] = avg_size
            details["font_size_variance"] = size_variance
        
        # Check for mixed font weights in same field type
        weights = set(f["font_weight"] for f in fonts)
        if len(weights) > 2:
            issues.append("Multiple font weights detected")
        
        # Calculate confidence
        confidence = 1.0 - (len(issues) * 0.2)
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine result
        if len(issues) == 0:
            result = CheckResult.PASS
        elif len(issues) <= 2:
            result = CheckResult.WARNING
        else:
            result = CheckResult.FAIL
        
        details["font_families"] = list(font_families)
        details["font_weights"] = list(weights)
        details["region_count"] = len(text_regions)
        
        return AuthenticityCheck(
            check_type=AuthenticityCheckType.FONT_CONSISTENCY,
            result=result,
            confidence=confidence,
            details=details,
            issues=issues
        )


# ============================================================================
# CROSS-FIELD CONSISTENCY CHECKER
# ============================================================================

class CrossFieldConsistencyChecker:
    """
    Check consistency between different fields on the document
    """
    
    def check_consistency(
        self,
        extracted_fields: Dict[str, Any],
        mrz_data: Optional[MRZData] = None
    ) -> AuthenticityCheck:
        """Check cross-field consistency"""
        issues = []
        details = {}
        
        # Compare MRZ with extracted fields
        if mrz_data:
            # Check name consistency
            if "name" in extracted_fields or "full_name" in extracted_fields:
                extracted_name = extracted_fields.get("name", extracted_fields.get("full_name", "")).upper()
                mrz_name = f"{mrz_data.given_names} {mrz_data.surname}".upper()
                
                if extracted_name and mrz_name:
                    # Simple similarity check
                    if not self._names_match(extracted_name, mrz_name):
                        issues.append(f"Name mismatch: OCR='{extracted_name}' vs MRZ='{mrz_name}'")
                        details["name_mismatch"] = True
            
            # Check document number consistency
            if "document_number" in extracted_fields:
                extracted_num = extracted_fields["document_number"].replace(" ", "").upper()
                mrz_num = mrz_data.document_number.upper()
                
                if extracted_num != mrz_num:
                    issues.append(f"Document number mismatch: OCR='{extracted_num}' vs MRZ='{mrz_num}'")
                    details["document_number_mismatch"] = True
            
            # Check date of birth consistency
            if "date_of_birth" in extracted_fields:
                extracted_dob = self._normalize_date(extracted_fields["date_of_birth"])
                mrz_dob = mrz_data.date_of_birth
                
                if extracted_dob and mrz_dob and extracted_dob != mrz_dob:
                    issues.append(f"DOB mismatch: OCR='{extracted_dob}' vs MRZ='{mrz_dob}'")
                    details["dob_mismatch"] = True
            
            # Check expiry date consistency
            if "expiry_date" in extracted_fields:
                extracted_exp = self._normalize_date(extracted_fields["expiry_date"])
                mrz_exp = mrz_data.expiry_date
                
                if extracted_exp and mrz_exp and extracted_exp != mrz_exp:
                    issues.append(f"Expiry date mismatch: OCR='{extracted_exp}' vs MRZ='{mrz_exp}'")
                    details["expiry_mismatch"] = True
        
        # Check internal field consistency
        if "date_of_birth" in extracted_fields and "issue_date" in extracted_fields:
            dob = self._parse_date(extracted_fields["date_of_birth"])
            issue = self._parse_date(extracted_fields["issue_date"])
            
            if dob and issue:
                age_at_issue = (issue - dob).days / 365.25
                if age_at_issue < 0:
                    issues.append("Issue date before date of birth")
                elif age_at_issue < 16:
                    issues.append(f"Unusually young age at issue: {age_at_issue:.1f} years")
        
        # Check expiry date validity
        if "expiry_date" in extracted_fields:
            expiry = self._parse_date(extracted_fields["expiry_date"])
            if expiry:
                if expiry < date.today():
                    issues.append("Document has expired")
                    details["is_expired"] = True
        
        # Calculate confidence
        confidence = 1.0 - (len(issues) * 0.15)
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine result
        if len(issues) == 0:
            result = CheckResult.PASS
        elif len(issues) <= 2:
            result = CheckResult.WARNING
        else:
            result = CheckResult.FAIL
        
        details["fields_checked"] = list(extracted_fields.keys())
        details["mrz_available"] = mrz_data is not None
        
        return AuthenticityCheck(
            check_type=AuthenticityCheckType.CROSS_FIELD_CONSISTENCY,
            result=result,
            confidence=confidence,
            details=details,
            issues=issues
        )
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two names match (allowing for minor variations)"""
        # Normalize
        n1 = re.sub(r'[^A-Z\s]', '', name1.upper())
        n2 = re.sub(r'[^A-Z\s]', '', name2.upper())
        
        # Exact match
        if n1 == n2:
            return True
        
        # Check if all words from one are in the other
        words1 = set(n1.split())
        words2 = set(n2.split())
        
        common = words1 & words2
        if len(common) >= 2:
            return True
        
        return False
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to YYYY-MM-DD format"""
        if not date_str:
            return None
        
        # Try various formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d %b %Y",
            "%d %B %Y",
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        return date_str
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        normalized = self._normalize_date(date_str)
        if normalized:
            try:
                return datetime.strptime(normalized, "%Y-%m-%d").date()
            except ValueError:
                pass
        return None


# ============================================================================
# DATE VALIDITY CHECKER
# ============================================================================

class DateValidityChecker:
    """
    Check date validity on documents
    """
    
    def check_dates(self, extracted_fields: Dict[str, Any]) -> AuthenticityCheck:
        """Check date validity"""
        issues = []
        details = {}
        today = date.today()
        
        # Check date of birth
        if "date_of_birth" in extracted_fields:
            dob = self._parse_date(extracted_fields["date_of_birth"])
            if dob:
                age = (today - dob).days / 365.25
                details["age"] = round(age, 1)
                
                if age < 0:
                    issues.append("Date of birth is in the future")
                elif age > 120:
                    issues.append(f"Unrealistic age: {age:.0f} years")
                elif age < 16:
                    issues.append(f"Subject appears to be a minor: {age:.0f} years")
        
        # Check issue date
        if "issue_date" in extracted_fields:
            issue = self._parse_date(extracted_fields["issue_date"])
            if issue:
                if issue > today:
                    issues.append("Issue date is in the future")
                
                days_since_issue = (today - issue).days
                details["days_since_issue"] = days_since_issue
        
        # Check expiry date
        if "expiry_date" in extracted_fields:
            expiry = self._parse_date(extracted_fields["expiry_date"])
            if expiry:
                if expiry < today:
                    issues.append("Document has expired")
                    details["is_expired"] = True
                    details["days_expired"] = (today - expiry).days
                else:
                    details["days_until_expiry"] = (expiry - today).days
                    
                    if (expiry - today).days < 30:
                        issues.append("Document expires within 30 days")
        
        # Check issue-expiry relationship
        if "issue_date" in extracted_fields and "expiry_date" in extracted_fields:
            issue = self._parse_date(extracted_fields["issue_date"])
            expiry = self._parse_date(extracted_fields["expiry_date"])
            
            if issue and expiry:
                validity_years = (expiry - issue).days / 365.25
                details["validity_period_years"] = round(validity_years, 1)
                
                if expiry < issue:
                    issues.append("Expiry date is before issue date")
                elif validity_years > 15:
                    issues.append(f"Unusually long validity period: {validity_years:.0f} years")
        
        # Calculate confidence
        confidence = 1.0 - (len(issues) * 0.2)
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine result
        if len(issues) == 0:
            result = CheckResult.PASS
        elif any("expired" in i.lower() or "future" in i.lower() for i in issues):
            result = CheckResult.FAIL
        else:
            result = CheckResult.WARNING
        
        return AuthenticityCheck(
            check_type=AuthenticityCheckType.DATE_VALIDITY,
            result=result,
            confidence=confidence,
            details=details,
            issues=issues
        )
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string"""
        if not date_str:
            return None
        
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None


# ============================================================================
# DOCUMENT AUTHENTICITY SERVICE
# ============================================================================

class DocumentAuthenticityService:
    """
    Main document authenticity service
    Combines all verification methods
    """
    
    def __init__(self):
        self._mrz_validator = MRZValidator()
        self._barcode_decoder = BarcodeQRDecoder()
        self._font_analyzer = FontConsistencyAnalyzer()
        self._cross_field_checker = CrossFieldConsistencyChecker()
        self._date_checker = DateValidityChecker()
        
        self._results: Dict[str, DocumentAuthenticityResult] = {}
    
    async def verify_document(
        self,
        document_type: DocumentType,
        extracted_fields: Dict[str, Any],
        mrz_lines: Optional[List[str]] = None,
        barcode_data: Optional[str] = None,
        barcode_type: Optional[str] = None,
        text_regions: Optional[List[Dict[str, Any]]] = None,
        image_analysis: Optional[Dict[str, Any]] = None
    ) -> DocumentAuthenticityResult:
        """Perform comprehensive document authenticity verification"""
        document_id = secrets.token_hex(16)
        checks = []
        mrz_data = None
        parsed_barcode = None
        
        # MRZ Validation
        if mrz_lines:
            mrz_data, mrz_errors = self._mrz_validator.parse_mrz(mrz_lines)
            
            mrz_check = AuthenticityCheck(
                check_type=AuthenticityCheckType.MRZ_VALIDATION,
                result=CheckResult.PASS if mrz_data and mrz_data.check_digits_valid else CheckResult.FAIL,
                confidence=1.0 if mrz_data and mrz_data.check_digits_valid else 0.5,
                details={
                    "check_digits_valid": mrz_data.check_digits_valid if mrz_data else False,
                    "document_type": mrz_data.document_type if mrz_data else None,
                    "country_code": mrz_data.country_code if mrz_data else None
                },
                issues=mrz_errors
            )
            checks.append(mrz_check)
        
        # Barcode/QR Validation
        if barcode_data and barcode_type:
            parsed_barcode = self._barcode_decoder.decode_barcode(barcode_data, barcode_type)
            
            barcode_check = AuthenticityCheck(
                check_type=AuthenticityCheckType.BARCODE_QR,
                result=CheckResult.PASS if parsed_barcode.is_valid else CheckResult.FAIL,
                confidence=0.9 if parsed_barcode.is_valid else 0.3,
                details={
                    "barcode_type": barcode_type,
                    "fields_parsed": len(parsed_barcode.parsed_fields)
                },
                issues=[] if parsed_barcode.is_valid else ["Failed to parse barcode"]
            )
            checks.append(barcode_check)
        
        # Font Consistency
        if text_regions:
            font_check = self._font_analyzer.analyze_fonts(text_regions)
            checks.append(font_check)
        
        # Cross-Field Consistency
        if extracted_fields:
            cross_field_check = self._cross_field_checker.check_consistency(
                extracted_fields, mrz_data
            )
            checks.append(cross_field_check)
        
        # Date Validity
        if extracted_fields:
            date_check = self._date_checker.check_dates(extracted_fields)
            checks.append(date_check)
        
        # Image Analysis (if provided)
        if image_analysis:
            # Compression artifacts
            if "compression_score" in image_analysis:
                compression_check = AuthenticityCheck(
                    check_type=AuthenticityCheckType.COMPRESSION_ARTIFACTS,
                    result=CheckResult.PASS if image_analysis["compression_score"] < 0.5 else CheckResult.WARNING,
                    confidence=1.0 - image_analysis["compression_score"],
                    details={"compression_score": image_analysis["compression_score"]},
                    issues=["High compression artifacts detected"] if image_analysis["compression_score"] >= 0.5 else []
                )
                checks.append(compression_check)
            
            # Photo tampering
            if "tampering_score" in image_analysis:
                tampering_check = AuthenticityCheck(
                    check_type=AuthenticityCheckType.PHOTO_TAMPERING,
                    result=CheckResult.PASS if image_analysis["tampering_score"] < 0.3 else CheckResult.FAIL,
                    confidence=1.0 - image_analysis["tampering_score"],
                    details={"tampering_score": image_analysis["tampering_score"]},
                    issues=["Photo tampering detected"] if image_analysis["tampering_score"] >= 0.3 else []
                )
                checks.append(tampering_check)
        
        # Calculate overall result
        overall_result, overall_confidence = self._calculate_overall_result(checks)
        risk_level = self._determine_risk_level(checks)
        recommendations = self._generate_recommendations(checks)
        
        result = DocumentAuthenticityResult(
            document_id=document_id,
            document_type=document_type,
            overall_result=overall_result,
            overall_confidence=overall_confidence,
            risk_level=risk_level,
            checks=checks,
            mrz_data=mrz_data,
            barcode_data=parsed_barcode,
            extracted_fields=extracted_fields,
            recommendations=recommendations
        )
        
        self._results[document_id] = result
        
        logger.info(f"Document verified: {document_id} - {overall_result.value} ({overall_confidence:.2f})")
        
        return result
    
    def _calculate_overall_result(
        self,
        checks: List[AuthenticityCheck]
    ) -> Tuple[CheckResult, float]:
        """Calculate overall result from individual checks"""
        if not checks:
            return CheckResult.INCONCLUSIVE, 0.0
        
        # Count results
        fail_count = sum(1 for c in checks if c.result == CheckResult.FAIL)
        warning_count = sum(1 for c in checks if c.result == CheckResult.WARNING)
        pass_count = sum(1 for c in checks if c.result == CheckResult.PASS)
        
        # Calculate weighted confidence
        total_confidence = sum(c.confidence for c in checks)
        avg_confidence = total_confidence / len(checks)
        
        # Determine overall result
        if fail_count > 0:
            overall_result = CheckResult.FAIL
            # Reduce confidence for failures
            avg_confidence *= 0.5
        elif warning_count > len(checks) / 2:
            overall_result = CheckResult.WARNING
            avg_confidence *= 0.8
        elif pass_count == len(checks):
            overall_result = CheckResult.PASS
        else:
            overall_result = CheckResult.WARNING
            avg_confidence *= 0.9
        
        return overall_result, avg_confidence
    
    def _determine_risk_level(self, checks: List[AuthenticityCheck]) -> RiskLevel:
        """Determine risk level from checks"""
        fail_count = sum(1 for c in checks if c.result == CheckResult.FAIL)
        warning_count = sum(1 for c in checks if c.result == CheckResult.WARNING)
        
        if fail_count >= 2:
            return RiskLevel.CRITICAL
        elif fail_count == 1:
            return RiskLevel.HIGH
        elif warning_count >= 3:
            return RiskLevel.HIGH
        elif warning_count >= 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_recommendations(self, checks: List[AuthenticityCheck]) -> List[str]:
        """Generate recommendations based on check results"""
        recommendations = []
        
        for check in checks:
            if check.result == CheckResult.FAIL:
                if check.check_type == AuthenticityCheckType.MRZ_VALIDATION:
                    recommendations.append("Request new document scan with clear MRZ visibility")
                elif check.check_type == AuthenticityCheckType.CROSS_FIELD_CONSISTENCY:
                    recommendations.append("Manual review required for field inconsistencies")
                elif check.check_type == AuthenticityCheckType.DATE_VALIDITY:
                    recommendations.append("Request valid, non-expired document")
                elif check.check_type == AuthenticityCheckType.PHOTO_TAMPERING:
                    recommendations.append("Escalate for fraud investigation")
            
            elif check.result == CheckResult.WARNING:
                if check.check_type == AuthenticityCheckType.FONT_CONSISTENCY:
                    recommendations.append("Review document for potential alterations")
                elif check.check_type == AuthenticityCheckType.COMPRESSION_ARTIFACTS:
                    recommendations.append("Request higher quality document scan")
        
        return list(set(recommendations))  # Remove duplicates
    
    def get_result(self, document_id: str) -> Optional[DocumentAuthenticityResult]:
        """Get verification result by ID"""
        return self._results.get(document_id)
    
    @property
    def mrz_validator(self) -> MRZValidator:
        return self._mrz_validator
    
    @property
    def barcode_decoder(self) -> BarcodeQRDecoder:
        return self._barcode_decoder


# Global instance
_authenticity_service: Optional[DocumentAuthenticityService] = None


def get_document_authenticity_service() -> DocumentAuthenticityService:
    """Get or create document authenticity service"""
    global _authenticity_service
    if _authenticity_service is None:
        _authenticity_service = DocumentAuthenticityService()
    return _authenticity_service
