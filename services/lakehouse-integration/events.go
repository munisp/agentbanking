package lakehouse

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// EventType represents the type of banking event
type EventType string

const (
	// Transaction events
	EventTransactionInitiated  EventType = "transaction.initiated"
	EventTransactionAuthorized EventType = "transaction.authorized"
	EventTransactionCompleted  EventType = "transaction.completed"
	EventTransactionFailed     EventType = "transaction.failed"
	EventTransactionReversed   EventType = "transaction.reversed"

	// Payment events
	EventPaymentCreated   EventType = "payment.created"
	EventPaymentProcessed EventType = "payment.processed"
	EventPaymentSettled   EventType = "payment.settled"
	EventPaymentFailed    EventType = "payment.failed"

	// Routing events
	EventRoutingDecision EventType = "routing.decision"
	EventRoutingOutcome  EventType = "routing.outcome"
	EventRoutingFallback EventType = "routing.fallback"

	// Float events
	EventFloatAllocated  EventType = "float.allocated"
	EventFloatReleased   EventType = "float.released"
	EventFloatAdjusted   EventType = "float.adjusted"
	EventFloatSettlement EventType = "float.settlement"

	// Commission events
	EventCommissionCalculated EventType = "commission.calculated"
	EventCommissionAccrued    EventType = "commission.accrued"
	EventCommissionSettled    EventType = "commission.settled"

	// Fraud events
	EventFraudScreening  EventType = "fraud.screening"
	EventFraudAlert      EventType = "fraud.alert"
	EventFraudDecision   EventType = "fraud.decision"
	EventFraudFeedback   EventType = "fraud.feedback"

	// Ledger events
	EventLedgerPosting    EventType = "ledger.posting"
	EventLedgerReservation EventType = "ledger.reservation"
	EventLedgerCommit     EventType = "ledger.commit"
	EventLedgerAbort      EventType = "ledger.abort"

	// Agent events
	EventAgentOnboarded   EventType = "agent.onboarded"
	EventAgentActivated   EventType = "agent.activated"
	EventAgentSuspended   EventType = "agent.suspended"
	EventAgentTransaction EventType = "agent.transaction"

	// Mojaloop events
	EventMojaloopQuote    EventType = "mojaloop.quote"
	EventMojaloopTransfer EventType = "mojaloop.transfer"
	EventMojaloopSettlement EventType = "mojaloop.settlement"
)

// DataLayer represents the lakehouse storage layer
type DataLayer string

const (
	LayerBronze   DataLayer = "bronze"   // Raw events
	LayerSilver   DataLayer = "silver"   // Cleaned/validated
	LayerGold     DataLayer = "gold"     // Aggregated/analytics
	LayerPlatinum DataLayer = "platinum" // ML features
)

// BankingEvent is the base event structure for all banking events
type BankingEvent struct {
	// Event metadata
	EventID       string    `json:"event_id"`
	EventType     EventType `json:"event_type"`
	EventVersion  string    `json:"event_version"`
	Timestamp     time.Time `json:"timestamp"`
	
	// Source information
	ServiceName   string `json:"service_name"`
	ServiceVersion string `json:"service_version"`
	CorrelationID string `json:"correlation_id"`
	CausationID   string `json:"causation_id,omitempty"`
	
	// Data classification
	DataLayer     DataLayer `json:"data_layer"`
	ContainsPII   bool      `json:"contains_pii"`
	
	// Idempotency
	IdempotencyKey string `json:"idempotency_key"`
	
	// Payload
	Payload       json.RawMessage `json:"payload"`
	
	// Schema reference
	SchemaID      string `json:"schema_id,omitempty"`
	SchemaVersion string `json:"schema_version,omitempty"`
}

// NewBankingEvent creates a new banking event
func NewBankingEvent(eventType EventType, serviceName string, payload interface{}) (*BankingEvent, error) {
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	eventID := uuid.New().String()
	
	return &BankingEvent{
		EventID:        eventID,
		EventType:      eventType,
		EventVersion:   "1.0",
		Timestamp:      time.Now().UTC(),
		ServiceName:    serviceName,
		ServiceVersion: "1.0.0",
		CorrelationID:  eventID, // Default to event ID, can be overridden
		DataLayer:      LayerBronze,
		ContainsPII:    false,
		IdempotencyKey: eventID,
		Payload:        payloadBytes,
	}, nil
}

// WithCorrelationID sets the correlation ID
func (e *BankingEvent) WithCorrelationID(id string) *BankingEvent {
	e.CorrelationID = id
	return e
}

// WithCausationID sets the causation ID
func (e *BankingEvent) WithCausationID(id string) *BankingEvent {
	e.CausationID = id
	return e
}

// WithIdempotencyKey sets the idempotency key
func (e *BankingEvent) WithIdempotencyKey(key string) *BankingEvent {
	e.IdempotencyKey = key
	return e
}

// WithPII marks the event as containing PII
func (e *BankingEvent) WithPII() *BankingEvent {
	e.ContainsPII = true
	return e
}

// WithSchema sets the schema reference
func (e *BankingEvent) WithSchema(schemaID, version string) *BankingEvent {
	e.SchemaID = schemaID
	e.SchemaVersion = version
	return e
}

// ToJSON serializes the event to JSON
func (e *BankingEvent) ToJSON() ([]byte, error) {
	return json.Marshal(e)
}

// TransactionPayload represents transaction event data
type TransactionPayload struct {
	TransactionID     string    `json:"transaction_id"`
	TransactionType   string    `json:"transaction_type"`
	Amount            float64   `json:"amount"`
	Currency          string    `json:"currency"`
	SourceAccount     string    `json:"source_account"`
	DestAccount       string    `json:"dest_account"`
	SourceBankCode    string    `json:"source_bank_code"`
	DestBankCode      string    `json:"dest_bank_code"`
	Status            string    `json:"status"`
	ErrorCode         string    `json:"error_code,omitempty"`
	ErrorMessage      string    `json:"error_message,omitempty"`
	InitiatedAt       time.Time `json:"initiated_at"`
	CompletedAt       time.Time `json:"completed_at,omitempty"`
	LatencyMs         int       `json:"latency_ms,omitempty"`
	AgentID           string    `json:"agent_id,omitempty"`
	CustomerID        string    `json:"customer_id,omitempty"`
	Channel           string    `json:"channel"`
	DeviceID          string    `json:"device_id,omitempty"`
	LocationLat       float64   `json:"location_lat,omitempty"`
	LocationLng       float64   `json:"location_lng,omitempty"`
}

// RoutingPayload represents routing decision event data
type RoutingPayload struct {
	TransferID           string    `json:"transfer_id"`
	SourceBankCode       string    `json:"source_bank_code"`
	DestBankCode         string    `json:"dest_bank_code"`
	Amount               float64   `json:"amount"`
	SelectedRail         string    `json:"selected_rail"`
	FallbackRails        []string  `json:"fallback_rails,omitempty"`
	Score                float64   `json:"score"`
	PredictedSuccessRate float64   `json:"predicted_success_rate"`
	PredictedLatencyMs   int       `json:"predicted_latency_ms"`
	PredictedCost        float64   `json:"predicted_cost"`
	ActualSuccessful     bool      `json:"actual_successful,omitempty"`
	ActualLatencyMs      int       `json:"actual_latency_ms,omitempty"`
	ActualCost           float64   `json:"actual_cost,omitempty"`
	ModelVersion         string    `json:"model_version,omitempty"`
	Features             map[string]interface{} `json:"features,omitempty"`
	DecisionTimestamp    time.Time `json:"decision_timestamp"`
}

// FloatPayload represents float event data
type FloatPayload struct {
	FloatID          string    `json:"float_id"`
	AgentID          string    `json:"agent_id"`
	BankCode         string    `json:"bank_code"`
	AccountNumber    string    `json:"account_number"`
	OperationType    string    `json:"operation_type"`
	Amount           float64   `json:"amount"`
	BalanceBefore    float64   `json:"balance_before"`
	BalanceAfter     float64   `json:"balance_after"`
	ReservedAmount   float64   `json:"reserved_amount,omitempty"`
	DailyLimit       float64   `json:"daily_limit"`
	DailyUsed        float64   `json:"daily_used"`
	RiskScore        float64   `json:"risk_score,omitempty"`
	Timestamp        time.Time `json:"timestamp"`
}

// CommissionPayload represents commission event data
type CommissionPayload struct {
	CommissionID     string    `json:"commission_id"`
	TransactionID    string    `json:"transaction_id"`
	AgentID          string    `json:"agent_id"`
	AgentTier        string    `json:"agent_tier"`
	TransactionType  string    `json:"transaction_type"`
	TransactionAmount float64  `json:"transaction_amount"`
	CommissionRate   float64   `json:"commission_rate"`
	CommissionAmount float64   `json:"commission_amount"`
	ParentAgentID    string    `json:"parent_agent_id,omitempty"`
	ParentCommission float64   `json:"parent_commission,omitempty"`
	Status           string    `json:"status"`
	SettlementDate   time.Time `json:"settlement_date,omitempty"`
	Timestamp        time.Time `json:"timestamp"`
}

// FraudPayload represents fraud detection event data
type FraudPayload struct {
	ScreeningID      string                 `json:"screening_id"`
	TransactionID    string                 `json:"transaction_id"`
	CustomerID       string                 `json:"customer_id,omitempty"`
	AgentID          string                 `json:"agent_id,omitempty"`
	RiskScore        float64                `json:"risk_score"`
	RiskLevel        string                 `json:"risk_level"`
	Decision         string                 `json:"decision"`
	Reasons          []string               `json:"reasons,omitempty"`
	Features         map[string]interface{} `json:"features,omitempty"`
	ModelVersion     string                 `json:"model_version"`
	LatencyMs        int                    `json:"latency_ms"`
	ManualReview     bool                   `json:"manual_review"`
	ReviewOutcome    string                 `json:"review_outcome,omitempty"`
	Timestamp        time.Time              `json:"timestamp"`
}

// LedgerPayload represents ledger posting event data
type LedgerPayload struct {
	PostingID        string    `json:"posting_id"`
	TransactionID    string    `json:"transaction_id"`
	AccountID        string    `json:"account_id"`
	DebitAccountID   string    `json:"debit_account_id"`
	CreditAccountID  string    `json:"credit_account_id"`
	Amount           uint64    `json:"amount"`
	Currency         string    `json:"currency"`
	LedgerCode       uint32    `json:"ledger_code"`
	TransferCode     uint16    `json:"transfer_code"`
	Status           string    `json:"status"`
	PendingID        string    `json:"pending_id,omitempty"`
	Flags            uint16    `json:"flags,omitempty"`
	UserData         string    `json:"user_data,omitempty"`
	Timestamp        time.Time `json:"timestamp"`
}

// MojaloopPayload represents Mojaloop event data
type MojaloopPayload struct {
	TransferID       string    `json:"transfer_id"`
	QuoteID          string    `json:"quote_id,omitempty"`
	PayerFSP         string    `json:"payer_fsp"`
	PayeeFSP         string    `json:"payee_fsp"`
	Amount           float64   `json:"amount"`
	Currency         string    `json:"currency"`
	TransferState    string    `json:"transfer_state"`
	ILPPacket        string    `json:"ilp_packet,omitempty"`
	Condition        string    `json:"condition,omitempty"`
	Fulfilment       string    `json:"fulfilment,omitempty"`
	ExpirationDate   time.Time `json:"expiration_date,omitempty"`
	SettlementID     string    `json:"settlement_id,omitempty"`
	ErrorCode        string    `json:"error_code,omitempty"`
	ErrorDescription string    `json:"error_description,omitempty"`
	Timestamp        time.Time `json:"timestamp"`
}

// AgentPayload represents agent event data
type AgentPayload struct {
	AgentID          string    `json:"agent_id"`
	AgentCode        string    `json:"agent_code"`
	AgentTier        string    `json:"agent_tier"`
	ParentAgentID    string    `json:"parent_agent_id,omitempty"`
	EventType        string    `json:"event_type"`
	Status           string    `json:"status"`
	TerritoryID      string    `json:"territory_id,omitempty"`
	TransactionCount int       `json:"transaction_count,omitempty"`
	TransactionVolume float64  `json:"transaction_volume,omitempty"`
	CommissionEarned float64   `json:"commission_earned,omitempty"`
	KYCStatus        string    `json:"kyc_status,omitempty"`
	RiskScore        float64   `json:"risk_score,omitempty"`
	Timestamp        time.Time `json:"timestamp"`
}

// Topic names for Kafka/Dapr pub/sub
const (
	TopicTransactions    = "lakehouse.transactions"
	TopicPayments        = "lakehouse.payments"
	TopicRouting         = "lakehouse.routing"
	TopicFloat           = "lakehouse.float"
	TopicCommissions     = "lakehouse.commissions"
	TopicFraud           = "lakehouse.fraud"
	TopicLedger          = "lakehouse.ledger"
	TopicMojaloop        = "lakehouse.mojaloop"
	TopicAgents          = "lakehouse.agents"
	TopicAnalytics       = "lakehouse.analytics"
	TopicMLFeatures      = "lakehouse.ml-features"
)

// GetTopicForEventType returns the appropriate topic for an event type
func GetTopicForEventType(eventType EventType) string {
	switch {
	case eventType == EventTransactionInitiated || eventType == EventTransactionAuthorized ||
		eventType == EventTransactionCompleted || eventType == EventTransactionFailed ||
		eventType == EventTransactionReversed:
		return TopicTransactions
	case eventType == EventPaymentCreated || eventType == EventPaymentProcessed ||
		eventType == EventPaymentSettled || eventType == EventPaymentFailed:
		return TopicPayments
	case eventType == EventRoutingDecision || eventType == EventRoutingOutcome ||
		eventType == EventRoutingFallback:
		return TopicRouting
	case eventType == EventFloatAllocated || eventType == EventFloatReleased ||
		eventType == EventFloatAdjusted || eventType == EventFloatSettlement:
		return TopicFloat
	case eventType == EventCommissionCalculated || eventType == EventCommissionAccrued ||
		eventType == EventCommissionSettled:
		return TopicCommissions
	case eventType == EventFraudScreening || eventType == EventFraudAlert ||
		eventType == EventFraudDecision || eventType == EventFraudFeedback:
		return TopicFraud
	case eventType == EventLedgerPosting || eventType == EventLedgerReservation ||
		eventType == EventLedgerCommit || eventType == EventLedgerAbort:
		return TopicLedger
	case eventType == EventMojaloopQuote || eventType == EventMojaloopTransfer ||
		eventType == EventMojaloopSettlement:
		return TopicMojaloop
	case eventType == EventAgentOnboarded || eventType == EventAgentActivated ||
		eventType == EventAgentSuspended || eventType == EventAgentTransaction:
		return TopicAgents
	default:
		return TopicAnalytics
	}
}
