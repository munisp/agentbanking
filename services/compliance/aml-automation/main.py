"""
Compliance Automation Service - Production Implementation
AML/CFT, Sanctions Screening, Regulatory Reporting
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
import logging
import httpx

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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Compliance Automation Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SanctionsList(str, Enum):
    OFAC = "ofac"
    UN = "un"
    EU = "eu"
    UK_HMT = "uk_hmt"
    INTERPOL = "interpol"

class ComplianceCheck(BaseModel):
    entity_id: str
    entity_type: str  # "individual" or "business"
    name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    address: Optional[Dict] = None
    business_registration: Optional[str] = None
    metadata: Optional[Dict] = None

class SanctionsResult(BaseModel):
    entity_id: str
    is_sanctioned: bool
    matches: List[Dict]
    lists_checked: List[str]
    risk_score: float
    timestamp: str

class AMLResult(BaseModel):
    entity_id: str
    risk_level: RiskLevel
    risk_score: float
    flags: List[str]
    pep_match: bool
    adverse_media: bool
    recommended_action: str
    timestamp: str

class ComplianceAutomation:
    """Automated Compliance Engine"""
    
    def __init__(self):
        self.sanctions_lists = {
            SanctionsList.OFAC: self._load_ofac_list(),
            SanctionsList.UN: self._load_un_list(),
            SanctionsList.EU: self._load_eu_list(),
            SanctionsList.UK_HMT: self._load_uk_list(),
            SanctionsList.INTERPOL: self._load_interpol_list()
        }
        self.pep_database = self._load_pep_database()
        logger.info("Compliance automation engine initialized")
    
    def _load_ofac_list(self) -> List[Dict]:
        """Load OFAC Specially Designated Nationals (SDN) list"""
        # In production: Fetch from OFAC API or database
        return [
            {"name": "SANCTIONED ENTITY 1", "type": "individual", "country": "XX"},
            {"name": "SANCTIONED COMPANY 1", "type": "business", "country": "YY"}
        ]
    
    def _load_un_list(self) -> List[Dict]:
        """Load UN Security Council Consolidated List"""
        return [
            {"name": "UN SANCTIONED 1", "type": "individual", "country": "ZZ"}
        ]
    
    def _load_eu_list(self) -> List[Dict]:
        """Load EU Sanctions List"""
        return [
            {"name": "EU SANCTIONED 1", "type": "individual", "country": "AA"}
        ]
    
    def _load_uk_list(self) -> List[Dict]:
        """Load UK HM Treasury Sanctions List"""
        return [
            {"name": "UK SANCTIONED 1", "type": "business", "country": "BB"}
        ]
    
    def _load_interpol_list(self) -> List[Dict]:
        """Load INTERPOL Red Notices"""
        return [
            {"name": "INTERPOL WANTED 1", "type": "individual", "country": "CC"}
        ]
    
    def _load_pep_database(self) -> List[Dict]:
        """Load Politically Exposed Persons database"""
        return [
            {"name": "POLITICAL FIGURE 1", "position": "Minister", "country": "DD"},
            {"name": "POLITICAL FIGURE 2", "position": "Governor", "country": "EE"}
        ]
    
    def _fuzzy_match(self, name1: str, name2: str, threshold: float = 0.85) -> float:
        """Fuzzy string matching for name comparison"""
        # Simplified: In production, use Levenshtein distance or phonetic matching
        name1_clean = name1.upper().replace(".", "").replace(",", "")
        name2_clean = name2.upper().replace(".", "").replace(",", "")
        
        if name1_clean == name2_clean:
            return 1.0
        
        # Simple word overlap
        words1 = set(name1_clean.split())
        words2 = set(name2_clean.split())
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0
    
    async def check_sanctions(self, check: ComplianceCheck) -> SanctionsResult:
        """Screen against all sanctions lists"""
        matches = []
        lists_checked = []
        
        for list_name, sanctions_list in self.sanctions_lists.items():
            lists_checked.append(list_name.value)
            
            for sanctioned_entity in sanctions_list:
                match_score = self._fuzzy_match(check.name, sanctioned_entity["name"])
                
                if match_score >= 0.85:
                    matches.append({
                        "list": list_name.value,
                        "matched_name": sanctioned_entity["name"],
                        "match_score": round(match_score, 2),
                        "entity_type": sanctioned_entity["type"],
                        "country": sanctioned_entity.get("country")
                    })
        
        is_sanctioned = len(matches) > 0
        risk_score = max([m["match_score"] for m in matches]) if matches else 0.0
        
        logger.info(f"Sanctions check for {check.entity_id}: sanctioned={is_sanctioned}, matches={len(matches)}")
        
        return SanctionsResult(
            entity_id=check.entity_id,
            is_sanctioned=is_sanctioned,
            matches=matches,
            lists_checked=lists_checked,
            risk_score=risk_score,
            timestamp=datetime.utcnow().isoformat()
        )
    
    async def check_pep(self, check: ComplianceCheck) -> bool:
        """Check if entity is a Politically Exposed Person"""
        for pep in self.pep_database:
            match_score = self._fuzzy_match(check.name, pep["name"])
            if match_score >= 0.90:
                logger.info(f"PEP match found for {check.entity_id}: {pep['name']}")
                return True
        return False
    
    async def check_adverse_media(self, check: ComplianceCheck) -> bool:
        """Screen for adverse media mentions"""
        # In production: Use news API, web scraping, or third-party service
        # Check for: fraud, corruption, money laundering, terrorism
        
        # Simulated: Random check
        import random
        has_adverse_media = random.random() < 0.05  # 5% chance
        
        if has_adverse_media:
            logger.warning(f"Adverse media found for {check.entity_id}")
        
        return has_adverse_media
    
    async def calculate_aml_risk(self, check: ComplianceCheck, sanctions: SanctionsResult, pep: bool, adverse_media: bool) -> AMLResult:
        """Calculate overall AML/CFT risk score"""
        
        risk_score = 0.0
        flags = []
        
        # Sanctions risk
        if sanctions.is_sanctioned:
            risk_score += 0.8
            flags.append(f"Sanctioned entity (score: {sanctions.risk_score})")
        
        # PEP risk
        if pep:
            risk_score += 0.3
            flags.append("Politically Exposed Person")
        
        # Adverse media risk
        if adverse_media:
            risk_score += 0.4
            flags.append("Adverse media mentions")
        
        # High-risk jurisdiction
        if check.nationality and check.nationality in ["XX", "YY", "ZZ"]:
            risk_score += 0.2
            flags.append(f"High-risk jurisdiction: {check.nationality}")
        
        # Business without registration
        if check.entity_type == "business" and not check.business_registration:
            risk_score += 0.3
            flags.append("Business without registration number")
        
        # Normalize risk score
        risk_score = min(risk_score, 1.0)
        
        # Determine risk level
        if risk_score >= 0.7:
            risk_level = RiskLevel.CRITICAL
            action = "REJECT"
        elif risk_score >= 0.5:
            risk_level = RiskLevel.HIGH
            action = "ENHANCED_DUE_DILIGENCE"
        elif risk_score >= 0.3:
            risk_level = RiskLevel.MEDIUM
            action = "STANDARD_DUE_DILIGENCE"
        else:
            risk_level = RiskLevel.LOW
            action = "APPROVE"
        
        logger.info(f"AML risk for {check.entity_id}: level={risk_level}, score={risk_score:.2f}, action={action}")
        
        return AMLResult(
            entity_id=check.entity_id,
            risk_level=risk_level,
            risk_score=round(risk_score, 2),
            flags=flags if flags else ["No significant risk factors"],
            pep_match=pep,
            adverse_media=adverse_media,
            recommended_action=action,
            timestamp=datetime.utcnow().isoformat()
        )

# Initialize engine
compliance_engine = ComplianceAutomation()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "compliance-automation",
        "sanctions_lists": len(compliance_engine.sanctions_lists),
        "pep_records": len(compliance_engine.pep_database)
    }

@app.post("/api/v1/compliance/sanctions", response_model=SanctionsResult)
async def screen_sanctions(check: ComplianceCheck):
    """Screen entity against sanctions lists"""
    try:
        result = await compliance_engine.check_sanctions(check)
        return result
    except Exception as e:
        logger.error(f"Sanctions screening error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sanctions screening failed: {str(e)}")

@app.post("/api/v1/compliance/aml", response_model=AMLResult)
async def aml_screening(check: ComplianceCheck):
    """Comprehensive AML/CFT screening"""
    try:
        # Run all checks
        sanctions = await compliance_engine.check_sanctions(check)
        pep = await compliance_engine.check_pep(check)
        adverse_media = await compliance_engine.check_adverse_media(check)
        
        # Calculate overall risk
        result = await compliance_engine.calculate_aml_risk(check, sanctions, pep, adverse_media)
        return result
    except Exception as e:
        logger.error(f"AML screening error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AML screening failed: {str(e)}")

@app.get("/api/v1/compliance/lists")
async def get_sanctions_lists():
    """Get available sanctions lists"""
    return {
        "lists": [
            {"name": "OFAC", "description": "US Office of Foreign Assets Control", "records": len(compliance_engine.sanctions_lists[SanctionsList.OFAC])},
            {"name": "UN", "description": "United Nations Security Council", "records": len(compliance_engine.sanctions_lists[SanctionsList.UN])},
            {"name": "EU", "description": "European Union Sanctions", "records": len(compliance_engine.sanctions_lists[SanctionsList.EU])},
            {"name": "UK_HMT", "description": "UK HM Treasury", "records": len(compliance_engine.sanctions_lists[SanctionsList.UK_HMT])},
            {"name": "INTERPOL", "description": "INTERPOL Red Notices", "records": len(compliance_engine.sanctions_lists[SanctionsList.INTERPOL])}
        ],
        "pep_database": len(compliance_engine.pep_database)
    }

@app.post("/api/v1/compliance/report/sar")
async def generate_sar(entity_id: str, transaction_ids: List[str], narrative: str):
    """Generate Suspicious Activity Report (SAR)"""
    sar = {
        "report_id": f"SAR-{datetime.utcnow().strftime('%Y%m%d')}-{entity_id}",
        "entity_id": entity_id,
        "transaction_ids": transaction_ids,
        "narrative": narrative,
        "generated_at": datetime.utcnow().isoformat(),
        "status": "PENDING_SUBMISSION"
    }
    
    logger.info(f"SAR generated: {sar['report_id']}")
    return sar

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8031)
