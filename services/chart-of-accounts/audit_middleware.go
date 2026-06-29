package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"
)

var (
	auditSvcURL  = os.Getenv("AUDIT_SVC_URL")
	skipPrefixes = []string{"/health", "/metrics", "/dapr", "/docs", "/ready"}
	skipMethods  = map[string]bool{"GET": true, "HEAD": true, "OPTIONS": true}
	auditUUIDRE  = regexp.MustCompile(`/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}`)
	auditIntRE   = regexp.MustCompile(`/[0-9]+`)
)

func init() {
	if auditSvcURL == "" {
		auditSvcURL = "http://audit-service:8000"
	}
}

type auditResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (w *auditResponseWriter) WriteHeader(code int) {
	w.statusCode = code
	w.ResponseWriter.WriteHeader(code)
}

func auditPathToEventType(method, path string) string {
	clean := auditUUIDRE.ReplaceAllString(path, "/{id}")
	clean = auditIntRE.ReplaceAllString(clean, "/{id}")
	return fmt.Sprintf("%s:%s", method, clean)
}

func sendAuditEvent(actorID, tenantID, eventType string, eventData map[string]interface{}) {
	payload, err := json.Marshal(map[string]interface{}{
		"actor_id":   actorID,
		"tenant_id":  tenantID,
		"event_type": eventType,
		"event_data": eventData,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	})
	if err != nil {
		return
	}
	req, err := http.NewRequest("POST", auditSvcURL+"/audits", bytes.NewBuffer(payload))
	if err != nil {
		return
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-tenant-id", tenantID)
	req.Header.Set("x-keycloak-id", "system")
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return
	}
	defer resp.Body.Close()
}

func auditMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if skipMethods[r.Method] {
			next.ServeHTTP(w, r)
			return
		}
		for _, p := range skipPrefixes {
			if strings.HasPrefix(r.URL.Path, p) {
				next.ServeHTTP(w, r)
				return
			}
		}

		rec := &auditResponseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		next.ServeHTTP(rec, r)

		actorID := r.Header.Get("X-Keycloak-ID")
		if actorID == "" {
			actorID = r.Header.Get("x-keycloak-id")
		}
		if actorID == "" {
			actorID = "unknown"
		}
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			tenantID = "unknown"
		}
		eventData := map[string]interface{}{
			"method":      r.Method,
			"path":        r.URL.Path,
			"status_code": rec.statusCode,
		}
		if r.URL.RawQuery != "" {
			eventData["query"] = r.URL.RawQuery
		}

		go sendAuditEvent(actorID, tenantID, auditPathToEventType(r.Method, r.URL.Path), eventData)
	})
}
