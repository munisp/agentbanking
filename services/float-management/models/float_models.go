package models

import (
	"time"
	"github.com/google/uuid"
	"gorm.io/gorm"
)

// FloatStatus represents the status of a float facility
type FloatStatus string

const (
	FloatStatusPending   FloatStatus = "pending"
	FloatStatusActive    FloatStatus = "active"
	FloatStatusSuspended FloatStatus = "suspended"
	FloatStatusClosed    FloatStatus = "closed"
	FloatStatusFrozen    FloatStatus = "frozen"
)

// FloatTransactionType represents the type of float transaction
type FloatTransactionType string

const (
	FloatTransactionAdvance     FloatTransactionType = "advance"
	FloatTransactionUtilization FloatTransactionType = "utilization"
	FloatTransactionSettlement  FloatTransactionType = "settlement"
	FloatTransactionInterest    FloatTransactionType = "interest"
	FloatTransactionFee         FloatTransactionType = "fee"
	FloatTransactionAdjustment  FloatTransactionType = "adjustment"
	FloatTransactionReversal    FloatTransactionType = "reversal"
)

// SettlementStatus represents the status of a settlement
type SettlementStatus string

const (
	SettlementStatusPending    SettlementStatus = "pending"
	SettlementStatusProcessing SettlementStatus = "processing"
	SettlementStatusCompleted  SettlementStatus = "completed"
	SettlementStatusFailed     SettlementStatus = "failed"
	SettlementStatusPartial    SettlementStatus = "partial"
	SettlementStatusCancelled  SettlementStatus = "cancelled"
)

// RiskLevel represents the risk level of an agent
type RiskLevel string

const (
	RiskLevelLow      RiskLevel = "low"
	RiskLevelMedium   RiskLevel = "medium"
	RiskLevelHigh     RiskLevel = "high"
	RiskLevelCritical RiskLevel = "critical"
)

// AgentTier represents the tier classification of agents
type AgentTier string

const (
	AgentTierBasic    AgentTier = "basic"
	AgentTierStandard AgentTier = "standard"
	AgentTierPremium  AgentTier = "premium"
	AgentTierElite    AgentTier = "elite"
)

// AgentFloat represents the main float facility for an agent
type AgentFloat struct {
	ID                    uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentID               uuid.UUID  `json:"agent_id" gorm:"not null;uniqueIndex"`
	AgentTier             AgentTier  `json:"agent_tier" gorm:"not null;default:'basic'"`
	FloatLimit            float64    `json:"float_limit" gorm:"not null;default:0"`
	UtilizedAmount        float64    `json:"utilized_amount" gorm:"not null;default:0"`
	AvailableFloat        float64    `json:"available_float" gorm:"not null;default:0"`
	ReservedAmount        float64    `json:"reserved_amount" gorm:"not null;default:0"`
	InterestRate          float64    `json:"interest_rate" gorm:"type:decimal(5,4);not null;default:0.0300"`
	FeeRate               float64    `json:"fee_rate" gorm:"type:decimal(5,4);not null;default:0.0050"`
	Currency              string     `json:"currency" gorm:"not null;default:'NGN'"`
	Status                FloatStatus `json:"status" gorm:"not null;default:'pending'"`
	RiskLevel             RiskLevel  `json:"risk_level" gorm:"not null;default:'medium'"`
	CreditScore           float64    `json:"credit_score" gorm:"type:decimal(5,2);default:50.0"`
	LastAssessmentDate    *time.Time `json:"last_assessment_date"`
	NextAssessmentDate    *time.Time `json:"next_assessment_date"`
	LastSettlementDate    *time.Time `json:"last_settlement_date"`
	NextSettlementDate    *time.Time `json:"next_settlement_date"`
	SettlementFrequency   string     `json:"settlement_frequency" gorm:"default:'daily'"`
	AutoSettlement        bool       `json:"auto_settlement" gorm:"default:true"`
	CollateralRequired    bool       `json:"collateral_required" gorm:"default:false"`
	CollateralAmount      float64    `json:"collateral_amount" gorm:"default:0"`
	GuarantorRequired     bool       `json:"guarantor_required" gorm:"default:false"`
	InsuranceCoverage     bool       `json:"insurance_coverage" gorm:"default:false"`
	InsurancePremium      float64    `json:"insurance_premium" gorm:"default:0"`
	DaysOutstanding       int        `json:"days_outstanding" gorm:"default:0"`
	MaxDaysOutstanding    int        `json:"max_days_outstanding" gorm:"default:7"`
	TotalInterestCharged  float64    `json:"total_interest_charged" gorm:"default:0"`
	TotalFeesCharged      float64    `json:"total_fees_charged" gorm:"default:0"`
	TotalSettlements      int        `json:"total_settlements" gorm:"default:0"`
	SuccessfulSettlements int        `json:"successful_settlements" gorm:"default:0"`
	FailedSettlements     int        `json:"failed_settlements" gorm:"default:0"`
	SettlementSuccessRate float64    `json:"settlement_success_rate" gorm:"type:decimal(5,2);default:100.0"`
	ApprovedBy            *uuid.UUID `json:"approved_by"`
	ApprovedAt            *time.Time `json:"approved_at"`
	ActivatedAt           *time.Time `json:"activated_at"`
	SuspendedAt           *time.Time `json:"suspended_at"`
	ClosedAt              *time.Time `json:"closed_at"`
	SuspensionReason      string     `json:"suspension_reason"`
	ClosureReason         string     `json:"closure_reason"`
	Notes                 string     `json:"notes" gorm:"type:text"`
	Metadata              JSON       `json:"metadata" gorm:"type:jsonb"`
	CreatedAt             time.Time  `json:"created_at"`
	UpdatedAt             time.Time  `json:"updated_at"`
	CreatedBy             *uuid.UUID `json:"created_by"`
	UpdatedBy             *uuid.UUID `json:"updated_by"`
	
	// Relationships
	Transactions []FloatTransaction `json:"transactions,omitempty" gorm:"foreignKey:AgentFloatID"`
	Settlements  []FloatSettlement  `json:"settlements,omitempty" gorm:"foreignKey:AgentFloatID"`
	Assessments  []RiskAssessment   `json:"assessments,omitempty" gorm:"foreignKey:AgentFloatID"`
}

// FloatTransaction represents individual float transactions
type FloatTransaction struct {
	ID                uuid.UUID            `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID      uuid.UUID            `json:"agent_float_id" gorm:"not null;index"`
	AgentID           uuid.UUID            `json:"agent_id" gorm:"not null;index"`
	TransactionRef    string               `json:"transaction_ref" gorm:"uniqueIndex;not null"`
	RelatedTxnID      *uuid.UUID           `json:"related_txn_id" gorm:"index"`
	Type              FloatTransactionType `json:"type" gorm:"not null"`
	Amount            float64              `json:"amount" gorm:"not null"`
	Currency          string               `json:"currency" gorm:"not null;default:'NGN'"`
	FloatBefore       float64              `json:"float_before" gorm:"not null"`
	FloatAfter        float64              `json:"float_after" gorm:"not null"`
	UtilizedBefore    float64              `json:"utilized_before" gorm:"not null"`
	UtilizedAfter     float64              `json:"utilized_after" gorm:"not null"`
	AvailableBefore   float64              `json:"available_before" gorm:"not null"`
	AvailableAfter    float64              `json:"available_after" gorm:"not null"`
	InterestRate      float64              `json:"interest_rate" gorm:"type:decimal(5,4);default:0"`
	InterestAmount    float64              `json:"interest_amount" gorm:"default:0"`
	FeeRate           float64              `json:"fee_rate" gorm:"type:decimal(5,4);default:0"`
	FeeAmount         float64              `json:"fee_amount" gorm:"default:0"`
	Description       string               `json:"description"`
	Status            string               `json:"status" gorm:"default:'completed'"`
	SettlementID      *uuid.UUID           `json:"settlement_id" gorm:"index"`
	ProcessedBy       *uuid.UUID           `json:"processed_by"`
	ProcessedAt       time.Time            `json:"processed_at" gorm:"default:CURRENT_TIMESTAMP"`
	ReversedAt        *time.Time           `json:"reversed_at"`
	ReversedBy        *uuid.UUID           `json:"reversed_by"`
	ReversalReason    string               `json:"reversal_reason"`
	Metadata          JSON                 `json:"metadata" gorm:"type:jsonb"`
	CreatedAt         time.Time            `json:"created_at"`
	UpdatedAt         time.Time            `json:"updated_at"`
	
	// Relationships
	AgentFloat *AgentFloat `json:"agent_float,omitempty" gorm:"foreignKey:AgentFloatID"`
}

// FloatSettlement represents settlement records
type FloatSettlement struct {
	ID                    uuid.UUID        `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID          uuid.UUID        `json:"agent_float_id" gorm:"not null;index"`
	AgentID               uuid.UUID        `json:"agent_id" gorm:"not null;index"`
	SettlementRef         string           `json:"settlement_ref" gorm:"uniqueIndex;not null"`
	SettlementType        string           `json:"settlement_type" gorm:"not null;default:'regular'"`
	OutstandingFloat      float64          `json:"outstanding_float" gorm:"not null"`
	SettlementAmount      float64          `json:"settlement_amount" gorm:"not null"`
	InterestCharged       float64          `json:"interest_charged" gorm:"default:0"`
	FeesCharged           float64          `json:"fees_charged" gorm:"default:0"`
	PenaltyCharged        float64          `json:"penalty_charged" gorm:"default:0"`
	TotalAmountDue        float64          `json:"total_amount_due" gorm:"not null"`
	AmountSettled         float64          `json:"amount_settled" gorm:"default:0"`
	RemainingBalance      float64          `json:"remaining_balance" gorm:"default:0"`
	Currency              string           `json:"currency" gorm:"not null;default:'NGN'"`
	Status                SettlementStatus `json:"status" gorm:"not null;default:'pending'"`
	SettlementMethod      string           `json:"settlement_method" gorm:"default:'auto_deduction'"`
	PaymentReference      string           `json:"payment_reference"`
	BankAccount           string           `json:"bank_account"`
	ScheduledDate         time.Time        `json:"scheduled_date" gorm:"not null"`
	DueDate               time.Time        `json:"due_date" gorm:"not null"`
	ProcessedAt           *time.Time       `json:"processed_at"`
	CompletedAt           *time.Time       `json:"completed_at"`
	FailedAt              *time.Time       `json:"failed_at"`
	CancelledAt           *time.Time       `json:"cancelled_at"`
	FailureReason         string           `json:"failure_reason"`
	RetryCount            int              `json:"retry_count" gorm:"default:0"`
	MaxRetries            int              `json:"max_retries" gorm:"default:3"`
	NextRetryAt           *time.Time       `json:"next_retry_at"`
	EscalatedAt           *time.Time       `json:"escalated_at"`
	EscalationLevel       int              `json:"escalation_level" gorm:"default:0"`
	ProcessedBy           *uuid.UUID       `json:"processed_by"`
	ApprovedBy            *uuid.UUID       `json:"approved_by"`
	Notes                 string           `json:"notes" gorm:"type:text"`
	Metadata              JSON             `json:"metadata" gorm:"type:jsonb"`
	CreatedAt             time.Time        `json:"created_at"`
	UpdatedAt             time.Time        `json:"updated_at"`
	CreatedBy             *uuid.UUID       `json:"created_by"`
	
	// Relationships
	AgentFloat   *AgentFloat        `json:"agent_float,omitempty" gorm:"foreignKey:AgentFloatID"`
	Transactions []FloatTransaction `json:"transactions,omitempty" gorm:"foreignKey:SettlementID"`
}

// RiskAssessment represents risk assessment records
type RiskAssessment struct {
	ID                        uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID              uuid.UUID  `json:"agent_float_id" gorm:"not null;index"`
	AgentID                   uuid.UUID  `json:"agent_id" gorm:"not null;index"`
	AssessmentRef             string     `json:"assessment_ref" gorm:"uniqueIndex;not null"`
	AssessmentType            string     `json:"assessment_type" gorm:"not null;default:'periodic'"`
	OverallScore              float64    `json:"overall_score" gorm:"type:decimal(5,2);not null"`
	CreditScore               float64    `json:"credit_score" gorm:"type:decimal(5,2);not null"`
	TransactionVolumeScore    float64    `json:"transaction_volume_score" gorm:"type:decimal(5,2)"`
	SettlementHistoryScore    float64    `json:"settlement_history_score" gorm:"type:decimal(5,2)"`
	BusinessStabilityScore    float64    `json:"business_stability_score" gorm:"type:decimal(5,2)"`
	GeographicRiskScore       float64    `json:"geographic_risk_score" gorm:"type:decimal(5,2)"`
	KYCComplianceScore        float64    `json:"kyc_compliance_score" gorm:"type:decimal(5,2)"`
	FinancialHealthScore      float64    `json:"financial_health_score" gorm:"type:decimal(5,2)"`
	BehavioralScore           float64    `json:"behavioral_score" gorm:"type:decimal(5,2)"`
	RiskLevel                 RiskLevel  `json:"risk_level" gorm:"not null"`
	RecommendedLimit          float64    `json:"recommended_limit" gorm:"not null"`
	CurrentLimit              float64    `json:"current_limit" gorm:"not null"`
	LimitAdjustmentRecommended bool      `json:"limit_adjustment_recommended" gorm:"default:false"`
	RecommendedAdjustment     float64    `json:"recommended_adjustment" gorm:"default:0"`
	RiskFactors               []string   `json:"risk_factors" gorm:"type:text[]"`
	PositiveFactors           []string   `json:"positive_factors" gorm:"type:text[]"`
	Recommendations           []string   `json:"recommendations" gorm:"type:text[]"`
	ModelVersion              string     `json:"model_version" gorm:"default:'1.0'"`
	AssessmentDate            time.Time  `json:"assessment_date" gorm:"not null"`
	ValidUntil                time.Time  `json:"valid_until" gorm:"not null"`
	AssessedBy                *uuid.UUID `json:"assessed_by"`
	ReviewedBy                *uuid.UUID `json:"reviewed_by"`
	ReviewedAt                *time.Time `json:"reviewed_at"`
	ApprovedBy                *uuid.UUID `json:"approved_by"`
	ApprovedAt                *time.Time `json:"approved_at"`
	ImplementedAt             *time.Time `json:"implemented_at"`
	Notes                     string     `json:"notes" gorm:"type:text"`
	Metadata                  JSON       `json:"metadata" gorm:"type:jsonb"`
	CreatedAt                 time.Time  `json:"created_at"`
	UpdatedAt                 time.Time  `json:"updated_at"`
	
	// Relationships
	AgentFloat *AgentFloat `json:"agent_float,omitempty" gorm:"foreignKey:AgentFloatID"`
}

// FloatLimit represents dynamic float limits
type FloatLimit struct {
	ID              uuid.UUID  `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID    uuid.UUID  `json:"agent_float_id" gorm:"not null;index"`
	AgentID         uuid.UUID  `json:"agent_id" gorm:"not null;index"`
	AgentTier       AgentTier  `json:"agent_tier" gorm:"not null"`
	LimitType       string     `json:"limit_type" gorm:"not null;default:'credit_limit'"`
	BaseLimit       float64    `json:"base_limit" gorm:"not null"`
	AdjustedLimit   float64    `json:"adjusted_limit" gorm:"not null"`
	UtilizedAmount  float64    `json:"utilized_amount" gorm:"default:0"`
	AvailableLimit  float64    `json:"available_limit" gorm:"not null"`
	UtilizationRate float64    `json:"utilization_rate" gorm:"type:decimal(5,2);default:0"`
	Currency        string     `json:"currency" gorm:"not null;default:'NGN'"`
	EffectiveFrom   time.Time  `json:"effective_from" gorm:"not null"`
	EffectiveTo     *time.Time `json:"effective_to"`
	IsActive        bool       `json:"is_active" gorm:"default:true"`
	AdjustmentReason string    `json:"adjustment_reason"`
	AdjustedBy      *uuid.UUID `json:"adjusted_by"`
	AdjustedAt      *time.Time `json:"adjusted_at"`
	CreatedAt       time.Time  `json:"created_at"`
	UpdatedAt       time.Time  `json:"updated_at"`
	
	// Relationships
	AgentFloat *AgentFloat `json:"agent_float,omitempty" gorm:"foreignKey:AgentFloatID"`
}

// FloatAlert represents float-related alerts
type FloatAlert struct {
	ID                uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	AgentFloatID      uuid.UUID `json:"agent_float_id" gorm:"not null;index"`
	AgentID           uuid.UUID `json:"agent_id" gorm:"not null;index"`
	AlertType         string    `json:"alert_type" gorm:"not null"`
	Severity          string    `json:"severity" gorm:"not null;default:'medium'"`
	Title             string    `json:"title" gorm:"not null"`
	Message           string    `json:"message" gorm:"not null"`
	TriggerValue      *float64  `json:"trigger_value"`
	ThresholdValue    *float64  `json:"threshold_value"`
	Currency          string    `json:"currency" gorm:"default:'NGN'"`
	Status            string    `json:"status" gorm:"default:'active'"`
	IsResolved        bool      `json:"is_resolved" gorm:"default:false"`
	AcknowledgedBy    *uuid.UUID `json:"acknowledged_by"`
	AcknowledgedAt    *time.Time `json:"acknowledged_at"`
	ResolvedBy        *uuid.UUID `json:"resolved_by"`
	ResolvedAt        *time.Time `json:"resolved_at"`
	EscalatedAt       *time.Time `json:"escalated_at"`
	EscalationLevel   int       `json:"escalation_level" gorm:"default:0"`
	ActionRequired    bool      `json:"action_required" gorm:"default:false"`
	ActionTaken       string    `json:"action_taken"`
	ActionTakenBy     *uuid.UUID `json:"action_taken_by"`
	ActionTakenAt     *time.Time `json:"action_taken_at"`
	Metadata          JSON      `json:"metadata" gorm:"type:jsonb"`
	CreatedAt         time.Time `json:"created_at"`
	UpdatedAt         time.Time `json:"updated_at"`
	
	// Relationships
	AgentFloat *AgentFloat `json:"agent_float,omitempty" gorm:"foreignKey:AgentFloatID"`
}

// FloatConfiguration represents system-wide float configuration
type FloatConfiguration struct {
	ID                        uuid.UUID `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	ConfigKey                 string    `json:"config_key" gorm:"uniqueIndex;not null"`
	ConfigValue               string    `json:"config_value" gorm:"not null"`
	ConfigType                string    `json:"config_type" gorm:"not null;default:'string'"`
	Description               string    `json:"description"`
	Category                  string    `json:"category" gorm:"not null;default:'general'"`
	IsActive                  bool      `json:"is_active" gorm:"default:true"`
	RequiresRestart           bool      `json:"requires_restart" gorm:"default:false"`
	LastModifiedBy            *uuid.UUID `json:"last_modified_by"`
	LastModifiedAt            *time.Time `json:"last_modified_at"`
	CreatedAt                 time.Time `json:"created_at"`
	UpdatedAt                 time.Time `json:"updated_at"`
}

// JSON type for JSONB fields
type JSON map[string]interface{}

// BeforeCreate hook for AgentFloat
func (af *AgentFloat) BeforeCreate(tx *gorm.DB) error {
	if af.ID == uuid.Nil {
		af.ID = uuid.New()
	}
	af.AvailableFloat = af.FloatLimit - af.UtilizedAmount
	return nil
}

// BeforeUpdate hook for AgentFloat
func (af *AgentFloat) BeforeUpdate(tx *gorm.DB) error {
	af.AvailableFloat = af.FloatLimit - af.UtilizedAmount - af.ReservedAmount
	if af.TotalSettlements > 0 {
		af.SettlementSuccessRate = float64(af.SuccessfulSettlements) / float64(af.TotalSettlements) * 100
	}
	return nil
}

// BeforeCreate hook for FloatTransaction
func (ft *FloatTransaction) BeforeCreate(tx *gorm.DB) error {
	if ft.ID == uuid.Nil {
		ft.ID = uuid.New()
	}
	if ft.TransactionRef == "" {
		ft.TransactionRef = generateTransactionRef()
	}
	return nil
}

// BeforeCreate hook for FloatSettlement
func (fs *FloatSettlement) BeforeCreate(tx *gorm.DB) error {
	if fs.ID == uuid.Nil {
		fs.ID = uuid.New()
	}
	if fs.SettlementRef == "" {
		fs.SettlementRef = generateSettlementRef()
	}
	fs.TotalAmountDue = fs.OutstandingFloat + fs.InterestCharged + fs.FeesCharged + fs.PenaltyCharged
	fs.RemainingBalance = fs.TotalAmountDue - fs.AmountSettled
	return nil
}

// Helper functions
func generateTransactionRef() string {
	return "FTX" + uuid.New().String()[:8]
}

func generateSettlementRef() string {
	return "FST" + uuid.New().String()[:8]
}

func generateAssessmentRef() string {
	return "FRA" + uuid.New().String()[:8]
}

// TableName methods for custom table names
func (AgentFloat) TableName() string {
	return "agent_floats"
}

func (FloatTransaction) TableName() string {
	return "float_transactions"
}

func (FloatSettlement) TableName() string {
	return "float_settlements"
}

func (RiskAssessment) TableName() string {
	return "float_risk_assessments"
}

func (FloatLimit) TableName() string {
	return "float_limits"
}

func (FloatAlert) TableName() string {
	return "float_alerts"
}

func (FloatConfiguration) TableName() string {
	return "float_configurations"
}

