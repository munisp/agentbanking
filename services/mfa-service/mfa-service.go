package main

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base32"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/pquerna/otp"
	"github.com/pquerna/otp/totp"
)

type MFAService struct {
	users map[string]*User
}

type User struct {
	ID       string `json:"id"`
	Username string `json:"username"`
	Secret   string `json:"secret,omitempty"`
	Enabled  bool   `json:"enabled"`
}

type SetupRequest struct {
	Username string `json:"username"`
}

type SetupResponse struct {
	Secret string `json:"secret"`
	QRCode string `json:"qr_code"`
}

type VerifyRequest struct {
	Username string `json:"username"`
	Token    string `json:"token"`
}

type VerifyResponse struct {
	Valid bool `json:"valid"`
}

func NewMFAService() *MFAService {
	return &MFAService{
		users: make(map[string]*User),
	}
}

func (m *MFAService) SetupMFA(w http.ResponseWriter, r *http.Request) {
	var req SetupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	// Generate a new secret
	secret := make([]byte, 20)
	_, err := rand.Read(secret)
	if err != nil {
		http.Error(w, "Failed to generate secret", http.StatusInternalServerError)
		return
	}

	secretBase32 := base32.StdEncoding.EncodeToString(secret)

	// Generate QR code URL
	key, err := otp.NewKeyFromURL(fmt.Sprintf("otpauth://totp/AgentBanking:%s?secret=%s&issuer=AgentBanking", req.Username, secretBase32))
	if err != nil {
		http.Error(w, "Failed to generate key", http.StatusInternalServerError)
		return
	}

	// Store user
	user := &User{
		ID:       req.Username,
		Username: req.Username,
		Secret:   secretBase32,
		Enabled:  true,
	}
	m.users[req.Username] = user

	response := SetupResponse{
		Secret: secretBase32,
		QRCode: key.URL(),
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (m *MFAService) VerifyMFA(w http.ResponseWriter, r *http.Request) {
	var req VerifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	user, exists := m.users[req.Username]
	if !exists || !user.Enabled {
		http.Error(w, "User not found or MFA not enabled", http.StatusNotFound)
		return
	}

	// Verify TOTP token
	valid := totp.Validate(req.Token, user.Secret)

	response := VerifyResponse{
		Valid: valid,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (m *MFAService) DisableMFA(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	username := vars["username"]

	user, exists := m.users[username]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	user.Enabled = false
	w.WriteHeader(http.StatusOK)
}

func (m *MFAService) GetMFAStatus(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	username := vars["username"]

	user, exists := m.users[username]
	if !exists {
		http.Error(w, "User not found", http.StatusNotFound)
		return
	}

	// Don't expose the secret in the response
	userResponse := User{
		ID:       user.ID,
		Username: user.Username,
		Enabled:  user.Enabled,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(userResponse)
}

func (m *MFAService) HealthCheck(w http.ResponseWriter, r *http.Request) {
	health := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC(),
		"service":   "mfa-service",
		"version":   "1.0.0",
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

func mfa_serviceMain() {
	mfaService := NewMFAService()

	r := mux.NewRouter()

	// MFA endpoints
	r.HandleFunc("/mfa/setup", mfaService.SetupMFA).Methods("POST")
	r.HandleFunc("/mfa/verify", mfaService.VerifyMFA).Methods("POST")
	r.HandleFunc("/mfa/users/{username}/disable", mfaService.DisableMFA).Methods("POST")
	r.HandleFunc("/mfa/users/{username}/status", mfaService.GetMFAStatus).Methods("GET")

	// Health check
	r.HandleFunc("/health", mfaService.HealthCheck).Methods("GET")

	log.Println("MFA Service starting on port 8081...")
	// P0 SECURITY: all routes now require a valid Keycloak bearer token
	// (health/metrics probes are exempt inside the middleware).
	log.Fatal(http.ListenAndServe(":8081", jwtAuthMiddleware(r)))
}


// --- Keycloak JWT authentication (P0 fix, stdlib-only) -------------------
//
// Validates RS256 bearer tokens against the Keycloak realm JWKS endpoint.
// Implemented with the standard library only so no go.mod/go.sum changes
// are required.

func keycloakIssuer() string {
	base := strings.TrimSuffix(getEnv("KEYCLOAK_URL", getEnv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")), "/")
	realm := getEnv("KEYCLOAK_REALM", "remittance")
	return fmt.Sprintf("%s/realms/%s", base, realm)
}

func jwksURL() string {
	return keycloakIssuer() + "/protocol/openid-connect/certs"
}

type jwkKey struct {
	Kty string `json:"kty"`
	Kid string `json:"kid"`
	Alg string `json:"alg"`
	N   string `json:"n"`
	E   string `json:"e"`
}

type jwksDoc struct {
	Keys []jwkKey `json:"keys"`
}

var (
	jwksMu        sync.RWMutex
	jwksKeys      []jwkKey
	jwksFetchedAt time.Time
)

const jwksTTL = 15 * time.Minute

func getJWKS(ctx context.Context) ([]jwkKey, error) {
	jwksMu.RLock()
	if time.Since(jwksFetchedAt) < jwksTTL && jwksKeys != nil {
		defer jwksMu.RUnlock()
		return jwksKeys, nil
	}
	jwksMu.RUnlock()

	jwksMu.Lock()
	defer jwksMu.Unlock()
	if time.Since(jwksFetchedAt) < jwksTTL && jwksKeys != nil {
		return jwksKeys, nil
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, jwksURL(), nil)
	if err != nil {
		return nil, err
	}
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("JWKS endpoint returned %d", resp.StatusCode)
	}
	var doc jwksDoc
	if err := json.NewDecoder(resp.Body).Decode(&doc); err != nil {
		return nil, err
	}
	jwksKeys = doc.Keys
	jwksFetchedAt = time.Now()
	return jwksKeys, nil
}

func rsaKeyFromJWK(k jwkKey) (*rsa.PublicKey, error) {
	nBytes, err := base64.RawURLEncoding.DecodeString(k.N)
	if err != nil {
		return nil, err
	}
	eBytes, err := base64.RawURLEncoding.DecodeString(k.E)
	if err != nil {
		return nil, err
	}
	n := new(big.Int).SetBytes(nBytes)
	e := 0
	for _, b := range eBytes {
		e = e<<8 | int(b)
	}
	if e == 0 {
		return nil, errors.New("invalid exponent")
	}
	return &rsa.PublicKey{N: n, E: e}, nil
}

type tokenHeader struct {
	Alg string `json:"alg"`
	Kid string `json:"kid"`
}

type tokenClaims struct {
	Subject   string `json:"sub"`
	Issuer    string `json:"iss"`
	Expiry    int64  `json:"exp"`
	NotBefore int64  `json:"nbf"`
}

// validateBearerToken parses and validates an RS256 JWT against the realm
// JWKS, enforcing signature, expiry, and issuer.
func validateBearerToken(ctx context.Context, tokenString string) error {
	parts := strings.Split(tokenString, ".")
	if len(parts) != 3 {
		return errors.New("malformed token")
	}
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return err
	}
	var hdr tokenHeader
	if err := json.Unmarshal(headerBytes, &hdr); err != nil {
		return err
	}
	if hdr.Alg != "RS256" {
		return fmt.Errorf("unexpected alg %q", hdr.Alg)
	}

	keys, err := getJWKS(ctx)
	if err != nil {
		return err
	}
	var pub *rsa.PublicKey
	for _, k := range keys {
		if k.Kid == hdr.Kid && k.Kty == "RSA" {
			pub, err = rsaKeyFromJWK(k)
			if err != nil {
				return err
			}
			break
		}
	}
	if pub == nil {
		return errors.New("unknown signing key")
	}

	signed := parts[0] + "." + parts[1]
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return err
	}
	digest := sha256.Sum256([]byte(signed))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, digest[:], sig); err != nil {
		return errors.New("invalid signature")
	}

	claimsBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return err
	}
	var claims tokenClaims
	if err := json.Unmarshal(claimsBytes, &claims); err != nil {
		return err
	}
	now := time.Now().Unix()
	if claims.Expiry == 0 || now > claims.Expiry {
		return errors.New("token expired")
	}
	if claims.NotBefore != 0 && now < claims.NotBefore {
		return errors.New("token not yet valid")
	}
	if claims.Issuer != "" && claims.Issuer != keycloakIssuer() {
		return errors.New("invalid issuer")
	}
	if claims.Subject == "" {
		return errors.New("missing subject")
	}
	return nil
}

// jwtAuthMiddleware enforces a valid Keycloak bearer token on all routes
// except health/metrics probes. 401 on missing/invalid tokens.
func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/healthz" || r.URL.Path == "/metrics" || r.URL.Path == "/ready" {
			next.ServeHTTP(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		if !strings.HasPrefix(auth, "Bearer ") {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing bearer token"}}`))
			return
		}
		tokenString := strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
		if tokenString == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"missing bearer token"}}`))
			return
		}
		if err := validateBearerToken(r.Context(), tokenString); err != nil {
			if strings.Contains(err.Error(), "JWKS") {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusServiceUnavailable)
				w.Write([]byte(`{"error":{"code":503,"message":"token validation service unavailable"}}`))
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusUnauthorized)
			w.Write([]byte(`{"error":{"code":401,"message":"invalid or expired token"}}`))
			return
		}
		next.ServeHTTP(w, r)
	})
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
