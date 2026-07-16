"""
Document Verification Accuracy Enhancement
Fine-tuned for Nigerian documents with improved field extraction
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class NigerianDocumentVerificationEnhancement:
    """
    Enhanced document verification specifically tuned for Nigerian documents
    
    Supported Documents:
    - National ID Card (NIN)
    - International Passport
    - Driver's License
    - Voter's Card
    - Bank Verification Number (BVN) slip
    """
    
    # Nigerian-specific patterns
    NIN_PATTERN = r'\b\d{11}\b'  # 11-digit NIN
    BVN_PATTERN = r'\b\d{11}\b'  # 11-digit BVN
    PASSPORT_PATTERN = r'\b[A-Z]\d{8}\b'  # A12345678
    DRIVERS_LICENSE_PATTERN = r'\b[A-Z]{3}[A-Z0-9]{9}\b'  # ABC123456789
    VOTERS_CARD_PATTERN = r'\b\d{19}\b'  # 19-digit VIN
    
    # Nigerian states for validation
    NIGERIAN_STATES = [
        "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa",
        "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo",
        "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna",
        "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa",
        "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers",
        "Sokoto", "Taraba", "Yobe", "Zamfara"
    ]
    
    def __init__(self):
        logger.info("Initialized Nigerian Document Verification Enhancement")
    
    def enhance_extraction(self, ocr_text: str, document_type: str) -> Dict[str, Any]:
        """
        Enhance field extraction with Nigerian-specific rules
        
        Args:
            ocr_text: Raw OCR text from document
            document_type: Type of document
            
        Returns:
            Enhanced extraction results
        """
        try:
            if document_type == "national_id":
                return self._extract_nin_card(ocr_text)
            elif document_type == "passport":
                return self._extract_passport(ocr_text)
            elif document_type == "drivers_license":
                return self._extract_drivers_license(ocr_text)
            elif document_type == "voters_card":
                return self._extract_voters_card(ocr_text)
            elif document_type == "bvn_slip":
                return self._extract_bvn(ocr_text)
            else:
                return {"success": False, "error": f"Unsupported document type: {document_type}"}
        except Exception as e:
            logger.error(f"Extraction enhancement failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _extract_nin_card(self, text: str) -> Dict[str, Any]:
        """Extract fields from National ID Card"""
        nin_match = re.search(self.NIN_PATTERN, text)
        
        # Extract name (usually after "Name:" or "Full Name:")
        name_match = re.search(r'(?:Full )?Name[:\s]+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        
        # Extract date of birth
        dob_match = re.search(r'(?:Date of Birth|DOB)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        # Extract gender
        gender_match = re.search(r'(?:Sex|Gender)[:\s]+(Male|Female|M|F)', text, re.IGNORECASE)
        
        # Extract state
        state = None
        for nigerian_state in self.NIGERIAN_STATES:
            if nigerian_state.lower() in text.lower():
                state = nigerian_state
                break
        
        return {
            "success": True,
            "document_type": "national_id",
            "nin": nin_match.group(0) if nin_match else None,
            "name": name_match.group(1).strip() if name_match else None,
            "date_of_birth": dob_match.group(1) if dob_match else None,
            "gender": gender_match.group(1) if gender_match else None,
            "state": state,
            "confidence": self._calculate_confidence([nin_match, name_match, dob_match]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_passport(self, text: str) -> Dict[str, Any]:
        """Extract fields from International Passport"""
        passport_match = re.search(self.PASSPORT_PATTERN, text)
        
        # Extract surname and given names
        surname_match = re.search(r'Surname[:\s]+([A-Z][A-Za-z]+)', text, re.IGNORECASE)
        given_names_match = re.search(r'Given Names?[:\s]+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        
        # Extract nationality (should be "Nigerian" or "Nigeria")
        nationality_match = re.search(r'Nationality[:\s]+(Nigerian?)', text, re.IGNORECASE)
        
        # Extract date of birth
        dob_match = re.search(r'Date of Birth[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        # Extract date of issue and expiry
        issue_match = re.search(r'Date of Issue[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        expiry_match = re.search(r'Date of Expiry[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        return {
            "success": True,
            "document_type": "passport",
            "passport_number": passport_match.group(0) if passport_match else None,
            "surname": surname_match.group(1).strip() if surname_match else None,
            "given_names": given_names_match.group(1).strip() if given_names_match else None,
            "nationality": nationality_match.group(1) if nationality_match else None,
            "date_of_birth": dob_match.group(1) if dob_match else None,
            "date_of_issue": issue_match.group(1) if issue_match else None,
            "date_of_expiry": expiry_match.group(1) if expiry_match else None,
            "confidence": self._calculate_confidence([passport_match, surname_match, dob_match]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_drivers_license(self, text: str) -> Dict[str, Any]:
        """Extract fields from Driver's License"""
        license_match = re.search(self.DRIVERS_LICENSE_PATTERN, text)
        
        name_match = re.search(r'Name[:\s]+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        dob_match = re.search(r'(?:Date of Birth|DOB)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        # Extract license class
        class_match = re.search(r'Class[:\s]+([A-Z]+)', text, re.IGNORECASE)
        
        # Extract issue and expiry dates
        issue_match = re.search(r'(?:Issue Date|Issued)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        expiry_match = re.search(r'(?:Expiry Date|Expires)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        return {
            "success": True,
            "document_type": "drivers_license",
            "license_number": license_match.group(0) if license_match else None,
            "name": name_match.group(1).strip() if name_match else None,
            "date_of_birth": dob_match.group(1) if dob_match else None,
            "license_class": class_match.group(1) if class_match else None,
            "date_of_issue": issue_match.group(1) if issue_match else None,
            "date_of_expiry": expiry_match.group(1) if expiry_match else None,
            "confidence": self._calculate_confidence([license_match, name_match, dob_match]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_voters_card(self, text: str) -> Dict[str, Any]:
        """Extract fields from Voter's Card"""
        vin_match = re.search(self.VOTERS_CARD_PATTERN, text)
        
        name_match = re.search(r'Name[:\s]+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        
        # Extract polling unit
        pu_match = re.search(r'Polling Unit[:\s]+([A-Za-z0-9\s]+)', text, re.IGNORECASE)
        
        # Extract state
        state = None
        for nigerian_state in self.NIGERIAN_STATES:
            if nigerian_state.lower() in text.lower():
                state = nigerian_state
                break
        
        return {
            "success": True,
            "document_type": "voters_card",
            "vin": vin_match.group(0) if vin_match else None,
            "name": name_match.group(1).strip() if name_match else None,
            "polling_unit": pu_match.group(1).strip() if pu_match else None,
            "state": state,
            "confidence": self._calculate_confidence([vin_match, name_match]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _extract_bvn(self, text: str) -> Dict[str, Any]:
        """Extract fields from BVN slip"""
        bvn_match = re.search(self.BVN_PATTERN, text)
        
        name_match = re.search(r'(?:Full )?Name[:\s]+([A-Z][A-Za-z\s]+)', text, re.IGNORECASE)
        dob_match = re.search(r'(?:Date of Birth|DOB)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        
        # Extract phone number
        phone_match = re.search(r'(?:Phone|Mobile)[:\s]+(\+?234\d{10}|0\d{10})', text, re.IGNORECASE)
        
        return {
            "success": True,
            "document_type": "bvn_slip",
            "bvn": bvn_match.group(0) if bvn_match else None,
            "name": name_match.group(1).strip() if name_match else None,
            "date_of_birth": dob_match.group(1) if dob_match else None,
            "phone_number": phone_match.group(1) if phone_match else None,
            "confidence": self._calculate_confidence([bvn_match, name_match, dob_match]),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_confidence(self, matches: List[Optional[re.Match]]) -> float:
        """Calculate extraction confidence score"""
        successful_matches = sum(1 for m in matches if m is not None)
        total_fields = len(matches)
        return round(successful_matches / total_fields, 2) if total_fields > 0 else 0.0
    
    def validate_nigerian_document(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate extracted data against Nigerian document rules
        
        Args:
            extracted_data: Extracted document fields
            
        Returns:
            Validation results with issues
        """
        issues = []
        warnings = []
        
        doc_type = extracted_data.get("document_type")
        
        # Validate NIN
        if doc_type == "national_id":
            nin = extracted_data.get("nin")
            if nin and len(nin) != 11:
                issues.append("NIN must be 11 digits")
            if not nin:
                issues.append("NIN not found")
        
        # Validate Passport
        elif doc_type == "passport":
            passport = extracted_data.get("passport_number")
            if passport and not re.match(self.PASSPORT_PATTERN, passport):
                issues.append("Invalid passport number format")
            nationality = extracted_data.get("nationality")
            if nationality and "nigeria" not in nationality.lower():
                warnings.append("Nationality is not Nigerian")
        
        # Validate state
        state = extracted_data.get("state")
        if state and state not in self.NIGERIAN_STATES:
            warnings.append(f"Unknown Nigerian state: {state}")
        
        # Calculate overall validity
        is_valid = len(issues) == 0 and extracted_data.get("confidence", 0) >= 0.6
        
        return {
            "is_valid": is_valid,
            "confidence": extracted_data.get("confidence", 0),
            "issues": issues,
            "warnings": warnings,
            "timestamp": datetime.utcnow().isoformat()
        }
