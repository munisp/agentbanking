package main

import (
	"context"
	"crypto"
	"crypto/rsa"
	"crypto/sha256"
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
)

// MFA Service
// Handles TOTP-based multi-factor authentication setup, verification, and management

type Config struct {
	Port        string
	DatabaseURL string
	RedisURL    string
}

type MFASetupRequest struct {
	UserID string `json:"user_id"`
	Email  string `json:"email"`
}

type MFASetupResponse struct {
	Secret      string   `json:"secret"`
	QRCodeURL   string   `json:"qr_code_url"`
	BackupCodes []string `json:"backup_codes"`
}

type MFAVerifyRequest struct {
	UserID string `json:"user_id"`
	Code   string `json:"code"`
}

type MFADisableRequest struct {
	UserID string `json:"user_id"`
	Code   string `json:"code"`
}

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

func main() {
	config := Config{
		Port:        getEnv("PORT", "8084"),
		DatabaseURL: getEnv("DATABASE_URL", ""),
		RedisURL:    getEnv("REDIS_URL", "redis://localhost:6379"),
	}

	// P0 SECURITY: every /mfa/* endpoint previously ran with NO
	// authentication — any caller could set up/verify/disable MFA for an
	// arbitrary user_id. All /mfa/* routes now require a valid Keycloak
	// bearer token and the target user is bound to the token's `sub` claim.
	mux := http.NewServeMux()
	mux.Handle("/mfa/", jwtAuthMiddleware(http.HandlerFunc(mfaHandler)))

	// Health endpoint (unauthenticated by design)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		jsonResponse(w, http.StatusOK, map[string]string{"status": "healthy"})
	})

	log.Printf("MFA Service starting on port %s", config.Port)
	if err := http.ListenAndServe(":"+config.Port, mux); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}

func mfaHandler(w http.ResponseWriter, r *http.Request) {
	subject := r.Context().Value(ctxSubjectKey).(string)
	path := r.URL.Path

	switch {
	case strings.HasSuffix(path, "/setup") && r.Method == http.MethodPost:
		handleMFASetup(w, r, subject)
	case strings.HasSuffix(path, "/verify") && r.Method == http.MethodPost:
		handleMFAVerify(w, r, subject)
	case strings.HasSuffix(path, "/disable") && r.Method == http.MethodPost:
		handleMFADisable(w, r, subject)
	case strings.HasSuffix(path, "/backup-codes") && r.Method == http.MethodPost:
		handleBackupCodes(w, r, subject)
	default:
		jsonResponse(w, http.StatusNotFound, ErrorResponse{Error: "not_found", Message: "Endpoint not found"})
	}
}

func handleMFASetup(w http.ResponseWriter, r *http.Request, subject string) {
	var req MFASetupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	// Bind the target user to the authenticated subject; a caller may not
	// set up MFA for a different user.
	if req.UserID == "" {
		req.UserID = subject
	}
	if req.UserID != subject {
		jsonResponse(w, http.StatusForbidden, ErrorResponse{Error: "forbidden", Message: "Cannot set up MFA for another user"})
		return
	}

	// In a real implementation:
	// 1. Generate TOTP secret using crypto/rand
	// 2. Store encrypted secret in database
	// 3. Generate QR code URL
	// 4. Generate backup codes
	// 5. Return setup response

	jsonResponse(w, http.StatusNotImplemented, ErrorResponse{Error: "not_implemented", Message: "MFA setup is not yet implemented. Contact system administrator."})
}

func handleMFAVerify(w http.ResponseWriter, r *http.Request, subject string) {
	var req MFAVerifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	if req.UserID == "" {
		req.UserID = subject
	}
	if req.UserID != subject {
		jsonResponse(w, http.StatusForbidden, ErrorResponse{Error: "forbidden", Message: "Cannot verify MFA for another user"})
		return
	}

	// In a real implementation:
	// 1. Retrieve encrypted TOTP secret from database
	// 2. Validate the provided code against the secret
	// 3. Check backup codes if primary fails
	// 4. Return verification result

	jsonResponse(w, http.StatusNotImplemented, ErrorResponse{Error: "not_implemented", Message: "MFA verification is not yet implemented"})
}

func handleMFADisable(w http.ResponseWriter, r *http.Request, subject string) {
	var req MFADisableRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	if req.UserID == "" {
		req.UserID = subject
	}
	if req.UserID != subject {
		jsonResponse(w, http.StatusForbidden, ErrorResponse{Error: "forbidden", Message: "Cannot disable MFA for another user"})
		return
	}

	// In a real implementation:
	// 1. Verify the provided code one last time
	// 2. Remove MFA secret from database
	// 3. Invalidate all backup codes
	// 4. Log the security event

	jsonResponse(w, http.StatusNotImplemented, ErrorResponse{Error: "not_implemented", Message: "MFA disable is not yet implemented"})
}

func handleBackupCodes(w http.ResponseWriter, r *http.Request, subject string) {
	// In a real implementation:
	// 1. Verify user has MFA enabled
	// 2. Generate new backup codes
	// 3. Invalidate old codes
	// 4. Return new codes

	jsonResponse(w, http.StatusNotImplemented, ErrorResponse{Error: "not_implemented", Message: "Backup code regeneration is not yet implemented"})
}

func jsonResponse(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// --- Keycloak JWT authentication (P0 fix, stdlib-only) -------------------
//
// Validates RS256 bearer tokens against the Keycloak realm JWKS endpoint.
// Implemented with the standard library only so no go.mod/go.sum changes
// are required.

type ctxKey string

const ctxSubjectKey ctxKey = "auth_subject"

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
	Subject  string `json:"sub"`
	Issuer   string `json:"iss"`
	Expiry   int64  `json:"exp"`
	NotBefore int64 `json:"nbf"`
}

// validateBearerToken parses and validates an RS256 JWT against the realm
// JWKS, enforcing signature, expiry, and issuer. Returns the subject claim.
func validateBearerToken(ctx context.Context, tokenString string) (string, error) {
	parts := strings.Split(tokenString, ".")
	if len(parts) != 3 {
		return "", errors.New("malformed token")
	}
	headerBytes, err := base64.RawURLEncoding.DecodeString(parts[0])
	if err != nil {
		return "", err
	}
	var hdr tokenHeader
	if err := json.Unmarshal(headerBytes, &hdr); err != nil {
		return "", err
	}
	if hdr.Alg != "RS256" {
		return "", fmt.Errorf("unexpected alg %q", hdr.Alg)
	}

	keys, err := getJWKS(ctx)
	if err != nil {
		return "", err
	}
	var pub *rsa.PublicKey
	for _, k := range keys {
		if k.Kid == hdr.Kid && k.Kty == "RSA" {
			pub, err = rsaKeyFromJWK(k)
			if err != nil {
				return "", err
			}
			break
		}
	}
	if pub == nil {
		return "", errors.New("unknown signing key")
	}

	signed := parts[0] + "." + parts[1]
	sig, err := base64.RawURLEncoding.DecodeString(parts[2])
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256([]byte(signed))
	if err := rsa.VerifyPKCS1v15(pub, crypto.SHA256, digest[:], sig); err != nil {
		return "", errors.New("invalid signature")
	}

	claimsBytes, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return "", err
	}
	var claims tokenClaims
	if err := json.Unmarshal(claimsBytes, &claims); err != nil {
		return "", err
	}
	now := time.Now().Unix()
	if claims.Expiry == 0 || now > claims.Expiry {
		return "", errors.New("token expired")
	}
	if claims.NotBefore != 0 && now < claims.NotBefore {
		return "", errors.New("token not yet valid")
	}
	if claims.Issuer != "" && claims.Issuer != keycloakIssuer() {
		return "", errors.New("invalid issuer")
	}
	if claims.Subject == "" {
		return "", errors.New("missing subject")
	}
	return claims.Subject, nil
}

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if !strings.HasPrefix(authHeader, "Bearer ") {
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Missing bearer token"})
			return
		}
		tokenString := strings.TrimSpace(strings.TrimPrefix(authHeader, "Bearer "))
		if tokenString == "" {
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Missing bearer token"})
			return
		}

		subject, err := validateBearerToken(r.Context(), tokenString)
		if err != nil {
			if strings.Contains(err.Error(), "JWKS") {
				jsonResponse(w, http.StatusServiceUnavailable, ErrorResponse{Error: "auth_unavailable", Message: "Token validation service unavailable"})
				return
			}
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Invalid or expired token"})
			return
		}

		ctx := context.WithValue(r.Context(), ctxSubjectKey, subject)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
