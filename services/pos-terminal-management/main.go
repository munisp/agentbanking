package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"reflect"
	"strconv"
	"strings"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/rs/cors"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// Helper functions for environment variables
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	valueStr := getEnv(key, fmt.Sprintf("%d", defaultValue))
	if value, err := strconv.Atoi(valueStr); err == nil {
		return value
	}
	return defaultValue
}

// Terminal represents a POS terminal
type Terminal struct {
	gorm.Model
	ID              string    `json:"id" gorm:"primaryKey"`
	DeviceID        string    `json:"device_id" gorm:"index"` // Link to POS hardware device
	Location        string    `json:"location" validate:"required,min=3,max=100"`
	Status          string    `json:"status" validate:"required,oneof=Active Inactive Maintenance"`
	LastService     time.Time `json:"last_service"`
	TerminalModel   string    `json:"model" validate:"required,min=2,max=50"`
	SerialNumber    string    `json:"serial_number" gorm:"uniqueIndex" validate:"required,alphanum,len=10"`
	AssignedTo      string    `json:"assigned_to" validate:"omitempty,min=3,max=100"`
	BusinessID      string    `json:"business_id" gorm:"index"` // Link to AgentBusiness
	IPAddress       string    `json:"ip_address" validate:"omitempty,ip"`
	SoftwareVersion string    `json:"software_version" validate:"omitempty,semver"`
	Notes           string    `json:"notes" validate:"omitempty,max=500"`
	// New fields for expanded functionality
	Configuration       string    `json:"configuration"` // JSON string of terminal configuration
	LastSoftwareUpdate  time.Time `json:"last_software_update"`
	NextMaintenanceDate time.Time `json:"next_maintenance_date"`
	IsOnline            bool      `json:"is_online"`
	BatteryLevel        float64   `json:"battery_level" validate:"min=0,max=100"`
	LastTransactionTime time.Time `json:"last_transaction_time"`
	TransactionCount    int       `json:"transaction_count" validate:"min=0"`
	// Additional fields for enterprise-grade management
	Manufacturer    string    `json:"manufacturer" validate:"omitempty,min=2,max=50"`
	PurchaseDate    time.Time `json:"purchase_date"`
	WarrantyEndDate time.Time `json:"warranty_end_date"`
	OperatingSystem string    `json:"operating_system" validate:"omitempty,min=2,max=50"`
	Processor       string    `json:"processor" validate:"omitempty,min=2,max=50"`
	MemoryGB        int       `json:"memory_gb" validate:"min=1"`
	StorageGB       int       `json:"storage_gb" validate:"min=1"`
	NetworkType     string    `json:"network_type" validate:"omitempty,oneof=Ethernet WiFi Cellular"`
	ContactPerson   string    `json:"contact_person" validate:"omitempty,min=3,max=100"`
	ContactEmail    string    `json:"contact_email" validate:"omitempty,email"`
	ContactPhone    string    `json:"contact_phone" validate:"omitempty,e164"`
	TerminalGroupID *uint     `json:"terminal_group_id"` // Foreign key for TerminalGroup
}

// BeforeCreate hook to generate UUID if ID is empty
func (t *Terminal) BeforeCreate(tx *gorm.DB) error {
	if t.ID == "" {
		t.ID = uuid.New().String()
	}
	return nil
}

// ServiceRecord represents a service record for a POS terminal
type ServiceRecord struct {
	gorm.Model
	TerminalID  string    `json:"terminal_id" validate:"required"`
	ServiceDate time.Time `json:"service_date" validate:"required"`
	Description string    `json:"description" validate:"required,min=10,max=1000"`
	PerformedBy string    `json:"performed_by" validate:"required,min=3,max=100"`
	Cost        float64   `json:"cost" validate:"min=0"`
	// New fields for service record details
	ServiceType          string    `json:"service_type" validate:"required,oneof=repair maintenance installation inspection"` // e.g., \'repair\', \'maintenance\', \'installation\'
	PartsUsed            string    `json:"parts_used"`                                                                        // JSON string of parts used
	Resolution           string    `json:"resolution" validate:"required,min=10,max=1000"`
	NextServiceDate      time.Time `json:"next_service_date"`
	ServiceDurationHours float64   `json:"service_duration_hours" validate:"min=0.1"`
}

// SoftwareUpdate represents a software update for terminals
type SoftwareUpdate struct {
	gorm.Model
	Version          string    `json:"version" gorm:"uniqueIndex" validate:"required,semver"`
	ReleaseDate      time.Time `json:"release_date" validate:"required"`
	Description      string    `json:"description" validate:"required,min=10,max=1000"`
	DownloadURL      string    `json:"download_url" validate:"required,url"`
	Criticality      string    `json:"criticality" validate:"required,oneof=low medium high critical"`
	ApplicableModels string    `json:"applicable_models"` // JSON string of applicable terminal models
}

// TerminalGroup represents a logical grouping of terminals
type TerminalGroup struct {
	gorm.Model
	Name        string     `json:"name" gorm:"uniqueIndex" validate:"required,min=3,max=100"`
	Description string     `json:"description" validate:"omitempty,max=500"`
	Terminals   []Terminal `json:"terminals" gorm:"foreignKey:TerminalGroupID"`
}

// ScheduledTask represents a task to be executed on terminals at a scheduled time
type ScheduledTask struct {
	gorm.Model
	Name        string    `json:"name" validate:"required,min=3,max=100"`
	TaskType    string    `json:"task_type" validate:"required,oneof=software_update configuration_push reboot"`
	Schedule    string    `json:"schedule" validate:"required"` // Cron string or specific timestamp
	TargetType  string    `json:"target_type" validate:"required,oneof=terminal_id terminal_group_id all"`
	TargetID    string    `json:"target_id"` // Terminal ID or Terminal Group ID
	Payload     string    `json:"payload"`   // JSON string for task specific data (e.g., new config, update version)
	Status      string    `json:"status" validate:"required,oneof=pending in_progress completed failed"`
	LastRunTime time.Time `json:"last_run_time"`
	NextRunTime time.Time `json:"next_run_time"`
}

// AuditLog represents an audit trail of actions performed on the system
type AuditLog struct {
	gorm.Model
	Timestamp    time.Time `json:"timestamp"`
	UserID       string    `json:"user_id"`
	Action       string    `json:"action"`
	ResourceType string    `json:"resource_type"`
	ResourceID   string    `json:"resource_id"`
	Details      string    `json:"details"` // JSON string of changed fields or additional context
	IPAddress    string    `json:"ip_address"`
}

var DB *gorm.DB
var RedisClient *redis.Client
var ctx = context.Background()

var (
	httpRequestsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests.",
		},
		[]string{"path", "method", "status"},
	)
	httpRequestDuration = prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"path", "method", "status"},
	)
	// Custom metrics for POS Terminal Management
	terminalCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "pos_terminal_count",
			Help: "Current number of POS terminals.",
		},
	)
	activeTerminalCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "pos_active_terminal_count",
			Help: "Current number of active POS terminals.",
		},
	)
	serviceRecordCount = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "pos_service_record_total",
			Help: "Total number of service records created.",
		},
	)
	softwareUpdateCount = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "pos_software_update_total",
			Help: "Total number of software updates.",
		},
	)
	terminalOnlineStatus = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "pos_terminal_online_status",
			Help: "Online status of POS terminals (1 for online, 0 for offline).",
		},
		[]string{"terminal_id"},
	)
	terminalBatteryLevel = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "pos_terminal_battery_level",
			Help: "Battery level of POS terminals.",
		},
		[]string{"terminal_id"},
	)
	terminalTransactionCount = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "pos_terminal_transaction_total",
			Help: "Total transactions processed by a terminal.",
		},
		[]string{"terminal_id"},
	)
	terminalGroupCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "pos_terminal_group_count",
			Help: "Current number of terminal groups.",
		},
	)
	scheduledTaskCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "pos_scheduled_task_count",
			Help: "Current number of scheduled tasks.",
		},
	)
	auditLogCount = prometheus.NewCounter(
		prometheus.CounterOpts{
			Name: "pos_audit_log_total",
			Help: "Total number of audit logs.",
		},
	)
)

func init() {
	prometheus.MustRegister(httpRequestsTotal)
	prometheus.MustRegister(httpRequestDuration)
	prometheus.MustRegister(terminalCount)
	prometheus.MustRegister(activeTerminalCount)
	prometheus.MustRegister(serviceRecordCount)
	prometheus.MustRegister(softwareUpdateCount)
	prometheus.MustRegister(terminalOnlineStatus)
	prometheus.MustRegister(terminalBatteryLevel)
	prometheus.MustRegister(terminalTransactionCount)
	prometheus.MustRegister(terminalGroupCount)
	prometheus.MustRegister(scheduledTaskCount)
	prometheus.MustRegister(auditLogCount)
}

func ConnectDatabase() {
	newLogger := logger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags),
		logger.Config{
			SlowThreshold: time.Second, // Slow SQL threshold
			LogLevel:      logger.Info, // Log level
			Colorful:      true,        // Disable color
		},
	)

	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=require TimeZone=UTC",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "password"),
		getEnv("DB_NAME", "link_core_banking"))
	database, err := gorm.Open(postgres.Open(dsn), &gorm.Config{Logger: newLogger})

	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	log.Println("Connected to database!")
	if err := database.AutoMigrate(&TerminalGroup{}, &Terminal{}, &ServiceRecord{}, &SoftwareUpdate{}, &ScheduledTask{}, &AuditLog{}); err != nil {
		log.Fatalf("Failed to run database migrations: %v", err)
	}
	log.Println("Database migrations completed successfully!")

	DB = database
}

func ConnectRedis() {
	RedisClient = redis.NewClient(&redis.Options{
		Addr:     getEnv("REDIS_ADDR", "localhost:6379"),
		Password: getEnv("REDIS_PASSWORD", ""),
		DB:       getEnvAsInt("REDIS_DB", 0),
	})

	_, err := RedisClient.Ping(ctx).Result()
	if err != nil {
		log.Fatalf("Could not connect to Redis: %v", err)
	}
	log.Println("Connected to Redis!")
}

func prometheusMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()

		lw := &loggingResponseWriter{w, http.StatusOK}

		next.ServeHTTP(lw, r)

		duration := time.Since(start).Seconds()
		path := r.URL.Path
		method := r.Method
		status := fmt.Sprintf("%d", lw.statusCode)

		httpRequestsTotal.WithLabelValues(path, method, status).Inc()
		httpRequestDuration.WithLabelValues(path, method, status).Observe(duration)
	})
}

type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	lrw.statusCode = code
	lrw.ResponseWriter.WriteHeader(code)
}

// Helper function to update terminal metrics
func updateTerminalMetrics() {
	var count int64
	DB.Model(&Terminal{}).Count(&count)
	terminalCount.Set(float64(count))

	var activeCount int64
	DB.Model(&Terminal{}).Where("status = ?", "Active").Count(&activeCount)
	activeTerminalCount.Set(float64(activeCount))

	var terminals []Terminal
	DB.Find(&terminals)
	for _, t := range terminals {
		if t.IsOnline {
			terminalOnlineStatus.WithLabelValues(t.ID).Set(1)
		} else {
			terminalOnlineStatus.WithLabelValues(t.ID).Set(0)
		}
		terminalBatteryLevel.WithLabelValues(t.ID).Set(t.BatteryLevel)
		terminalTransactionCount.WithLabelValues(t.ID).Add(float64(t.TransactionCount))
	}

	var groupCount int64
	DB.Model(&TerminalGroup{}).Count(&groupCount)
	terminalGroupCount.Set(float64(groupCount))

	var taskCount int64
	DB.Model(&ScheduledTask{}).Count(&taskCount)
	scheduledTaskCount.Set(float64(taskCount))
}

// Utility function for input validation
func validateStruct(s interface{}) error {
	val := reflect.ValueOf(s)
	typ := reflect.TypeOf(s)

	for i := 0; i < val.NumField(); i++ {
		field := val.Field(i)
		tag := typ.Field(i).Tag.Get("validate")

		if tag == "" {
			continue
		}

		switch field.Kind() {
		case reflect.String:
			strVal := field.String()
			if contains(tag, "required") && strVal == "" {
				return fmt.Errorf("%s is required", typ.Field(i).Name)
			}
			if contains(tag, "min=") {
				minLen, _ := strconv.Atoi(extractTagValue(tag, "min"))
				if len(strVal) < minLen {
					return fmt.Errorf("%s must be at least %d characters long", typ.Field(i).Name, minLen)
				}
			}
			if contains(tag, "max=") {
				maxLen, _ := strconv.Atoi(extractTagValue(tag, "max"))
				if len(strVal) > maxLen {
					return fmt.Errorf("%s must be at most %d characters long", typ.Field(i).Name, maxLen)
				}
			}
			// Add more string validations (e.g., email, url, alphanum, semver, oneof)
			if contains(tag, "email") && strVal != "" && !isValidEmail(strVal) {
				return fmt.Errorf("%s is not a valid email address", typ.Field(i).Name)
			}
			if contains(tag, "url") && strVal != "" && !isValidURL(strVal) {
				return fmt.Errorf("%s is not a valid URL", typ.Field(i).Name)
			}
			if contains(tag, "alphanum") && strVal != "" && !isAlphanumeric(strVal) {
				return fmt.Errorf("%s must be alphanumeric", typ.Field(i).Name)
			}
			if contains(tag, "len=") {
				exactLen, _ := strconv.Atoi(extractTagValue(tag, "len"))
				if len(strVal) != exactLen {
					return fmt.Errorf("%s must be exactly %d characters long", typ.Field(i).Name, exactLen)
				}
			}
			if contains(tag, "oneof=") {
				options := parseOneOf(extractTagValue(tag, "oneof"))
				if strVal != "" && !containsString(options, strVal) {
					return fmt.Errorf("%s must be one of %v", typ.Field(i).Name, options)
				}
			}
			// Simplified semver check
			if contains(tag, "semver") && strVal != "" && !isValidSemver(strVal) {
				return fmt.Errorf("%s is not a valid semantic version", typ.Field(i).Name)
			}

		case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
			intVal := field.Int()
			if contains(tag, "min=") {
				minVal, _ := strconv.ParseInt(extractTagValue(tag, "min"), 10, 64)
				if intVal < minVal {
					return fmt.Errorf("%s must be at least %d", typ.Field(i).Name, minVal)
				}
			}
			// Add max validation for int
			if contains(tag, "max=") {
				maxVal, _ := strconv.ParseInt(extractTagValue(tag, "max"), 10, 64)
				if intVal > maxVal {
					return fmt.Errorf("%s must be at most %d", typ.Field(i).Name, maxVal)
				}
			}
		case reflect.Float32, reflect.Float64:
			floatVal := field.Float()
			if contains(tag, "min=") {
				minVal, _ := strconv.ParseFloat(extractTagValue(tag, "min"), 64)
				if floatVal < minVal {
					return fmt.Errorf("%s must be at least %f", typ.Field(i).Name, minVal)
				}
			}
			// Add max validation for float
			if contains(tag, "max=") {
				maxVal, _ := strconv.ParseFloat(extractTagValue(tag, "max"), 64)
				if floatVal > maxVal {
					return fmt.Errorf("%s must be at most %f", typ.Field(i).Name, maxVal)
				}
			}
		case reflect.Struct:
			if field.Type() == reflect.TypeOf(time.Time{}) {
				timeVal := field.Interface().(time.Time)
				if contains(tag, "required") && timeVal.IsZero() {
					return fmt.Errorf("%s is required", typ.Field(i).Name)
				}
			}
		}
	}
	return nil
}

func contains(s, substr string) bool {
	return strings.Contains(s, substr)
}

func extractTagValue(tag, key string) string {
	parts := strings.Split(tag, ",")
	for _, part := range parts {
		if strings.HasPrefix(part, key) {
			return strings.TrimPrefix(part, key+"=")
		}
	}
	return ""
}

func parseOneOf(s string) []string {
	return strings.Split(s, " ")
}

func containsString(slice []string, item string) bool {
	for _, a := range slice {
		if a == item {
			return true
		}
	}
	return false
}

// Simplified email validation (for demonstration)
func isValidEmail(email string) bool {
	return strings.Contains(email, "@")
}

// Simplified URL validation (for demonstration)
func isValidURL(url string) bool {
	return strings.HasPrefix(url, "http://") || strings.HasPrefix(url, "https://")
}

// Simplified alphanumeric validation (for demonstration)
func isAlphanumeric(s string) bool {
	for _, r := range s {
		if (r < 'a' || r > 'z') && (r < 'A' || r > 'Z') && (r < '0' || r > '9') {
			return false
		}
	}
	return true
}

// Simplified semantic version validation (for demonstration)
func isValidSemver(s string) bool {
	// Very basic check: X.Y.Z format
	parts := strings.Split(s, ".")
	if len(parts) != 3 {
		return false
	}
	for _, p := range parts {
		if _, err := strconv.Atoi(p); err != nil {
			return false
		}
	}
	return true
}

func getTerminals(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	terminalsJSON, err := RedisClient.Get(ctx, "terminals").Result()
	if err == nil {
		log.Println("Cache hit for terminals!")
		json.NewEncoder(w).Encode(json.RawMessage(terminalsJSON))
		return
	}

	var terminals []Terminal
	if result := DB.Find(&terminals); result.Error != nil {
		log.Printf("Error fetching terminals from DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	jsonBytes, err := json.Marshal(terminals)
	if err != nil {
		log.Printf("Error marshalling terminals to JSON: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	RedisClient.Set(ctx, "terminals", jsonBytes, 10*time.Minute)

	json.NewEncoder(w).Encode(terminals)
	updateTerminalMetrics()
}

func getTerminal(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	terminalJSON, err := RedisClient.Get(ctx, terminalID).Result()
	if err == nil {
		log.Printf("Cache hit for terminal: %s", terminalID)
		json.NewEncoder(w).Encode(json.RawMessage(terminalJSON))
		return
	}

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s from DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	jsonBytes, err := json.Marshal(terminal)
	if err != nil {
		log.Printf("Error marshalling terminal %s to JSON: %v", terminalID, err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	RedisClient.Set(ctx, terminalID, jsonBytes, 10*time.Minute)

	json.NewEncoder(w).Encode(terminal)
}

func createTerminal(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var terminal Terminal
	if err := json.NewDecoder(r.Body).Decode(&terminal); err != nil {
		log.Printf("Error decoding request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	if err := validateStruct(terminal); err != nil {
		log.Printf("Validation error for new terminal: %v", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if result := DB.Create(&terminal); result.Error != nil {
		log.Printf("Error creating terminal in DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, "terminals", terminal.ID)

	json.NewEncoder(w).Encode(terminal)
	updateTerminalMetrics()
	logAudit("create", "Terminal", terminal.ID, r.RemoteAddr, "Terminal created")
}

func updateTerminal(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s for update from DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	var updatedTerminal Terminal
	if err := json.NewDecoder(r.Body).Decode(&updatedTerminal); err != nil {
		log.Printf("Error decoding request body for update: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// Store old values for audit logging
	oldTerminal := terminal

	// Update fields individually to avoid overwriting GORM fields like CreatedAt
	terminal.DeviceID = updatedTerminal.DeviceID
	terminal.Location = updatedTerminal.Location
	terminal.Status = updatedTerminal.Status
	terminal.LastService = updatedTerminal.LastService
	terminal.Model = updatedTerminal.Model
	terminal.SerialNumber = updatedTerminal.SerialNumber
	terminal.AssignedTo = updatedTerminal.AssignedTo
	terminal.BusinessID = updatedTerminal.BusinessID
	terminal.IPAddress = updatedTerminal.IPAddress
	terminal.SoftwareVersion = updatedTerminal.SoftwareVersion
	terminal.Notes = updatedTerminal.Notes
	terminal.Configuration = updatedTerminal.Configuration
	terminal.LastSoftwareUpdate = updatedTerminal.LastSoftwareUpdate
	terminal.NextMaintenanceDate = updatedTerminal.NextMaintenanceDate
	terminal.IsOnline = updatedTerminal.IsOnline
	terminal.BatteryLevel = updatedTerminal.BatteryLevel
	terminal.LastTransactionTime = updatedTerminal.LastTransactionTime
	terminal.TransactionCount = updatedTerminal.TransactionCount
	terminal.Manufacturer = updatedTerminal.Manufacturer
	terminal.PurchaseDate = updatedTerminal.PurchaseDate
	terminal.WarrantyEndDate = updatedTerminal.WarrantyEndDate
	terminal.OperatingSystem = updatedTerminal.OperatingSystem
	terminal.Processor = updatedTerminal.Processor
	terminal.MemoryGB = updatedTerminal.MemoryGB
	terminal.StorageGB = updatedTerminal.StorageGB
	terminal.NetworkType = updatedTerminal.NetworkType
	terminal.ContactPerson = updatedTerminal.ContactPerson
	terminal.ContactEmail = updatedTerminal.ContactEmail
	terminal.ContactPhone = updatedTerminal.ContactPhone
	terminal.TerminalGroupID = updatedTerminal.TerminalGroupID

	if err := validateStruct(terminal); err != nil {
		log.Printf("Validation error for updating terminal %s: %v", terminalID, err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if result := DB.Save(&terminal); result.Error != nil {
		log.Printf("Error updating terminal %s in DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, "terminals", terminalID)

	json.NewEncoder(w).Encode(terminal)
	updateTerminalMetrics()
	logAudit("update", "Terminal", terminal.ID, r.RemoteAddr, generateUpdateDetails(oldTerminal, terminal))
}

func deleteTerminal(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var terminal Terminal
	if result := DB.Delete(&terminal, "id = ?", terminalID); result.Error != nil {
		log.Printf("Error deleting terminal %s from DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, "terminals", terminalID)

	json.NewEncoder(w).Encode(fmt.Sprintf("Terminal %s Deleted", terminalID))
	updateTerminalMetrics()
	logAudit("delete", "Terminal", terminalID, r.RemoteAddr, "Terminal deleted")
}

// Service Record Endpoints
func createServiceRecord(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var serviceRecord ServiceRecord
	if err := json.NewDecoder(r.Body).Decode(&serviceRecord); err != nil {
		log.Printf("Error decoding service record request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// Validate TerminalID exists
	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", serviceRecord.TerminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found for service record", http.StatusNotFound)
			return
		}
		log.Printf("Error checking terminal for service record: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	// Basic validation for ServiceRecord
	if err := validateStruct(serviceRecord); err != nil {
		log.Printf("Validation error for new service record: %v", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if result := DB.Create(&serviceRecord); result.Error != nil {
		log.Printf("Error creating service record in DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	serviceRecordCount.Inc()
	json.NewEncoder(w).Encode(serviceRecord)
	logAudit("create", "ServiceRecord", fmt.Sprintf("Terminal:%s, RecordID:%d", serviceRecord.TerminalID, serviceRecord.ID), r.RemoteAddr, "Service record created")
}

func getServiceRecords(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var serviceRecords []ServiceRecord
	if result := DB.Where("terminal_id = ?", terminalID).Find(&serviceRecords); result.Error != nil {
		log.Printf("Error fetching service records for terminal %s from DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(serviceRecords)
}

// Software Update Endpoints
func createSoftwareUpdate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var softwareUpdate SoftwareUpdate
	if err := json.NewDecoder(r.Body).Decode(&softwareUpdate); err != nil {
		log.Printf("Error decoding software update request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// Basic validation for SoftwareUpdate
	if err := validateStruct(softwareUpdate); err != nil {
		log.Printf("Validation error for new software update: %v", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if result := DB.Create(&softwareUpdate); result.Error != nil {
		log.Printf("Error creating software update in DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	softwareUpdateCount.Inc()
	json.NewEncoder(w).Encode(softwareUpdate)
	logAudit("create", "SoftwareUpdate", softwareUpdate.Version, r.RemoteAddr, "Software update created")
}

func getSoftwareUpdates(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var softwareUpdates []SoftwareUpdate
	if result := DB.Find(&softwareUpdates); result.Error != nil {
		log.Printf("Error fetching software updates from DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(softwareUpdates)
}

func applySoftwareUpdate(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]
	updateVersion := params["version"]

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s for software update: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	var softwareUpdate SoftwareUpdate
	if result := DB.First(&softwareUpdate, "version = ?", updateVersion); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Software update version not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching software update %s: %v", updateVersion, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	terminal.SoftwareVersion = softwareUpdate.Version
	terminal.LastSoftwareUpdate = time.Now()

	if result := DB.Save(&terminal); result.Error != nil {
		log.Printf("Error applying software update to terminal %s: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, "terminals", terminalID)
	json.NewEncoder(w).Encode(fmt.Sprintf("Software update %s applied to terminal %s", updateVersion, terminalID))
	logAudit("apply_software_update", "Terminal", terminalID, r.RemoteAddr, fmt.Sprintf("Applied software update %s", updateVersion))
}

// Terminal Configuration Endpoints
func updateTerminalConfiguration(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s for configuration update: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	var config map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
		log.Printf("Error decoding configuration request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	configBytes, err := json.Marshal(config)
	if err != nil {
		log.Printf("Error marshalling configuration to JSON: %v", err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	terminal.Configuration = string(configBytes)

	if result := DB.Save(&terminal); result.Error != nil {
		log.Printf("Error updating terminal configuration for %s: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, "terminals", terminalID)
	json.NewEncoder(w).Encode(fmt.Sprintf("Configuration updated for terminal %s", terminalID))
	logAudit("update_configuration", "Terminal", terminalID, r.RemoteAddr, "Terminal configuration updated")
}

func getTerminalConfiguration(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s for configuration: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	if terminal.Configuration == "" {
		json.NewEncoder(w).Encode(map[string]string{"message": "No configuration found for this terminal"})
		return
	}

	var config map[string]interface{}
	if err := json.Unmarshal([]byte(terminal.Configuration), &config); err != nil {
		log.Printf("Error unmarshalling terminal configuration for %s: %v", terminalID, err)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(config)
}

// Terminal Group Endpoints
func createTerminalGroup(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var group TerminalGroup
	if err := json.NewDecoder(r.Body).Decode(&group); err != nil {
		log.Printf("Error decoding terminal group request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// Basic validation for TerminalGroup
	if err := validateStruct(group); err != nil {
		log.Printf("Validation error for new terminal group: %v", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	if result := DB.Create(&group); result.Error != nil {
		log.Printf("Error creating terminal group in DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(group)
	updateTerminalMetrics()
	logAudit("create", "TerminalGroup", fmt.Sprintf("%d", group.ID), r.RemoteAddr, "Terminal group created")
}

func getTerminalGroups(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var groups []TerminalGroup
	if result := DB.Preload("Terminals").Find(&groups); result.Error != nil {
		log.Printf("Error fetching terminal groups from DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(groups)
}

// Scheduled Task Endpoints
func createScheduledTask(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var task ScheduledTask
	if err := json.NewDecoder(r.Body).Decode(&task); err != nil {
		log.Printf("Error decoding scheduled task request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// Basic validation for ScheduledTask
	if err := validateStruct(task); err != nil {
		log.Printf("Validation error for new scheduled task: %v", err)
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	task.Status = "pending"
	if result := DB.Create(&task); result.Error != nil {
		log.Printf("Error creating scheduled task in DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(task)
	updateTerminalMetrics()
	logAudit("create", "ScheduledTask", fmt.Sprintf("%d", task.ID), r.RemoteAddr, "Scheduled task created")
}

func getScheduledTasks(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var tasks []ScheduledTask
	if result := DB.Find(&tasks); result.Error != nil {
		log.Printf("Error fetching scheduled tasks from DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(tasks)
}

// Audit Log Endpoints
func getAuditLogs(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	var logs []AuditLog
	if result := DB.Order("timestamp desc").Limit(100).Find(&logs); result.Error != nil {
		log.Printf("Error fetching audit logs from DB: %v", result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(logs)
}

func logAudit(action, resourceType, resourceID, ipAddress, details string) {
	auditLog := AuditLog{
		Timestamp:    time.Now(),
		UserID:       "system", // In a real app, get this from authentication context
		Action:       action,
		ResourceType: resourceType,
		ResourceID:   resourceID,
		Details:      details,
		IPAddress:    ipAddress,
	}
	if result := DB.Create(&auditLog); result.Error != nil {
		log.Printf("Error logging audit entry: %v", result.Error)
	}
	auditLogCount.Inc()
}

func generateUpdateDetails(oldTerminal, newTerminal Terminal) string {
	details := make(map[string]interface{})
	valOld := reflect.ValueOf(oldTerminal)
	valNew := reflect.ValueOf(newTerminal)
	typ := reflect.TypeOf(oldTerminal)

	for i := 0; i < valOld.NumField(); i++ {
		fieldOld := valOld.Field(i)
		fieldNew := valNew.Field(i)
		fieldName := typ.Field(i).Name

		if fmt.Sprintf("%v", fieldOld.Interface()) != fmt.Sprintf("%v", fieldNew.Interface()) {
			details[fieldName] = fmt.Sprintf("%v -> %v", fieldOld.Interface(), fieldNew.Interface())
		}
	}
	jsonBytes, _ := json.Marshal(details)
	return string(jsonBytes)
}

func healthCheck(w http.ResponseWriter, r *http.Request) {
	// Check database connection
	sqlDB, err := DB.DB()
	if err != nil {
		log.Printf("Database connection error: %v", err)
		http.Error(w, "Database connection error", http.StatusInternalServerError)
		return
	}
	if err = sqlDB.Ping(); err != nil {
		log.Printf("Database ping error: %v", err)
		http.Error(w, "Database ping error", http.StatusInternalServerError)
		return
	}

	// Check Redis connection
	_, err = RedisClient.Ping(ctx).Result()
	if err != nil {
		log.Printf("Redis connection error: %v", err)
		http.Error(w, "Redis connection error", http.StatusInternalServerError)
		return
	}

	fmt.Fprintf(w, "POS Terminal Management Service is healthy!")
}

func main() {
	ConnectDatabase()
	ConnectRedis()

	r := mux.NewRouter()

	// Prometheus metrics endpoint
	r.Path("/metrics").Handler(promhttp.Handler())

	// Apply Prometheus middleware to all other routes
	r.Use(prometheusMiddleware)

	// CORS middleware
	c := cors.New(cors.Options{
		AllowedOrigins:   []string{"*"}, // Allow all origins for development
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"},
		AllowedHeaders:   []string{"Content-Type", "Authorization", "X-Tenant-Id", "X-Keycloak-Id", "X-Business-Id"},
		AllowCredentials: true,
		Debug:            false, // Disable debug to reduce log noise
	})

	// Terminal Management Endpoints
	r.HandleFunc("/health", healthCheck).Methods("GET")
	r.HandleFunc("/terminals", getTerminals).Methods("GET")
	r.HandleFunc("/terminals/{id}", getTerminal).Methods("GET")
	r.HandleFunc("/terminals", createTerminal).Methods("POST")
	r.HandleFunc("/terminals/{id}", updateTerminal).Methods("PUT")
	r.HandleFunc("/terminals/{id}", deleteTerminal).Methods("DELETE")

	// Service Record Endpoints
	r.HandleFunc("/terminals/{id}/servicerecords", createServiceRecord).Methods("POST")
	r.HandleFunc("/terminals/{id}/servicerecords", getServiceRecords).Methods("GET")

	// Software Update Endpoints
	r.HandleFunc("/softwareupdates", createSoftwareUpdate).Methods("POST")
	r.HandleFunc("/softwareupdates", getSoftwareUpdates).Methods("GET")
	r.HandleFunc("/terminals/{id}/softwareupdate/{version}", applySoftwareUpdate).Methods("PUT")

	// Terminal Configuration Endpoints
	r.HandleFunc("/terminals/{id}/configuration", updateTerminalConfiguration).Methods("PUT")
	r.HandleFunc("/terminals/{id}/configuration", getTerminalConfiguration).Methods("GET")

	// Reporting Endpoints
	r.HandleFunc("/reports/terminalstatus", getTerminalStatusReport).Methods("GET")
	r.HandleFunc("/reports/servicehistory", getServiceHistoryReport).Methods("GET")

	// Advanced Query Endpoints
	r.HandleFunc("/terminals/search", searchTerminals).Methods("GET")
	r.HandleFunc("/terminals/status/{status}", getTerminalsByStatus).Methods("GET")
	r.HandleFunc("/terminals/maintenance", getTerminalsNeedingMaintenance).Methods("GET")

	// Business Linking Endpoints
	r.HandleFunc("/terminals/{id}/link-business", linkTerminalToBusiness).Methods("PUT")
	r.HandleFunc("/terminals/business/{business_id}", getTerminalsByBusiness).Methods("GET")

	// Terminal Group Endpoints
	r.HandleFunc("/terminalgroups", createTerminalGroup).Methods("POST")
	r.HandleFunc("/terminalgroups", getTerminalGroups).Methods("GET")

	// Scheduled Task Endpoints
	r.HandleFunc("/scheduledtasks", createScheduledTask).Methods("POST")
	r.HandleFunc("/scheduledtasks", getScheduledTasks).Methods("GET")

	// Audit Log Endpoints
	r.HandleFunc("/auditlogs", getAuditLogs).Methods("GET")

	port := getEnv("APP_PORT", "8080")
	log.Printf("Server starting on port %s...", port)
	log.Fatal(http.ListenAndServe(":"+port, c.Handler(r)))
}

func getTerminalStatusReport(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var activeTerminals, inactiveTerminals, maintenanceTerminals []Terminal
	DB.Where("status = ?", "Active").Find(&activeTerminals)
	DB.Where("status = ?", "Inactive").Find(&inactiveTerminals)
	DB.Where("status = ?", "Maintenance").Find(&maintenanceTerminals)

	report := map[string]interface{}{
		"active_terminals":      len(activeTerminals),
		"inactive_terminals":    len(inactiveTerminals),
		"maintenance_terminals": len(maintenanceTerminals),
		"details": map[string]interface{}{
			"active":      activeTerminals,
			"inactive":    inactiveTerminals,
			"maintenance": maintenanceTerminals,
		},
	}
	json.NewEncoder(w).Encode(report)
}

func getServiceHistoryReport(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var serviceRecords []ServiceRecord
	DB.Order("service_date desc").Find(&serviceRecords)

	json.NewEncoder(w).Encode(serviceRecords)
}

func searchTerminals(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	query := r.URL.Query().Get("q")

	var terminals []Terminal
	// Search by Location, Model, SerialNumber, or AssignedTo
	DB.Where("location ILIKE ? OR model ILIKE ? OR serial_number ILIKE ? OR assigned_to ILIKE ?",
		"%"+query+"%", "%"+query+"%", "%"+query+"%", "%"+query+"%").Find(&terminals)

	json.NewEncoder(w).Encode(terminals)
}

func getTerminalsByStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	status := params["status"]

	var terminals []Terminal
	DB.Where("status ILIKE ?", "%"+status+"%").Find(&terminals)

	json.NewEncoder(w).Encode(terminals)
}

func getTerminalsNeedingMaintenance(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var terminals []Terminal
	// Terminals needing maintenance are those with status 'Maintenance' or next maintenance date in the past
	DB.Where("status = ? OR next_maintenance_date < ?", "Maintenance", time.Now()).Find(&terminals)

	json.NewEncoder(w).Encode(terminals)
}

func linkTerminalToBusiness(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	terminalID := params["id"]

	var payload struct {
		BusinessID string `json:"business_id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		log.Printf("Error decoding request body: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	var terminal Terminal
	if result := DB.First(&terminal, "id = ?", terminalID); result.Error != nil {
		if errors.Is(result.Error, gorm.ErrRecordNotFound) {
			http.Error(w, "Terminal not found", http.StatusNotFound)
			return
		}
		log.Printf("Error fetching terminal %s from DB: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	terminal.BusinessID = payload.BusinessID

	if result := DB.Save(&terminal); result.Error != nil {
		log.Printf("Error updating terminal %s business: %v", terminalID, result.Error)
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}

	RedisClient.Del(ctx, terminalID)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"message":  "Terminal linked to business successfully",
		"terminal": terminal,
	})
	logAudit("link_business", "Terminal", terminalID, r.RemoteAddr, fmt.Sprintf("Linked to business %s", payload.BusinessID))
}

func getTerminalsByBusiness(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	params := mux.Vars(r)
	businessID := params["business_id"]

	var terminals []Terminal
	DB.Where("business_id = ?", businessID).Order("created_at desc").Find(&terminals)

	json.NewEncoder(w).Encode(terminals)
}
