package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"github.com/lib/pq"
	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// =====================================================
// CONFIGURATION
// =====================================================

type Config struct {
	DBHost        string
	DBPort        string
	DBName        string
	DBUser        string
	DBPassword    string
	RedisHost     string
	RedisPort     string
	RedisPassword string
	RedisDB       int
	Port          string
	MQTTBroker    string
	MQTTPort      string
}

func loadConfig() *Config {
	return &Config{
		DBHost:        getEnv("DB_HOST", "localhost"),
		DBPort:        getEnv("DB_PORT", "5432"),
		DBName:        getEnv("DB_NAME", "link_core_banking"),
		DBUser:        getEnv("DB_USER", "postgres"),
		DBPassword:    getEnv("DB_PASSWORD", "password"),
		RedisHost:     getEnv("REDIS_HOST", "localhost"),
		RedisPort:     getEnv("REDIS_PORT", "6379"),
		RedisPassword: getEnv("REDIS_PASSWORD", ""),
		RedisDB:       getEnvAsInt("REDIS_DB", 0),
		Port:          getEnv("PORT", "8080"),
		MQTTBroker:    getEnv("MQTT_BROKER", "localhost"),
		MQTTPort:      getEnv("MQTT_PORT", "1883"),
	}
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

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

// =====================================================
// DEVICE CATALOG MODELS
// =====================================================

type CatalogManufacturer struct {
	ID        string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Name      string    `json:"name" gorm:"type:varchar(100);not null;uniqueIndex"`
	Slug      string    `json:"slug" gorm:"type:varchar(100);not null;uniqueIndex"`
	LogoURL   string    `json:"logo_url" gorm:"type:varchar(500)"`
	Website   string    `json:"website" gorm:"type:varchar(500)"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

type CatalogModel struct {
	ID             string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	ManufacturerID string    `json:"manufacturer_id" gorm:"type:uuid;not null;index"`
	Name           string    `json:"name" gorm:"type:varchar(100);not null"`
	Slug           string    `json:"slug" gorm:"type:varchar(100);not null"`
	MdmModelID     string    `json:"mdm_model_id" gorm:"type:varchar(100);not null;uniqueIndex"`
	ApkVariant     string    `json:"apk_variant" gorm:"type:varchar(100);not null"`
	DeviceType     string    `json:"device_type" gorm:"type:varchar(50);default:'pos_terminal'"`
	Connectivity   string    `json:"connectivity" gorm:"type:varchar(30);default:'cellular_4g'"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

// =====================================================
// DATABASE MODELS
// =====================================================

type DeviceType string

const (
	POSTerminal      DeviceType = "pos_terminal"
	MobilePOS        DeviceType = "mobile_pos"
	TabletPOS        DeviceType = "tablet_pos"
	SmartPOS         DeviceType = "smart_pos"
	CardReader       DeviceType = "card_reader"
	BiometricScanner DeviceType = "biometric_scanner"
	ReceiptPrinter   DeviceType = "receipt_printer"
	CashDrawer       DeviceType = "cash_drawer"
	BarcodeScanner   DeviceType = "barcode_scanner"
	IoTSensor        DeviceType = "iot_sensor"
	EdgeGateway      DeviceType = "edge_gateway"
	SecurityCamera   DeviceType = "security_camera"
)

type DeviceStatus string

const (
	Active         DeviceStatus = "active"
	Inactive       DeviceStatus = "inactive"
	Maintenance    DeviceStatus = "maintenance"
	Faulty         DeviceStatus = "faulty"
	Offline        DeviceStatus = "offline"
	Updating       DeviceStatus = "updating"
	Provisioning   DeviceStatus = "provisioning"
	Decommissioned DeviceStatus = "decommissioned"
	Stolen         DeviceStatus = "stolen"
	Quarantined    DeviceStatus = "quarantined"
)

type ConnectivityType string

const (
	WiFi       ConnectivityType = "wifi"
	Ethernet   ConnectivityType = "ethernet"
	Cellular4G ConnectivityType = "cellular_4g"
	Cellular5G ConnectivityType = "cellular_5g"
	Bluetooth  ConnectivityType = "bluetooth"
	NFC        ConnectivityType = "nfc"
	Satellite  ConnectivityType = "satellite"
	LoRa       ConnectivityType = "lora"
	ZigBee     ConnectivityType = "zigbee"
)

type POSDevice struct {
	ID                         string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	DeviceID                   string                 `json:"device_id" gorm:"type:varchar(100);unique;not null"`
	DeviceName                 string                 `json:"device_name" gorm:"type:varchar(255);not null"`
	DeviceType                 DeviceType             `json:"device_type" gorm:"type:varchar(30);not null"`
	DeviceStatus               DeviceStatus           `json:"device_status" gorm:"type:varchar(30);not null;default:'provisioning'"`
	Manufacturer               string                 `json:"manufacturer" gorm:"type:varchar(100);not null"`
	Model                      string                 `json:"model" gorm:"type:varchar(100);not null"`
	SerialNumber               string                 `json:"serial_number" gorm:"type:varchar(100);unique;not null"`
	FirmwareVersion            *string                `json:"firmware_version" gorm:"type:varchar(50)"`
	HardwareVersion            *string                `json:"hardware_version" gorm:"type:varchar(50)"`
	AssignedAgentID            *string                `json:"assigned_agent_id" gorm:"type:uuid"`
	AssignedLocation           *string                `json:"assigned_location" gorm:"type:varchar(255)"`
	InstallationDate           *time.Time             `json:"installation_date" gorm:"type:date"`
	LastMaintenanceDate        *time.Time             `json:"last_maintenance_date" gorm:"type:date"`
	NextMaintenanceDate        *time.Time             `json:"next_maintenance_date" gorm:"type:date"`
	MACAddress                 *string                `json:"mac_address" gorm:"type:varchar(17);unique"`
	IPAddress                  *string                `json:"ip_address" gorm:"type:varchar(45)"`
	ConnectivityType           ConnectivityType       `json:"connectivity_type" gorm:"type:varchar(30);not null;default:'wifi'"`
	NetworkSSID                *string                `json:"network_ssid" gorm:"type:varchar(100)"`
	Latitude                   *float64               `json:"latitude" gorm:"type:decimal(10,8)"`
	Longitude                  *float64               `json:"longitude" gorm:"type:decimal(11,8)"`
	Address                    *string                `json:"address" gorm:"type:text"`
	Timezone                   string                 `json:"timezone" gorm:"type:varchar(50);default:'UTC'"`
	SupportsContactless        bool                   `json:"supports_contactless" gorm:"default:false"`
	SupportsChipCard           bool                   `json:"supports_chip_card" gorm:"default:false"`
	SupportsMagneticStripe     bool                   `json:"supports_magnetic_stripe" gorm:"default:false"`
	SupportsBiometric          bool                   `json:"supports_biometric" gorm:"default:false"`
	SupportsReceiptPrinting    bool                   `json:"supports_receipt_printing" gorm:"default:false"`
	SupportsCashDrawer         bool                   `json:"supports_cash_drawer" gorm:"default:false"`
	EncryptionEnabled          bool                   `json:"encryption_enabled" gorm:"default:true"`
	TamperDetectionEnabled     bool                   `json:"tamper_detection_enabled" gorm:"default:true"`
	SecureBootEnabled          bool                   `json:"secure_boot_enabled" gorm:"default:true"`
	DeviceCertificate          *string                `json:"device_certificate" gorm:"type:text"`
	LastSecurityScan           *time.Time             `json:"last_security_scan"`
	UptimePercentage           float64                `json:"uptime_percentage" gorm:"type:decimal(5,2);default:0.00"`
	AverageResponseTimeMs      int                    `json:"average_response_time_ms" gorm:"default:0"`
	TotalTransactionsProcessed int64                  `json:"total_transactions_processed" gorm:"default:0"`
	LastTransactionTime        *time.Time             `json:"last_transaction_time"`
	BatteryLevel               *int                   `json:"battery_level"`
	IsCharging                 bool                   `json:"is_charging" gorm:"default:false"`
	PowerSource                string                 `json:"power_source" gorm:"type:varchar(20);default:'ac'"`
	EdgeComputingEnabled       bool                   `json:"edge_computing_enabled" gorm:"default:false"`
	CPUCores                   *int                   `json:"cpu_cores"`
	RAMMemoryMB                *int                   `json:"ram_memory_mb"`
	StorageGB                  *int                   `json:"storage_gb"`
	GPUEnabled                 bool                   `json:"gpu_enabled" gorm:"default:false"`
	LastHeartbeat              *time.Time             `json:"last_heartbeat"`
	LastSeen                   *time.Time             `json:"last_seen"`
	ConnectionQuality          string                 `json:"connection_quality" gorm:"type:varchar(20);default:'unknown'"`
	CreatedBy                  *string                `json:"created_by" gorm:"type:uuid"`
	UpdatedBy                  *string                `json:"updated_by" gorm:"type:uuid"`
	CreatedAt                  time.Time              `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt                  time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
	Metadata                   map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

type DeviceConfigurationProfile struct {
	ID                string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	ProfileName       string                 `json:"profile_name" gorm:"type:varchar(100);not null"`
	DeviceType        DeviceType             `json:"device_type" gorm:"type:varchar(30);not null"`
	Configuration     map[string]interface{} `json:"configuration" gorm:"type:jsonb;not null"`
	SecurityPolicy    map[string]interface{} `json:"security_policy" gorm:"type:jsonb"`
	NetworkConfig     map[string]interface{} `json:"network_config" gorm:"type:jsonb"`
	AppConfig         map[string]interface{} `json:"app_config" gorm:"type:jsonb"`
	AutoUpdateEnabled bool                   `json:"auto_update_enabled" gorm:"default:true"`
	UpdateWindowStart *time.Time             `json:"update_window_start" gorm:"type:time"`
	UpdateWindowEnd   *time.Time             `json:"update_window_end" gorm:"type:time"`
	IsActive          bool                   `json:"is_active" gorm:"not null;default:true"`
	IsDefault         bool                   `json:"is_default" gorm:"not null;default:false"`
	Version           int                    `json:"version" gorm:"not null;default:1"`
	CreatedBy         string                 `json:"created_by" gorm:"type:uuid;not null"`
	UpdatedBy         *string                `json:"updated_by" gorm:"type:uuid"`
	CreatedAt         time.Time              `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt         time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
	Metadata          map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

type DeviceTelemetry struct {
	ID                    string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	DeviceID              string                 `json:"device_id" gorm:"type:uuid;not null"`
	Timestamp             time.Time              `json:"timestamp" gorm:"not null;default:CURRENT_TIMESTAMP"`
	CPUUsagePercent       *float64               `json:"cpu_usage_percent" gorm:"type:decimal(5,2)"`
	MemoryUsagePercent    *float64               `json:"memory_usage_percent" gorm:"type:decimal(5,2)"`
	DiskUsagePercent      *float64               `json:"disk_usage_percent" gorm:"type:decimal(5,2)"`
	NetworkUsageMbps      *float64               `json:"network_usage_mbps" gorm:"type:decimal(10,2)"`
	ResponseTimeMs        *int                   `json:"response_time_ms"`
	TransactionCount      int                    `json:"transaction_count" gorm:"default:0"`
	ErrorCount            int                    `json:"error_count" gorm:"default:0"`
	TemperatureCelsius    *float64               `json:"temperature_celsius" gorm:"type:decimal(5,2)"`
	HumidityPercent       *float64               `json:"humidity_percent" gorm:"type:decimal(5,2)"`
	BatteryLevel          *int                   `json:"battery_level"`
	PowerConsumptionWatts *float64               `json:"power_consumption_watts" gorm:"type:decimal(8,2)"`
	Voltage               *float64               `json:"voltage" gorm:"type:decimal(6,2)"`
	SignalStrengthDbm     *int                   `json:"signal_strength_dbm"`
	NetworkLatencyMs      *int                   `json:"network_latency_ms"`
	DataSentMB            float64                `json:"data_sent_mb" gorm:"type:decimal(10,2);default:0.00"`
	DataReceivedMB        float64                `json:"data_received_mb" gorm:"type:decimal(10,2);default:0.00"`
	FailedAuthAttempts    int                    `json:"failed_auth_attempts" gorm:"default:0"`
	SecurityEventsCount   int                    `json:"security_events_count" gorm:"default:0"`
	CustomMetrics         map[string]interface{} `json:"custom_metrics" gorm:"type:jsonb"`
	Metadata              map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

type DeviceAlert struct {
	ID                   string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	DeviceID             string                 `json:"device_id" gorm:"type:uuid;not null"`
	AlertType            string                 `json:"alert_type" gorm:"type:varchar(50);not null"`
	AlertSeverity        string                 `json:"alert_severity" gorm:"type:varchar(20);not null"`
	AlertTitle           string                 `json:"alert_title" gorm:"type:varchar(255);not null"`
	AlertMessage         string                 `json:"alert_message" gorm:"type:text;not null"`
	ThresholdValue       *float64               `json:"threshold_value" gorm:"type:decimal(15,4)"`
	ActualValue          *float64               `json:"actual_value" gorm:"type:decimal(15,4)"`
	ConditionMet         *string                `json:"condition_met" gorm:"type:varchar(100)"`
	Status               string                 `json:"status" gorm:"type:varchar(30);not null;default:'active'"`
	AcknowledgedBy       *string                `json:"acknowledged_by" gorm:"type:uuid"`
	AcknowledgedAt       *time.Time             `json:"acknowledged_at"`
	ResolvedBy           *string                `json:"resolved_by" gorm:"type:uuid"`
	ResolvedAt           *time.Time             `json:"resolved_at"`
	ResolutionNotes      *string                `json:"resolution_notes" gorm:"type:text"`
	NotificationSent     bool                   `json:"notification_sent" gorm:"not null;default:false"`
	NotificationChannels pq.StringArray         `json:"notification_channels" gorm:"type:text[]"`
	NotificationSentAt   *time.Time             `json:"notification_sent_at"`
	TriggeredAt          time.Time              `json:"triggered_at" gorm:"not null;default:CURRENT_TIMESTAMP"`
	ExpiresAt            *time.Time             `json:"expires_at"`
	Metadata             map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

type EdgeComputingNode struct {
	ID                      string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	NodeID                  string                 `json:"node_id" gorm:"type:varchar(100);unique;not null"`
	NodeName                string                 `json:"node_name" gorm:"type:varchar(255);not null"`
	NodeType                string                 `json:"node_type" gorm:"type:varchar(50);not null"`
	HardwareProfile         *string                `json:"hardware_profile" gorm:"type:varchar(100)"`
	CPUCores                int                    `json:"cpu_cores" gorm:"not null"`
	CPUFrequencyGHz         *float64               `json:"cpu_frequency_ghz" gorm:"type:decimal(4,2)"`
	RAMMemoryGB             int                    `json:"ram_memory_gb" gorm:"not null"`
	StorageGB               int                    `json:"storage_gb" gorm:"not null"`
	GPUEnabled              bool                   `json:"gpu_enabled" gorm:"default:false"`
	GPUMemoryGB             *int                   `json:"gpu_memory_gb"`
	NetworkInterfaces       map[string]interface{} `json:"network_interfaces" gorm:"type:jsonb"`
	BandwidthMbps           *int                   `json:"bandwidth_mbps"`
	Supports5G              bool                   `json:"supports_5g" gorm:"default:false"`
	SupportsWiFi6           bool                   `json:"supports_wifi6" gorm:"default:false"`
	Latitude                *float64               `json:"latitude" gorm:"type:decimal(10,8)"`
	Longitude               *float64               `json:"longitude" gorm:"type:decimal(11,8)"`
	CoverageRadiusKm        *float64               `json:"coverage_radius_km" gorm:"type:decimal(6,2)"`
	MaxConnectedDevices     int                    `json:"max_connected_devices" gorm:"default:100"`
	CurrentConnectedDevices int                    `json:"current_connected_devices" gorm:"default:0"`
	Status                  string                 `json:"status" gorm:"type:varchar(30);not null;default:'active'"`
	HealthScore             float64                `json:"health_score" gorm:"type:decimal(5,2);default:100.00"`
	LastHeartbeat           *time.Time             `json:"last_heartbeat"`
	RunningServices         map[string]interface{} `json:"running_services" gorm:"type:jsonb"`
	AvailableServices       map[string]interface{} `json:"available_services" gorm:"type:jsonb"`
	SecurityLevel           string                 `json:"security_level" gorm:"type:varchar(20);default:'standard'"`
	EncryptionEnabled       bool                   `json:"encryption_enabled" gorm:"default:true"`
	FirewallEnabled         bool                   `json:"firewall_enabled" gorm:"default:true"`
	CreatedBy               string                 `json:"created_by" gorm:"type:uuid;not null"`
	UpdatedBy               *string                `json:"updated_by" gorm:"type:uuid"`
	CreatedAt               time.Time              `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt               time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
	Metadata                map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

type IoTDevice struct {
	ID                         string                 `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	DeviceID                   string                 `json:"device_id" gorm:"type:varchar(100);unique;not null"`
	DeviceName                 string                 `json:"device_name" gorm:"type:varchar(255);not null"`
	DeviceType                 string                 `json:"device_type" gorm:"type:varchar(50);not null"`
	Manufacturer               *string                `json:"manufacturer" gorm:"type:varchar(100)"`
	Model                      *string                `json:"model" gorm:"type:varchar(100)"`
	FirmwareVersion            *string                `json:"firmware_version" gorm:"type:varchar(50)"`
	EdgeNodeID                 *string                `json:"edge_node_id" gorm:"type:uuid"`
	ConnectionProtocol         *string                `json:"connection_protocol" gorm:"type:varchar(30)"`
	ConnectionStatus           string                 `json:"connection_status" gorm:"type:varchar(20);default:'disconnected'"`
	MQTTTopic                  *string                `json:"mqtt_topic" gorm:"type:varchar(255)"`
	MQTTQoS                    int                    `json:"mqtt_qos" gorm:"default:1"`
	MQTTRetain                 bool                   `json:"mqtt_retain" gorm:"default:false"`
	DataCollectionIntervalSecs int                    `json:"data_collection_interval_secs" gorm:"default:60"`
	LastDataReceived           *time.Time             `json:"last_data_received"`
	DataFormat                 string                 `json:"data_format" gorm:"type:varchar(20);default:'json'"`
	Latitude                   *float64               `json:"latitude" gorm:"type:decimal(10,8)"`
	Longitude                  *float64               `json:"longitude" gorm:"type:decimal(11,8)"`
	Status                     string                 `json:"status" gorm:"type:varchar(30);not null;default:'active'"`
	BatteryLevel               *int                   `json:"battery_level"`
	SignalStrength             *int                   `json:"signal_strength"`
	DeviceKey                  *string                `json:"device_key" gorm:"type:varchar(255)"`
	Certificate                *string                `json:"certificate" gorm:"type:text"`
	LastAuthentication         *time.Time             `json:"last_authentication"`
	CreatedBy                  string                 `json:"created_by" gorm:"type:uuid;not null"`
	UpdatedBy                  *string                `json:"updated_by" gorm:"type:uuid"`
	CreatedAt                  time.Time              `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt                  time.Time              `json:"updated_at" gorm:"autoUpdateTime"`
	Metadata                   map[string]interface{} `json:"metadata" gorm:"type:jsonb"`
}

// =====================================================
// REQUEST/RESPONSE MODELS
// =====================================================

type RegisterPOSDeviceRequest struct {
	DeviceID         string                 `json:"device_id" binding:"required"`
	DeviceName       string                 `json:"device_name" binding:"required"`
	DeviceType       DeviceType             `json:"device_type" binding:"required"`
	Manufacturer     string                 `json:"manufacturer" binding:"required"`
	Model            string                 `json:"model" binding:"required"`
	SerialNumber     string                 `json:"serial_number" binding:"required"`
	AssignedAgentID  *string                `json:"assigned_agent_id"`
	ConnectivityType ConnectivityType       `json:"connectivity_type"`
	Latitude         *float64               `json:"latitude"`
	Longitude        *float64               `json:"longitude"`
	Address          *string                `json:"address"`
	CreatedBy        *string                `json:"created_by"`
	Metadata         map[string]interface{} `json:"metadata"`
}

type UpdateDeviceStatusRequest struct {
	Status    DeviceStatus `json:"status" binding:"required"`
	Reason    *string      `json:"reason"`
	UpdatedBy *string      `json:"updated_by"`
}

type DeviceHeartbeatRequest struct {
	DeviceID        string                 `json:"device_id" binding:"required"`
	Timestamp       time.Time              `json:"timestamp"`
	TelemetryData   map[string]interface{} `json:"telemetry_data"`
	SystemMetrics   map[string]interface{} `json:"system_metrics"`
	SecurityMetrics map[string]interface{} `json:"security_metrics"`
}

type CreateEdgeNodeRequest struct {
	NodeID              string                 `json:"node_id" binding:"required"`
	NodeName            string                 `json:"node_name" binding:"required"`
	NodeType            string                 `json:"node_type" binding:"required"`
	CPUCores            int                    `json:"cpu_cores" binding:"required,gt=0"`
	RAMMemoryGB         int                    `json:"ram_memory_gb" binding:"required,gt=0"`
	StorageGB           int                    `json:"storage_gb" binding:"required,gt=0"`
	Latitude            *float64               `json:"latitude"`
	Longitude           *float64               `json:"longitude"`
	MaxConnectedDevices int                    `json:"max_connected_devices"`
	CreatedBy           string                 `json:"created_by" binding:"required"`
	Metadata            map[string]interface{} `json:"metadata"`
}

type RegisterIoTDeviceRequest struct {
	DeviceID                   string                 `json:"device_id" binding:"required"`
	DeviceName                 string                 `json:"device_name" binding:"required"`
	DeviceType                 string                 `json:"device_type" binding:"required"`
	EdgeNodeID                 *string                `json:"edge_node_id"`
	ConnectionProtocol         *string                `json:"connection_protocol"`
	MQTTTopic                  *string                `json:"mqtt_topic"`
	DataCollectionIntervalSecs int                    `json:"data_collection_interval_secs"`
	Latitude                   *float64               `json:"latitude"`
	Longitude                  *float64               `json:"longitude"`
	CreatedBy                  string                 `json:"created_by" binding:"required"`
	Metadata                   map[string]interface{} `json:"metadata"`
}

type DeviceResponse struct {
	ID           string       `json:"id"`
	DeviceID     string       `json:"device_id"`
	DeviceName   string       `json:"device_name"`
	DeviceType   DeviceType   `json:"device_type"`
	DeviceStatus DeviceStatus `json:"device_status"`
	Message      string       `json:"message"`
	CreatedAt    time.Time    `json:"created_at"`
}

type ListDevicesResponse struct {
	Data       []POSDevice `json:"data"`
	Total      int64       `json:"total"`
	Page       int         `json:"page"`
	Limit      int         `json:"limit"`
	TotalPages int         `json:"total_pages"`
}

type DeviceHealthResponse struct {
	DeviceID          string     `json:"device_id"`
	DeviceName        string     `json:"device_name"`
	Status            string     `json:"status"`
	HealthScore       float64    `json:"health_score"`
	UptimePercentage  float64    `json:"uptime_percentage"`
	LastHeartbeat     *time.Time `json:"last_heartbeat"`
	ActiveAlerts      int        `json:"active_alerts"`
	CriticalAlerts    int        `json:"critical_alerts"`
	ConnectionQuality string     `json:"connection_quality"`
}

// =====================================================
// DATABASE SERVICE
// =====================================================

type DatabaseService struct {
	db *gorm.DB
}

func NewDatabaseService(config *Config) (*DatabaseService, error) {
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=require TimeZone=UTC",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	return &DatabaseService{db: db}, nil
}

func seedDeviceCatalog(db *gorm.DB) {
	type mfr struct {
		name    string
		slug    string
		website string
		models  []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}
	}
	catalog := []mfr{
		{name: "PAX Technology", slug: "pax", website: "https://www.pax.us", models: []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}{
			{"A920 Max", "a920_max", "pax_a920_max", "paxbiz-a920", "cellular_4g"},
			{"A8900", "a8900", "pax_a8900", "paxbiz-a8900", "cellular_4g"},
		}},
		{name: "Newland", slug: "newland", website: "https://www.newlandgroup.com", models: []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}{
			{"N910", "n910", "newland_n910", "paydroid-n910", "cellular_4g"},
			{"N910 Pro", "n910_pro", "newland_n910_pro", "paydroid-n910pro", "cellular_4g"},
			{"ME30SU", "me30su", "newland_me30su", "mpos-companion", "bluetooth"},
			{"N750", "n750", "newland_n750", "aosp-mini-keypad", "cellular_4g"},
		}},
		{name: "HorizonPay", slug: "horizonpay", website: "https://www.horizonpay.com", models: []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}{
			{"K11", "k11", "horizonpay_k11", "aosp-full", "cellular_4g"},
			{"K11 Lite", "k11_lite", "horizonpay_k11_lite", "aosp-full", "cellular_4g"},
		}},
		{name: "Topwise", slug: "topwise", website: "https://www.topwise.cn", models: []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}{
			{"T11 Pro", "t11_pro", "topwise_t11_pro", "aosp-full", "cellular_4g"},
			{"MP45P", "mp45p", "topwise_mp45p", "aosp-compact", "cellular_4g"},
		}},
		{name: "Sunmi", slug: "sunmi", website: "https://www.sunmi.com", models: []struct {
			name         string
			slug         string
			mdmModelID   string
			apkVariant   string
			connectivity string
		}{
			{"P1", "p1", "sunmi_p1", "sunmi", "cellular_4g"},
			{"P2", "p2", "sunmi_p2", "sunmi", "cellular_4g"},
			{"P2 Pro", "p2_pro", "sunmi_p2_pro", "sunmi", "cellular_4g"},
			{"P3", "p3", "sunmi_p3", "sunmi", "cellular_4g"},
		}},
	}

	for _, m := range catalog {
		var existing CatalogManufacturer
		if db.Where("slug = ?", m.slug).First(&existing).Error != nil {
			existing = CatalogManufacturer{
				ID:      uuid.New().String(),
				Name:    m.name,
				Slug:    m.slug,
				Website: m.website,
			}
			db.Create(&existing)
		}
		for _, mdl := range m.models {
			var existingModel CatalogModel
			if db.Where("mdm_model_id = ?", mdl.mdmModelID).First(&existingModel).Error != nil {
				db.Create(&CatalogModel{
					ID:             uuid.New().String(),
					ManufacturerID: existing.ID,
					Name:           mdl.name,
					Slug:           mdl.slug,
					MdmModelID:     mdl.mdmModelID,
					ApkVariant:     mdl.apkVariant,
					Connectivity:   mdl.connectivity,
				})
			}
		}
	}
}

// =====================================================
// POS DEVICE SERVICE
// =====================================================

type POSDeviceService struct {
	db *DatabaseService
}

func NewPOSDeviceService(db *DatabaseService) *POSDeviceService {
	return &POSDeviceService{db: db}
}

func (pds *POSDeviceService) RegisterDevice(req *RegisterPOSDeviceRequest) (*DeviceResponse, error) {
	// Check if device already exists
	var existing POSDevice
	err := pds.db.db.Where("device_id = ? OR serial_number = ?", req.DeviceID, req.SerialNumber).First(&existing).Error
	if err == nil {
		return nil, fmt.Errorf("device with ID %s or serial number %s already exists", req.DeviceID, req.SerialNumber)
	}

	// Create new device
	device := &POSDevice{
		ID:               uuid.New().String(),
		DeviceID:         req.DeviceID,
		DeviceName:       req.DeviceName,
		DeviceType:       req.DeviceType,
		DeviceStatus:     Provisioning,
		Manufacturer:     req.Manufacturer,
		Model:            req.Model,
		SerialNumber:     req.SerialNumber,
		AssignedAgentID:  req.AssignedAgentID,
		ConnectivityType: getConnectivityTypeOrDefault(req.ConnectivityType, WiFi),
		Latitude:         req.Latitude,
		Longitude:        req.Longitude,
		Address:          req.Address,
		CreatedBy:        req.CreatedBy,
		Metadata:         req.Metadata,
	}

	// Set device capabilities based on type
	pds.setDeviceCapabilities(device)

	err = pds.db.db.Create(device).Error
	if err != nil {
		return nil, fmt.Errorf("failed to register device: %w", err)
	}

	// Create default configuration profile if it doesn't exist
	err = pds.createDefaultConfigurationProfile(device.DeviceType, req.CreatedBy)
	if err != nil {
		log.Printf("Failed to create default configuration profile: %v", err)
	}

	return &DeviceResponse{
		ID:           device.ID,
		DeviceID:     device.DeviceID,
		DeviceName:   device.DeviceName,
		DeviceType:   device.DeviceType,
		DeviceStatus: device.DeviceStatus,
		Message:      "Device registered successfully",
		CreatedAt:    device.CreatedAt,
	}, nil
}

func (pds *POSDeviceService) UpdateDeviceStatus(deviceID string, req *UpdateDeviceStatusRequest) (*DeviceResponse, error) {
	var device POSDevice
	err := pds.db.db.Where("device_id = ?", deviceID).First(&device).Error
	if err != nil {
		return nil, fmt.Errorf("device not found: %w", err)
	}

	previousStatus := device.DeviceStatus
	device.DeviceStatus = req.Status
	device.UpdatedBy = req.UpdatedBy

	err = pds.db.db.Save(&device).Error
	if err != nil {
		return nil, fmt.Errorf("failed to update device status: %w", err)
	}

	// Create alert for status change if significant
	if pds.isSignificantStatusChange(previousStatus, req.Status) {
		err = pds.createStatusChangeAlert(&device, previousStatus, req.Status, req.Reason)
		if err != nil {
			log.Printf("Failed to create status change alert: %v", err)
		}
	}

	return &DeviceResponse{
		ID:           device.ID,
		DeviceID:     device.DeviceID,
		DeviceName:   device.DeviceName,
		DeviceType:   device.DeviceType,
		DeviceStatus: device.DeviceStatus,
		Message:      fmt.Sprintf("Device status updated to %s", req.Status),
		CreatedAt:    device.CreatedAt,
	}, nil
}

func (pds *POSDeviceService) ProcessHeartbeat(req *DeviceHeartbeatRequest) error {
	var device POSDevice
	err := pds.db.db.Where("device_id = ?", req.DeviceID).First(&device).Error
	if err != nil {
		return fmt.Errorf("device not found: %w", err)
	}

	// Update device heartbeat
	now := time.Now()
	device.LastHeartbeat = &now
	device.LastSeen = &now

	// Update device status if it was offline
	if device.DeviceStatus == Offline {
		device.DeviceStatus = Active
	}

	// Extract and update system metrics from telemetry
	if req.TelemetryData != nil {
		pds.updateDeviceMetricsFromTelemetry(&device, req.TelemetryData)
	}

	err = pds.db.db.Save(&device).Error
	if err != nil {
		return fmt.Errorf("failed to update device heartbeat: %w", err)
	}

	// Create telemetry record
	telemetry := &DeviceTelemetry{
		ID:        uuid.New().String(),
		DeviceID:  device.ID,
		Timestamp: req.Timestamp,
	}

	// Extract telemetry data
	if req.TelemetryData != nil {
		pds.extractTelemetryData(telemetry, req.TelemetryData)
	}

	if req.SystemMetrics != nil {
		pds.extractSystemMetrics(telemetry, req.SystemMetrics)
	}

	if req.SecurityMetrics != nil {
		pds.extractSecurityMetrics(telemetry, req.SecurityMetrics)
	}

	err = pds.db.db.Create(telemetry).Error
	if err != nil {
		return fmt.Errorf("failed to create telemetry record: %w", err)
	}

	// Check for alerts based on telemetry data
	err = pds.checkTelemetryAlerts(&device, telemetry)
	if err != nil {
		log.Printf("Failed to check telemetry alerts: %v", err)
	}

	return nil
}

func (pds *POSDeviceService) GetDevice(deviceID string) (*POSDevice, error) {
	var device POSDevice
	err := pds.db.db.Where("device_id = ?", deviceID).First(&device).Error
	if err != nil {
		return nil, fmt.Errorf("device not found: %w", err)
	}
	return &device, nil
}

func (pds *POSDeviceService) ListDevices(filters map[string]interface{}, page, limit int) (*ListDevicesResponse, error) {
	var devices []POSDevice
	var total int64

	query := pds.db.db.Model(&POSDevice{})

	// Apply filters
	if status, ok := filters["status"]; ok {
		query = query.Where("device_status = ?", status)
	}
	if deviceType, ok := filters["type"]; ok {
		query = query.Where("device_type = ?", deviceType)
	}
	if agentID, ok := filters["agent_id"]; ok {
		query = query.Where("assigned_agent_id = ?", agentID)
	}
	if manufacturer, ok := filters["manufacturer"]; ok {
		query = query.Where("manufacturer = ?", manufacturer)
	}

	// Count total records
	query.Count(&total)

	// Apply pagination
	offset := (page - 1) * limit
	err := query.Offset(offset).Limit(limit).Order("created_at DESC").Find(&devices).Error
	if err != nil {
		return nil, err
	}

	totalPages := int((total + int64(limit) - 1) / int64(limit))

	return &ListDevicesResponse{
		Data:       devices,
		Total:      total,
		Page:       page,
		Limit:      limit,
		TotalPages: totalPages,
	}, nil
}

func (pds *POSDeviceService) GetDeviceHealth(deviceID string) (*DeviceHealthResponse, error) {
	var device POSDevice
	err := pds.db.db.Where("device_id = ?", deviceID).First(&device).Error
	if err != nil {
		return nil, fmt.Errorf("device not found: %w", err)
	}

	// Count active alerts
	var activeAlerts, criticalAlerts int64
	pds.db.db.Model(&DeviceAlert{}).Where("device_id = ? AND status = 'active'", device.ID).Count(&activeAlerts)
	pds.db.db.Model(&DeviceAlert{}).Where("device_id = ? AND status = 'active' AND alert_severity = 'critical'", device.ID).Count(&criticalAlerts)

	// Calculate health score based on various factors
	healthScore := pds.calculateHealthScore(&device, int(activeAlerts), int(criticalAlerts))

	return &DeviceHealthResponse{
		DeviceID:          device.DeviceID,
		DeviceName:        device.DeviceName,
		Status:            string(device.DeviceStatus),
		HealthScore:       healthScore,
		UptimePercentage:  device.UptimePercentage,
		LastHeartbeat:     device.LastHeartbeat,
		ActiveAlerts:      int(activeAlerts),
		CriticalAlerts:    int(criticalAlerts),
		ConnectionQuality: device.ConnectionQuality,
	}, nil
}

func (pds *POSDeviceService) setDeviceCapabilities(device *POSDevice) {
	switch device.DeviceType {
	case POSTerminal, SmartPOS:
		device.SupportsContactless = true
		device.SupportsChipCard = true
		device.SupportsMagneticStripe = true
		device.SupportsReceiptPrinting = true
		device.SupportsCashDrawer = true
	case MobilePOS, TabletPOS:
		device.SupportsContactless = true
		device.SupportsChipCard = true
		device.SupportsMagneticStripe = true
	case CardReader:
		device.SupportsContactless = true
		device.SupportsChipCard = true
		device.SupportsMagneticStripe = true
	case BiometricScanner:
		device.SupportsBiometric = true
	case ReceiptPrinter:
		device.SupportsReceiptPrinting = true
	case CashDrawer:
		device.SupportsCashDrawer = true
	}
}

func (pds *POSDeviceService) createDefaultConfigurationProfile(deviceType DeviceType, createdBy *string) error {
	// Check if default profile already exists
	var existing DeviceConfigurationProfile
	err := pds.db.db.Where("device_type = ? AND is_default = true", deviceType).First(&existing).Error
	if err == nil {
		return nil // Profile already exists
	}

	// Create default configuration based on device type
	config := pds.getDefaultConfiguration(deviceType)
	securityPolicy := pds.getDefaultSecurityPolicy(deviceType)

	profile := &DeviceConfigurationProfile{
		ID:             uuid.New().String(),
		ProfileName:    fmt.Sprintf("Default %s Profile", deviceType),
		DeviceType:     deviceType,
		Configuration:  config,
		SecurityPolicy: securityPolicy,
		IsActive:       true,
		IsDefault:      true,
		Version:        1,
		CreatedBy:      getStringOrDefault(createdBy, uuid.New().String()),
	}

	return pds.db.db.Create(profile).Error
}

func (pds *POSDeviceService) getDefaultConfiguration(deviceType DeviceType) map[string]interface{} {
	baseConfig := map[string]interface{}{
		"auto_update":        true,
		"heartbeat_interval": 30,
		"log_level":          "info",
		"timezone":           "UTC",
	}

	switch deviceType {
	case POSTerminal, SmartPOS:
		baseConfig["transaction_timeout"] = 120
		baseConfig["receipt_auto_print"] = true
		baseConfig["cash_drawer_auto_open"] = false
	case MobilePOS, TabletPOS:
		baseConfig["battery_optimization"] = true
		baseConfig["screen_timeout"] = 300
		baseConfig["auto_sleep"] = true
	}

	return baseConfig
}

func (pds *POSDeviceService) getDefaultSecurityPolicy(deviceType DeviceType) map[string]interface{} {
	return map[string]interface{}{
		"encryption":        true,
		"tamper_detection":  true,
		"secure_boot":       true,
		"auto_lock_timeout": 300,
		"max_failed_auth":   3,
	}
}

func (pds *POSDeviceService) updateDeviceMetricsFromTelemetry(device *POSDevice, telemetryData map[string]interface{}) {
	if batteryLevel, ok := telemetryData["battery_level"].(float64); ok {
		level := int(batteryLevel)
		device.BatteryLevel = &level
	}

	if responseTime, ok := telemetryData["response_time_ms"].(float64); ok {
		device.AverageResponseTimeMs = int(responseTime)
	}

	if connectionQuality, ok := telemetryData["connection_quality"].(string); ok {
		device.ConnectionQuality = connectionQuality
	}
}

func (pds *POSDeviceService) extractTelemetryData(telemetry *DeviceTelemetry, data map[string]interface{}) {
	if cpu, ok := data["cpu_usage"].(float64); ok {
		telemetry.CPUUsagePercent = &cpu
	}
	if memory, ok := data["memory_usage"].(float64); ok {
		telemetry.MemoryUsagePercent = &memory
	}
	if disk, ok := data["disk_usage"].(float64); ok {
		telemetry.DiskUsagePercent = &disk
	}
	if temp, ok := data["temperature"].(float64); ok {
		telemetry.TemperatureCelsius = &temp
	}
	if battery, ok := data["battery_level"].(float64); ok {
		level := int(battery)
		telemetry.BatteryLevel = &level
	}
	if responseTime, ok := data["response_time_ms"].(float64); ok {
		rt := int(responseTime)
		telemetry.ResponseTimeMs = &rt
	}

	telemetry.CustomMetrics = data
}

func (pds *POSDeviceService) extractSystemMetrics(telemetry *DeviceTelemetry, metrics map[string]interface{}) {
	if network, ok := metrics["network_usage_mbps"].(float64); ok {
		telemetry.NetworkUsageMbps = &network
	}
	if power, ok := metrics["power_consumption_watts"].(float64); ok {
		telemetry.PowerConsumptionWatts = &power
	}
	if voltage, ok := metrics["voltage"].(float64); ok {
		telemetry.Voltage = &voltage
	}
	if signal, ok := metrics["signal_strength_dbm"].(float64); ok {
		strength := int(signal)
		telemetry.SignalStrengthDbm = &strength
	}
}

func (pds *POSDeviceService) extractSecurityMetrics(telemetry *DeviceTelemetry, metrics map[string]interface{}) {
	if failedAuth, ok := metrics["failed_auth_attempts"].(float64); ok {
		telemetry.FailedAuthAttempts = int(failedAuth)
	}
	if securityEvents, ok := metrics["security_events_count"].(float64); ok {
		telemetry.SecurityEventsCount = int(securityEvents)
	}
}

func (pds *POSDeviceService) isSignificantStatusChange(oldStatus, newStatus DeviceStatus) bool {
	significantChanges := map[DeviceStatus][]DeviceStatus{
		Active:      {Offline, Faulty, Stolen, Quarantined},
		Offline:     {Active, Faulty, Stolen},
		Faulty:      {Active, Offline, Maintenance},
		Stolen:      {Active, Offline, Faulty},
		Quarantined: {Active, Offline},
	}

	if changes, exists := significantChanges[oldStatus]; exists {
		for _, status := range changes {
			if status == newStatus {
				return true
			}
		}
	}
	return false
}

func (pds *POSDeviceService) createStatusChangeAlert(device *POSDevice, oldStatus, newStatus DeviceStatus, reason *string) error {
	severity := "info"
	if newStatus == Offline || newStatus == Faulty || newStatus == Stolen {
		severity = "critical"
	} else if newStatus == Quarantined || newStatus == Maintenance {
		severity = "warning"
	}

	message := fmt.Sprintf("Device status changed from %s to %s", oldStatus, newStatus)
	if reason != nil && *reason != "" {
		message += fmt.Sprintf(". Reason: %s", *reason)
	}

	alert := &DeviceAlert{
		ID:            uuid.New().String(),
		DeviceID:      device.ID,
		AlertType:     "status_change",
		AlertSeverity: severity,
		AlertTitle:    "Device Status Change",
		AlertMessage:  message,
		Status:        "active",
		TriggeredAt:   time.Now(),
	}

	return pds.db.db.Create(alert).Error
}

func (pds *POSDeviceService) checkTelemetryAlerts(device *POSDevice, telemetry *DeviceTelemetry) error {
	alerts := []DeviceAlert{}

	// Check CPU usage
	if telemetry.CPUUsagePercent != nil && *telemetry.CPUUsagePercent > 90 {
		alerts = append(alerts, DeviceAlert{
			ID:             uuid.New().String(),
			DeviceID:       device.ID,
			AlertType:      "performance",
			AlertSeverity:  "warning",
			AlertTitle:     "High CPU Usage",
			AlertMessage:   fmt.Sprintf("CPU usage is %.2f%%, exceeding 90%% threshold", *telemetry.CPUUsagePercent),
			ThresholdValue: floatPtr(90.0),
			ActualValue:    telemetry.CPUUsagePercent,
			Status:         "active",
			TriggeredAt:    time.Now(),
		})
	}

	// Check memory usage
	if telemetry.MemoryUsagePercent != nil && *telemetry.MemoryUsagePercent > 85 {
		alerts = append(alerts, DeviceAlert{
			ID:             uuid.New().String(),
			DeviceID:       device.ID,
			AlertType:      "performance",
			AlertSeverity:  "warning",
			AlertTitle:     "High Memory Usage",
			AlertMessage:   fmt.Sprintf("Memory usage is %.2f%%, exceeding 85%% threshold", *telemetry.MemoryUsagePercent),
			ThresholdValue: floatPtr(85.0),
			ActualValue:    telemetry.MemoryUsagePercent,
			Status:         "active",
			TriggeredAt:    time.Now(),
		})
	}

	// Check battery level for mobile devices
	if (device.DeviceType == MobilePOS || device.DeviceType == TabletPOS) &&
		telemetry.BatteryLevel != nil && *telemetry.BatteryLevel < 20 {
		alerts = append(alerts, DeviceAlert{
			ID:             uuid.New().String(),
			DeviceID:       device.ID,
			AlertType:      "battery",
			AlertSeverity:  "warning",
			AlertTitle:     "Low Battery",
			AlertMessage:   fmt.Sprintf("Battery level is %d%%, below 20%% threshold", *telemetry.BatteryLevel),
			ThresholdValue: floatPtr(20.0),
			ActualValue:    floatPtr(float64(*telemetry.BatteryLevel)),
			Status:         "active",
			TriggeredAt:    time.Now(),
		})
	}

	// Check temperature
	if telemetry.TemperatureCelsius != nil && *telemetry.TemperatureCelsius > 70 {
		alerts = append(alerts, DeviceAlert{
			ID:             uuid.New().String(),
			DeviceID:       device.ID,
			AlertType:      "temperature",
			AlertSeverity:  "critical",
			AlertTitle:     "High Temperature",
			AlertMessage:   fmt.Sprintf("Device temperature is %.2f°C, exceeding 70°C threshold", *telemetry.TemperatureCelsius),
			ThresholdValue: floatPtr(70.0),
			ActualValue:    telemetry.TemperatureCelsius,
			Status:         "active",
			TriggeredAt:    time.Now(),
		})
	}

	// Check security events
	if telemetry.SecurityEventsCount > 0 {
		alerts = append(alerts, DeviceAlert{
			ID:            uuid.New().String(),
			DeviceID:      device.ID,
			AlertType:     "security",
			AlertSeverity: "error",
			AlertTitle:    "Security Events Detected",
			AlertMessage:  fmt.Sprintf("%d security events detected in the last reporting period", telemetry.SecurityEventsCount),
			ActualValue:   floatPtr(float64(telemetry.SecurityEventsCount)),
			Status:        "active",
			TriggeredAt:   time.Now(),
		})
	}

	// Create alerts in batch
	if len(alerts) > 0 {
		return pds.db.db.Create(&alerts).Error
	}

	return nil
}

func (pds *POSDeviceService) calculateHealthScore(device *POSDevice, activeAlerts, criticalAlerts int) float64 {
	score := 100.0

	// Deduct points for device status
	switch device.DeviceStatus {
	case Offline:
		score -= 50
	case Faulty:
		score -= 40
	case Maintenance:
		score -= 20
	case Quarantined:
		score -= 60
	case Stolen:
		score = 0
	}

	// Deduct points for alerts
	score -= float64(activeAlerts * 5)
	score -= float64(criticalAlerts * 15)

	// Deduct points for poor uptime
	if device.UptimePercentage < 95 {
		score -= (95 - device.UptimePercentage) * 2
	}

	// Deduct points for old heartbeat
	if device.LastHeartbeat != nil {
		timeSinceHeartbeat := time.Since(*device.LastHeartbeat)
		if timeSinceHeartbeat > 5*time.Minute {
			score -= 20
		} else if timeSinceHeartbeat > 2*time.Minute {
			score -= 10
		}
	} else {
		score -= 30
	}

	// Ensure score is between 0 and 100
	if score < 0 {
		score = 0
	}
	if score > 100 {
		score = 100
	}

	return score
}

// =====================================================
// EDGE COMPUTING SERVICE
// =====================================================

type EdgeComputingService struct {
	db *DatabaseService
}

func NewEdgeComputingService(db *DatabaseService) *EdgeComputingService {
	return &EdgeComputingService{db: db}
}

func (ecs *EdgeComputingService) CreateEdgeNode(req *CreateEdgeNodeRequest) (*EdgeComputingNode, error) {
	// Check if node already exists
	var existing EdgeComputingNode
	err := ecs.db.db.Where("node_id = ?", req.NodeID).First(&existing).Error
	if err == nil {
		return nil, fmt.Errorf("edge node with ID %s already exists", req.NodeID)
	}

	node := &EdgeComputingNode{
		ID:                      uuid.New().String(),
		NodeID:                  req.NodeID,
		NodeName:                req.NodeName,
		NodeType:                req.NodeType,
		CPUCores:                req.CPUCores,
		RAMMemoryGB:             req.RAMMemoryGB,
		StorageGB:               req.StorageGB,
		Latitude:                req.Latitude,
		Longitude:               req.Longitude,
		MaxConnectedDevices:     getIntOrDefault(req.MaxConnectedDevices, 100),
		CurrentConnectedDevices: 0,
		Status:                  "active",
		HealthScore:             100.0,
		CreatedBy:               req.CreatedBy,
		Metadata:                req.Metadata,
	}

	err = ecs.db.db.Create(node).Error
	if err != nil {
		return nil, fmt.Errorf("failed to create edge node: %w", err)
	}

	return node, nil
}

func (ecs *EdgeComputingService) GetEdgeNode(nodeID string) (*EdgeComputingNode, error) {
	var node EdgeComputingNode
	err := ecs.db.db.Where("node_id = ?", nodeID).First(&node).Error
	if err != nil {
		return nil, fmt.Errorf("edge node not found: %w", err)
	}
	return &node, nil
}

// =====================================================
// IOT DEVICE SERVICE
// =====================================================

type IoTDeviceService struct {
	db *DatabaseService
}

func NewIoTDeviceService(db *DatabaseService) *IoTDeviceService {
	return &IoTDeviceService{db: db}
}

func (ids *IoTDeviceService) RegisterIoTDevice(req *RegisterIoTDeviceRequest) (*IoTDevice, error) {
	// Check if device already exists
	var existing IoTDevice
	err := ids.db.db.Where("device_id = ?", req.DeviceID).First(&existing).Error
	if err == nil {
		return nil, fmt.Errorf("IoT device with ID %s already exists", req.DeviceID)
	}

	device := &IoTDevice{
		ID:                         uuid.New().String(),
		DeviceID:                   req.DeviceID,
		DeviceName:                 req.DeviceName,
		DeviceType:                 req.DeviceType,
		EdgeNodeID:                 req.EdgeNodeID,
		ConnectionProtocol:         req.ConnectionProtocol,
		MQTTTopic:                  req.MQTTTopic,
		DataCollectionIntervalSecs: getIntOrDefault(req.DataCollectionIntervalSecs, 60),
		Latitude:                   req.Latitude,
		Longitude:                  req.Longitude,
		Status:                     "active",
		ConnectionStatus:           "disconnected",
		CreatedBy:                  req.CreatedBy,
		Metadata:                   req.Metadata,
	}

	err = ids.db.db.Create(device).Error
	if err != nil {
		return nil, fmt.Errorf("failed to register IoT device: %w", err)
	}

	return device, nil
}

func (ids *IoTDeviceService) GetIoTDevice(deviceID string) (*IoTDevice, error) {
	var device IoTDevice
	err := ids.db.db.Where("device_id = ?", deviceID).First(&device).Error
	if err != nil {
		return nil, fmt.Errorf("IoT device not found: %w", err)
	}
	return &device, nil
}

// =====================================================
// HTTP HANDLERS
// =====================================================

type POSHardwareHandler struct {
	posDeviceService     *POSDeviceService
	edgeComputingService *EdgeComputingService
	iotDeviceService     *IoTDeviceService
	db                   *gorm.DB
}

func NewPOSHardwareHandler(pds *POSDeviceService, ecs *EdgeComputingService, ids *IoTDeviceService, db *gorm.DB) *POSHardwareHandler {
	return &POSHardwareHandler{
		posDeviceService:     pds,
		edgeComputingService: ecs,
		iotDeviceService:     ids,
		db:                   db,
	}
}

// ── Catalog handlers ──────────────────────────────────────────────────────────

func (phh *POSHardwareHandler) ListManufacturers(c *gin.Context) {
	var manufacturers []CatalogManufacturer
	if err := phh.db.Order("name").Find(&manufacturers).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load manufacturers"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"manufacturers": manufacturers, "count": len(manufacturers)})
}

func (phh *POSHardwareHandler) CreateManufacturer(c *gin.Context) {
	var req struct {
		Name    string `json:"name" binding:"required"`
		Slug    string `json:"slug" binding:"required"`
		LogoURL string `json:"logo_url"`
		Website string `json:"website"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	m := CatalogManufacturer{
		ID: uuid.New().String(), Name: req.Name, Slug: req.Slug,
		LogoURL: req.LogoURL, Website: req.Website,
	}
	if err := phh.db.Create(&m).Error; err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": "manufacturer already exists or slug conflict"})
		return
	}
	c.JSON(http.StatusCreated, m)
}

func (phh *POSHardwareHandler) DeleteManufacturer(c *gin.Context) {
	id := c.Param("id")
	if err := phh.db.Delete(&CatalogManufacturer{}, "id = ?", id).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete manufacturer"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

func (phh *POSHardwareHandler) ListModels(c *gin.Context) {
	manufacturerID := c.Query("manufacturer_id")
	var models []CatalogModel
	q := phh.db.Order("name")
	if manufacturerID != "" {
		q = q.Where("manufacturer_id = ?", manufacturerID)
	}
	if err := q.Find(&models).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load models"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"models": models, "count": len(models)})
}

func (phh *POSHardwareHandler) CreateModel(c *gin.Context) {
	var req struct {
		ManufacturerID string `json:"manufacturer_id" binding:"required"`
		Name           string `json:"name" binding:"required"`
		Slug           string `json:"slug" binding:"required"`
		MdmModelID     string `json:"mdm_model_id" binding:"required"`
		ApkVariant     string `json:"apk_variant" binding:"required"`
		DeviceType     string `json:"device_type"`
		Connectivity   string `json:"connectivity"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.DeviceType == "" {
		req.DeviceType = "pos_terminal"
	}
	if req.Connectivity == "" {
		req.Connectivity = "cellular_4g"
	}
	m := CatalogModel{
		ID: uuid.New().String(), ManufacturerID: req.ManufacturerID,
		Name: req.Name, Slug: req.Slug, MdmModelID: req.MdmModelID,
		ApkVariant: req.ApkVariant, DeviceType: req.DeviceType, Connectivity: req.Connectivity,
	}
	if err := phh.db.Create(&m).Error; err != nil {
		c.JSON(http.StatusConflict, gin.H{"error": "model already exists or mdm_model_id conflict"})
		return
	}
	c.JSON(http.StatusCreated, m)
}

func (phh *POSHardwareHandler) UpdateModel(c *gin.Context) {
	id := c.Param("id")
	var req map[string]interface{}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := phh.db.Model(&CatalogModel{}).Where("id = ?", id).Updates(req).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to update model"})
		return
	}
	var updated CatalogModel
	phh.db.First(&updated, "id = ?", id)
	c.JSON(http.StatusOK, updated)
}

func (phh *POSHardwareHandler) DeleteModel(c *gin.Context) {
	id := c.Param("id")
	if err := phh.db.Delete(&CatalogModel{}, "id = ?", id).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to delete model"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"status": "deleted"})
}

func (phh *POSHardwareHandler) RegisterPOSDevice(c *gin.Context) {
	var req RegisterPOSDeviceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	response, err := phh.posDeviceService.RegisterDevice(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, response)
}

func (phh *POSHardwareHandler) UpdateDeviceStatus(c *gin.Context) {
	deviceID := c.Param("device_id")

	var req UpdateDeviceStatusRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	response, err := phh.posDeviceService.UpdateDeviceStatus(deviceID, &req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

func (phh *POSHardwareHandler) ProcessHeartbeat(c *gin.Context) {
	var req DeviceHeartbeatRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	err := phh.posDeviceService.ProcessHeartbeat(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Heartbeat processed successfully"})
}

func (phh *POSHardwareHandler) GetPOSDevice(c *gin.Context) {
	deviceID := c.Param("device_id")

	device, err := phh.posDeviceService.GetDevice(deviceID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, device)
}

func (phh *POSHardwareHandler) ListPOSDevices(c *gin.Context) {
	// Parse query parameters
	page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
	limit, _ := strconv.Atoi(c.DefaultQuery("limit", "20"))

	filters := make(map[string]interface{})
	if status := c.Query("status"); status != "" {
		filters["status"] = status
	}
	if deviceType := c.Query("type"); deviceType != "" {
		filters["type"] = deviceType
	}
	if agentID := c.Query("agent_id"); agentID != "" {
		filters["agent_id"] = agentID
	}
	if manufacturer := c.Query("manufacturer"); manufacturer != "" {
		filters["manufacturer"] = manufacturer
	}

	response, err := phh.posDeviceService.ListDevices(filters, page, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, response)
}

func (phh *POSHardwareHandler) GetDeviceHealth(c *gin.Context) {
	deviceID := c.Param("device_id")

	health, err := phh.posDeviceService.GetDeviceHealth(deviceID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, health)
}

func (phh *POSHardwareHandler) CreateEdgeNode(c *gin.Context) {
	var req CreateEdgeNodeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	node, err := phh.edgeComputingService.CreateEdgeNode(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, node)
}

func (phh *POSHardwareHandler) GetEdgeNode(c *gin.Context) {
	nodeID := c.Param("node_id")

	node, err := phh.edgeComputingService.GetEdgeNode(nodeID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, node)
}

func (phh *POSHardwareHandler) RegisterIoTDevice(c *gin.Context) {
	var req RegisterIoTDeviceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	device, err := phh.iotDeviceService.RegisterIoTDevice(&req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusCreated, device)
}

func (phh *POSHardwareHandler) GetIoTDevice(c *gin.Context) {
	deviceID := c.Param("device_id")

	device, err := phh.iotDeviceService.GetIoTDevice(deviceID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, device)
}

// =====================================================
// REDIS SERVICE
// =====================================================

type RedisService struct {
	client *redis.Client
}

func NewRedisService(config *Config) *RedisService {
	rdb := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", config.RedisHost, config.RedisPort),
		DB:       config.RedisDB,
		Password: config.RedisPassword,
	})

	return &RedisService{client: rdb}
}

// =====================================================
// HEALTH CHECK
// =====================================================

func healthCheck(db *DatabaseService, redis *RedisService) gin.HandlerFunc {
	return func(c *gin.Context) {
		// Check database connection
		sqlDB, err := db.db.DB()
		if err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status": "unhealthy",
				"error":  "database connection failed",
			})
			return
		}

		if err := sqlDB.Ping(); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status": "unhealthy",
				"error":  "database ping failed",
			})
			return
		}

		// Check Redis connection
		ctx := context.Background()
		if err := redis.client.Ping(ctx).Err(); err != nil {
			c.JSON(http.StatusServiceUnavailable, gin.H{
				"status": "unhealthy",
				"error":  "redis connection failed",
			})
			return
		}

		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"service":   "pos-hardware-management",
			"timestamp": time.Now().Format(time.RFC3339),
			"version":   "1.0.0",
		})
	}
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

func getStringOrDefault(value *string, defaultValue string) string {
	if value == nil || *value == "" {
		return defaultValue
	}
	return *value
}

func getConnectivityTypeOrDefault(value, defaultValue ConnectivityType) ConnectivityType {
	if value == "" {
		return defaultValue
	}
	return value
}

func getIntOrDefault(value, defaultValue int) int {
	if value == 0 {
		return defaultValue
	}
	return value
}

func floatPtr(f float64) *float64 {
	return &f
}

// =====================================================
// MAIN FUNCTION
// =====================================================

func main() {
	// Load configuration
	config := loadConfig()

	// Initialize database
	db, err := NewDatabaseService(config)
	if err != nil {
		log.Fatalf("Failed to initialize database: %v", err)
	}

	// Initialize Redis
	redis := NewRedisService(config)

	// Initialize services
	posDeviceService := NewPOSDeviceService(db)
	edgeComputingService := NewEdgeComputingService(db)
	iotDeviceService := NewIoTDeviceService(db)

	// Initialize handlers
	handler := NewPOSHardwareHandler(posDeviceService, edgeComputingService, iotDeviceService, db.db)

	// Initialize Gin router
	router := gin.Default()

	// Configure CORS
	corsConfig := cors.DefaultConfig()
	corsConfig.AllowAllOrigins = true
	corsConfig.AllowMethods = []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
	corsConfig.AllowHeaders = []string{"Origin", "Content-Type", "Accept", "Authorization", "X-Requested-With"}
	router.Use(cors.New(corsConfig))

	// Health check endpoint
	router.GET("/health", healthCheck(db, redis))

	// API routes
	v1 := router.Group("/api/v1")
	{
		// POS device routes
		posDevices := v1.Group("/pos-devices")
		{
			posDevices.POST("", handler.RegisterPOSDevice)
			posDevices.GET("", handler.ListPOSDevices)
			posDevices.GET("/:device_id", handler.GetPOSDevice)
			posDevices.PATCH("/:device_id/status", handler.UpdateDeviceStatus)
			posDevices.GET("/:device_id/health", handler.GetDeviceHealth)
		}

		// Device heartbeat
		v1.POST("/heartbeat", handler.ProcessHeartbeat)

		// Edge computing routes
		edgeNodes := v1.Group("/edge-nodes")
		{
			edgeNodes.POST("", handler.CreateEdgeNode)
			edgeNodes.GET("/:node_id", handler.GetEdgeNode)
		}

		// IoT device routes
		iotDevices := v1.Group("/iot-devices")
		{
			iotDevices.POST("", handler.RegisterIoTDevice)
			iotDevices.GET("/:device_id", handler.GetIoTDevice)
		}

		// Device catalog routes
		catalog := v1.Group("/catalog")
		{
			catalog.GET("/manufacturers", handler.ListManufacturers)
			catalog.POST("/manufacturers", handler.CreateManufacturer)
			catalog.DELETE("/manufacturers/:id", handler.DeleteManufacturer)
			catalog.GET("/models", handler.ListModels)
			catalog.POST("/models", handler.CreateModel)
			catalog.PUT("/models/:id", handler.UpdateModel)
			catalog.DELETE("/models/:id", handler.DeleteModel)
		}
	}

	// Start server
	srv := &http.Server{
		Addr:    ":" + config.Port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	log.Printf("POS Hardware Management Service started on port %s", config.Port)

	// Wait for interrupt signal to gracefully shutdown the server
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exited")
}
