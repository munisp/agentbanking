package main

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

type APIKey struct {
	Key       string    `json:"key"`
	Name      string    `json:"name"`
	PartnerID string    `json:"partner_id"`
	Tier      string    `json:"tier"`
	RateLimit int       `json:"rate_limit"`
	Scopes    []string  `json:"scopes"`
	Active    bool      `json:"active"`
	CreatedAt time.Time `json:"created_at"`
}

type APIRequest struct {
	Key       string    `json:"key"`
	Endpoint  string    `json:"endpoint"`
	Method    string    `json:"method"`
	Status    int       `json:"status"`
	Latency   float64   `json:"latency_ms"`
	Timestamp time.Time `json:"timestamp"`
}

type Gateway struct {
	db       *sql.DB
	mu       sync.RWMutex
	keys     map[string]*APIKey
	requests []APIRequest
}

func NewGateway(db *sql.DB) *Gateway {
	return &Gateway{
		db:       db,
		keys:     make(map[string]*APIKey),
		requests: make([]APIRequest, 0),
	}
}

func generateAPIKey() string {
	b := make([]byte, 24)
	rand.Read(b)
	return "ob_live_" + hex.EncodeToString(b)
}

func (g *Gateway) RegisterPartner(name, partnerID, tier string, scopes []string) (*APIKey, error) {
	rateLimit := 100
	switch tier {
	case "premium":
		rateLimit = 1000
	case "enterprise":
		rateLimit = 10000
	}

	key := &APIKey{
		Key:       generateAPIKey(),
		Name:      name,
		PartnerID: partnerID,
		Tier:      tier,
		RateLimit: rateLimit,
		Scopes:    scopes,
		Active:    true,
		CreatedAt: time.Now(),
	}

	query := `INSERT INTO api_keys (key, name, partner_id, tier, rate_limit, scopes, active, created_at)
	           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`
	scopeJSON, _ := json.Marshal(scopes)
	_, err := g.db.Exec(query, key.Key, key.Name, key.PartnerID, key.Tier, key.RateLimit, string(scopeJSON), key.Active, key.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to register partner: %w", err)
	}

	g.mu.Lock()
	g.keys[key.Key] = key
	g.mu.Unlock()
	return key, nil
}

func (g *Gateway) ValidateKey(key string) (*APIKey, error) {
	g.mu.RLock()
	apiKey, ok := g.keys[key]
	g.mu.RUnlock()
	if !ok || !apiKey.Active {
		return nil, fmt.Errorf("invalid or inactive API key")
	}
	return apiKey, nil
}

func (g *Gateway) HasScope(key *APIKey, scope string) bool {
	for _, s := range key.Scopes {
		if s == scope || s == "*" {
			return true
		}
	}
	return false
}

func (g *Gateway) authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/api/v1/partners/register" {
			next.ServeHTTP(w, r)
			return
		}

		auth := r.Header.Get("Authorization")
		if !strings.HasPrefix(auth, "Bearer ") {
			http.Error(w, `{"error":"missing API key"}`, http.StatusUnauthorized)
			return
		}
		key := strings.TrimPrefix(auth, "Bearer ")
		apiKey, err := g.ValidateKey(key)
		if err != nil {
			http.Error(w, `{"error":"invalid API key"}`, http.StatusForbidden)
			return
		}

		r.Header.Set("X-Partner-ID", apiKey.PartnerID)
		r.Header.Set("X-API-Tier", apiKey.Tier)
		next.ServeHTTP(w, r)
	})
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8402"
	}
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://localhost:5432/agentbanking?sslmode=disable"
	}

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("DB error: %v", err)
	}
	defer db.Close()
	db.SetMaxOpenConns(50)

	gw := NewGateway(db)
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := db.Ping(); err != nil {
			http.Error(w, "unhealthy", http.StatusServiceUnavailable)
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "open-banking-gateway"})
	})

	mux.HandleFunc("/api/v1/partners/register", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			Name      string   `json:"name"`
			PartnerID string   `json:"partner_id"`
			Tier      string   `json:"tier"`
			Scopes    []string `json:"scopes"`
		}
		json.NewDecoder(r.Body).Decode(&req)
		key, err := gw.RegisterPartner(req.Name, req.PartnerID, req.Tier, req.Scopes)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(key)
	})

	mux.HandleFunc("/api/v1/accounts/balance", func(w http.ResponseWriter, r *http.Request) {
		partnerID := r.Header.Get("X-Partner-ID")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"partner_id": partnerID,
			"accounts":   []map[string]interface{}{},
			"timestamp":  time.Now().Format(time.RFC3339),
		})
	})

	mux.HandleFunc("/api/v1/payments/initiate", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		partnerID := r.Header.Get("X-Partner-ID")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"payment_id": fmt.Sprintf("PAY-%d", time.Now().UnixMilli()),
			"partner_id": partnerID,
			"status":     "initiated",
			"timestamp":  time.Now().Format(time.RFC3339),
		})
	})

	handler := gw.authMiddleware(mux)
	server := &http.Server{Addr: ":" + port, Handler: handler}

	go func() {
		log.Printf("Open Banking Gateway on :%s", port)
		server.ListenAndServe()
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	server.Shutdown(ctx)
}
