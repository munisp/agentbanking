"""
Banking Document Parsers
Nigerian-specific document field extraction
"""

import re
from typing import Dict, Any, List
from models.document import DocumentType

class BankingDocumentParser:
    def parse_document(
        self,
        text: str,
        document_type: DocumentType,
        structured_data: List[Dict[str, Any]] = []
    ) -> Dict[str, Any]:
        """Parse banking document based on type"""
        
        if document_type == DocumentType.NATIONAL_ID:
            return self._parse_national_id(text)
        elif document_type == DocumentType.PASSPORT:
            return self._parse_passport(text)
        elif document_type == DocumentType.DRIVERS_LICENSE:
            return self._parse_drivers_license(text)
        elif document_type == DocumentType.BANK_STATEMENT:
            return self._parse_bank_statement(text, structured_data)
        elif document_type == DocumentType.UTILITY_BILL:
            return self._parse_utility_bill(text)
        elif document_type == DocumentType.CORPORATE_REGISTRATION:
            return self._parse_corporate_registration(text)
        else:
            return {"raw_text": text}
    
    def _parse_national_id(self, text: str) -> Dict[str, str]:
        """Parse Nigerian National ID"""
        fields = {}
        
        # ID number (11 digits)
        id_match = re.search(r'\b\d{11}\b', text)
        if id_match:
            fields['id_number'] = id_match.group()
        
        # Name
        name_match = re.search(r'(?:Name|SURNAME)[:\s]+([A-Z\s]+)', text, re.IGNORECASE)
        if name_match:
            fields['name'] = name_match.group(1).strip()
        
        # Date of birth
        dob_match = re.search(r'(?:Date of Birth|DOB)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})', text, re.IGNORECASE)
        if dob_match:
            fields['date_of_birth'] = dob_match.group(1)
        
        # Gender
        gender_match = re.search(r'(?:Sex|Gender)[:\s]+(Male|Female|M|F)', text, re.IGNORECASE)
        if gender_match:
            fields['gender'] = gender_match.group(1)
        
        return fields
    
    def _parse_passport(self, text: str) -> Dict[str, str]:
        """Parse Nigerian Passport"""
        fields = {}
        
        # Passport number (A + 8 digits)
        passport_match = re.search(r'\bA\d{8}\b', text)
        if passport_match:
            fields['passport_number'] = passport_match.group()
        
        # Surname
        surname_match = re.search(r'(?:Surname|SURNAME)[:\s]+([A-Z]+)', text)
        if surname_match:
            fields['surname'] = surname_match.group(1)
        
        # Given names
        given_match = re.search(r'(?:Given names|GIVEN NAMES)[:\s]+([A-Z\s]+)', text)
        if given_match:
            fields['given_names'] = given_match.group(1).strip()
        
        # Nationality
        fields['nationality'] = 'NIGERIAN' if 'NIGERIA' in text.upper() else 'Unknown'
        
        return fields
    
    def _parse_drivers_license(self, text: str) -> Dict[str, str]:
        """Parse Driver's License"""
        fields = {}
        
        # License number
        license_match = re.search(r'(?:License No|LICENSE NUMBER)[:\s]+([A-Z0-9]+)', text, re.IGNORECASE)
        if license_match:
            fields['license_number'] = license_match.group(1)
        
        # Expiry date
        expiry_match = re.search(r'(?:Expiry|EXPIRY DATE)[:\s]+(\d{2}[/-]\d{2}[/-]\d{4})', text, re.IGNORECASE)
        if expiry_match:
            fields['expiry_date'] = expiry_match.group(1)
        
        return fields
    
    def _parse_bank_statement(self, text: str, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Parse Bank Statement"""
        fields = {}
        
        # Account number
        account_match = re.search(r'(?:Account|A/C)[:\s]+(\d{10})', text, re.IGNORECASE)
        if account_match:
            fields['account_number'] = account_match.group(1)
        
        # Account name
        name_match = re.search(r'(?:Account Name|Name)[:\s]+([A-Z\s]+)', text, re.IGNORECASE)
        if name_match:
            fields['account_name'] = name_match.group(1).strip()
        
        # Extract transactions from tables
        if tables:
            fields['transactions'] = tables[0] if tables else []
        
        return fields
    
    def _parse_utility_bill(self, text: str) -> Dict[str, str]:
        """Parse Utility Bill"""
        fields = {}
        
        # Address
        address_match = re.search(r'(?:Address|CUSTOMER ADDRESS)[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if address_match:
            fields['address'] = address_match.group(1).strip()
        
        # Account number
        account_match = re.search(r'(?:Account|Customer) (?:No|Number)[:\s]+(\d+)', text, re.IGNORECASE)
        if account_match:
            fields['account_number'] = account_match.group(1)
        
        return fields
    
    def _parse_corporate_registration(self, text: str) -> Dict[str, str]:
        """Parse Corporate Registration (CAC)"""
        fields = {}
        
        # RC number
        rc_match = re.search(r'(?:RC|Registration)[:\s]+(\d+)', text, re.IGNORECASE)
        if rc_match:
            fields['rc_number'] = rc_match.group(1)
        
        # Company name
        company_match = re.search(r'(?:Company Name|Name of Company)[:\s]+(.+?)(?:\n|$)', text, re.IGNORECASE)
        if company_match:
            fields['company_name'] = company_match.group(1).strip()
        
        return fields
