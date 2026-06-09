from pydantic import BaseModel, Field, conint, constr
from typing import Optional, List
from datetime import datetime
from models import CaseStatus, RiskLevel

# --- Base Schemas ---

class EnhancedKYCCaseBase(BaseModel):
    customer_id: constr(min_length=1, max_length=100) = Field(..., example="CUST-12345", description="Unique identifier for the customer.")
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM, description="The assigned risk level for the customer.")
    assigned_analyst_id: Optional[constr(min_length=1, max_length=100)] = Field(None, example="ANALYST-001", description="ID of the analyst handling the case.")

class EDDDetailBase(BaseModel):
    source_of_funds_verified: bool = Field(False, description="Whether the source of funds has been verified.")
    source_of_wealth_description: Optional[constr(max_length=1000)] = Field(None, description="Description of the customer's source of wealth.")
    ubo_identified: bool = Field(False, description="Whether the Ultimate Beneficial Owner (UBO) has been identified.")
    ubo_details: Optional[constr(max_length=1000)] = Field(None, description="Details about the UBO.")
    adverse_media_hits: conint(ge=0) = Field(0, description="Number of adverse media hits found.")
    sanctions_list_hit: bool = Field(False, description="Whether a sanctions list hit was found.")
    suspicious_activity_report_filed: bool = Field(False, description="Whether a Suspicious Activity Report (SAR) has been filed.")
    transaction_volume_anomaly_score: float = Field(0.0, ge=0.0, le=10.0, description="Anomaly score from transaction monitoring (0.0 to 10.0).")
    analyst_notes: Optional[constr(max_length=2000)] = Field(None, description="Analyst's final notes and conclusion.")

# --- Create Schemas (Input) ---

class EnhancedKYCCaseCreate(EnhancedKYCCaseBase):
    # customer_id is required for creation
    pass

class EDDDetailCreate(EDDDetailBase):
    # EDD details are typically created after the case is initiated
    pass

# --- Update Schemas (Input) ---

class EnhancedKYCCaseUpdate(BaseModel):
    risk_level: Optional[RiskLevel] = Field(None, description="The assigned risk level for the customer.")
    status: Optional[CaseStatus] = Field(None, description="The current status of the case.")
    assigned_analyst_id: Optional[constr(min_length=1, max_length=100)] = Field(None, description="ID of the analyst handling the case.")

class EDDDetailUpdate(EDDDetailBase):
    # All fields are optional for update
    pass

# --- Read Schemas (Output) ---

class EDDDetailRead(EDDDetailBase):
    id: int
    kyc_case_id: int
    
    class Config:
        from_attributes = True

class EnhancedKYCCaseRead(EnhancedKYCCaseBase):
    id: int
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    
    # Include the details relationship
    details: Optional[EDDDetailRead] = None
    
    class Config:
        from_attributes = True

# --- List Schema ---

class EnhancedKYCCaseList(BaseModel):
    cases: List[EnhancedKYCCaseRead]
    total: int
    
# --- Status Update Schema ---

class CaseStatusUpdate(BaseModel):
    status: CaseStatus = Field(..., description="The new status for the case.")
    analyst_notes: Optional[constr(max_length=2000)] = Field(None, description="Notes related to the status change.")