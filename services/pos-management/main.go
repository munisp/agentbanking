package main

import (
	"crypto/tls"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// POS Device Models
type POSDevice struct {
	ID                 string                 `json:"id" gorm:"primaryKey"`
	SerialNumber       string                 `json:"serial_number" gorm:"uniqueIndex"`
	Model              string                 `json:"model"`
	Manufacturer       string                 `json:"manufacturer"`
	FirmwareVersion    string                 `json:"firmware_version"`
	AgentID            string                 `json:"agent_id"`
	LocationID         string                 `json:"location_id"`
	Status             string                 `json:"status"` // online, offline, maintenance, error
	LastHeartbeat      time.Time              `json:"last_heartbeat"`
	Configuration      map[string]interface{} `json:"configuration" gorm:"type:jsonb"`
	Capabilities       []string               `json:"capabilities" gorm:"type:text[]"`
	NetworkInfo        NetworkInfo            `json:"network_info" gorm:"embedded"`
	SecurityInfo       SecurityInfo           `json:"security_info" gorm:"embedded"`
	PerformanceMetrics PerformanceMetrics     `json:"performance_metrics" gorm:"embedded"`
	CreatedAt          time.Time              `json:"created_at"`
	UpdatedAt          time.Time              `json:"updated_at"`
}

type NetworkInfo struct {
	IPAddress      string `json:"ip_address"`
	MACAddress     string `json:"mac_address"`
	NetworkType    string `json:"network_type"` // wifi, ethernet, cellular
	SignalStrength int    `json:"signal_strength"`
	Bandwidth      int    `json:"bandwidth"`
}

type SecurityInfo struct {
	CertificateExpiry time.Time `json:"certificate_expiry"`
	LastSecurityScan  time.Time `json:"last_security_scan"`
	SecurityLevel     string    `json:"security_level"` // high, medium, low
	EncryptionEnabled bool      `json:"encryption_enabled"`
	TamperDetected    bool      `json:"tamper_detected"`
}

type PerformanceMetrics struct {
	CPUUsage       float64 `json:"cpu_usage"`
	MemoryUsage    float64 `json:"memory_usage"`
	DiskUsage      float64 `json:"disk_usage"`
	TransactionTPS float64 `json:"transaction_tps"`
	UptimeHours    float64 `json:"uptime_hours"`
	ErrorRate      float64 `json:"error_rate"`
}

type Application struct {
	ID            string                 `json:"id" gorm:"primaryKey"`
	Name          string                 `json:"name"`
	Version       string                 `json:"version"`
	Description   string                 `json:"description"`
	Type          string                 `json:"type"` // banking, payment, utility, security
	Size          int64                  `json:"size"`
	Checksum      string                 `json:"checksum"`
	Dependencies  []string               `json:"dependencies" gorm:"type:text[]"`
	Configuration map[string]interface{} `json:"configuration" gorm:"type:jsonb"`
	CreatedAt     time.Time              `json:"created_at"`
	UpdatedAt     time.Time              `json:"updated_at"`
}

type POSApplication struct {
	ID            string                 `json:"id" gorm:"primaryKey"`
	POSDeviceID   string                 `json:"pos_device_id"`
	ApplicationID string                 `json:"application_id"`
	Status        string                 `json:"status"` // installed, running, stopped, error, updating
	Version       string                 `json:"version"`
	InstallDate   time.Time              `json:"install_date"`
	LastUsed      time.Time              `json:"last_used"`
	Configuration map[string]interface{} `json:"configuration" gorm:"type:jsonb"`
	CreatedAt     time.Time              `json:"created_at"`
	UpdatedAt     time.Time              `json:"updated_at"`
}

type RemoteCommand struct {
	ID          string                 `json:"id" gorm:"primaryKey"`
	POSDeviceID string                 `json:"pos_device_id"`
	Command     string                 `json:"command"` // install, uninstall, update, restart, configure
	Parameters  map[string]interface{} `json:"parameters" gorm:"type:jsonb"`
	Status      string                 `json:"status"` // pending, executing, completed, failed
	Result      string                 `json:"result"`
	CreatedAt   time.Time              `json:"created_at"`
	ExecutedAt  *time.Time             `json:"executed_at"`
	CompletedAt *time.Time             `json:"completed_at"`
}

type Transaction struct {
	ID            string                 `json:"id" gorm:"primaryKey"`
	POSDeviceID   string                 `json:"pos_device_id"`
	TransactionID string                 `json:"transaction_id"`
	Type          string                 `json:"type"` // payment, withdrawal, deposit, transfer
	Amount        float64                `json:"amount"`
	Currency      string                 `json:"currency"`
	Status        string                 `json:"status"` // pending, completed, failed, cancelled
	CustomerID    string                 `json:"customer_id"`
	AgentID       string                 `json:"agent_id"`
	Metadata      map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
	CreatedAt     time.Time              `json:"created_at"`
	CompletedAt   *time.Time             `json:"completed_at"`
}

// WebSocket Connection Manager
type ConnectionManager struct {
	connections map[string]*websocket.Conn
	mutex       sync.RWMutex
	upgrader    websocket.Upgrader
}

func NewConnectionManager() *ConnectionManager {
	return &ConnectionManager{
		connections: make(map[string]*websocket.Conn),
		upgrader: websocket.Upgrader{
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins for development
			},
		},
	}
}

func (cm *ConnectionManager) AddConnection(deviceID string, conn *websocket.Conn) {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()
	cm.connections[deviceID] = conn
}

func (cm *ConnectionManager) RemoveConnection(deviceID string) {
	cm.mutex.Lock()
	defer cm.mutex.Unlock()
	if conn, exists := cm.connections[deviceID]; exists {
		conn.Close()
		delete(cm.connections, deviceID)
	}
}

func (cm *ConnectionManager) SendMessage(deviceID string, message interface{}) error {
	cm.mutex.RLock()
	conn, exists := cm.connections[deviceID]
	cm.mutex.RUnlock()

	if !exists {
		return fmt.Errorf("device %s not connected", deviceID)
	}

	return conn.WriteJSON(message)
}

func (cm *ConnectionManager) BroadcastMessage(message interface{}) {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()

	for deviceID, conn := range cm.connections {
		if err := conn.WriteJSON(message); err != nil {
			log.Printf("Error broadcasting to device %s: %v", deviceID, err)
			conn.Close()
			delete(cm.connections, deviceID)
		}
	}
}

// POS Management Service
type POSManagementService struct {
	db                *gorm.DB
	connectionManager *ConnectionManager
	keycloakClient    *KeycloakClient
	pbacClient        *PBACClient
	fluvioClient      *FluvioClient
}

// External Service Clients
type KeycloakClient struct {
	BaseURL      string
	ClientID     string
	ClientSecret string
	httpClient   *http.Client
}

type PBACClient struct {
	BaseURL    string
	httpClient *http.Client
}

type FluvioClient struct {
	BootstrapServers string
	Topic            string
}

// Prometheus Metrics
var (
	posDevicesTotal = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "pos_devices_total",
			Help: "Total number of POS devices",
		},
		[]string{"status"},
	)

	posTransactionsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "pos_transactions_total",
			Help: "Total number of POS transactions",
		},
		[]string{"device_id", "type", "status"},
	)

	posCommandsTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "pos_commands_total",
			Help: "Total number of remote commands sent to POS devices",
		},
		[]string{"command", "status"},
	)

	posConnectionsActive = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "pos_connections_active",
			Help: "Number of active POS device connections",
		},
	)
)

func init() {
	prometheus.MustRegister(posDevicesTotal)
	prometheus.MustRegister(posTransactionsTotal)
	prometheus.MustRegister(posCommandsTotal)
	prometheus.MustRegister(posConnectionsActive)
}

func NewPOSManagementService() *POSManagementService {
	// Database connection
	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=require",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "password"),
		getEnv("DB_NAME", "link_core_banking"),
		getEnv("DB_PORT", "5432"),
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}

	// Auto-migrate tables
	db.AutoMigrate(&POSDevice{}, &Application{}, &POSApplication{}, &RemoteCommand{}, &Transaction{})

	// Initialize external clients
	keycloakClient := &KeycloakClient{
		BaseURL:      getEnv("KEYCLOAK_URL", getEnv("SERVICE_URL_8080", "http://localhost:8080")),
		ClientID:     getEnv("KEYCLOAK_CLIENT_ID", "pos-management"),
		ClientSecret: getEnv("KEYCLOAK_CLIENT_SECRET", "secret"),
		httpClient:   &http.Client{Timeout: 30 * time.Second},
	}

	pbacClient := &PBACClient{
		BaseURL:    getEnv("PBAC_URL", getEnv("SERVICE_URL_8090", "http://localhost:8090")),
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}

	fluvioClient := &FluvioClient{
		BootstrapServers: getEnv("FLUVIO_SERVERS", getEnv("SERVICE_URL_9003", "localhost:9003")),
		Topic:            getEnv("FLUVIO_TOPIC", "pos-events"),
	}

	return &POSManagementService{
		db:                db,
		connectionManager: NewConnectionManager(),
		keycloakClient:    keycloakClient,
		pbacClient:        pbacClient,
		fluvioClient:      fluvioClient,
	}
}

// POS Device Management Endpoints
func (s *POSManagementService) RegisterDevice(c *gin.Context) {
	var device POSDevice
	if err := c.ShouldBindJSON(&device); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate with PBAC
	if !s.validatePBACPermission(c, "pos_device", "register", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	device.ID = generateID("POS")
	device.Status = "offline"
	device.CreatedAt = time.Now()
	device.UpdatedAt = time.Now()

	if err := s.db.Create(&device).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to register device"})
		return
	}

	// Send event to Fluvio
	s.sendFluvioEvent("device_registered", map[string]interface{}{
		"device_id":     device.ID,
		"serial_number": device.SerialNumber,
		"agent_id":      device.AgentID,
		"timestamp":     time.Now(),
	})

	posDevicesTotal.WithLabelValues("offline").Inc()

	c.JSON(http.StatusCreated, device)
}

func (s *POSManagementService) GetDevices(c *gin.Context) {
	var devices []POSDevice
	query := s.db

	// Filter by agent if specified
	if agentID := c.Query("agent_id"); agentID != "" {
		if !s.validatePBACPermission(c, "pos_device", "read", agentID) {
			c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
			return
		}
		query = query.Where("agent_id = ?", agentID)
	}

	// Filter by status if specified
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}

	if err := query.Find(&devices).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch devices"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"devices": devices,
		"total":   len(devices),
	})
}

func (s *POSManagementService) GetDevice(c *gin.Context) {
	deviceID := c.Param("id")
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}
	if !s.validatePBACPermission(c, "pos_device", "read", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}
	c.JSON(http.StatusOK, device)
}

func (s *POSManagementService) UpdateDevice(c *gin.Context) {
	deviceID := c.Param("id")

	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_device", "update", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	var updateData map[string]interface{}
	if err := c.ShouldBindJSON(&updateData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	updateData["updated_at"] = time.Now()

	if err := s.db.Model(&device).Updates(updateData).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update device"})
		return
	}

	// Send real-time update to device
	s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type": "configuration_update",
		"data": updateData,
	})

	c.JSON(http.StatusOK, gin.H{"message": "Device updated successfully"})
}

// Application Management
func (s *POSManagementService) DeployApplication(c *gin.Context) {
	var request struct {
		DeviceID      string                 `json:"device_id"`
		ApplicationID string                 `json:"application_id"`
		Configuration map[string]interface{} `json:"configuration"`
	}

	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate device exists and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", request.DeviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_application", "deploy", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Get application details
	var app Application
	if err := s.db.First(&app, "id = ?", request.ApplicationID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Application not found"})
		return
	}

	// Create remote command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: request.DeviceID,
		Command:     "install",
		Parameters: map[string]interface{}{
			"application_id":   request.ApplicationID,
			"application_name": app.Name,
			"version":          app.Version,
			"configuration":    request.Configuration,
		},
		Status:    "pending",
		CreatedAt: time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create deployment command"})
		return
	}

	// Send command to device via WebSocket
	if err := s.connectionManager.SendMessage(request.DeviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "install",
		"parameters": command.Parameters,
	}); err != nil {
		log.Printf("Failed to send command to device %s: %v", request.DeviceID, err)
		// Update command status to failed
		s.db.Model(&command).Updates(map[string]interface{}{
			"status": "failed",
			"result": "Device not connected",
		})
	}

	posCommandsTotal.WithLabelValues("install", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Application deployment initiated",
	})
}

func (s *POSManagementService) RemoveApplication(c *gin.Context) {
	deviceID := c.Param("id")
	applicationID := c.Param("application_id")

	// Validate device and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_application", "remove", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Create remote command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: deviceID,
		Command:     "uninstall",
		Parameters: map[string]interface{}{
			"application_id": applicationID,
		},
		Status:    "pending",
		CreatedAt: time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create removal command"})
		return
	}

	// Send command to device
	s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "uninstall",
		"parameters": command.Parameters,
	})

	posCommandsTotal.WithLabelValues("uninstall", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Application removal initiated",
	})
}

// WebSocket Handler for Bi-directional Communication
func (s *POSManagementService) HandleWebSocket(c *gin.Context) {
	deviceID := c.Query("device_id")
	if deviceID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "device_id is required"})
		return
	}

	// Validate device exists
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	// Upgrade to WebSocket
	conn, err := s.connectionManager.upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("WebSocket upgrade failed: %v", err)
		return
	}
	defer conn.Close()

	// Add connection to manager
	s.connectionManager.AddConnection(deviceID, conn)
	defer s.connectionManager.RemoveConnection(deviceID)

	// Update device status to online
	s.db.Model(&device).Updates(POSDevice{
		Status:        "online",
		LastHeartbeat: time.Now(),
	})

	// Update metrics
	posConnectionsActive.Inc()
	defer posConnectionsActive.Dec()

	// Send connection event to Fluvio
	s.sendFluvioEvent("device_connected", map[string]interface{}{
		"device_id": deviceID,
		"timestamp": time.Now(),
		"agent_id":  device.AgentID,
		"location":  device.LocationID,
	})

	// Handle incoming messages
	for {
		var message map[string]interface{}
		if err := conn.ReadJSON(&message); err != nil {
			log.Printf("WebSocket read error for device %s: %v", deviceID, err)
			break
		}

		// Process message based on type
		s.processDeviceMessage(deviceID, message)
	}

	// Update device status to offline
	s.db.Model(&device).Updates(POSDevice{
		Status:        "offline",
		LastHeartbeat: time.Now(),
	})

	// Send disconnection event to Fluvio
	s.sendFluvioEvent("device_disconnected", map[string]interface{}{
		"device_id": deviceID,
		"timestamp": time.Now(),
	})
}

func (s *POSManagementService) processDeviceMessage(deviceID string, message map[string]interface{}) {
	messageType, ok := message["type"].(string)
	if !ok {
		log.Printf("Invalid message type from device %s", deviceID)
		return
	}

	switch messageType {
	case "heartbeat":
		s.handleHeartbeat(deviceID, message)
	case "command_response":
		s.handleCommandResponse(deviceID, message)
	case "transaction_update":
		s.handleTransactionUpdate(deviceID, message)
	case "application_status":
		s.handleApplicationStatus(deviceID, message)
	case "performance_metrics":
		s.handlePerformanceMetrics(deviceID, message)
	case "security_alert":
		s.handleSecurityAlert(deviceID, message)
	case "error_report":
		s.handleErrorReport(deviceID, message)
	default:
		log.Printf("Unknown message type '%s' from device %s", messageType, deviceID)
	}
}

func (s *POSManagementService) handleHeartbeat(deviceID string, message map[string]interface{}) {
	// Update device last heartbeat
	s.db.Model(&POSDevice{}).Where("id = ?", deviceID).Updates(POSDevice{
		LastHeartbeat: time.Now(),
		Status:        "online",
	})

	// Extract and update performance metrics if provided
	if metrics, ok := message["metrics"].(map[string]interface{}); ok {
		var perfMetrics PerformanceMetrics
		if data, err := json.Marshal(metrics); err == nil {
			json.Unmarshal(data, &perfMetrics)
			s.db.Model(&POSDevice{}).Where("id = ?", deviceID).Updates(POSDevice{
				PerformanceMetrics: perfMetrics,
			})
		}
	}

	// Send heartbeat event to Fluvio for monitoring
	s.sendFluvioEvent("device_heartbeat", map[string]interface{}{
		"device_id": deviceID,
		"timestamp": time.Now(),
		"metrics":   message["metrics"],
	})
}

func (s *POSManagementService) handleCommandResponse(deviceID string, message map[string]interface{}) {
	commandID, ok := message["command_id"].(string)
	if !ok {
		log.Printf("Command response missing command_id from device %s", deviceID)
		return
	}

	status, _ := message["status"].(string)
	result, _ := message["result"].(string)

	// Update command in database
	now := time.Now()
	updates := map[string]interface{}{
		"status":       status,
		"result":       result,
		"completed_at": &now,
	}

	if err := s.db.Model(&RemoteCommand{}).Where("id = ? AND pos_device_id = ?", commandID, deviceID).Updates(updates).Error; err != nil {
		log.Printf("Failed to update command %s: %v", commandID, err)
		return
	}

	// Update metrics
	posCommandsTotal.WithLabelValues("unknown", status).Inc()

	// Send command completion event to Fluvio
	s.sendFluvioEvent("command_completed", map[string]interface{}{
		"device_id":  deviceID,
		"command_id": commandID,
		"status":     status,
		"result":     result,
		"timestamp":  time.Now(),
	})
}

func (s *POSManagementService) handleTransactionUpdate(deviceID string, message map[string]interface{}) {
	transactionID, ok := message["transaction_id"].(string)
	if !ok {
		log.Printf("Transaction update missing transaction_id from device %s", deviceID)
		return
	}

	// Update transaction in database
	var transaction Transaction
	if err := s.db.First(&transaction, "transaction_id = ? AND pos_device_id = ?", transactionID, deviceID).Error; err != nil {
		log.Printf("Transaction %s not found for device %s", transactionID, deviceID)
		return
	}

	if status, ok := message["status"].(string); ok {
		transaction.Status = status
		if status == "completed" {
			now := time.Now()
			transaction.CompletedAt = &now
		}
	}

	if metadata, ok := message["metadata"].(map[string]interface{}); ok {
		transaction.Metadata = metadata
	}

	s.db.Save(&transaction)

	// Update metrics
	posTransactionsTotal.WithLabelValues(deviceID, transaction.Type, transaction.Status).Inc()

	// Send transaction update to Fluvio
	s.sendFluvioEvent("transaction_updated", map[string]interface{}{
		"device_id":      deviceID,
		"transaction_id": transactionID,
		"status":         transaction.Status,
		"amount":         transaction.Amount,
		"type":           transaction.Type,
		"timestamp":      time.Now(),
	})
}

func (s *POSManagementService) handleApplicationStatus(deviceID string, message map[string]interface{}) {
	applicationID, ok := message["application_id"].(string)
	if !ok {
		log.Printf("Application status missing application_id from device %s", deviceID)
		return
	}

	status, _ := message["status"].(string)
	version, _ := message["version"].(string)

	// Update or create POS application record
	var posApp POSApplication
	if err := s.db.First(&posApp, "pos_device_id = ? AND application_id = ?", deviceID, applicationID).Error; err != nil {
		// Create new record
		posApp = POSApplication{
			ID:            generateID("POSAPP"),
			POSDeviceID:   deviceID,
			ApplicationID: applicationID,
			Status:        status,
			Version:       version,
			InstallDate:   time.Now(),
			CreatedAt:     time.Now(),
			UpdatedAt:     time.Now(),
		}
		s.db.Create(&posApp)
	} else {
		// Update existing record
		posApp.Status = status
		posApp.Version = version
		posApp.LastUsed = time.Now()
		posApp.UpdatedAt = time.Now()
		s.db.Save(&posApp)
	}

	// Send application status to Fluvio
	s.sendFluvioEvent("application_status_updated", map[string]interface{}{
		"device_id":      deviceID,
		"application_id": applicationID,
		"status":         status,
		"version":        version,
		"timestamp":      time.Now(),
	})
}

func (s *POSManagementService) handlePerformanceMetrics(deviceID string, message map[string]interface{}) {
	if metrics, ok := message["metrics"].(map[string]interface{}); ok {
		var perfMetrics PerformanceMetrics
		if data, err := json.Marshal(metrics); err == nil {
			json.Unmarshal(data, &perfMetrics)

			// Update device performance metrics
			s.db.Model(&POSDevice{}).Where("id = ?", deviceID).Updates(POSDevice{
				PerformanceMetrics: perfMetrics,
			})

			// Send metrics to Fluvio for analytics
			s.sendFluvioEvent("device_metrics", map[string]interface{}{
				"device_id": deviceID,
				"metrics":   perfMetrics,
				"timestamp": time.Now(),
			})
		}
	}
}

func (s *POSManagementService) handleSecurityAlert(deviceID string, message map[string]interface{}) {
	alertType, _ := message["alert_type"].(string)
	severity, _ := message["severity"].(string)
	description, _ := message["description"].(string)

	// Send security alert to Fluvio for immediate processing
	s.sendFluvioEvent("security_alert", map[string]interface{}{
		"device_id":   deviceID,
		"alert_type":  alertType,
		"severity":    severity,
		"description": description,
		"timestamp":   time.Now(),
	})

	// Update device security info if tamper detected
	if alertType == "tamper_detected" {
		s.db.Model(&POSDevice{}).Where("id = ?", deviceID).Updates(POSDevice{
			SecurityInfo: SecurityInfo{
				TamperDetected:   true,
				LastSecurityScan: time.Now(),
				SecurityLevel:    "critical",
			},
		})
	}

	log.Printf("Security alert from device %s: %s - %s", deviceID, alertType, description)
}

func (s *POSManagementService) handleErrorReport(deviceID string, message map[string]interface{}) {
	errorType, _ := message["error_type"].(string)
	errorCode, _ := message["error_code"].(string)
	description, _ := message["description"].(string)

	// Send error report to Fluvio for analysis
	s.sendFluvioEvent("device_error", map[string]interface{}{
		"device_id":   deviceID,
		"error_type":  errorType,
		"error_code":  errorCode,
		"description": description,
		"timestamp":   time.Now(),
	})

	log.Printf("Error report from device %s: %s (%s) - %s", deviceID, errorType, errorCode, description)
}

// Remote Application Management
func (s *POSManagementService) PushApplication(c *gin.Context) {
	deviceID := c.Param("id")

	var request struct {
		ApplicationName string                 `json:"application_name"`
		Version         string                 `json:"version"`
		PackageURL      string                 `json:"package_url"`
		Checksum        string                 `json:"checksum"`
		Configuration   map[string]interface{} `json:"configuration"`
		ForceUpdate     bool                   `json:"force_update"`
	}

	if err := c.ShouldBindJSON(&request); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate device exists and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_application", "push", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Create push command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: deviceID,
		Command:     "push_application",
		Parameters: map[string]interface{}{
			"application_name": request.ApplicationName,
			"version":          request.Version,
			"package_url":      request.PackageURL,
			"checksum":         request.Checksum,
			"configuration":    request.Configuration,
			"force_update":     request.ForceUpdate,
		},
		Status:    "pending",
		CreatedAt: time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create push command"})
		return
	}

	// Send command to device via WebSocket
	if err := s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "push_application",
		"parameters": command.Parameters,
	}); err != nil {
		log.Printf("Failed to send push command to device %s: %v", deviceID, err)
		s.db.Model(&command).Updates(map[string]interface{}{
			"status": "failed",
			"result": "Device not connected",
		})
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Device not connected"})
		return
	}

	posCommandsTotal.WithLabelValues("push_application", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Application push initiated",
	})
}

func (s *POSManagementService) PullApplication(c *gin.Context) {
	deviceID := c.Param("id")
	applicationName := c.Param("application_name")

	// Validate device exists and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_application", "pull", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Create pull command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: deviceID,
		Command:     "pull_application",
		Parameters: map[string]interface{}{
			"application_name": applicationName,
		},
		Status:    "pending",
		CreatedAt: time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create pull command"})
		return
	}

	// Send command to device via WebSocket
	if err := s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "pull_application",
		"parameters": command.Parameters,
	}); err != nil {
		log.Printf("Failed to send pull command to device %s: %v", deviceID, err)
		s.db.Model(&command).Updates(map[string]interface{}{
			"status": "failed",
			"result": "Device not connected",
		})
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Device not connected"})
		return
	}

	posCommandsTotal.WithLabelValues("pull_application", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Application pull initiated",
	})
}

// Remote Configuration Management
func (s *POSManagementService) UpdateConfiguration(c *gin.Context) {
	deviceID := c.Param("id")

	var configUpdate map[string]interface{}
	if err := c.ShouldBindJSON(&configUpdate); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate device exists and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_device", "configure", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Create configuration update command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: deviceID,
		Command:     "update_configuration",
		Parameters: map[string]interface{}{
			"configuration": configUpdate,
		},
		Status:    "pending",
		CreatedAt: time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create configuration command"})
		return
	}

	// Send command to device via WebSocket
	if err := s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "update_configuration",
		"parameters": command.Parameters,
	}); err != nil {
		log.Printf("Failed to send configuration update to device %s: %v", deviceID, err)
		s.db.Model(&command).Updates(map[string]interface{}{
			"status": "failed",
			"result": "Device not connected",
		})
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Device not connected"})
		return
	}

	// Update local configuration
	device.Configuration = configUpdate
	device.UpdatedAt = time.Now()
	s.db.Save(&device)

	posCommandsTotal.WithLabelValues("update_configuration", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Configuration update initiated",
	})
}

// Remote Device Control
func (s *POSManagementService) RestartDevice(c *gin.Context) {
	deviceID := c.Param("id")

	// Validate device exists and permissions
	var device POSDevice
	if err := s.db.First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	if !s.validatePBACPermission(c, "pos_device", "restart", device.AgentID) {
		c.JSON(http.StatusForbidden, gin.H{"error": "Access denied"})
		return
	}

	// Create restart command
	command := RemoteCommand{
		ID:          generateID("CMD"),
		POSDeviceID: deviceID,
		Command:     "restart",
		Parameters:  map[string]interface{}{},
		Status:      "pending",
		CreatedAt:   time.Now(),
	}

	if err := s.db.Create(&command).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create restart command"})
		return
	}

	// Send command to device via WebSocket
	if err := s.connectionManager.SendMessage(deviceID, map[string]interface{}{
		"type":       "remote_command",
		"command_id": command.ID,
		"command":    "restart",
		"parameters": command.Parameters,
	}); err != nil {
		log.Printf("Failed to send restart command to device %s: %v", deviceID, err)
		s.db.Model(&command).Updates(map[string]interface{}{
			"status": "failed",
			"result": "Device not connected",
		})
		c.JSON(http.StatusServiceUnavailable, gin.H{"error": "Device not connected"})
		return
	}

	posCommandsTotal.WithLabelValues("restart", "pending").Inc()

	c.JSON(http.StatusAccepted, gin.H{
		"command_id": command.ID,
		"status":     "pending",
		"message":    "Device restart initiated",
	})
}

func (s *POSManagementService) GetDeviceStatus(c *gin.Context) {
	deviceID := c.Param("id")

	var device POSDevice
	if err := s.db.Preload("Applications").First(&device, "id = ?", deviceID).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "Device not found"})
		return
	}

	// Get recent commands
	var recentCommands []RemoteCommand
	s.db.Where("pos_device_id = ?", deviceID).Order("created_at DESC").Limit(10).Find(&recentCommands)

	// Get recent transactions
	var recentTransactions []Transaction
	s.db.Where("pos_device_id = ?", deviceID).Order("created_at DESC").Limit(10).Find(&recentTransactions)

	// Check if device is currently connected
	isConnected := s.connectionManager.IsConnected(deviceID)

	status := map[string]interface{}{
		"device":              device,
		"is_connected":        isConnected,
		"recent_commands":     recentCommands,
		"recent_transactions": recentTransactions,
		"last_seen":           device.LastHeartbeat,
		"uptime_hours":        device.PerformanceMetrics.UptimeHours,
	}

	c.JSON(http.StatusOK, status)
}

// Enhanced Connection Manager Methods
func (cm *ConnectionManager) IsConnected(deviceID string) bool {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()
	_, exists := cm.connections[deviceID]
	return exists
}

func (cm *ConnectionManager) GetConnectedDevices() []string {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()

	devices := make([]string, 0, len(cm.connections))
	for deviceID := range cm.connections {
		devices = append(devices, deviceID)
	}
	return devices
}

func (cm *ConnectionManager) GetConnectionCount() int {
	cm.mutex.RLock()
	defer cm.mutex.RUnlock()
	return len(cm.connections)
}

// External Service Integration Methods
func (s *POSManagementService) validatePBACPermission(c *gin.Context, resource, action, context string) bool {
	// Extract JWT token from Authorization header
	authHeader := c.GetHeader("Authorization")
	if authHeader == "" {
		log.Printf("No authorization header provided")
		return false
	}

	token := strings.TrimPrefix(authHeader, "Bearer ")

	// Make PBAC evaluation request
	request := map[string]interface{}{
		"token":    token,
		"resource": resource,
		"action":   action,
		"context":  context,
	}

	requestBody, _ := json.Marshal(request)
	resp, err := s.pbacClient.httpClient.Post(
		s.pbacClient.BaseURL+"/api/v1/evaluate",
		"application/json",
		strings.NewReader(string(requestBody)),
	)
	if err != nil {
		log.Printf("PBAC evaluation error: %v", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("PBAC evaluation failed with status: %d", resp.StatusCode)
		return false
	}

	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		log.Printf("PBAC response decode error: %v", err)
		return false
	}

	allowed, ok := result["allowed"].(bool)
	return ok && allowed
}

func (s *POSManagementService) validateKeycloakToken(token string) (map[string]interface{}, error) {
	req, err := http.NewRequest("GET",
		fmt.Sprintf("%s/auth/realms/remittance/protocol/openid_connect/userinfo", s.keycloakClient.BaseURL),
		nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("Authorization", "Bearer "+token)

	resp, err := s.keycloakClient.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("invalid token, status: %d", resp.StatusCode)
	}

	var userInfo map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&userInfo); err != nil {
		return nil, err
	}

	return userInfo, nil
}

func (s *POSManagementService) sendFluvioEvent(eventType string, data map[string]interface{}) {
	event := map[string]interface{}{
		"event_type": eventType,
		"data":       data,
		"timestamp":  time.Now(),
		"source":     "pos-management-service",
	}

	// Create HTTP request to Fluvio REST API
	eventJSON, err := json.Marshal(event)
	if err != nil {
		log.Printf("Failed to marshal Fluvio event: %v", err)
		return
	}

	req, err := http.NewRequest("POST",
		fmt.Sprintf("%s/topics/%s", s.fluvioClient.BootstrapServers, s.fluvioClient.Topic),
		strings.NewReader(string(eventJSON)))
	if err != nil {
		log.Printf("Failed to create Fluvio request: %v", err)
		return
	}

	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
		},
	}

	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Failed to send event to Fluvio: %v", err)
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		log.Printf("Fluvio event failed with status %d: %s", resp.StatusCode, string(body))
		return
	}

	log.Printf("Fluvio event sent successfully: %s", eventType)
}

// Additional API Endpoints
func (s *POSManagementService) GetDeviceApplications(c *gin.Context) {
	deviceID := c.Param("id")

	var applications []POSApplication
	if err := s.db.Where("pos_device_id = ?", deviceID).Find(&applications).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch applications"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"applications": applications,
		"total":        len(applications),
	})
}

func (s *POSManagementService) GetDeviceCommands(c *gin.Context) {
	deviceID := c.Param("id")

	var commands []RemoteCommand
	query := s.db.Where("pos_device_id = ?", deviceID)

	// Filter by status if provided
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}

	// Pagination
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))
	offset := (page - 1) * limit

	var total int64
	query.Model(&RemoteCommand{}).Count(&total)

	if err := query.Order("created_at DESC").Offset(offset).Limit(limit).Find(&commands).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch commands"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"commands": commands,
		"total":    total,
		"page":     page,
		"limit":    limit,
	})
}

func (s *POSManagementService) GetDeviceTransactions(c *gin.Context) {
	deviceID := c.Param("id")

	var transactions []Transaction
	query := s.db.Where("pos_device_id = ?", deviceID)

	// Filter by status if provided
	if status := c.Query("status"); status != "" {
		query = query.Where("status = ?", status)
	}

	// Filter by type if provided
	if txnType := c.Query("type"); txnType != "" {
		query = query.Where("type = ?", txnType)
	}

	// Date range filter
	if startDate := c.Query("start_date"); startDate != "" {
		query = query.Where("created_at >= ?", startDate)
	}
	if endDate := c.Query("end_date"); endDate != "" {
		query = query.Where("created_at <= ?", endDate)
	}

	// Pagination
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "50"))
	offset := (page - 1) * limit

	var total int64
	query.Model(&Transaction{}).Count(&total)

	if err := query.Order("created_at DESC").Offset(offset).Limit(limit).Find(&transactions).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch transactions"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"transactions": transactions,
		"total":        total,
		"page":         page,
		"limit":        limit,
	})
}

func (s *POSManagementService) GetDeviceAnalytics(c *gin.Context) {
	// Get device statistics
	var stats struct {
		TotalDevices      int64 `json:"total_devices"`
		OnlineDevices     int64 `json:"online_devices"`
		OfflineDevices    int64 `json:"offline_devices"`
		ErrorDevices      int64 `json:"error_devices"`
		ActiveConnections int   `json:"active_connections"`
	}

	s.db.Model(&POSDevice{}).Count(&stats.TotalDevices)
	s.db.Model(&POSDevice{}).Where("status = ?", "online").Count(&stats.OnlineDevices)
	s.db.Model(&POSDevice{}).Where("status = ?", "offline").Count(&stats.OfflineDevices)
	s.db.Model(&POSDevice{}).Where("status = ?", "error").Count(&stats.ErrorDevices)
	stats.ActiveConnections = s.connectionManager.GetConnectionCount()

	// Get transaction statistics for today
	today := time.Now().Format("2006-01-02")
	var txnStats struct {
		TotalTransactions     int64   `json:"total_transactions"`
		CompletedTransactions int64   `json:"completed_transactions"`
		FailedTransactions    int64   `json:"failed_transactions"`
		TotalAmount           float64 `json:"total_amount"`
	}

	s.db.Model(&Transaction{}).Where("DATE(created_at) = ?", today).Count(&txnStats.TotalTransactions)
	s.db.Model(&Transaction{}).Where("DATE(created_at) = ? AND status = ?", today, "completed").Count(&txnStats.CompletedTransactions)
	s.db.Model(&Transaction{}).Where("DATE(created_at) = ? AND status = ?", today, "failed").Count(&txnStats.FailedTransactions)

	var totalAmount sql.NullFloat64
	s.db.Model(&Transaction{}).Where("DATE(created_at) = ? AND status = ?", today, "completed").Select("SUM(amount)").Scan(&totalAmount)
	if totalAmount.Valid {
		txnStats.TotalAmount = totalAmount.Float64
	}

	// Get command statistics
	var cmdStats struct {
		PendingCommands   int64 `json:"pending_commands"`
		CompletedCommands int64 `json:"completed_commands"`
		FailedCommands    int64 `json:"failed_commands"`
	}

	s.db.Model(&RemoteCommand{}).Where("status = ?", "pending").Count(&cmdStats.PendingCommands)
	s.db.Model(&RemoteCommand{}).Where("status = ?", "completed").Count(&cmdStats.CompletedCommands)
	s.db.Model(&RemoteCommand{}).Where("status = ?", "failed").Count(&cmdStats.FailedCommands)

	c.JSON(http.StatusOK, gin.H{
		"device_stats":      stats,
		"transaction_stats": txnStats,
		"command_stats":     cmdStats,
		"timestamp":         time.Now(),
	})
}

// Utility Functions
func generateID(prefix string) string {
	return fmt.Sprintf("%s_%d_%d", prefix, time.Now().Unix(), time.Now().Nanosecond()%10000)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// requireEnv returns the value of an environment variable or panics if not set
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}

// Health Check
func (s *POSManagementService) HealthCheck(c *gin.Context) {
	health := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now(),
		"version":   "2.0.0",
		"services":  make(map[string]interface{}),
	}

	// Check database connection
	sqlDB, err := s.db.DB()
	if err != nil {
		health["services"].(map[string]interface{})["database"] = "unhealthy"
		health["status"] = "unhealthy"
	} else if err := sqlDB.Ping(); err != nil {
		health["services"].(map[string]interface{})["database"] = "unhealthy"
		health["status"] = "unhealthy"
	} else {
		health["services"].(map[string]interface{})["database"] = "healthy"
	}

	// Check Keycloak connectivity
	req, err := http.NewRequest("GET", s.keycloakClient.BaseURL+"/auth/realms/remittance", nil)
	if err == nil {
		resp, err := s.keycloakClient.httpClient.Do(req)
		if err != nil || resp.StatusCode != http.StatusOK {
			health["services"].(map[string]interface{})["keycloak"] = "unhealthy"
		} else {
			health["services"].(map[string]interface{})["keycloak"] = "healthy"
		}
		if resp != nil {
			resp.Body.Close()
		}
	} else {
		health["services"].(map[string]interface{})["keycloak"] = "unhealthy"
	}

	// Check PBAC connectivity
	req, err = http.NewRequest("GET", s.pbacClient.BaseURL+"/health", nil)
	if err == nil {
		resp, err := s.pbacClient.httpClient.Do(req)
		if err != nil || resp.StatusCode != http.StatusOK {
			health["services"].(map[string]interface{})["pbac"] = "unhealthy"
		} else {
			health["services"].(map[string]interface{})["pbac"] = "healthy"
		}
		if resp != nil {
			resp.Body.Close()
		}
	} else {
		health["services"].(map[string]interface{})["pbac"] = "unhealthy"
	}

	// Add device statistics
	var deviceStats struct {
		Total   int64 `json:"total"`
		Online  int64 `json:"online"`
		Offline int64 `json:"offline"`
	}

	s.db.Model(&POSDevice{}).Count(&deviceStats.Total)
	s.db.Model(&POSDevice{}).Where("status = ?", "online").Count(&deviceStats.Online)
	s.db.Model(&POSDevice{}).Where("status = ?", "offline").Count(&deviceStats.Offline)

	health["devices"] = deviceStats
	health["connections"] = s.connectionManager.GetConnectionCount()

	if health["status"] == "healthy" {
		c.JSON(http.StatusOK, health)
	} else {
		c.JSON(http.StatusServiceUnavailable, health)
	}
}

func main() {
	// Initialize service
	service := NewPOSManagementService()

	// Setup Gin router
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	// CORS middleware
	router.Use(cors.New(cors.Config{
		AllowAllOrigins:  true,
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"*"},
		ExposeHeaders:    []string{"*"},
		AllowCredentials: true,
	}))

	// API routes
	api := router.Group("/api/v1")
	{
		// Device management
		api.POST("/devices", service.RegisterDevice)
		api.GET("/devices", service.GetDevices)
		api.GET("/devices/:id", service.GetDevice)
		api.PUT("/devices/:id", service.UpdateDevice)
		api.GET("/devices/:id/status", service.GetDeviceStatus)

		// Application management
		api.POST("/devices/:id/applications", service.DeployApplication)
		api.GET("/devices/:id/applications", service.GetDeviceApplications)
		api.DELETE("/devices/:id/applications/:application_id", service.RemoveApplication)
		api.POST("/devices/:id/applications/push", service.PushApplication)
		api.POST("/devices/:id/applications/:application_name/pull", service.PullApplication)

		// Remote commands and control
		api.GET("/devices/:id/commands", service.GetDeviceCommands)
		api.POST("/devices/:id/restart", service.RestartDevice)
		api.PUT("/devices/:id/configuration", service.UpdateConfiguration)

		// Transactions
		api.GET("/devices/:id/transactions", service.GetDeviceTransactions)

		// Analytics and monitoring
		api.GET("/analytics/devices", service.GetDeviceAnalytics)
	}

	// WebSocket endpoint for bi-directional communication
	router.GET("/ws", service.HandleWebSocket)

	// Health check
	router.GET("/health", service.HealthCheck)

	// Metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// Start server
	port := getEnv("PORT", "8095")
	log.Printf("🚀 POS Management Service v2.0 starting on port %s", port)
	log.Printf("📡 WebSocket endpoint: ws://localhost:%s/ws", port)
	log.Printf("🔗 API endpoints: http://localhost:%s/api/v1", port)
	log.Printf("❤️  Health check: http://localhost:%s/health", port)
	log.Printf("📊 Metrics: http://localhost:%s/metrics", port)

	log.Fatal(http.ListenAndServe("0.0.0.0:"+port, router))
}
