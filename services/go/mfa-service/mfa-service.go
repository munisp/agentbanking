package main

import (
	"crypto/rand"
	"encoding/base32"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
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
	log.Fatal(http.ListenAndServe(":8081", r))
}
