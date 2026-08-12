package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/lestrrat-go/jwx/v2/jwk"
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
	// bearer token and the subject is bound to the token's `sub` claim.
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
	claims := r.Context().Value(ctxClaimsKey).(*jwt.RegisteredClaims)
	path := r.URL.Path

	switch {
	case strings.HasSuffix(path, "/setup") && r.Method == http.MethodPost:
		handleMFASetup(w, r, claims)
	case strings.HasSuffix(path, "/verify") && r.Method == http.MethodPost:
		handleMFAVerify(w, r, claims)
	case strings.HasSuffix(path, "/disable") && r.Method == http.MethodPost:
		handleMFADisable(w, r, claims)
	case strings.HasSuffix(path, "/backup-codes") && r.Method == http.MethodPost:
		handleBackupCodes(w, r, claims)
	default:
		jsonResponse(w, http.StatusNotFound, ErrorResponse{Error: "not_found", Message: "Endpoint not found"})
	}
}

func handleMFASetup(w http.ResponseWriter, r *http.Request, claims *jwt.RegisteredClaims) {
	var req MFASetupRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	// Bind the target user to the authenticated subject; a caller may not
	// set up MFA for a different user.
	if req.UserID == "" {
		req.UserID = claims.Subject
	}
	if req.UserID != claims.Subject {
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

func handleMFAVerify(w http.ResponseWriter, r *http.Request, claims *jwt.RegisteredClaims) {
	var req MFAVerifyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	if req.UserID == "" {
		req.UserID = claims.Subject
	}
	if req.UserID != claims.Subject {
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

func handleMFADisable(w http.ResponseWriter, r *http.Request, claims *jwt.RegisteredClaims) {
	var req MFADisableRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonResponse(w, http.StatusBadRequest, ErrorResponse{Error: "invalid_request", Message: "Invalid request body"})
		return
	}
	if req.UserID == "" {
		req.UserID = claims.Subject
	}
	if req.UserID != claims.Subject {
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

func handleBackupCodes(w http.ResponseWriter, r *http.Request, claims *jwt.RegisteredClaims) {
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

// --- Keycloak JWT authentication (P0 fix) -------------------------------

type ctxKey string

const ctxClaimsKey ctxKey = "claims"

var (
	jwksCache    *jwk.Cache
	jwksCacheErr error
	jwksOnce     sync.Once
)

func keycloakIssuer() string {
	base := strings.TrimSuffix(getEnv("KEYCLOAK_URL", getEnv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")), "/")
	realm := getEnv("KEYCLOAK_REALM", "remittance")
	return fmt.Sprintf("%s/realms/%s", base, realm)
}

func jwksURL() string {
	return keycloakIssuer() + "/protocol/openid-connect/certs"
}

func getJWKS(ctx context.Context) (jwk.Set, error) {
	jwksOnce.Do(func() {
		jwksCache = jwk.NewCache(ctx)
		jwksCacheErr = jwksCache.Register(jwksURL(), jwk.WithMinRefreshInterval(15*time.Minute))
		if jwksCacheErr == nil {
			// Pre-warm the cache so the first request does not pay full latency.
			if _, err := jwksCache.Refresh(ctx, jwksURL()); err != nil {
				log.Printf("warning: initial JWKS fetch failed: %v", err)
			}
		}
	})
	if jwksCacheErr != nil {
		return nil, jwksCacheErr
	}
	return jwksCache.Get(ctx, jwksURL())
}

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if !strings.HasPrefix(authHeader, "Bearer ") {
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Missing bearer token"})
			return
		}
		tokenString := strings.TrimPrefix(authHeader, "Bearer ")

		set, err := getJWKS(r.Context())
		if err != nil {
			log.Printf("JWKS unavailable: %v", err)
			jsonResponse(w, http.StatusServiceUnavailable, ErrorResponse{Error: "auth_unavailable", Message: "Token validation service unavailable"})
			return
		}

		token, err := jwt.ParseWithClaims(
			tokenString,
			&jwt.RegisteredClaims{},
			func(t *jwt.Token) (interface{}, error) {
				if _, ok := t.Method.(*jwt.SigningMethodRSA); !ok {
					return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
				}
				kid, _ := t.Header["kid"].(string)
				key, found := set.LookupKeyID(kid)
				if !found {
					return nil, errors.New("unknown signing key")
				}
				var pub interface{}
				if err := key.Raw(&pub); err != nil {
					return nil, err
				}
				return pub, nil
			},
			jwt.WithIssuer(keycloakIssuer()),
			jwt.WithExpirationRequired(),
		)
		if err != nil || !token.Valid {
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Invalid or expired token"})
			return
		}

		claims, ok := token.Claims.(*jwt.RegisteredClaims)
		if !ok || claims.Subject == "" {
			jsonResponse(w, http.StatusUnauthorized, ErrorResponse{Error: "unauthorized", Message: "Invalid token claims"})
			return
		}

		ctx := context.WithValue(r.Context(), ctxClaimsKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
