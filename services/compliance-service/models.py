"""
models.py: SQLAlchemy models and Pydantic schemas for the compliance-service.
"""
import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field
from pydantic.types import UUID4

# Assuming config.py is in the same directory and defines 'Base'
from config import Base 

# --- Enumerations ---

class RuleCategory(str, enum.Enum):
    """Categories for compliance rules."""
    FINANCIAL = "Financial"
    DATA_PRIVACY = "Data Privacy"
    SECURITY = "Security"
    OPERATIONAL = "Operational"
    OTHER = "Other"

class RuleSeverity(str, enum.Enum):
    """Severity levels for rule violations."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class CheckStatus(str, enum.Enum):
    """Status of a compliance check."""
    PASS = "Pass"
    FAIL = "Fail"
    PENDING = "Pending"
    EXEMPT = "Exempt"

# --- SQLAlchemy Models ---

class ComplianceRule(Base):
    """
    Represents a single compliance rule that needs to be enforced.
    """
    __tablename__ = "compliance_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False, doc="Short, unique name for the rule.")
    description = Column(Text, nullable=False, doc="Detailed description of the rule and its requirements.")
    category = Column(Enum(RuleCategory), default=RuleCategory.OTHER, nullable=False, index=True, doc="The category of the rule (e.g., Financial, Data Privacy).")
    severity = Column(Enum(RuleSeverity), default=RuleSeverity.MEDIUM, nullable=False, doc="The severity of a violation of this rule.")
    is_active = Column(Boolean, default=True, nullable=False, index=True, doc="Whether the rule is currently active and being enforced.")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    checks = relationship("ComplianceCheck", back_populates="rule", cascade="all, delete-orphan")
    violations = relationship("Violation", back_populates="rule", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ComplianceRule(id={self.id}, name='{self.name}', category='{self.category.value}')>"

class ComplianceCheck(Base):
    """
    Represents a single instance of a compliance rule check against an entity.
    """
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("compliance_rules.id"), nullable=False, index=True, doc="Foreign key to the ComplianceRule.")
    entity_id = Column(String, nullable=False, index=True, doc="The ID of the entity being checked (e.g., user_id, transaction_id).")
    entity_type = Column(String, nullable=False, index=True, doc="The type of the entity (e.g., 'User', 'Transaction', 'Account').")
    status = Column(Enum(CheckStatus), default=CheckStatus.PENDING, nullable=False, index=True, doc="The result status of the check.")
    check_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, doc="The time the check was performed.")
    details = Column(Text, doc="Additional details or context about the check.")

    # Relationships
    rule = relationship("ComplianceRule", back_populates="checks")
    violation = relationship("Violation", back_populates="check", uselist=False, cascade="all, delete-orphan")

    # Composite index for fast lookups of a specific rule check on an entity
    __table_args__ = (
        Index('idx_entity_rule', 'entity_id', 'entity_type', 'rule_id'),
    )

    def __repr__(self):
        return f"<ComplianceCheck(id={self.id}, rule_id={self.rule_id}, entity='{self.entity_type}:{self.entity_id}', status='{self.status.value}')>"

class Violation(Base):
    """
    Represents a violation recorded when a ComplianceCheck fails.
    """
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    check_id = Column(Integer, ForeignKey("compliance_checks.id"), unique=True, nullable=False, index=True, doc="Foreign key to the ComplianceCheck that failed.")
    rule_id = Column(Integer, ForeignKey("compliance_rules.id"), nullable=False, index=True, doc="Foreign key to the ComplianceRule.")
    entity_id = Column(String, nullable=False, index=True, doc="The ID of the entity that violated the rule.")
    entity_type = Column(String, nullable=False, index=True, doc="The type of the entity that violated the rule.")
    violation_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, doc="The time the violation was recorded.")
    is_resolved = Column(Boolean, default=False, nullable=False, index=True, doc="Flag indicating if the violation has been resolved.")
    resolution_details = Column(Text, doc="Details on how the violation was resolved.")
    resolution_timestamp = Column(DateTime, doc="The time the violation was resolved.")

    # Relationships
    check = relationship("ComplianceCheck", back_populates="violation")
    rule = relationship("ComplianceRule", back_populates="violations")

    def __repr__(self):
        return f"<Violation(id={self.id}, entity='{self.entity_type}:{self.entity_id}', resolved={self.is_resolved})>"

# --- Pydantic Schemas ---

# Shared base schema for common fields
class ComplianceBase(BaseModel):
    """Base model for shared configuration."""
    class Config:
        from_attributes = True # Alias for orm_mode = True in Pydantic v2

# --- ComplianceRule Schemas ---

class ComplianceRuleCreate(ComplianceBase):
    """Schema for creating a new compliance rule."""
    name: str = Field(..., max_length=100, description="Short, unique name for the rule.")
    description: str = Field(..., description="Detailed description of the rule and its requirements.")
    category: RuleCategory = Field(RuleCategory.OTHER, description="The category of the rule.")
    severity: RuleSeverity = Field(RuleSeverity.MEDIUM, description="The severity of a violation of this rule.")
    is_active: bool = Field(True, description="Whether the rule is currently active.")

class ComplianceRuleUpdate(ComplianceBase):
    """Schema for updating an existing compliance rule."""
    name: Optional[str] = Field(None, max_length=100, description="Short, unique name for the rule.")
    description: Optional[str] = Field(None, description="Detailed description of the rule and its requirements.")
    category: Optional[RuleCategory] = Field(None, description="The category of the rule.")
    severity: Optional[RuleSeverity] = Field(None, description="The severity of a violation of this rule.")
    is_active: Optional[bool] = Field(None, description="Whether the rule is currently active.")

class ComplianceRuleRead(ComplianceBase):
    """Schema for reading a compliance rule (response model)."""
    id: int
    name: str
    description: str
    category: RuleCategory
    severity: RuleSeverity
    is_active: bool
    created_at: datetime
    updated_at: datetime

# --- ComplianceCheck Schemas ---

class ComplianceCheckCreate(ComplianceBase):
    """Schema for initiating a new compliance check."""
    rule_id: int = Field(..., description="The ID of the rule to check against.")
    entity_id: str = Field(..., max_length=255, description="The ID of the entity being checked.")
    entity_type: str = Field(..., max_length=50, description="The type of the entity (e.g., 'User').")
    details: Optional[str] = Field(None, description="Additional context for the check.")

class ComplianceCheckUpdate(ComplianceBase):
    """Schema for updating the result of a compliance check."""
    status: CheckStatus = Field(..., description="The final status of the check.")
    details: Optional[str] = Field(None, description="Additional details or context about the check result.")

class ComplianceCheckRead(ComplianceBase):
    """Schema for reading a compliance check (response model)."""
    id: int
    rule_id: int
    entity_id: str
    entity_type: str
    status: CheckStatus
    check_timestamp: datetime
    details: Optional[str] = None
    
    # Nested rule information for convenience
    rule: ComplianceRuleRead

# --- Violation Schemas ---

class ViolationRead(ComplianceBase):
    """Schema for reading a violation (response model)."""
    id: int
    check_id: int
    rule_id: int
    entity_id: str
    entity_type: str
    violation_timestamp: datetime
    is_resolved: bool
    resolution_details: Optional[str] = None
    resolution_timestamp: Optional[datetime] = None

    # Nested check and rule information
    check: ComplianceCheckRead
    rule: ComplianceRuleRead

class ViolationResolve(ComplianceBase):
    """Schema for resolving an existing violation."""
    is_resolved: bool = Field(True, description="Set to True to mark the violation as resolved.")
    resolution_details: str = Field(..., description="Details on how the violation was resolved.")
