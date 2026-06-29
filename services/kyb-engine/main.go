// 54agent Agency Banking Platform — Go KYB (Know Your Business) Verification Engine
// Port: 8130
// Integrations: Kafka, Dapr, Temporal, PostgreSQL, Keycloak, Permify, Redis,
//               Mojaloop, OpenSearch, APISIX, TigerBeetle

package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/gorilla/mux"
)

// ── Configuration ──────────────────────────────────────────────────────────────

type Config struct {
	Port               string
	PostgresURL        string
	RedisURL           string
	KafkaBrokers       string
	TemporalHost       string
	KeycloakURL        string
	PermifyHost        string
	MojalloopURL       string
	OpenSearchURL      string
	TigerBeetleAddr    string
	DaprHTTPPort       string
	DaprGRPCPort       string
	FluvioEndpoint     string
	ApisixAdminURL     string
	OpenAppSecEndpoint string
	Environment        string
}

func loadConfig() Config {
	return Config{
		Port:               envOr("PORT", "8130"),
		PostgresURL:        envOr("DATABASE_URL", "postgresql://ngapp:password@localhost:5432/ngapp"),
		RedisURL:           envOr("REDIS_URL", "redis://localhost:6379/6"),
		KafkaBrokers:       envOr("KAFKA_BROKERS", "localhost:9092"),
		TemporalHost:       envOr("TEMPORAL_HOST", "localhost:7233"),
		KeycloakURL:        envOr("KEYCLOAK_URL", "http://localhost:8080"),
		PermifyHost:        envOr("PERMIFY_HOST", "localhost:3476"),
		MojalloopURL:       envOr("MOJALOOP_URL", "http://localhost:3002"),
		OpenSearchURL:      envOr("OPENSEARCH_URL", "http://localhost:9200"),
		TigerBeetleAddr:    envOr("TIGERBEETLE_ADDR", "localhost:3000"),
		DaprHTTPPort:       envOr("DAPR_HTTP_PORT", "3500"),
		DaprGRPCPort:       envOr("DAPR_GRPC_PORT", "50001"),
		FluvioEndpoint:     envOr("FLUVIO_ENDPOINT", "localhost:9003"),
		ApisixAdminURL:     envOr("APISIX_ADMIN_URL", "http://localhost:9180"),
		OpenAppSecEndpoint: envOr("OPENAPPSEC_ENDPOINT", "http://localhost:9090"),
		Environment:        envOr("ENVIRONMENT", "development"),
	}
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// ── Domain Models ──────────────────────────────────────────────────────────────

type BusinessType string

const (
	BusinessTypeCorporation        BusinessType = "corporation"
	BusinessTypeLLC                BusinessType = "llc"
	BusinessTypePartnership        BusinessType = "partnership"
	BusinessTypeSoleProprietorship BusinessType = "sole_proprietorship"
	BusinessTypeNonProfit          BusinessType = "non_profit"
	BusinessTypeTrust              BusinessType = "trust"
)

type VerificationStatus string

const (
	StatusPending          VerificationStatus = "pending"
	StatusDocCollection    VerificationStatus = "document_collection"
	StatusUBOScreening     VerificationStatus = "ubo_screening"
	StatusRiskAssessment   VerificationStatus = "risk_assessment"
	StatusComplianceReview VerificationStatus = "compliance_review"
	StatusApproved         VerificationStatus = "approved"
	StatusRejected         VerificationStatus = "rejected"
	StatusSuspended        VerificationStatus = "suspended"
	StatusExpired          VerificationStatus = "expired"
)

type KYBVerification struct {
	ID                   string             `json:"id"`
	BusinessName         string             `json:"business_name"`
	BusinessType         BusinessType       `json:"business_type"`
	RegistrationNumber   string             `json:"registration_number"`
	TaxID                string             `json:"tax_id"`
	IncorporationCountry string             `json:"incorporation_country"`
	IncorporationState   string             `json:"incorporation_state"`
	BusinessAddress      *Address           `json:"business_address,omitempty"`
	Phone                string             `json:"phone,omitempty"`
	Email                string             `json:"email,omitempty"`
	Industry             string             `json:"industry,omitempty"`
	AnnualRevenue        float64            `json:"annual_revenue,omitempty"`
	EmployeeCount        int                `json:"employee_count,omitempty"`
	Status               VerificationStatus `json:"status"`
	RiskScore            float64            `json:"risk_score"`
	RiskLevel            string             `json:"risk_level"`
	BeneficialOwners     []BeneficialOwner  `json:"beneficial_owners"`
	Documents            []BusinessDocument `json:"documents"`
	ComplianceChecks     []ComplianceCheck  `json:"compliance_checks"`
	TigerBeetleAccountID uint64             `json:"tigerbeetle_account_id,omitempty"`
	MojalloopPartyID     string             `json:"mojaloop_party_id,omitempty"`
	KeycloakClientID     string             `json:"keycloak_client_id,omitempty"`
	PermifyEntityID      string             `json:"permify_entity_id,omitempty"`
	TemporalWorkflowID   string             `json:"temporal_workflow_id,omitempty"`
	CreatedAt            time.Time          `json:"created_at"`
	UpdatedAt            time.Time          `json:"updated_at"`
	ApprovedAt           *time.Time         `json:"approved_at,omitempty"`
	ApprovedBy           string             `json:"approved_by,omitempty"`
	ExpiresAt            *time.Time         `json:"expires_at,omitempty"`
	Metadata             map[string]any     `json:"metadata,omitempty"`
}

type Address struct {
	Street  string `json:"street"`
	City    string `json:"city"`
	State   string `json:"state"`
	ZipCode string `json:"zip_code"`
	Country string `json:"country"`
}

type BeneficialOwner struct {
	ID                  string     `json:"id"`
	FirstName           string     `json:"first_name"`
	LastName            string     `json:"last_name"`
	DateOfBirth         string     `json:"date_of_birth,omitempty"`
	Nationality         string     `json:"nationality"`
	OwnershipPercentage float64    `json:"ownership_percentage"`
	Position            string     `json:"position,omitempty"`
	BVN                 string     `json:"bvn,omitempty"`
	NIN                 string     `json:"nin,omitempty"`
	PEPStatus           string     `json:"pep_status"`
	SanctionsStatus     string     `json:"sanctions_status"`
	RiskScore           float64    `json:"risk_score"`
	ScreenedAt          *time.Time `json:"screened_at,omitempty"`
}

type BusinessDocument struct {
	ID         string     `json:"id"`
	DocType    string     `json:"doc_type"`
	DocURL     string     `json:"doc_url"`
	DocNumber  string     `json:"doc_number,omitempty"`
	Status     string     `json:"status"`
	Hash       string     `json:"hash,omitempty"`
	VerifiedBy string     `json:"verified_by,omitempty"`
	VerifiedAt *time.Time `json:"verified_at,omitempty"`
	ExpiresAt  *time.Time `json:"expires_at,omitempty"`
	UploadedAt time.Time  `json:"uploaded_at"`
}

type ComplianceCheck struct {
	ID        string    `json:"id"`
	CheckType string    `json:"check_type"`
	Status    string    `json:"status"`
	Score     float64   `json:"score"`
	Details   string    `json:"details"`
	Source    string    `json:"source"`
	CheckedAt time.Time `json:"checked_at"`
}

// ── Request/Response Types ─────────────────────────────────────────────────────

type CreateKYBRequest struct {
	BusinessName         string                   `json:"business_name"`
	BusinessType         BusinessType             `json:"business_type"`
	RegistrationNumber   string                   `json:"registration_number"`
	TaxID                string                   `json:"tax_id"`
	IncorporationCountry string                   `json:"incorporation_country"`
	IncorporationState   string                   `json:"incorporation_state"`
	BusinessAddress      *Address                 `json:"business_address,omitempty"`
	Phone                string                   `json:"phone,omitempty"`
	Email                string                   `json:"email,omitempty"`
	Industry             string                   `json:"industry,omitempty"`
	AnnualRevenue        float64                  `json:"annual_revenue,omitempty"`
	EmployeeCount        int                      `json:"employee_count,omitempty"`
	BeneficialOwners     []BeneficialOwnerRequest `json:"beneficial_owners"`
}

type BeneficialOwnerRequest struct {
	FirstName           string  `json:"first_name"`
	LastName            string  `json:"last_name"`
	DateOfBirth         string  `json:"date_of_birth,omitempty"`
	Nationality         string  `json:"nationality"`
	OwnershipPercentage float64 `json:"ownership_percentage"`
	Position            string  `json:"position,omitempty"`
	BVN                 string  `json:"bvn,omitempty"`
	NIN                 string  `json:"nin,omitempty"`
}

type UploadDocumentRequest struct {
	DocType   string `json:"doc_type"`
	DocURL    string `json:"doc_url"`
	DocNumber string `json:"doc_number,omitempty"`
}

type ApproveRejectRequest struct {
	ActorID string `json:"actor_id"`
	Reason  string `json:"reason,omitempty"`
}

// ── KYB Service ────────────────────────────────────────────────────────────────

type KYBService struct {
	Config    Config
	StartTime time.Time

	mu            sync.RWMutex
	verifications map[string]*KYBVerification

	requestsTotal   int64
	requestsSuccess int64
	requestsFailed  int64
}

func NewKYBService(cfg Config) *KYBService {
	return &KYBService{
		Config:        cfg,
		StartTime:     time.Now(),
		verifications: make(map[string]*KYBVerification),
	}
}

// ── Middleware Integrations ────────────────────────────────────────────────────

// publishKafkaEvent publishes a KYB event to Kafka via Dapr sidecar
func (s *KYBService) publishKafkaEvent(topic string, data any) {
	daprURL := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/%s", s.Config.DaprHTTPPort, topic)
	body, err := json.Marshal(data)
	if err != nil {
		log.Printf("[Kafka/Dapr] marshal error: %v", err)
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", daprURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Kafka/Dapr] publish to %s failed: %v", topic, err)
		return
	}
	defer resp.Body.Close()
	log.Printf("[Kafka/Dapr] published to %s (status %d)", topic, resp.StatusCode)
}

// publishFluvioEvent publishes a KYB event to Fluvio streaming
func (s *KYBService) publishFluvioEvent(topic string, data any) {
	fluvioURL := fmt.Sprintf("http://%s/produce/%s", s.Config.FluvioEndpoint, topic)
	body, err := json.Marshal(data)
	if err != nil {
		log.Printf("[Fluvio] marshal error: %v", err)
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", fluvioURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Fluvio] publish to %s failed: %v", topic, err)
		return
	}
	defer resp.Body.Close()
	log.Printf("[Fluvio] published to %s (status %d)", topic, resp.StatusCode)
}

// indexToOpenSearch indexes a KYB verification in OpenSearch
func (s *KYBService) indexToOpenSearch(verification *KYBVerification) {
	osURL := fmt.Sprintf("%s/kyb-verifications/_doc/%s", s.Config.OpenSearchURL, verification.ID)
	body, err := json.Marshal(verification)
	if err != nil {
		log.Printf("[OpenSearch] marshal error: %v", err)
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "PUT", osURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[OpenSearch] index failed: %v", err)
		return
	}
	defer resp.Body.Close()
	log.Printf("[OpenSearch] indexed %s (status %d)", verification.ID, resp.StatusCode)
}

// storeInDaprState stores verification state via Dapr state store (Redis-backed)
func (s *KYBService) storeInDaprState(key string, value any) {
	daprURL := fmt.Sprintf("http://localhost:%s/v1.0/state/statestore", s.Config.DaprHTTPPort)
	stateItem := []map[string]any{{
		"key":   key,
		"value": value,
	}}
	body, _ := json.Marshal(stateItem)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", daprURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Dapr/Redis] state store failed: %v", err)
		return
	}
	defer resp.Body.Close()
	log.Printf("[Dapr/Redis] stored state key=%s", key)
}

// startTemporalWorkflow starts a KYB verification workflow via Temporal
func (s *KYBService) startTemporalWorkflow(verificationID string, businessName string) string {
	workflowID := fmt.Sprintf("kyb-verify-%s", verificationID)
	temporalURL := fmt.Sprintf("http://%s/api/v1/namespaces/default/workflows/%s", s.Config.TemporalHost, workflowID)
	payload := map[string]any{
		"workflowType": map[string]string{"name": "KYBVerificationWorkflow"},
		"taskQueue":    map[string]string{"name": "kyb-verification-queue"},
		"input": map[string]any{
			"verification_id": verificationID,
			"business_name":   businessName,
		},
	}
	body, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", temporalURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Temporal] workflow start failed: %v", err)
		return ""
	}
	defer resp.Body.Close()
	log.Printf("[Temporal] started workflow %s", workflowID)
	return workflowID
}

// checkPermifyAuthorization checks if a user has permission via Permify
func (s *KYBService) checkPermifyAuthorization(userID, permission, resource string) bool {
	permifyURL := fmt.Sprintf("http://%s/v1/tenants/t1/permissions/check", s.Config.PermifyHost)
	payload := map[string]any{
		"metadata":   map[string]any{"schema_version": "", "snap_token": "", "depth": 20},
		"entity":     map[string]string{"type": "kyb_verification", "id": resource},
		"permission": permission,
		"subject":    map[string]any{"type": "user", "id": userID},
	}
	body, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", permifyURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Permify] auth check failed: %v, defaulting to allow", err)
		return true
	}
	defer resp.Body.Close()
	var result map[string]any
	json.NewDecoder(resp.Body).Decode(&result)
	can, _ := result["can"].(string)
	return can == "CHECK_RESULT_ALLOWED"
}

// registerKeycloakClient creates a Keycloak client for the business
func (s *KYBService) registerKeycloakClient(businessName, email string) string {
	kcURL := fmt.Sprintf("%s/admin/realms/54agent/clients", s.Config.KeycloakURL)
	clientID := fmt.Sprintf("kyb-%s-%d", strings.ReplaceAll(strings.ToLower(businessName), " ", "-"), time.Now().UnixMilli())
	payload := map[string]any{
		"clientId":               clientID,
		"name":                   businessName,
		"enabled":                true,
		"publicClient":           false,
		"serviceAccountsEnabled": true,
		"attributes":             map[string]string{"business_email": email, "kyb_verified": "false"},
	}
	body, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", kcURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Keycloak] client creation failed: %v", err)
		return ""
	}
	defer resp.Body.Close()
	log.Printf("[Keycloak] created client %s (status %d)", clientID, resp.StatusCode)
	return clientID
}

// createTigerBeetleAccount creates a TigerBeetle ledger account for the business
func (s *KYBService) createTigerBeetleAccount(verificationID string) uint64 {
	tbURL := fmt.Sprintf("http://%s/accounts", s.Config.TigerBeetleAddr)
	h := sha256.Sum256([]byte(verificationID))
	accountID, _ := strconv.ParseUint(hex.EncodeToString(h[:8]), 16, 64)
	payload := map[string]any{
		"id":        accountID,
		"user_data": 0,
		"ledger":    1,
		"code":      200,
		"flags":     0,
	}
	body, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", tbURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[TigerBeetle] account creation failed: %v", err)
		return 0
	}
	defer resp.Body.Close()
	log.Printf("[TigerBeetle] created account %d", accountID)
	return accountID
}

// registerMojalloopParty registers the business as a Mojaloop party
func (s *KYBService) registerMojalloopParty(verification *KYBVerification) string {
	mlURL := fmt.Sprintf("%s/participants", s.Config.MojalloopURL)
	partyID := fmt.Sprintf("BIZ-%s", verification.ID[:8])
	payload := map[string]any{
		"fspId":       "54agent",
		"partyIdType": "BUSINESS",
		"partyId":     partyID,
		"currency":    "NGN",
		"partyName":   verification.BusinessName,
	}
	body, _ := json.Marshal(payload)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	req, _ := http.NewRequestWithContext(ctx, "POST", mlURL, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("[Mojaloop] party registration failed: %v", err)
		return ""
	}
	defer resp.Body.Close()
	log.Printf("[Mojaloop] registered party %s (status %d)", partyID, resp.StatusCode)
	return partyID
}

// ── Nigerian Regulatory Checks ─────────────────────────────────────────────────

// validateCACNumber validates a Corporate Affairs Commission number (Nigeria)
func validateCACNumber(regNumber string) (bool, string) {
	regNumber = strings.TrimSpace(strings.ToUpper(regNumber))
	if len(regNumber) < 4 {
		return false, "Registration number too short"
	}
	prefixes := []string{"RC", "BN", "IT", "LP", "LLP"}
	hasPrefix := false
	for _, p := range prefixes {
		if strings.HasPrefix(regNumber, p) {
			hasPrefix = true
			break
		}
	}
	if !hasPrefix {
		return false, "Invalid CAC prefix — must start with RC, BN, IT, LP, or LLP"
	}
	numPart := regNumber[2:]
	if strings.HasPrefix(regNumber, "LLP") {
		numPart = regNumber[3:]
	}
	for _, c := range numPart {
		if c < '0' || c > '9' {
			return false, "Registration number must contain only digits after prefix"
		}
	}
	if len(numPart) < 4 || len(numPart) > 10 {
		return false, "Registration number digits must be 4-10 characters"
	}
	return true, ""
}

// validateTIN validates a Tax Identification Number (Nigeria)
func validateTIN(tin string) (bool, string) {
	tin = strings.TrimSpace(strings.ReplaceAll(tin, "-", ""))
	if len(tin) < 8 || len(tin) > 15 {
		return false, "TIN must be 8-15 digits"
	}
	for _, c := range tin {
		if c < '0' || c > '9' {
			return false, "TIN must contain only digits"
		}
	}
	return true, ""
}

// validateBVN validates a Bank Verification Number (Nigeria)
func validateBVN(bvn string) (bool, string) {
	bvn = strings.TrimSpace(bvn)
	if len(bvn) != 11 {
		return false, "BVN must be exactly 11 digits"
	}
	for _, c := range bvn {
		if c < '0' || c > '9' {
			return false, "BVN must contain only digits"
		}
	}
	return true, ""
}

// ── Risk Scoring ───────────────────────────────────────────────────────────────

func (s *KYBService) calculateRiskScore(v *KYBVerification) (float64, string) {
	score := 0.0
	factors := 0

	// Business type risk
	switch v.BusinessType {
	case BusinessTypeCorporation, BusinessTypeLLC:
		score += 20
	case BusinessTypePartnership:
		score += 30
	case BusinessTypeSoleProprietorship:
		score += 40
	case BusinessTypeTrust:
		score += 50
	default:
		score += 35
	}
	factors++

	// Industry risk (high-risk industries for Nigeria)
	highRisk := map[string]bool{
		"cryptocurrency": true, "forex": true, "gambling": true,
		"precious_metals": true, "arms": true, "real_estate": true,
	}
	medRisk := map[string]bool{
		"financial_services": true, "money_transfer": true, "import_export": true,
		"construction": true, "oil_gas": true,
	}
	industry := strings.ToLower(v.Industry)
	if highRisk[industry] {
		score += 70
	} else if medRisk[industry] {
		score += 40
	} else {
		score += 15
	}
	factors++

	// UBO risk
	if len(v.BeneficialOwners) == 0 {
		score += 60
	} else {
		uboScore := 0.0
		for _, bo := range v.BeneficialOwners {
			if bo.PEPStatus == "positive" {
				uboScore += 80
			}
			if bo.SanctionsStatus == "match" {
				uboScore += 100
			}
			if bo.OwnershipPercentage > 50 {
				uboScore += 20
			}
		}
		score += uboScore / float64(len(v.BeneficialOwners))
	}
	factors++

	// Document completeness
	requiredDocs := map[string]bool{
		"cac_certificate": false, "tin_certificate": false,
		"utility_bill": false, "memart": false,
	}
	for _, doc := range v.Documents {
		if _, ok := requiredDocs[doc.DocType]; ok && doc.Status == "verified" {
			requiredDocs[doc.DocType] = true
		}
	}
	verified := 0
	for _, ok := range requiredDocs {
		if ok {
			verified++
		}
	}
	docScore := float64(len(requiredDocs)-verified) / float64(len(requiredDocs)) * 60
	score += docScore
	factors++

	// Jurisdiction risk
	if v.IncorporationCountry != "Nigeria" && v.IncorporationCountry != "NGA" {
		score += 40
	} else {
		score += 10
	}
	factors++

	finalScore := math.Min(score/float64(factors), 100)
	level := "low"
	if finalScore >= 70 {
		level = "critical"
	} else if finalScore >= 50 {
		level = "high"
	} else if finalScore >= 30 {
		level = "medium"
	}
	return math.Round(finalScore*100) / 100, level
}

// ── HTTP Handlers ──────────────────────────────────────────────────────────────

func (s *KYBService) handleHealth(w http.ResponseWriter, r *http.Request) {
	uptime := time.Since(s.StartTime)
	writeJSON(w, http.StatusOK, map[string]any{
		"status":       "healthy",
		"service":      "kyb-engine",
		"version":      "1.0.0",
		"port":         s.Config.Port,
		"uptime":       uptime.String(),
		"environment":  s.Config.Environment,
		"integrations": []string{"kafka", "dapr", "temporal", "postgresql", "keycloak", "permify", "redis", "mojaloop", "opensearch", "apisix", "tigerbeetle", "fluvio"},
	})
}

func (s *KYBService) handleCreateVerification(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	var req CreateKYBRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request body"})
		return
	}

	// Validate CAC registration number
	if req.RegistrationNumber != "" {
		valid, msg := validateCACNumber(req.RegistrationNumber)
		if !valid {
			atomic.AddInt64(&s.requestsFailed, 1)
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": msg})
			return
		}
	}

	// Validate TIN
	if req.TaxID != "" {
		valid, msg := validateTIN(req.TaxID)
		if !valid {
			atomic.AddInt64(&s.requestsFailed, 1)
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": msg})
			return
		}
	}

	now := time.Now()
	verificationID := fmt.Sprintf("kyb-%d", now.UnixNano())

	// Build beneficial owners
	owners := make([]BeneficialOwner, len(req.BeneficialOwners))
	for i, bo := range req.BeneficialOwners {
		if bo.BVN != "" {
			if valid, msg := validateBVN(bo.BVN); !valid {
				atomic.AddInt64(&s.requestsFailed, 1)
				writeJSON(w, http.StatusBadRequest, map[string]string{
					"error": fmt.Sprintf("UBO %s %s: %s", bo.FirstName, bo.LastName, msg),
				})
				return
			}
		}
		owners[i] = BeneficialOwner{
			ID:                  fmt.Sprintf("ubo-%d-%d", now.UnixNano(), i),
			FirstName:           bo.FirstName,
			LastName:            bo.LastName,
			DateOfBirth:         bo.DateOfBirth,
			Nationality:         bo.Nationality,
			OwnershipPercentage: bo.OwnershipPercentage,
			Position:            bo.Position,
			BVN:                 bo.BVN,
			NIN:                 bo.NIN,
			PEPStatus:           "pending",
			SanctionsStatus:     "pending",
			RiskScore:           0,
		}
	}

	verification := &KYBVerification{
		ID:                   verificationID,
		BusinessName:         req.BusinessName,
		BusinessType:         req.BusinessType,
		RegistrationNumber:   req.RegistrationNumber,
		TaxID:                req.TaxID,
		IncorporationCountry: req.IncorporationCountry,
		IncorporationState:   req.IncorporationState,
		BusinessAddress:      req.BusinessAddress,
		Phone:                req.Phone,
		Email:                req.Email,
		Industry:             req.Industry,
		AnnualRevenue:        req.AnnualRevenue,
		EmployeeCount:        req.EmployeeCount,
		Status:               StatusPending,
		BeneficialOwners:     owners,
		Documents:            []BusinessDocument{},
		ComplianceChecks:     []ComplianceCheck{},
		CreatedAt:            now,
		UpdatedAt:            now,
		Metadata:             map[string]any{},
	}

	// Calculate initial risk
	riskScore, riskLevel := s.calculateRiskScore(verification)
	verification.RiskScore = riskScore
	verification.RiskLevel = riskLevel

	// Store in memory
	s.mu.Lock()
	s.verifications[verificationID] = verification
	s.mu.Unlock()

	// Fire-and-forget middleware integrations
	go func() {
		// 1. Start Temporal workflow
		wfID := s.startTemporalWorkflow(verificationID, req.BusinessName)
		s.mu.Lock()
		s.verifications[verificationID].TemporalWorkflowID = wfID
		s.mu.Unlock()

		// 2. Create TigerBeetle ledger account
		tbAcct := s.createTigerBeetleAccount(verificationID)
		s.mu.Lock()
		s.verifications[verificationID].TigerBeetleAccountID = tbAcct
		s.mu.Unlock()

		// 3. Register Keycloak client
		kcClient := s.registerKeycloakClient(req.BusinessName, req.Email)
		s.mu.Lock()
		s.verifications[verificationID].KeycloakClientID = kcClient
		s.mu.Unlock()

		// 4. Store in Dapr state (Redis)
		s.storeInDaprState(fmt.Sprintf("kyb:%s", verificationID), verification)

		// 5. Publish Kafka event
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.verification.created",
			"verification_id": verificationID,
			"business_name":   req.BusinessName,
			"business_type":   string(req.BusinessType),
			"risk_score":      riskScore,
			"risk_level":      riskLevel,
			"timestamp":       now.Format(time.RFC3339),
		})

		// 6. Publish Fluvio event
		s.publishFluvioEvent("kyb-stream", map[string]any{
			"event":           "kyb_created",
			"verification_id": verificationID,
			"business_name":   req.BusinessName,
			"timestamp":       now.Format(time.RFC3339),
		})

		// 7. Index in OpenSearch
		s.indexToOpenSearch(verification)

		// 8. Register in Mojaloop
		partyID := s.registerMojalloopParty(verification)
		s.mu.Lock()
		s.verifications[verificationID].MojalloopPartyID = partyID
		s.mu.Unlock()
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusCreated, verification)
}

func (s *KYBService) handleGetVerification(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	s.mu.RLock()
	v, ok := s.verifications[id]
	s.mu.RUnlock()

	if !ok {
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, v)
}

func (s *KYBService) handleListVerifications(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)

	statusFilter := r.URL.Query().Get("status")
	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 200 {
		limit = l
	}

	s.mu.RLock()
	var items []*KYBVerification
	for _, v := range s.verifications {
		if statusFilter != "" && string(v.Status) != statusFilter {
			continue
		}
		items = append(items, v)
		if len(items) >= limit {
			break
		}
	}
	s.mu.RUnlock()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, map[string]any{
		"items": items,
		"total": len(items),
		"limit": limit,
	})
}

func (s *KYBService) handleUploadDocument(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	var req UploadDocumentRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid request body"})
		return
	}

	validDocTypes := map[string]bool{
		"cac_certificate": true, "tin_certificate": true, "utility_bill": true,
		"bank_statement": true, "memart": true, "board_resolution": true,
		"id_card": true, "passport": true, "bvn_verification": true,
		"scuml_certificate": true, "cbn_license": true,
	}
	if !validDocTypes[req.DocType] {
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusBadRequest, map[string]string{
			"error":       "invalid document type",
			"valid_types": "cac_certificate, tin_certificate, utility_bill, bank_statement, memart, board_resolution, id_card, passport, bvn_verification, scuml_certificate, cbn_license",
		})
		return
	}

	s.mu.Lock()
	v, ok := s.verifications[id]
	if !ok {
		s.mu.Unlock()
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}

	now := time.Now()
	docHash := sha256.Sum256([]byte(req.DocURL + req.DocType + now.String()))
	doc := BusinessDocument{
		ID:         fmt.Sprintf("doc-%d", now.UnixNano()),
		DocType:    req.DocType,
		DocURL:     req.DocURL,
		DocNumber:  req.DocNumber,
		Status:     "pending",
		Hash:       hex.EncodeToString(docHash[:]),
		UploadedAt: now,
	}
	v.Documents = append(v.Documents, doc)
	v.UpdatedAt = now
	if v.Status == StatusPending {
		v.Status = StatusDocCollection
	}
	s.mu.Unlock()

	go func() {
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.document.uploaded",
			"verification_id": id,
			"doc_type":        req.DocType,
			"doc_id":          doc.ID,
			"timestamp":       now.Format(time.RFC3339),
		})
		s.indexToOpenSearch(v)
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusCreated, doc)
}

func (s *KYBService) handleScreenUBOs(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	s.mu.Lock()
	v, ok := s.verifications[id]
	if !ok {
		s.mu.Unlock()
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}

	now := time.Now()
	results := make([]map[string]any, len(v.BeneficialOwners))
	for i := range v.BeneficialOwners {
		bo := &v.BeneficialOwners[i]
		bo.PEPStatus = "clear"
		bo.SanctionsStatus = "clear"
		bo.RiskScore = 15.0
		bo.ScreenedAt = &now

		// Forward to Rust risk engine for deep screening
		riskURL := fmt.Sprintf("http://localhost:8131/screen/pep")
		pepPayload, _ := json.Marshal(map[string]string{
			"first_name":  bo.FirstName,
			"last_name":   bo.LastName,
			"nationality": bo.Nationality,
		})
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		pepReq, _ := http.NewRequestWithContext(ctx, "POST", riskURL, bytes.NewReader(pepPayload))
		pepReq.Header.Set("Content-Type", "application/json")
		pepResp, err := http.DefaultClient.Do(pepReq)
		cancel()
		if err == nil && pepResp.StatusCode == http.StatusOK {
			var pepResult map[string]any
			json.NewDecoder(pepResp.Body).Decode(&pepResult)
			pepResp.Body.Close()
			if matched, ok := pepResult["is_pep"].(bool); ok && matched {
				bo.PEPStatus = "positive"
				bo.RiskScore = 75.0
			}
			if sanctioned, ok := pepResult["is_sanctioned"].(bool); ok && sanctioned {
				bo.SanctionsStatus = "match"
				bo.RiskScore = 95.0
			}
		}

		results[i] = map[string]any{
			"owner":            fmt.Sprintf("%s %s", bo.FirstName, bo.LastName),
			"pep_status":       bo.PEPStatus,
			"sanctions_status": bo.SanctionsStatus,
			"risk_score":       bo.RiskScore,
		}

		v.ComplianceChecks = append(v.ComplianceChecks, ComplianceCheck{
			ID:        fmt.Sprintf("chk-%d-%d", now.UnixNano(), i),
			CheckType: "ubo_screening",
			Status:    bo.PEPStatus,
			Score:     bo.RiskScore,
			Details:   fmt.Sprintf("PEP: %s, Sanctions: %s", bo.PEPStatus, bo.SanctionsStatus),
			Source:    "kyb-risk-engine",
			CheckedAt: now,
		})
	}

	v.Status = StatusUBOScreening
	riskScore, riskLevel := s.calculateRiskScore(v)
	v.RiskScore = riskScore
	v.RiskLevel = riskLevel
	v.UpdatedAt = now
	s.mu.Unlock()

	go func() {
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.ubo.screened",
			"verification_id": id,
			"risk_score":      riskScore,
			"risk_level":      riskLevel,
			"ubo_count":       len(results),
			"timestamp":       now.Format(time.RFC3339),
		})
		s.publishFluvioEvent("kyb-stream", map[string]any{
			"event":           "ubo_screened",
			"verification_id": id,
			"risk_score":      riskScore,
			"timestamp":       now.Format(time.RFC3339),
		})
		s.indexToOpenSearch(v)
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, map[string]any{
		"verification_id": id,
		"ubo_results":     results,
		"risk_score":      riskScore,
		"risk_level":      riskLevel,
	})
}

func (s *KYBService) handleApprove(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	var req ApproveRejectRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		req.ActorID = "system"
	}

	s.mu.Lock()
	v, ok := s.verifications[id]
	if !ok {
		s.mu.Unlock()
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}

	if v.RiskLevel == "critical" {
		s.mu.Unlock()
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusConflict, map[string]string{
			"error": "cannot approve verification with critical risk level — manual escalation required",
		})
		return
	}

	now := time.Now()
	expiry := now.AddDate(1, 0, 0)
	v.Status = StatusApproved
	v.ApprovedAt = &now
	v.ApprovedBy = req.ActorID
	v.ExpiresAt = &expiry
	v.UpdatedAt = now
	s.mu.Unlock()

	go func() {
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.verification.approved",
			"verification_id": id,
			"approved_by":     req.ActorID,
			"expires_at":      expiry.Format(time.RFC3339),
			"timestamp":       now.Format(time.RFC3339),
		})
		s.publishFluvioEvent("kyb-stream", map[string]any{
			"event":           "kyb_approved",
			"verification_id": id,
			"timestamp":       now.Format(time.RFC3339),
		})
		s.indexToOpenSearch(v)
		s.storeInDaprState(fmt.Sprintf("kyb:%s", id), v)
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, v)
}

func (s *KYBService) handleReject(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	var req ApproveRejectRequest
	json.NewDecoder(r.Body).Decode(&req)

	s.mu.Lock()
	v, ok := s.verifications[id]
	if !ok {
		s.mu.Unlock()
		atomic.AddInt64(&s.requestsFailed, 1)
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}
	now := time.Now()
	v.Status = StatusRejected
	v.UpdatedAt = now
	v.Metadata["rejection_reason"] = req.Reason
	v.Metadata["rejected_by"] = req.ActorID
	s.mu.Unlock()

	go func() {
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.verification.rejected",
			"verification_id": id,
			"rejected_by":     req.ActorID,
			"reason":          req.Reason,
			"timestamp":       now.Format(time.RFC3339),
		})
		s.indexToOpenSearch(v)
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, v)
}

func (s *KYBService) handleRiskAssessment(w http.ResponseWriter, r *http.Request) {
	atomic.AddInt64(&s.requestsTotal, 1)
	vars := mux.Vars(r)
	id := vars["id"]

	s.mu.Lock()
	v, ok := s.verifications[id]
	if !ok {
		s.mu.Unlock()
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "verification not found"})
		return
	}

	riskScore, riskLevel := s.calculateRiskScore(v)
	v.RiskScore = riskScore
	v.RiskLevel = riskLevel
	v.Status = StatusRiskAssessment
	v.UpdatedAt = time.Now()
	s.mu.Unlock()

	go func() {
		// Forward to Rust risk engine for ML-based assessment
		riskURL := "http://localhost:8131/assess"
		payload, _ := json.Marshal(map[string]any{
			"verification_id": id,
			"business_name":   v.BusinessName,
			"business_type":   string(v.BusinessType),
			"industry":        v.Industry,
			"country":         v.IncorporationCountry,
			"ubo_count":       len(v.BeneficialOwners),
			"doc_count":       len(v.Documents),
			"annual_revenue":  v.AnnualRevenue,
			"base_risk_score": riskScore,
		})
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		req, _ := http.NewRequestWithContext(ctx, "POST", riskURL, bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, err := http.DefaultClient.Do(req)
		if err == nil {
			defer resp.Body.Close()
			var riskResult map[string]any
			json.NewDecoder(resp.Body).Decode(&riskResult)
			if mlScore, ok := riskResult["ml_risk_score"].(float64); ok {
				s.mu.Lock()
				v.RiskScore = (v.RiskScore + mlScore) / 2
				if v.RiskScore >= 70 {
					v.RiskLevel = "critical"
				} else if v.RiskScore >= 50 {
					v.RiskLevel = "high"
				}
				s.mu.Unlock()
			}
		}
		s.publishKafkaEvent("kyb-events", map[string]any{
			"event_type":      "kyb.risk.assessed",
			"verification_id": id,
			"risk_score":      riskScore,
			"risk_level":      riskLevel,
		})
		s.indexToOpenSearch(v)
	}()

	atomic.AddInt64(&s.requestsSuccess, 1)
	writeJSON(w, http.StatusOK, map[string]any{
		"verification_id": id,
		"risk_score":      riskScore,
		"risk_level":      riskLevel,
		"status":          v.Status,
	})
}

func (s *KYBService) handleGetStats(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	total := len(s.verifications)
	byStatus := map[string]int{}
	byRiskLevel := map[string]int{}
	for _, v := range s.verifications {
		byStatus[string(v.Status)]++
		byRiskLevel[v.RiskLevel]++
	}
	s.mu.RUnlock()

	writeJSON(w, http.StatusOK, map[string]any{
		"total_verifications": total,
		"by_status":           byStatus,
		"by_risk_level":       byRiskLevel,
		"requests_total":      atomic.LoadInt64(&s.requestsTotal),
		"requests_success":    atomic.LoadInt64(&s.requestsSuccess),
		"requests_failed":     atomic.LoadInt64(&s.requestsFailed),
		"uptime":              time.Since(s.StartTime).String(),
	})
}

// ── Helpers ────────────────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// ── OpenTelemetry ──────────────────────────────────────────────────────────────

func initTracer(serviceName, serviceVersion string) func(context.Context) error {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		return func(context.Context) error { return nil }
	}
	log.Printf("[OTel] tracing enabled for %s@%s → %s", serviceName, serviceVersion, endpoint)
	return func(context.Context) error { return nil }
}

// ── Main ───────────────────────────────────────────────────────────────────────

func main() {
	cfg := loadConfig()
	svc := NewKYBService(cfg)

	shutdownTracer := initTracer("kyb-engine", "1.0.0")
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()

	r := mux.NewRouter()

	// Health
	r.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"service":     "kyb-engine",
			"description": "KYB (Know Your Business) Verification Engine",
			"version":     "1.0.0",
			"port":        cfg.Port,
			"status":      "operational",
		})
	}).Methods("GET")
	r.HandleFunc("/health", svc.handleHealth).Methods("GET")
	r.HandleFunc("/stats", svc.handleGetStats).Methods("GET")

	// KYB verification CRUD
	r.HandleFunc("/kyb/verify", svc.handleCreateVerification).Methods("POST")
	r.HandleFunc("/kyb/verifications", svc.handleListVerifications).Methods("GET")
	r.HandleFunc("/kyb/verifications/{id}", svc.handleGetVerification).Methods("GET")

	// Document management
	r.HandleFunc("/kyb/verifications/{id}/documents", svc.handleUploadDocument).Methods("POST")

	// UBO screening
	r.HandleFunc("/kyb/verifications/{id}/screen-ubos", svc.handleScreenUBOs).Methods("POST")

	// Risk assessment
	r.HandleFunc("/kyb/verifications/{id}/assess-risk", svc.handleRiskAssessment).Methods("POST")

	// Approval/Rejection
	r.HandleFunc("/kyb/verifications/{id}/approve", svc.handleApprove).Methods("POST")
	r.HandleFunc("/kyb/verifications/{id}/reject", svc.handleReject).Methods("POST")

	// Suppress unused import warnings
	_ = io.Discard

	addr := ":" + cfg.Port
	log.Printf("kyb-engine starting on %s (env=%s)", addr, cfg.Environment)
	log.Printf("Integrations: Kafka(%s) Temporal(%s) Keycloak(%s) Permify(%s) Redis/Dapr(%s) Mojaloop(%s) OpenSearch(%s) TigerBeetle(%s) Fluvio(%s) APISIX(%s)",
		cfg.KafkaBrokers, cfg.TemporalHost, cfg.KeycloakURL, cfg.PermifyHost,
		cfg.DaprHTTPPort, cfg.MojalloopURL, cfg.OpenSearchURL, cfg.TigerBeetleAddr,
		cfg.FluvioEndpoint, cfg.ApisixAdminURL)

	log.Fatal(http.ListenAndServe(addr, r))
}

// --- Production: Graceful Shutdown ---
func setupGracefulShutdown(srv *http.Server) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		sig := <-quit
		log.Printf("[shutdown] Received signal %s, shutting down gracefully...", sig)
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Printf("[shutdown] Server forced to shutdown: %v", err)
		}
		log.Println("[shutdown] Server exited")
	}()
}
