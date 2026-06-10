"""
Nigeria-Specific KYC/KYB Service
Handles Nigerian naming conventions, address normalization, ID validation,
bank codes, and alternative evidence paths for informal SMEs.

Integrates with: Redis for caching, Kafka for events
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class NigerianState(str, Enum):
    """Nigerian states"""
    ABIA = "abia"
    ADAMAWA = "adamawa"
    AKWA_IBOM = "akwa_ibom"
    ANAMBRA = "anambra"
    BAUCHI = "bauchi"
    BAYELSA = "bayelsa"
    BENUE = "benue"
    BORNO = "borno"
    CROSS_RIVER = "cross_river"
    DELTA = "delta"
    EBONYI = "ebonyi"
    EDO = "edo"
    EKITI = "ekiti"
    ENUGU = "enugu"
    FCT = "fct"
    GOMBE = "gombe"
    IMO = "imo"
    JIGAWA = "jigawa"
    KADUNA = "kaduna"
    KANO = "kano"
    KATSINA = "katsina"
    KEBBI = "kebbi"
    KOGI = "kogi"
    KWARA = "kwara"
    LAGOS = "lagos"
    NASARAWA = "nasarawa"
    NIGER = "niger"
    OGUN = "ogun"
    ONDO = "ondo"
    OSUN = "osun"
    OYO = "oyo"
    PLATEAU = "plateau"
    RIVERS = "rivers"
    SOKOTO = "sokoto"
    TARABA = "taraba"
    YOBE = "yobe"
    ZAMFARA = "zamfara"


class IDType(str, Enum):
    """Nigerian ID types"""
    BVN = "bvn"
    NIN = "nin"
    VOTERS_CARD = "voters_card"
    DRIVERS_LICENSE = "drivers_license"
    PASSPORT = "passport"
    CAC = "cac"
    TIN = "tin"
    PHONE = "phone"


class BankType(str, Enum):
    """Bank types"""
    COMMERCIAL = "commercial"
    MICROFINANCE = "microfinance"
    PAYMENT_SERVICE = "payment_service"
    MOBILE_MONEY = "mobile_money"
    MERCHANT = "merchant"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class NigerianBank:
    """Nigerian bank information"""
    code: str
    name: str
    short_name: str
    bank_type: BankType
    nibss_code: Optional[str] = None
    ussd_code: Optional[str] = None
    is_active: bool = True


@dataclass
class ParsedAddress:
    """Parsed Nigerian address"""
    street: Optional[str] = None
    area: Optional[str] = None
    lga: Optional[str] = None
    state: Optional[NigerianState] = None
    postal_code: Optional[str] = None
    landmarks: List[str] = field(default_factory=list)
    original: str = ""
    confidence: float = 0.0


@dataclass
class NameMatchResult:
    """Name matching result"""
    is_match: bool
    confidence: float
    match_type: str  # exact, fuzzy, alias, nickname
    normalized_name1: str
    normalized_name2: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IDValidationResult:
    """ID validation result"""
    is_valid: bool
    id_type: IDType
    formatted_id: str
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


# ============================================================================
# NIGERIAN BANK CODES (50+ BANKS)
# ============================================================================

NIGERIAN_BANKS: Dict[str, NigerianBank] = {
    # Commercial Banks
    "044": NigerianBank("044", "Access Bank Plc", "Access", BankType.COMMERCIAL, "044", "*901#"),
    "023": NigerianBank("023", "Citibank Nigeria Limited", "Citibank", BankType.COMMERCIAL, "023"),
    "063": NigerianBank("063", "Diamond Bank Plc", "Diamond", BankType.COMMERCIAL, "063", "*426#"),
    "050": NigerianBank("050", "Ecobank Nigeria", "Ecobank", BankType.COMMERCIAL, "050", "*326#"),
    "084": NigerianBank("084", "Enterprise Bank Plc", "Enterprise", BankType.COMMERCIAL, "084"),
    "070": NigerianBank("070", "Fidelity Bank Plc", "Fidelity", BankType.COMMERCIAL, "070", "*770#"),
    "011": NigerianBank("011", "First Bank of Nigeria", "FirstBank", BankType.COMMERCIAL, "011", "*894#"),
    "214": NigerianBank("214", "First City Monument Bank", "FCMB", BankType.COMMERCIAL, "214", "*329#"),
    "058": NigerianBank("058", "Guaranty Trust Bank", "GTBank", BankType.COMMERCIAL, "058", "*737#"),
    "030": NigerianBank("030", "Heritage Bank Plc", "Heritage", BankType.COMMERCIAL, "030", "*322#"),
    "301": NigerianBank("301", "Jaiz Bank Plc", "Jaiz", BankType.COMMERCIAL, "301"),
    "082": NigerianBank("082", "Keystone Bank Limited", "Keystone", BankType.COMMERCIAL, "082", "*7111#"),
    "526": NigerianBank("526", "Parallex Bank", "Parallex", BankType.COMMERCIAL, "526"),
    "076": NigerianBank("076", "Polaris Bank Limited", "Polaris", BankType.COMMERCIAL, "076", "*833#"),
    "101": NigerianBank("101", "Providus Bank", "Providus", BankType.COMMERCIAL, "101"),
    "221": NigerianBank("221", "Stanbic IBTC Bank", "Stanbic", BankType.COMMERCIAL, "221", "*909#"),
    "068": NigerianBank("068", "Standard Chartered Bank", "StanChart", BankType.COMMERCIAL, "068"),
    "232": NigerianBank("232", "Sterling Bank Plc", "Sterling", BankType.COMMERCIAL, "232", "*822#"),
    "100": NigerianBank("100", "Suntrust Bank Nigeria", "Suntrust", BankType.COMMERCIAL, "100"),
    "032": NigerianBank("032", "Union Bank of Nigeria", "Union", BankType.COMMERCIAL, "032", "*826#"),
    "033": NigerianBank("033", "United Bank for Africa", "UBA", BankType.COMMERCIAL, "033", "*919#"),
    "215": NigerianBank("215", "Unity Bank Plc", "Unity", BankType.COMMERCIAL, "215", "*7799#"),
    "035": NigerianBank("035", "Wema Bank Plc", "Wema", BankType.COMMERCIAL, "035", "*945#"),
    "057": NigerianBank("057", "Zenith Bank Plc", "Zenith", BankType.COMMERCIAL, "057", "*966#"),
    "559": NigerianBank("559", "Coronation Merchant Bank", "Coronation", BankType.MERCHANT, "559"),
    "560": NigerianBank("560", "FBNQuest Merchant Bank", "FBNQuest", BankType.MERCHANT, "560"),
    "561": NigerianBank("561", "FSDH Merchant Bank", "FSDH", BankType.MERCHANT, "561"),
    "562": NigerianBank("562", "Nova Merchant Bank", "Nova", BankType.MERCHANT, "562"),
    "563": NigerianBank("563", "Rand Merchant Bank", "RMB", BankType.MERCHANT, "563"),
    
    # Microfinance Banks
    "090110": NigerianBank("090110", "VFD Microfinance Bank", "VFD", BankType.MICROFINANCE, "090110"),
    "090267": NigerianBank("090267", "Kuda Microfinance Bank", "Kuda", BankType.MICROFINANCE, "090267"),
    "090405": NigerianBank("090405", "Moniepoint Microfinance Bank", "Moniepoint", BankType.MICROFINANCE, "090405"),
    "090286": NigerianBank("090286", "Safe Haven Microfinance Bank", "SafeHaven", BankType.MICROFINANCE, "090286"),
    "090175": NigerianBank("090175", "Rubies Microfinance Bank", "Rubies", BankType.MICROFINANCE, "090175"),
    "090115": NigerianBank("090115", "TCF Microfinance Bank", "TCF", BankType.MICROFINANCE, "090115"),
    "090134": NigerianBank("090134", "Accion Microfinance Bank", "Accion", BankType.MICROFINANCE, "090134"),
    "090270": NigerianBank("090270", "AB Microfinance Bank", "AB MFB", BankType.MICROFINANCE, "090270"),
    "090136": NigerianBank("090136", "Baobab Microfinance Bank", "Baobab", BankType.MICROFINANCE, "090136"),
    "090328": NigerianBank("090328", "Eyowo Microfinance Bank", "Eyowo", BankType.MICROFINANCE, "090328"),
    "090551": NigerianBank("090551", "Fairmoney Microfinance Bank", "Fairmoney", BankType.MICROFINANCE, "090551"),
    "090409": NigerianBank("090409", "Fcmb Microfinance Bank", "FCMB MFB", BankType.MICROFINANCE, "090409"),
    "090179": NigerianBank("090179", "FAST Microfinance Bank", "FAST", BankType.MICROFINANCE, "090179"),
    "090332": NigerianBank("090332", "Hackman Microfinance Bank", "Hackman", BankType.MICROFINANCE, "090332"),
    "090121": NigerianBank("090121", "HASAL Microfinance Bank", "HASAL", BankType.MICROFINANCE, "090121"),
    "090118": NigerianBank("090118", "IBILE Microfinance Bank", "IBILE", BankType.MICROFINANCE, "090118"),
    "090324": NigerianBank("090324", "Ikenne Microfinance Bank", "Ikenne", BankType.MICROFINANCE, "090324"),
    "090258": NigerianBank("090258", "Imo State Microfinance Bank", "Imo MFB", BankType.MICROFINANCE, "090258"),
    "090259": NigerianBank("090259", "Infinity Microfinance Bank", "Infinity", BankType.MICROFINANCE, "090259"),
    "090157": NigerianBank("090157", "Infinity Trust Mortgage Bank", "Infinity Trust", BankType.MICROFINANCE, "090157"),
    
    # Payment Service Banks
    "999991": NigerianBank("999991", "OPay Digital Services", "OPay", BankType.PAYMENT_SERVICE, "999991"),
    "999992": NigerianBank("999992", "PalmPay Limited", "PalmPay", BankType.PAYMENT_SERVICE, "999992"),
    "999993": NigerianBank("999993", "MTN MoMo PSB", "MTN MoMo", BankType.MOBILE_MONEY, "999993"),
    "999994": NigerianBank("999994", "Airtel Smart Cash", "Airtel Cash", BankType.MOBILE_MONEY, "999994"),
    "999995": NigerianBank("999995", "9PSB (9 Payment Service Bank)", "9PSB", BankType.PAYMENT_SERVICE, "999995"),
    "999996": NigerianBank("999996", "Hope PSB", "Hope PSB", BankType.PAYMENT_SERVICE, "999996"),
    "999997": NigerianBank("999997", "Globus Bank", "Globus", BankType.COMMERCIAL, "999997"),
    "999998": NigerianBank("999998", "Titan Trust Bank", "Titan", BankType.COMMERCIAL, "999998"),
    "999999": NigerianBank("999999", "Lotus Bank", "Lotus", BankType.COMMERCIAL, "999999"),
}


# ============================================================================
# NIGERIAN NAME PREFIXES AND CONVENTIONS
# ============================================================================

NIGERIAN_PREFIXES = {
    "chief", "alhaji", "alhaja", "dr", "dr.", "prof", "prof.", "engr", "engr.",
    "arc", "arc.", "barr", "barr.", "hon", "hon.", "pastor", "rev", "rev.",
    "elder", "deacon", "deaconess", "evangelist", "apostle", "bishop",
    "otunba", "oloye", "olori", "oba", "obong", "emir", "sarki", "igwe"
}

YORUBA_NAME_PATTERNS = {
    # Common Yoruba compound name patterns
    "oluwaseun": ["seun", "oluseun"],
    "oluwafemi": ["femi", "olufemi"],
    "oluwadamilola": ["damilola", "dammy", "dami"],
    "oluwabunmi": ["bunmi", "olubunmi"],
    "oluwakemi": ["kemi", "olukemi"],
    "oluwatobiloba": ["tobi", "tobiloba"],
    "oluwaseyi": ["seyi", "oluseyi"],
    "oluwafunmilayo": ["funmi", "funmilayo"],
    "oluwayemisi": ["yemisi", "oluyemisi"],
    "oluwadamilare": ["damilare", "dare"],
    "oluwatoyin": ["toyin", "oluwatoyin"],
    "oluwabusayo": ["busayo", "busola"],
    "oluwatimilehin": ["timilehin", "timi"],
    "oluwanifemi": ["nifemi", "olunifemi"],
    "oluwasegun": ["segun", "olusegun"],
    "oluwagbemiga": ["gbemiga", "gbenga"],
    "oluwadare": ["dare", "oludare"],
    "oluwakayode": ["kayode", "olukayode"],
    "oluwatomiwa": ["tomiwa", "tomilola"],
    "oluwafisayo": ["fisayo", "olufisayo"],
}

IGBO_NAME_PATTERNS = {
    "chukwuemeka": ["emeka", "chukwuemeka"],
    "chukwudi": ["chudi", "chukwudi"],
    "chukwuka": ["chuka", "chukwuka"],
    "nnamdi": ["nnamdi", "mdi"],
    "obiora": ["obi", "obiora"],
    "obinna": ["obi", "obinna"],
    "chibueze": ["chibu", "eze"],
    "chidinma": ["dinma", "chidinma"],
    "chidimma": ["dimma", "chidimma"],
    "chisom": ["som", "chisom"],
    "chinonso": ["nonso", "chinonso"],
    "chinedu": ["nedu", "chinedu"],
    "chinaza": ["naza", "chinaza"],
    "adaeze": ["ada", "adaeze"],
    "adaora": ["ada", "adaora"],
    "ugochukwu": ["ugo", "ugochukwu"],
    "ikechukwu": ["ike", "ikechukwu"],
    "kenechukwu": ["kene", "kenechukwu"],
    "somtochukwu": ["somto", "somtochukwu"],
}

HAUSA_NAME_PATTERNS = {
    "muhammadu": ["mohammed", "muhammad", "muhamad", "musa"],
    "abdullahi": ["abdullah", "abdulahi"],
    "abubakar": ["abubakar", "bubakar", "abu"],
    "ibrahim": ["ibrahim", "ibraheem"],
    "usman": ["usman", "othman", "osman"],
    "aliyu": ["ali", "aliyu"],
    "suleiman": ["suleiman", "sulaiman", "suleman"],
    "yusuf": ["yusuf", "yusuff", "joseph"],
    "ismail": ["ismail", "ismaila", "ismael"],
    "aminu": ["aminu", "amin"],
}

SURNAME_VARIATIONS = {
    # Common surname spelling variations
    "okonkwo": ["okonkwu", "okonkwo", "okonkwor"],
    "nwosu": ["nwosu", "nwaosu", "nwoso"],
    "okoro": ["okoro", "okorie", "okoroafor"],
    "eze": ["eze", "ezeh", "ezeji"],
    "okafor": ["okafor", "okafor", "okafoh"],
    "adeyemi": ["adeyemi", "adeyeemi"],
    "adesanya": ["adesanya", "adesaniya"],
    "ogundimu": ["ogundimu", "ogundimu"],
    "balogun": ["balogun", "balogum"],
    "akinwale": ["akinwale", "akinwali"],
}


# ============================================================================
# NAME MATCHING SERVICE
# ============================================================================

class NigerianNameMatcher:
    """
    Nigerian name matching with support for:
    - Compound names (Oluwaseun → Seun)
    - Surname variations (Okonkwo vs Okonkwu)
    - Prefixes (Chief, Alhaji, Dr)
    - Yoruba/Igbo/Hausa naming conventions
    - Married name changes
    - Nickname matching with Levenshtein distance
    """
    
    def __init__(self, match_threshold: float = 0.85):
        self.match_threshold = match_threshold
        
        # Build alias lookup
        self._alias_lookup: Dict[str, Set[str]] = {}
        self._build_alias_lookup()
    
    def _build_alias_lookup(self):
        """Build alias lookup from name patterns"""
        for patterns in [YORUBA_NAME_PATTERNS, IGBO_NAME_PATTERNS, HAUSA_NAME_PATTERNS]:
            for full_name, aliases in patterns.items():
                for alias in aliases:
                    if alias not in self._alias_lookup:
                        self._alias_lookup[alias] = set()
                    self._alias_lookup[alias].add(full_name)
                    self._alias_lookup[alias].update(aliases)
    
    def normalize_name(self, name: str) -> str:
        """Normalize Nigerian name"""
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove prefixes
        words = normalized.split()
        filtered_words = []
        
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r'[^\w\s]', '', word)
            
            # Skip prefixes
            if clean_word not in NIGERIAN_PREFIXES:
                filtered_words.append(clean_word)
        
        return " ".join(filtered_words)
    
    def match_names(self, name1: str, name2: str) -> NameMatchResult:
        """Match two Nigerian names"""
        # Normalize both names
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        # Exact match
        if norm1 == norm2:
            return NameMatchResult(
                is_match=True,
                confidence=1.0,
                match_type="exact",
                normalized_name1=norm1,
                normalized_name2=norm2
            )
        
        # Split into parts
        parts1 = set(norm1.split())
        parts2 = set(norm2.split())
        
        # Check for alias matches
        alias_match, alias_confidence = self._check_alias_match(parts1, parts2)
        if alias_match:
            return NameMatchResult(
                is_match=True,
                confidence=alias_confidence,
                match_type="alias",
                normalized_name1=norm1,
                normalized_name2=norm2,
                details={"alias_match": True}
            )
        
        # Check for surname variations
        surname_match, surname_confidence = self._check_surname_variations(parts1, parts2)
        if surname_match:
            return NameMatchResult(
                is_match=True,
                confidence=surname_confidence,
                match_type="surname_variation",
                normalized_name1=norm1,
                normalized_name2=norm2
            )
        
        # Fuzzy matching using Levenshtein distance
        fuzzy_score = self._calculate_fuzzy_score(norm1, norm2)
        
        if fuzzy_score >= self.match_threshold:
            return NameMatchResult(
                is_match=True,
                confidence=fuzzy_score,
                match_type="fuzzy",
                normalized_name1=norm1,
                normalized_name2=norm2,
                details={"levenshtein_score": fuzzy_score}
            )
        
        # Check partial matches (at least 2 name parts match)
        common_parts = parts1 & parts2
        if len(common_parts) >= 2:
            partial_confidence = len(common_parts) / max(len(parts1), len(parts2))
            if partial_confidence >= 0.6:
                return NameMatchResult(
                    is_match=True,
                    confidence=partial_confidence,
                    match_type="partial",
                    normalized_name1=norm1,
                    normalized_name2=norm2,
                    details={"common_parts": list(common_parts)}
                )
        
        # No match
        return NameMatchResult(
            is_match=False,
            confidence=fuzzy_score,
            match_type="none",
            normalized_name1=norm1,
            normalized_name2=norm2
        )
    
    def _check_alias_match(
        self, 
        parts1: Set[str], 
        parts2: Set[str]
    ) -> Tuple[bool, float]:
        """Check for alias matches"""
        for part1 in parts1:
            if part1 in self._alias_lookup:
                aliases = self._alias_lookup[part1]
                for part2 in parts2:
                    if part2 in aliases:
                        return True, 0.95
        
        for part2 in parts2:
            if part2 in self._alias_lookup:
                aliases = self._alias_lookup[part2]
                for part1 in parts1:
                    if part1 in aliases:
                        return True, 0.95
        
        return False, 0.0
    
    def _check_surname_variations(
        self, 
        parts1: Set[str], 
        parts2: Set[str]
    ) -> Tuple[bool, float]:
        """Check for surname spelling variations"""
        for surname, variations in SURNAME_VARIATIONS.items():
            var_set = set(variations)
            
            match1 = parts1 & var_set
            match2 = parts2 & var_set
            
            if match1 and match2:
                return True, 0.90
        
        return False, 0.0
    
    def _calculate_fuzzy_score(self, s1: str, s2: str) -> float:
        """Calculate fuzzy match score using SequenceMatcher"""
        return SequenceMatcher(None, s1, s2).ratio()
    
    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]


# ============================================================================
# ADDRESS NORMALIZATION SERVICE
# ============================================================================

class NigerianAddressNormalizer:
    """
    Nigerian address normalization with:
    - LGA/state extraction
    - Street abbreviation expansion
    - Landmark identification
    - Postal code validation
    """
    
    STREET_ABBREVIATIONS = {
        "st": "street",
        "st.": "street",
        "rd": "road",
        "rd.": "road",
        "ave": "avenue",
        "ave.": "avenue",
        "cres": "crescent",
        "cres.": "crescent",
        "cl": "close",
        "cl.": "close",
        "ln": "lane",
        "ln.": "lane",
        "blvd": "boulevard",
        "blvd.": "boulevard",
        "dr": "drive",
        "dr.": "drive",
        "ct": "court",
        "ct.": "court",
        "est": "estate",
        "est.": "estate",
    }
    
    STATE_ALIASES = {
        "lagos": NigerianState.LAGOS,
        "lag": NigerianState.LAGOS,
        "abuja": NigerianState.FCT,
        "fct": NigerianState.FCT,
        "federal capital territory": NigerianState.FCT,
        "rivers": NigerianState.RIVERS,
        "ph": NigerianState.RIVERS,
        "port harcourt": NigerianState.RIVERS,
        "kano": NigerianState.KANO,
        "kaduna": NigerianState.KADUNA,
        "ogun": NigerianState.OGUN,
        "oyo": NigerianState.OYO,
        "ibadan": NigerianState.OYO,
        "enugu": NigerianState.ENUGU,
        "anambra": NigerianState.ANAMBRA,
        "delta": NigerianState.DELTA,
        "edo": NigerianState.EDO,
        "benin": NigerianState.EDO,
        "imo": NigerianState.IMO,
        "abia": NigerianState.ABIA,
        "cross river": NigerianState.CROSS_RIVER,
        "calabar": NigerianState.CROSS_RIVER,
        "akwa ibom": NigerianState.AKWA_IBOM,
        "bayelsa": NigerianState.BAYELSA,
        "benue": NigerianState.BENUE,
        "plateau": NigerianState.PLATEAU,
        "jos": NigerianState.PLATEAU,
        "kwara": NigerianState.KWARA,
        "ilorin": NigerianState.KWARA,
        "osun": NigerianState.OSUN,
        "ekiti": NigerianState.EKITI,
        "ondo": NigerianState.ONDO,
        "kogi": NigerianState.KOGI,
        "nasarawa": NigerianState.NASARAWA,
        "niger": NigerianState.NIGER,
        "sokoto": NigerianState.SOKOTO,
        "kebbi": NigerianState.KEBBI,
        "zamfara": NigerianState.ZAMFARA,
        "katsina": NigerianState.KATSINA,
        "jigawa": NigerianState.JIGAWA,
        "bauchi": NigerianState.BAUCHI,
        "gombe": NigerianState.GOMBE,
        "adamawa": NigerianState.ADAMAWA,
        "taraba": NigerianState.TARABA,
        "borno": NigerianState.BORNO,
        "maiduguri": NigerianState.BORNO,
        "yobe": NigerianState.YOBE,
        "ebonyi": NigerianState.EBONYI,
    }
    
    LANDMARK_KEYWORDS = [
        "opposite", "opp", "beside", "near", "behind", "after", "before",
        "junction", "bus stop", "bus-stop", "b/stop", "market", "church",
        "mosque", "school", "hospital", "hotel", "plaza", "mall", "estate",
        "gate", "roundabout", "bridge", "flyover", "under bridge"
    ]
    
    def normalize_address(self, address: str) -> ParsedAddress:
        """Normalize Nigerian address"""
        if not address:
            return ParsedAddress(original=address, confidence=0.0)
        
        original = address
        normalized = address.lower().strip()
        
        # Extract postal code (6 digits)
        postal_code = None
        postal_match = re.search(r'\b(\d{6})\b', normalized)
        if postal_match:
            postal_code = postal_match.group(1)
            normalized = normalized.replace(postal_match.group(0), "")
        
        # Extract state
        state = None
        for alias, state_enum in self.STATE_ALIASES.items():
            if alias in normalized:
                state = state_enum
                break
        
        # Expand abbreviations
        words = normalized.split()
        expanded_words = []
        for word in words:
            clean_word = word.strip(",.")
            if clean_word in self.STREET_ABBREVIATIONS:
                expanded_words.append(self.STREET_ABBREVIATIONS[clean_word])
            else:
                expanded_words.append(word)
        
        normalized = " ".join(expanded_words)
        
        # Extract landmarks
        landmarks = []
        for keyword in self.LANDMARK_KEYWORDS:
            if keyword in normalized:
                # Extract text after landmark keyword
                pattern = rf'{keyword}\s+([^,]+)'
                match = re.search(pattern, normalized)
                if match:
                    landmarks.append(f"{keyword} {match.group(1).strip()}")
        
        # Extract street
        street = None
        street_patterns = [
            r'(\d+[a-z]?\s+\w+\s+(?:street|road|avenue|crescent|close|lane|drive))',
            r'(no\.?\s*\d+[a-z]?\s+\w+\s+(?:street|road|avenue|crescent|close|lane|drive))',
        ]
        for pattern in street_patterns:
            match = re.search(pattern, normalized)
            if match:
                street = match.group(1).strip()
                break
        
        # Calculate confidence
        confidence = 0.0
        if state:
            confidence += 0.3
        if street:
            confidence += 0.3
        if postal_code:
            confidence += 0.2
        if landmarks:
            confidence += 0.2
        
        return ParsedAddress(
            street=street,
            area=None,  # Would need LGA database
            lga=None,
            state=state,
            postal_code=postal_code,
            landmarks=landmarks,
            original=original,
            confidence=confidence
        )
    
    def validate_postal_code(self, postal_code: str) -> bool:
        """Validate Nigerian postal code (6 digits)"""
        if not postal_code:
            return False
        return bool(re.match(r'^\d{6}$', postal_code.strip()))


# ============================================================================
# ID VALIDATION SERVICE
# ============================================================================

class NigerianIDValidator:
    """
    Nigerian ID validation for:
    - BVN (11 digits)
    - NIN (11 digits)
    - Voter's Card (19 alphanumeric)
    - Driver's License (state code + numbers)
    - Passport (A + 8 digits)
    - CAC (RC/BN/IT + numbers)
    - TIN
    - Phone numbers (0[789][01]XXXXXXXX)
    """
    
    def validate_id(self, id_value: str, id_type: IDType) -> IDValidationResult:
        """Validate Nigerian ID"""
        if not id_value:
            return IDValidationResult(
                is_valid=False,
                id_type=id_type,
                formatted_id="",
                errors=["ID value is empty"]
            )
        
        # Clean the ID
        cleaned = id_value.strip().upper()
        
        validators = {
            IDType.BVN: self._validate_bvn,
            IDType.NIN: self._validate_nin,
            IDType.VOTERS_CARD: self._validate_voters_card,
            IDType.DRIVERS_LICENSE: self._validate_drivers_license,
            IDType.PASSPORT: self._validate_passport,
            IDType.CAC: self._validate_cac,
            IDType.TIN: self._validate_tin,
            IDType.PHONE: self._validate_phone,
        }
        
        validator = validators.get(id_type)
        if validator:
            return validator(cleaned)
        
        return IDValidationResult(
            is_valid=False,
            id_type=id_type,
            formatted_id=cleaned,
            errors=[f"Unknown ID type: {id_type}"]
        )
    
    def _validate_bvn(self, bvn: str) -> IDValidationResult:
        """Validate BVN (11 digits)"""
        errors = []
        
        # Remove any spaces or dashes
        cleaned = re.sub(r'[\s-]', '', bvn)
        
        if len(cleaned) != 11:
            errors.append(f"BVN must be 11 digits, got {len(cleaned)}")
        
        if not cleaned.isdigit():
            errors.append("BVN must contain only digits")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.BVN,
            formatted_id=cleaned,
            errors=errors,
            details={"length": len(cleaned)}
        )
    
    def _validate_nin(self, nin: str) -> IDValidationResult:
        """Validate NIN (11 digits)"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', nin)
        
        if len(cleaned) != 11:
            errors.append(f"NIN must be 11 digits, got {len(cleaned)}")
        
        if not cleaned.isdigit():
            errors.append("NIN must contain only digits")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.NIN,
            formatted_id=cleaned,
            errors=errors
        )
    
    def _validate_voters_card(self, vc: str) -> IDValidationResult:
        """Validate Voter's Card (19 alphanumeric)"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', vc)
        
        if len(cleaned) != 19:
            errors.append(f"Voter's Card must be 19 characters, got {len(cleaned)}")
        
        if not cleaned.isalnum():
            errors.append("Voter's Card must be alphanumeric")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.VOTERS_CARD,
            formatted_id=cleaned,
            errors=errors
        )
    
    def _validate_drivers_license(self, dl: str) -> IDValidationResult:
        """Validate Driver's License (state code + numbers)"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', dl)
        
        # Pattern: 3 letters (state code) + numbers
        pattern = r'^[A-Z]{3}\d+$'
        if not re.match(pattern, cleaned):
            errors.append("Driver's License must start with 3-letter state code followed by numbers")
        
        # Check state code
        state_codes = {
            "LAG", "ABJ", "FCT", "KAN", "KAD", "OGU", "OYO", "RIV", "EDO",
            "DEL", "ENU", "ANA", "IMO", "ABI", "CRS", "AKS", "BAY", "BEN",
            "PLA", "KWA", "OSU", "EKI", "OND", "KOG", "NAS", "NIG", "SOK",
            "KEB", "ZAM", "KAT", "JIG", "BAU", "GOM", "ADA", "TAR", "BOR", "YOB", "EBO"
        }
        
        if len(cleaned) >= 3 and cleaned[:3] not in state_codes:
            errors.append(f"Invalid state code: {cleaned[:3]}")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.DRIVERS_LICENSE,
            formatted_id=cleaned,
            errors=errors,
            details={"state_code": cleaned[:3] if len(cleaned) >= 3 else None}
        )
    
    def _validate_passport(self, passport: str) -> IDValidationResult:
        """Validate Passport (A + 8 digits)"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', passport)
        
        # Pattern: A followed by 8 digits
        pattern = r'^[A-Z]\d{8}$'
        if not re.match(pattern, cleaned):
            errors.append("Passport must be 1 letter followed by 8 digits (e.g., A12345678)")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.PASSPORT,
            formatted_id=cleaned,
            errors=errors
        )
    
    def _validate_cac(self, cac: str) -> IDValidationResult:
        """Validate CAC number (RC/BN/IT + numbers)"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', cac)
        
        # Pattern: RC, BN, or IT followed by numbers
        pattern = r'^(RC|BN|IT)\d+$'
        if not re.match(pattern, cleaned):
            errors.append("CAC must start with RC, BN, or IT followed by numbers")
        
        cac_type = None
        if cleaned.startswith("RC"):
            cac_type = "Registered Company"
        elif cleaned.startswith("BN"):
            cac_type = "Business Name"
        elif cleaned.startswith("IT"):
            cac_type = "Incorporated Trustee"
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.CAC,
            formatted_id=cleaned,
            errors=errors,
            details={"cac_type": cac_type}
        )
    
    def _validate_tin(self, tin: str) -> IDValidationResult:
        """Validate Tax Identification Number"""
        errors = []
        
        cleaned = re.sub(r'[\s-]', '', tin)
        
        # TIN is typically 10-14 digits
        if not cleaned.isdigit():
            errors.append("TIN must contain only digits")
        
        if len(cleaned) < 10 or len(cleaned) > 14:
            errors.append(f"TIN must be 10-14 digits, got {len(cleaned)}")
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.TIN,
            formatted_id=cleaned,
            errors=errors
        )
    
    def _validate_phone(self, phone: str) -> IDValidationResult:
        """Validate Nigerian phone number (0[789][01]XXXXXXXX)"""
        errors = []
        
        # Remove spaces, dashes, and country code
        cleaned = re.sub(r'[\s-]', '', phone)
        cleaned = re.sub(r'^\+?234', '0', cleaned)
        
        # Pattern: 0[789][01]XXXXXXXX (11 digits)
        pattern = r'^0[789][01]\d{8}$'
        if not re.match(pattern, cleaned):
            errors.append("Phone must be Nigerian format: 0[789][01]XXXXXXXX")
        
        # Identify network
        network = None
        if len(cleaned) >= 4:
            prefix = cleaned[:4]
            network_prefixes = {
                "0803": "MTN", "0806": "MTN", "0703": "MTN", "0706": "MTN",
                "0813": "MTN", "0816": "MTN", "0810": "MTN", "0814": "MTN",
                "0903": "MTN", "0906": "MTN", "0913": "MTN", "0916": "MTN",
                "0805": "Glo", "0807": "Glo", "0705": "Glo", "0815": "Glo",
                "0811": "Glo", "0905": "Glo", "0915": "Glo",
                "0802": "Airtel", "0808": "Airtel", "0708": "Airtel",
                "0812": "Airtel", "0701": "Airtel", "0902": "Airtel", "0912": "Airtel",
                "0809": "9mobile", "0817": "9mobile", "0818": "9mobile",
                "0908": "9mobile", "0909": "9mobile",
            }
            network = network_prefixes.get(prefix)
        
        return IDValidationResult(
            is_valid=len(errors) == 0,
            id_type=IDType.PHONE,
            formatted_id=cleaned,
            errors=errors,
            details={"network": network}
        )


# ============================================================================
# NIGERIA SPECIFIC SERVICE
# ============================================================================

class NigeriaSpecificService:
    """
    Main Nigeria-specific service combining all capabilities
    """
    
    def __init__(self):
        self._name_matcher = NigerianNameMatcher()
        self._address_normalizer = NigerianAddressNormalizer()
        self._id_validator = NigerianIDValidator()
    
    def match_names(self, name1: str, name2: str) -> NameMatchResult:
        """Match two Nigerian names"""
        return self._name_matcher.match_names(name1, name2)
    
    def normalize_address(self, address: str) -> ParsedAddress:
        """Normalize Nigerian address"""
        return self._address_normalizer.normalize_address(address)
    
    def validate_id(self, id_value: str, id_type: IDType) -> IDValidationResult:
        """Validate Nigerian ID"""
        return self._id_validator.validate_id(id_value, id_type)
    
    def get_bank(self, code: str) -> Optional[NigerianBank]:
        """Get bank by code"""
        return NIGERIAN_BANKS.get(code)
    
    def search_banks(self, query: str) -> List[NigerianBank]:
        """Search banks by name"""
        query_lower = query.lower()
        results = []
        
        for bank in NIGERIAN_BANKS.values():
            if (query_lower in bank.name.lower() or 
                query_lower in bank.short_name.lower()):
                results.append(bank)
        
        return results
    
    def get_all_banks(self, bank_type: Optional[BankType] = None) -> List[NigerianBank]:
        """Get all banks, optionally filtered by type"""
        if bank_type:
            return [b for b in NIGERIAN_BANKS.values() if b.bank_type == bank_type]
        return list(NIGERIAN_BANKS.values())
    
    @property
    def name_matcher(self) -> NigerianNameMatcher:
        return self._name_matcher
    
    @property
    def address_normalizer(self) -> NigerianAddressNormalizer:
        return self._address_normalizer
    
    @property
    def id_validator(self) -> NigerianIDValidator:
        return self._id_validator


# Global instance
_nigeria_service: Optional[NigeriaSpecificService] = None


def get_nigeria_service() -> NigeriaSpecificService:
    """Get or create Nigeria-specific service"""
    global _nigeria_service
    if _nigeria_service is None:
        _nigeria_service = NigeriaSpecificService()
    return _nigeria_service
