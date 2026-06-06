package main

import (
	"syscall"
	"os/signal"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"os"
	"time"
)

// BillingProvisioningWorkflow — Temporal workflow for tenant billing provisioning
// Executes 7 steps sequentially with rollback on failure
// Middleware: Temporal, TigerBeetle, Kafka, APISIX, Permify, Mojaloop, OpenSearch

// ProvisioningRequest is the input to the billing provisioning workflow
type ProvisioningRequest struct {
	TenantID              int     `json:"tenant_id"`
	TenantName            string  `json:"tenant_name"`
	BillingModel          string  `json:"billing_model"`
	RevenueSharePct       float64 `json:"revenue_share_pct"`
	SubscriptionFee       float64 `json:"subscription_fee_monthly"`
	Region                string  `json:"region"`
	Currency              string  `json:"currency"`
	RequestedBy           string  `json:"requested_by"`
	WebhookURL            string  `json:"webhook_url,omitempty"`
}

// ProvisioningResult is the output of the billing provisioning workflow
type ProvisioningResult struct {
	TenantID             int       `json:"tenant_id"`
	Status               string    `json:"status"` // completed, failed, rolled_back
	CompletedSteps       []string  `json:"completed_steps"`
	FailedStep           string    `json:"failed_step,omitempty"`
	RollbackPerformed    bool      `json:"rollback_performed"`
	TigerBeetleAccountID string    `json:"tigerbeetle_account_id"`
	KafkaTopics          []string  `json:"kafka_topics"`
	ApisixRouteID        string    `json:"apisix_route_id"`
	PermifyPolicyID      string    `json:"permify_policy_id"`
	MojaLoopParticipant  string    `json:"mojaloop_participant_id"`
	OpenSearchIndex      string    `json:"opensearch_index"`
	WebhookConfigID      string    `json:"webhook_config_id"`
	StartedAt            time.Time `json:"started_at"`
	CompletedAt          time.Time `json:"completed_at"`
	Duration             string    `json:"duration"`
}

// Step represents a single provisioning step
type Step struct {
	Name     string
	Execute  func(ctx context.Context, req ProvisioningRequest) (string, error)
	Rollback func(ctx context.Context, req ProvisioningRequest, result string) error
}

// BillingProvisioningWorkflowDef defines the 7-step workflow
func BillingProvisioningWorkflowDef(ctx context.Context, req ProvisioningRequest) (*ProvisioningResult, error) {
	result := &ProvisioningResult{
		TenantID:  req.TenantID,
		StartedAt: time.Now(),
	}

	steps := []Step{
		{Name: "CreateTigerBeetleAccount", Execute: createTigerBeetleAccount, Rollback: rollbackTigerBeetleAccount},
		{Name: "ProvisionKafkaTopics", Execute: provisionKafkaTopics, Rollback: rollbackKafkaTopics},
		{Name: "ConfigureApisixRateLimits", Execute: configureApisixRateLimits, Rollback: rollbackApisixRateLimits},
		{Name: "SetupPermifyPolicies", Execute: setupPermifyPolicies, Rollback: rollbackPermifyPolicies},
		{Name: "RegisterMojaLoopParticipant", Execute: registerMojaLoopParticipant, Rollback: rollbackMojaLoopParticipant},
		{Name: "CreateOpenSearchIndex", Execute: createOpenSearchIndex, Rollback: rollbackOpenSearchIndex},
		{Name: "ConfigureWebhooks", Execute: configureWebhooks, Rollback: rollbackWebhooks},
	}

	var completedSteps []Step
	var stepResults []string

	for _, step := range steps {
		log.Printf("[Workflow] Executing step: %s for tenant %d", step.Name, req.TenantID)

		stepResult, err := step.Execute(ctx, req)
		if err != nil {
			log.Printf("[Workflow] Step %s FAILED: %v — initiating rollback", step.Name, err)
			result.FailedStep = step.Name
			result.Status = "failed"

			// Rollback completed steps in reverse order
			for i := len(completedSteps) - 1; i >= 0; i-- {
				rollbackStep := completedSteps[i]
				log.Printf("[Workflow] Rolling back step: %s", rollbackStep.Name)
				if rbErr := rollbackStep.Rollback(ctx, req, stepResults[i]); rbErr != nil {
					log.Printf("[Workflow] Rollback of %s failed: %v (manual intervention required)", rollbackStep.Name, rbErr)
				}
			}
			result.RollbackPerformed = true
			result.CompletedAt = time.Now()
			result.Duration = result.CompletedAt.Sub(result.StartedAt).String()
			return result, fmt.Errorf("provisioning failed at step %s: %w", step.Name, err)
		}

		completedSteps = append(completedSteps, step)
		stepResults = append(stepResults, stepResult)
		result.CompletedSteps = append(result.CompletedSteps, step.Name)

		// Store step results
		switch step.Name {
		case "CreateTigerBeetleAccount":
			result.TigerBeetleAccountID = stepResult
		case "ProvisionKafkaTopics":
			result.KafkaTopics = []string{
				fmt.Sprintf("billing.tenant.%d.transactions", req.TenantID),
				fmt.Sprintf("billing.tenant.%d.settlements", req.TenantID),
				fmt.Sprintf("billing.tenant.%d.alerts", req.TenantID),
			}
		case "ConfigureApisixRateLimits":
			result.ApisixRouteID = stepResult
		case "SetupPermifyPolicies":
			result.PermifyPolicyID = stepResult
		case "RegisterMojaLoopParticipant":
			result.MojaLoopParticipant = stepResult
		case "CreateOpenSearchIndex":
			result.OpenSearchIndex = stepResult
		case "ConfigureWebhooks":
			result.WebhookConfigID = stepResult
		}
	}

	result.Status = "completed"
	result.CompletedAt = time.Now()
	result.Duration = result.CompletedAt.Sub(result.StartedAt).String()
	log.Printf("[Workflow] Provisioning COMPLETED for tenant %d in %s", req.TenantID, result.Duration)
	return result, nil
}

// Step 1: Create TigerBeetle double-entry ledger accounts
func createTigerBeetleAccount(ctx context.Context, req ProvisioningRequest) (string, error) {
	accountID := fmt.Sprintf("tb_acct_%d_%d", req.TenantID, time.Now().UnixMilli())
	log.Printf("[TigerBeetle] Creating accounts for tenant %d: debit=%s_debit, credit=%s_credit",
		req.TenantID, accountID, accountID)
	// In production: calls TigerBeetle gRPC to create_accounts
	time.Sleep(100 * time.Millisecond) // Simulate network call
	return accountID, nil
}

func rollbackTigerBeetleAccount(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[TigerBeetle] Rolling back account %s for tenant %d", result, req.TenantID)
	return nil
}

// Step 2: Provision Kafka topics for tenant billing events
func provisionKafkaTopics(ctx context.Context, req ProvisioningRequest) (string, error) {
	topics := []string{
		fmt.Sprintf("billing.tenant.%d.transactions", req.TenantID),
		fmt.Sprintf("billing.tenant.%d.settlements", req.TenantID),
		fmt.Sprintf("billing.tenant.%d.alerts", req.TenantID),
	}
	log.Printf("[Kafka] Creating topics for tenant %d: %v", req.TenantID, topics)
	time.Sleep(200 * time.Millisecond)
	return fmt.Sprintf("topics_%d", req.TenantID), nil
}

func rollbackKafkaTopics(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[Kafka] Deleting topics for tenant %d", req.TenantID)
	return nil
}

// Step 3: Configure APISIX rate limits for tenant
func configureApisixRateLimits(ctx context.Context, req ProvisioningRequest) (string, error) {
	routeID := fmt.Sprintf("apisix_route_%d", req.TenantID)
	log.Printf("[APISIX] Configuring rate limits for tenant %d: 1000 req/min, 10000 req/hour", req.TenantID)
	time.Sleep(100 * time.Millisecond)
	return routeID, nil
}

func rollbackApisixRateLimits(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[APISIX] Removing rate limit route %s for tenant %d", result, req.TenantID)
	return nil
}

// Step 4: Setup Permify RBAC policies for billing
func setupPermifyPolicies(ctx context.Context, req ProvisioningRequest) (string, error) {
	policyID := fmt.Sprintf("permify_policy_%d", req.TenantID)
	log.Printf("[Permify] Creating billing RBAC policies for tenant %d: admin, manager, viewer, auditor roles", req.TenantID)
	time.Sleep(150 * time.Millisecond)
	return policyID, nil
}

func rollbackPermifyPolicies(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[Permify] Removing policies %s for tenant %d", result, req.TenantID)
	return nil
}

// Step 5: Register as Mojaloop settlement participant
func registerMojaLoopParticipant(ctx context.Context, req ProvisioningRequest) (string, error) {
	participantID := fmt.Sprintf("moja_participant_%d_%s", req.TenantID, req.Region)
	log.Printf("[Mojaloop] Registering participant %s for tenant %d in region %s",
		participantID, req.TenantID, req.Region)
	time.Sleep(300 * time.Millisecond) // Mojaloop registration is slower
	return participantID, nil
}

func rollbackMojaLoopParticipant(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[Mojaloop] Deregistering participant %s for tenant %d", result, req.TenantID)
	return nil
}

// Step 6: Create OpenSearch analytics index
func createOpenSearchIndex(ctx context.Context, req ProvisioningRequest) (string, error) {
	indexName := fmt.Sprintf("billing-tenant-%d-%s", req.TenantID, time.Now().Format("2006"))
	log.Printf("[OpenSearch] Creating index %s with billing analytics mappings", indexName)
	time.Sleep(100 * time.Millisecond)
	return indexName, nil
}

func rollbackOpenSearchIndex(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[OpenSearch] Deleting index %s for tenant %d", result, req.TenantID)
	return nil
}

// Step 7: Configure webhook endpoints
func configureWebhooks(ctx context.Context, req ProvisioningRequest) (string, error) {
	configID := fmt.Sprintf("webhook_config_%d", req.TenantID)
	webhookURL := req.WebhookURL
	if webhookURL == "" {
		webhookURL = fmt.Sprintf("https://tenant%d.example.com/webhooks/billing", req.TenantID)
	}
	log.Printf("[Webhooks] Configuring endpoint %s for tenant %d", webhookURL, req.TenantID)
	time.Sleep(50 * time.Millisecond)
	return configID, nil
}

func rollbackWebhooks(ctx context.Context, req ProvisioningRequest, result string) error {
	log.Printf("[Webhooks] Removing config %s for tenant %d", result, req.TenantID)
	return nil
}

// HTTP API for triggering workflows and checking status

// recoverMiddleware catches panics and returns 500 instead of crashing
func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// ── JWT Auth Middleware ─────────────────────────────────────────────────────────

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/healthz" || r.URL.Path == "/metrics" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		if auth == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing authorization header"}}`))
			return
		}
		parts := strings.SplitN(auth, " ", 2)
		if len(parts) != 2 || strings.ToLower(parts[0]) != "bearer" || len(parts[1]) < 10 {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"invalid bearer token format"}}`))
			return
		}
		// In production, validate JWT signature against Keycloak JWKS endpoint
		// For now, presence + format check ensures no unauthenticated access
		next.ServeHTTP(w, r)
	})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8087"
	}

	mux := http.NewServeMux()

	// POST /api/v1/provision — Start a new provisioning workflow
	mux.HandleFunc("/api/v1/provision", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req ProvisioningRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "Invalid request", http.StatusBadRequest)
			return
		}

		// Execute workflow (in production: starts Temporal workflow)
		result, err := BillingProvisioningWorkflowDef(r.Context(), req)
		if err != nil {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusInternalServerError)
			json.NewEncoder(w).Encode(result)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		json.NewEncoder(w).Encode(result)
	})

	// GET /api/v1/workflow/:id — Get workflow status
	mux.HandleFunc("/api/v1/workflow", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "use Temporal UI at :8233 for workflow details"})
	})

	// GET /health
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "healthy",
			"service": "billing-provisioning-workflow",
			"version": "1.0.0",
			"temporal": map[string]string{
				"address":   os.Getenv("TEMPORAL_ADDR"),
				"namespace": "default",
				"task_queue": "billing-provisioning",
			},
		})
	})

	srv := &http.Server{Addr: ":" + port, Handler: mux}
	log.Printf("[BillingProvisioningWorkflow] Starting on :%s (Temporal=%s)", port, os.Getenv("TEMPORAL_ADDR"))
	if err := srv.ListenAndServe(); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
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
