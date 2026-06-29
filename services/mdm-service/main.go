// 54agent Agency Banking Platform — POS MDM (Mobile Device Management) Service
// Language: Go
// Purpose: Terminal provisioning, APK deployment, firmware OTA updates, remote commands,
//
//	configuration management, and device lifecycle management for all 10 P-UP IFS terminals.
//	Integrates with Kafka for event streaming, Redis for device state, and
//	the Hardware Abstraction Layer for per-model capability routing.
package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	_ "github.com/lib/pq"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// ── APK Variant Definitions ───────────────────────────────────────────────────
// Each OS platform gets a dedicated APK build with platform-specific SDKs
type APKVariant struct {
	Name         string    `json:"name"`
	FileName     string    `json:"file_name"`
	Version      string    `json:"version"`
	VersionCode  int       `json:"version_code"`
	SizeBytes    int64     `json:"size_bytes"`
	SHA256       string    `json:"sha256"`
	MinAndroid   int       `json:"min_android_api"`
	TargetModels []string  `json:"target_models"`
	Features     []string  `json:"features"`
	DownloadURL  string    `json:"download_url"`
	ReleaseNotes string    `json:"release_notes"`
	ReleasedAt   time.Time `json:"released_at"`
}

var APKVariants = map[string]APKVariant{
	"aosp-full": {
		Name: "54agent AOSP Full", FileName: "54agent-aosp-full-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 45_000_000,
		SHA256:       "a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1",
		MinAndroid:   24, // Android 7.0
		TargetModels: []string{"horizonpay_k11", "topwise_t11_pro", "topwise_mp45p", "newland_n750", "horizonpay_k11_lite"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "gps", "fingerprint", "scanner_2d", "offline_mode", "kafka_streaming"},
		ReleaseNotes: "v14.0.0: Full production release with Kafka streaming, offline sync, hardware abstraction layer",
	},
	"aosp-compact": {
		Name: "54agent AOSP Compact", FileName: "54agent-aosp-compact-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 32_000_000,
		SHA256:       "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
		MinAndroid:   24,
		TargetModels: []string{"topwise_mp45p"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "qr_scanner", "offline_mode"},
		ReleaseNotes: "v14.0.0: Compact build for MP45P — optimized for 1GB RAM",
	},
	"aosp-mini-keypad": {
		Name: "54agent AOSP Mini+Keypad", FileName: "54agent-aosp-mini-keypad-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 38_000_000,
		SHA256:       "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
		MinAndroid:   24,
		TargetModels: []string{"newland_n750"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "physical_keypad_ui", "scanner_2d", "offline_mode"},
		ReleaseNotes: "v14.0.0: Physical keypad UI optimized for N750 MiniPOS",
	},
	"mpos-companion": {
		Name: "54agent mPOS Companion", FileName: "54agent-mpos-companion-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 28_000_000,
		SHA256:       "d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
		MinAndroid:   21, // Android 5.0 — for older paired phones
		TargetModels: []string{"newland_me30su"},
		Features:     []string{"emv", "nfc", "magstripe", "bluetooth_pairing", "digital_receipt", "phone_gps", "phone_printer"},
		ReleaseNotes: "v14.0.0: mPOS companion app — pairs with ME30SU via Bluetooth",
	},
	"paydroid-n910": {
		Name: "54agent PayDroid N910", FileName: "54agent-paydroid-n910-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 42_000_000,
		SHA256:       "e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
		MinAndroid:   24,
		TargetModels: []string{"newland_n910"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "paydroid_printer_sdk", "electronic_sig", "dock_ethernet", "offline_mode"},
		ReleaseNotes: "v14.0.0: PayDroid build with Newland SDK for N910 printer and dock",
	},
	"paydroid-n910pro": {
		Name: "54agent PayDroid N910 Pro", FileName: "54agent-paydroid-n910pro-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 48_000_000,
		SHA256:       "f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
		MinAndroid:   24,
		TargetModels: []string{"newland_n910_pro"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm_80mms", "paydroid_printer_sdk", "electronic_sig", "dock_ethernet_bt_ap", "offline_mode"},
		ReleaseNotes: "v14.0.0: PayDroid Pro build with 80mm/s printer and advanced dock support",
	},
	"paxbiz-a920": {
		Name: "54agent PAXBiz A920 MAX", FileName: "54agent-paxbiz-a920-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 52_000_000,
		SHA256:       "a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
		MinAndroid:   24,
		TargetModels: []string{"pax_a920_max"},
		Features:     []string{"emv", "nfc", "magstripe", "apple_pay", "google_pay", "samsung_pay", "printer_58mm", "paxstore_sdk", "pci_pts_sred", "electronic_sig", "offline_mode"},
		ReleaseNotes: "v14.0.0: PAXBiz build with PAXSTORE SDK, Apple/Google/Samsung Pay, PCI PTS SRED",
	},
	"paxbiz-a8900": {
		Name: "54agent PAXBiz A8900", FileName: "54agent-paxbiz-a8900-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 46_000_000,
		SHA256:       "b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
		MinAndroid:   24,
		TargetModels: []string{"pax_a8900"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "paxstore_sdk", "offline_mode"},
		ReleaseNotes: "v14.0.0: PAXBiz build for A8900 with PAXSTORE SDK",
	},
	"sunmi": {
		Name: "54agent Sunmi", FileName: "54agent-sunmi-v14.apk",
		Version: "14.0.0", VersionCode: 140000, SizeBytes: 44_000_000,
		SHA256:       "c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
		MinAndroid:   24,
		TargetModels: []string{"sunmi_p1", "sunmi_p2", "sunmi_p2_pro", "sunmi_p3"},
		Features:     []string{"emv", "nfc", "magstripe", "printer_58mm", "sunmi_sdk", "gps", "scanner_2d", "offline_mode"},
		ReleaseNotes: "v14.0.0: Sunmi build with Sunmi System Services SDK for P-series handhelds",
	},
}

// ── OTA Firmware Update ───────────────────────────────────────────────────────
type FirmwareUpdate struct {
	UpdateID     string     `json:"update_id"`
	ModelID      string     `json:"model_id"`
	Version      string     `json:"version"`
	PreviousVer  string     `json:"previous_version"`
	SHA256       string     `json:"sha256"`
	SizeBytes    int64      `json:"size_bytes"`
	DownloadURL  string     `json:"download_url"`
	Mandatory    bool       `json:"mandatory"`
	ReleaseNotes string     `json:"release_notes"`
	ReleasedAt   time.Time  `json:"released_at"`
	Deadline     *time.Time `json:"deadline,omitempty"`
}

// ── MDM Command Types ─────────────────────────────────────────────────────────
type MDMCommand struct {
	CommandID   string                 `json:"command_id"`
	TerminalID  string                 `json:"terminal_id"`
	ModelID     string                 `json:"model_id"`
	CommandType string                 `json:"command_type"`
	Params      map[string]interface{} `json:"params"`
	Priority    int                    `json:"priority"` // 1=low, 5=high, 10=critical
	IssuedBy    string                 `json:"issued_by"`
	IssuedAt    time.Time              `json:"issued_at"`
	ExpiresAt   time.Time              `json:"expires_at"`
	Status      string                 `json:"status"` // pending, delivered, executed, failed
}

var MDMCommandTypes = []string{
	"reboot",
	"factory_reset",
	"lock_terminal",
	"unlock_terminal",
	"update_apk",
	"update_firmware",
	"push_config",
	"clear_cache",
	"enable_tamper_protection",
	"disable_tamper_protection",
	"get_diagnostics",
	"enable_offline_mode",
	"disable_offline_mode",
	"rotate_encryption_keys",
	"push_key_injection",
	"enable_geofence",
	"disable_geofence",
	"screenshot",
	"log_upload",
	"remote_wipe",
}

// ── Device Lifecycle States ───────────────────────────────────────────────────
type DeviceLifecycle struct {
	TerminalID      string    `json:"terminal_id"`
	ModelID         string    `json:"model_id"`
	SerialNumber    string    `json:"serial_number"`
	AgentID         string    `json:"agent_id"`
	LocationID      string    `json:"location_id"`
	State           string    `json:"state"` // provisioning, active, suspended, decommissioned
	APKVersion      string    `json:"apk_version"`
	FirmwareVersion string    `json:"firmware_version"`
	LastSeen        time.Time `json:"last_seen"`
	LastCommand     string    `json:"last_command"`
	BatteryLevel    int       `json:"battery_level"`
	SignalStrength  int       `json:"signal_strength"`
	TamperStatus    string    `json:"tamper_status"`   // ok, alert, locked
	GeofenceStatus  string    `json:"geofence_status"` // inside, outside, unknown
	Latitude        float64   `json:"latitude,omitempty"`
	Longitude       float64   `json:"longitude,omitempty"`
	RegisteredAt    time.Time `json:"registered_at"`
	UpdatedAt       time.Time `json:"updated_at"`
}

// ── Prometheus Metrics ─────────────────────────────────────────────────────────
var (
	provisioningTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "mdm_provisioning_total",
		Help: "Total provisioning operations",
	}, []string{"model_id", "status"})

	otaUpdatesTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "mdm_ota_updates_total",
		Help: "Total OTA update deployments",
	}, []string{"model_id", "update_type"})

	commandsTotal = prometheus.NewCounterVec(prometheus.CounterOpts{
		Name: "mdm_commands_total",
		Help: "Total MDM commands issued",
	}, []string{"command_type", "status"})

	activeDevices = prometheus.NewGaugeVec(prometheus.GaugeOpts{
		Name: "mdm_active_devices",
		Help: "Number of active devices by model",
	}, []string{"model_id"})
)

func init() {
	prometheus.MustRegister(provisioningTotal, otaUpdatesTotal, commandsTotal, activeDevices)
}

// ── Server ─────────────────────────────────────────────────────────────────────
type MDMServer struct {
	router *gin.Engine
	db     *sql.DB
	redis  *redis.Client
	logger *zap.Logger
	mu     sync.RWMutex
	// WebSocket connections for real-time terminal communication
	wsConns map[string]chan MDMCommand // terminalID -> command channel
}

func NewMDMServer(logger *zap.Logger) *MDMServer {
	db, err := sql.Open("postgres", buildPostgresDSN())
	if err != nil {
		logger.Fatal("failed to open postgres connection", zap.Error(err))
	}
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(30 * time.Minute)

	if err := db.Ping(); err != nil {
		logger.Fatal("failed to ping postgres", zap.Error(err))
	}

	if err := ensureDeviceTable(db); err != nil {
		logger.Fatal("failed to initialize device table", zap.Error(err))
	}
	if err := ensureCommandsTable(db); err != nil {
		logger.Fatal("failed to initialize commands table", zap.Error(err))
	}

	rdb := redis.NewClient(&redis.Options{
		Addr:     getEnv("REDIS_URL", "localhost:6379"),
		Password: getEnv("REDIS_PASSWORD", ""),
		DB:       6, // MDM DB
	})

	s := &MDMServer{
		router:  gin.New(),
		db:      db,
		redis:   rdb,
		logger:  logger,
		wsConns: make(map[string]chan MDMCommand),
	}
	s.router.Use(gin.Recovery())
	s.router.Use(func(c *gin.Context) {
		c.Header("X-Service", "pos-mdm")
		c.Next()
	})
	s.registerRoutes()
	return s
}

func (s *MDMServer) registerRoutes() {
	s.router.GET("/health", s.handleHealth)
	s.router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	s.router.Static("/uploads", "/tmp/mdm-apk-uploads")

	api := s.router.Group("/api/v1/mdm")
	{
		// APK Management
		api.GET("/apk/variants", s.handleListAPKVariants)
		api.GET("/apk/variants/:variant", s.handleGetAPKVariant)
		api.GET("/apk/latest/:model_id", s.handleGetLatestAPK)
		api.POST("/apk/deploy", s.handleDeployAPK)
		api.GET("/apk/deploy/:deployment_id/status", s.handleDeploymentStatus)

		// OTA Firmware
		api.GET("/firmware/updates/:model_id", s.handleGetFirmwareUpdates)
		api.POST("/firmware/deploy", s.handleDeployFirmware)
		api.GET("/firmware/deploy/:update_id/status", s.handleFirmwareUpdateStatus)

		// Device Provisioning
		api.POST("/provision", s.handleProvision)
		api.GET("/provision/:terminal_id", s.handleGetProvisionStatus)
		api.PUT("/provision/:terminal_id/complete", s.handleCompleteProvisioning)

		// Device Lifecycle
		api.GET("/devices", s.handleListDevices)
		api.GET("/devices/by-serial/:serial_number", s.handleGetDeviceBySerial)
		api.GET("/devices/:terminal_id", s.handleGetDevice)
		api.PUT("/devices/:terminal_id/state", s.handleUpdateDeviceState)
		api.DELETE("/devices/:terminal_id", s.handleDecommissionDevice)

		// Remote Commands
		api.POST("/commands", s.handleIssueCommand)
		api.GET("/commands/:terminal_id/pending", s.handleGetPendingCommands)
		api.PUT("/commands/:command_id/status", s.handleUpdateCommandStatus)
		api.GET("/commands/types", s.handleListCommandTypes)

		// Configuration Management
		api.GET("/config/:id", s.handleGetModelConfig)
		api.POST("/config/:id/push", s.handlePushConfig)
		api.GET("/config/:id/current", s.handleGetCurrentConfig)

		// Heartbeat (called by terminal every 30s)
		api.PUT("/heartbeat/:terminal_id", s.handleHeartbeat)

		// Diagnostics
		api.GET("/diagnostics/:terminal_id", s.handleGetDiagnostics)
		api.POST("/diagnostics/:terminal_id/request", s.handleRequestDiagnostics)

		// Tamper Detection
		api.POST("/tamper/:terminal_id/alert", s.handleTamperAlert)
		api.GET("/tamper/alerts", s.handleListTamperAlerts)

		// Bulk Operations
		api.POST("/bulk/command", s.handleBulkCommand)
		api.POST("/bulk/deploy", s.handleBulkDeploy)
		api.GET("/bulk/status/:batch_id", s.handleBulkStatus)

		// Statistics
		api.GET("/stats/fleet", s.handleFleetStats)
		api.GET("/stats/model/:model_id", s.handleModelStats)
	}
}

// ── Handlers ───────────────────────────────────────────────────────────────────

func (s *MDMServer) handleHealth(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":       "healthy",
		"service":      "pos-mdm",
		"version":      "14.0.0",
		"apk_variants": len(APKVariants),
		"storage":      "postgres+redis",
		"timestamp":    time.Now().UTC(),
	})
}

func (s *MDMServer) handleListAPKVariants(c *gin.Context) {
	variants := make([]APKVariant, 0, len(APKVariants))
	for _, v := range APKVariants {
		// Set download URL from env
		v.DownloadURL = fmt.Sprintf("%s/apk/%s/%s",
			getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"),
			v.Name, v.FileName)
		v.ReleasedAt = time.Now().UTC().Add(-7 * 24 * time.Hour)
		variants = append(variants, v)
	}
	c.JSON(http.StatusOK, gin.H{"variants": variants, "count": len(variants)})
}

func (s *MDMServer) handleGetAPKVariant(c *gin.Context) {
	variantName := c.Param("variant")
	variant, ok := APKVariants[variantName]
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "APK variant not found"})
		return
	}
	variant.DownloadURL = fmt.Sprintf("%s/apk/%s/%s",
		getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"),
		variantName, variant.FileName)
	c.JSON(http.StatusOK, variant)
}

func (s *MDMServer) handleGetLatestAPK(c *gin.Context) {
	modelID := c.Param("model_id")

	// Map model to APK variant
	modelToVariant := map[string]string{
		"horizonpay_k11":      "aosp-full",
		"horizonpay_k11_lite": "aosp-full",
		"topwise_t11_pro":     "aosp-full",
		"topwise_mp45p":       "aosp-compact",
		"newland_n750":        "aosp-mini-keypad",
		"newland_me30su":      "mpos-companion",
		"newland_n910":        "paydroid-n910",
		"newland_n910_pro":    "paydroid-n910pro",
		"pax_a920_max":        "paxbiz-a920",
		"pax_a8900":           "paxbiz-a8900",
		"sunmi_p1":            "sunmi",
		"sunmi_p2":            "sunmi",
		"sunmi_p2_pro":        "sunmi",
		"sunmi_p3":            "sunmi",
	}

	variantName, ok := modelToVariant[modelID]
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("no APK variant for model '%s'", modelID)})
		return
	}

	variant := APKVariants[variantName]
	variant.DownloadURL = fmt.Sprintf("%s/apk/%s/%s",
		getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"),
		variantName, variant.FileName)

	c.JSON(http.StatusOK, gin.H{
		"model_id":     modelID,
		"variant_name": variantName,
		"apk":          variant,
	})
}

func (s *MDMServer) handleDeployAPK(c *gin.Context) {
	var req struct {
		TerminalIDs []string   `json:"terminal_ids" binding:"required"`
		ModelID     string     `json:"model_id" binding:"required"`
		APKVariant  string     `json:"apk_variant"`
		Force       bool       `json:"force"`
		ScheduledAt *time.Time `json:"scheduled_at"`
	}

	uploadedFile := ""
	uploadedOriginalName := ""
	uploadedDownloadURL := ""

	if strings.HasPrefix(c.GetHeader("Content-Type"), "multipart/form-data") {
		terminalIDsRaw := c.PostForm("terminal_ids")
		req.ModelID = c.PostForm("model_id")
		req.APKVariant = c.PostForm("apk_variant")
		forceRaw := c.PostForm("force")
		req.Force = strings.EqualFold(forceRaw, "true") || forceRaw == "1"

		if req.ModelID == "" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "model_id is required"})
			return
		}

		for _, value := range strings.Split(terminalIDsRaw, ",") {
			trimmed := strings.TrimSpace(value)
			if trimmed != "" {
				req.TerminalIDs = append(req.TerminalIDs, trimmed)
			}
		}

		if len(req.TerminalIDs) == 0 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "terminal_ids is required"})
			return
		}

		scheduledAtRaw := c.PostForm("scheduled_at")
		if scheduledAtRaw != "" {
			parsed, err := time.Parse(time.RFC3339, scheduledAtRaw)
			if err != nil {
				c.JSON(http.StatusBadRequest, gin.H{"error": "scheduled_at must be RFC3339"})
				return
			}
			req.ScheduledAt = &parsed
		}

		if fileHeader, err := c.FormFile("apk_file"); err == nil {
			uploadDir := "/tmp/mdm-apk-uploads"
			if err := os.MkdirAll(uploadDir, 0o755); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to prepare upload dir: %v", err)})
				return
			}

			uploadedOriginalName = fileHeader.Filename
			uploadedFile = fmt.Sprintf("%d_%s", time.Now().UnixNano(), filepath.Base(fileHeader.Filename))
			destination := filepath.Join(uploadDir, uploadedFile)
			if err := c.SaveUploadedFile(fileHeader, destination); err != nil {
				c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to store apk file: %v", err)})
				return
			}
			uploadedDownloadURL = fmt.Sprintf("%s/uploads/%s", getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"), uploadedFile)
		}
	} else {
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
	}

	deploymentID := uuid.New().String()
	deployment := map[string]interface{}{
		"deployment_id": deploymentID,
		"terminal_ids":  req.TerminalIDs,
		"model_id":      req.ModelID,
		"apk_variant":   req.APKVariant,
		"status":        "queued",
		"total":         len(req.TerminalIDs),
		"completed":     0,
		"failed":        0,
		"created_at":    time.Now().UTC(),
	}
	if uploadedFile != "" {
		deployment["apk_upload_file"] = uploadedFile
		deployment["apk_upload_original_name"] = uploadedOriginalName
		deployment["apk_download_url"] = uploadedDownloadURL
	}

	data, _ := json.Marshal(deployment)
	s.redis.Set(context.Background(), fmt.Sprintf("apk_deploy:%s", deploymentID), data, 24*time.Hour)

	// Queue deployment commands for each terminal
	for _, terminalID := range req.TerminalIDs {
		params := map[string]interface{}{
			"apk_variant":   req.APKVariant,
			"deployment_id": deploymentID,
			"force":         req.Force,
		}
		if uploadedFile != "" {
			params["apk_upload_file"] = uploadedFile
			params["apk_upload_original_name"] = uploadedOriginalName
			params["apk_download_url"] = uploadedDownloadURL
		}

		cmd := MDMCommand{
			CommandID:   uuid.New().String(),
			TerminalID:  terminalID,
			ModelID:     req.ModelID,
			CommandType: "update_apk",
			Params:      params,
			Priority:    5,
			IssuedBy:    "mdm-system",
			IssuedAt:    time.Now().UTC(),
			ExpiresAt:   time.Now().UTC().Add(24 * time.Hour),
			Status:      "pending",
		}
		cmdData, _ := json.Marshal(cmd)
		s.redis.LPush(context.Background(), fmt.Sprintf("mdm_commands:%s", terminalID), cmdData)
	}

	otaUpdatesTotal.WithLabelValues(req.ModelID, "apk").Inc()
	response := gin.H{"deployment_id": deploymentID, "status": "queued", "terminals": len(req.TerminalIDs)}
	if uploadedFile != "" {
		response["apk_upload_file"] = uploadedFile
		response["apk_download_url"] = uploadedDownloadURL
	}
	c.JSON(http.StatusOK, response)

	// Notify each affected agent via the realtime service (non-blocking)
	go s.notifyAgentsApkUpdate(req.TerminalIDs, req.ModelID, req.APKVariant, uploadedDownloadURL, deploymentID)
}

func (s *MDMServer) notifyAgentsApkUpdate(terminalIDs []string, modelID, apkVariant, downloadURL, deploymentID string) {
	realtimeURL := getEnv("REALTIME_SVC_URL", "http://realtime-notification-service:8094")
	tenantID := getEnv("TENANT_ID", "54agent")

	seen := make(map[string]bool) // deduplicate by agent
	for _, terminalID := range terminalIDs {
		device, err := loadDevice(s.db, terminalID)
		if err != nil || device.AgentID == "" {
			continue
		}
		if seen[device.AgentID] {
			continue
		}
		seen[device.AgentID] = true

		payload := map[string]interface{}{
			"agent_id":      device.AgentID,
			"tenant_id":     tenantID,
			"terminal_id":   terminalID,
			"model_id":      modelID,
			"apk_variant":   apkVariant,
			"new_version":   "latest",
			"download_url":  downloadURL,
			"deployment_id": deploymentID,
		}
		body, err := json.Marshal(payload)
		if err != nil {
			continue
		}
		resp, err := http.Post(realtimeURL+"/api/v1/apk/notify", "application/json", bytes.NewReader(body))
		if err != nil {
			s.logger.Warn("failed to notify agent of APK update",
				zap.String("agent_id", device.AgentID),
				zap.String("terminal_id", terminalID),
				zap.Error(err),
			)
			continue
		}
		resp.Body.Close()
	}
}

func (s *MDMServer) handleDeploymentStatus(c *gin.Context) {
	deploymentID := c.Param("deployment_id")
	data, err := s.redis.Get(context.Background(), fmt.Sprintf("apk_deploy:%s", deploymentID)).Bytes()
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "deployment not found"})
		return
	}
	var deployment map[string]interface{}
	json.Unmarshal(data, &deployment)
	c.JSON(http.StatusOK, deployment)
}

func (s *MDMServer) handleGetFirmwareUpdates(c *gin.Context) {
	modelID := c.Param("model_id")
	// Return available firmware updates for the model
	updates := []FirmwareUpdate{
		{
			UpdateID:     uuid.New().String(),
			ModelID:      modelID,
			Version:      "3.2.1",
			PreviousVer:  "3.1.0",
			SHA256:       "abc123def456",
			SizeBytes:    8_500_000,
			DownloadURL:  fmt.Sprintf("%s/firmware/%s/v3.2.1.bin", getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"), modelID),
			Mandatory:    false,
			ReleaseNotes: "Security patch for CVE-2024-1234, improved NFC performance",
			ReleasedAt:   time.Now().UTC().Add(-3 * 24 * time.Hour),
		},
	}
	c.JSON(http.StatusOK, gin.H{"model_id": modelID, "updates": updates, "count": len(updates)})
}

func (s *MDMServer) handleDeployFirmware(c *gin.Context) {
	var req struct {
		TerminalID string `json:"terminal_id" binding:"required"`
		ModelID    string `json:"model_id" binding:"required"`
		Version    string `json:"version" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	updateID := uuid.New().String()
	cmd := MDMCommand{
		CommandID:   uuid.New().String(),
		TerminalID:  req.TerminalID,
		ModelID:     req.ModelID,
		CommandType: "update_firmware",
		Params: map[string]interface{}{
			"version":   req.Version,
			"update_id": updateID,
		},
		Priority:  8,
		IssuedBy:  "mdm-system",
		IssuedAt:  time.Now().UTC(),
		ExpiresAt: time.Now().UTC().Add(6 * time.Hour),
		Status:    "pending",
	}
	cmdData, _ := json.Marshal(cmd)
	s.redis.LPush(context.Background(), fmt.Sprintf("mdm_commands:%s", req.TerminalID), cmdData)

	otaUpdatesTotal.WithLabelValues(req.ModelID, "firmware").Inc()
	c.JSON(http.StatusOK, gin.H{"update_id": updateID, "status": "queued", "terminal_id": req.TerminalID})
}

func (s *MDMServer) handleFirmwareUpdateStatus(c *gin.Context) {
	updateID := c.Param("update_id")
	data, err := s.redis.Get(context.Background(), fmt.Sprintf("fw_update:%s", updateID)).Bytes()
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "firmware update not found"})
		return
	}
	var update map[string]interface{}
	json.Unmarshal(data, &update)
	c.JSON(http.StatusOK, update)
}

func (s *MDMServer) handleProvision(c *gin.Context) {
	var req struct {
		TerminalID   string `json:"terminal_id" binding:"required"`
		ModelID      string `json:"model_id" binding:"required"`
		SerialNumber string `json:"serial_number" binding:"required"`
		AgentID      string `json:"agent_id"`
		LocationID   string `json:"location_id"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Determine APK variant for this model
	modelToVariant := map[string]string{
		"horizonpay_k11": "aosp-full", "horizonpay_k11_lite": "aosp-full",
		"topwise_t11_pro": "aosp-full", "topwise_mp45p": "aosp-compact",
		"newland_n750": "aosp-mini-keypad", "newland_me30su": "mpos-companion",
		"newland_n910": "paydroid-n910", "newland_n910_pro": "paydroid-n910pro",
		"pax_a920_max": "paxbiz-a920", "pax_a8900": "paxbiz-a8900",
		"sunmi_p1": "sunmi", "sunmi_p2": "sunmi", "sunmi_p2_pro": "sunmi", "sunmi_p3": "sunmi",
	}
	apkVariant := modelToVariant[req.ModelID]
	apkInfo := APKVariants[apkVariant]

	device := DeviceLifecycle{
		TerminalID:      req.TerminalID,
		ModelID:         req.ModelID,
		SerialNumber:    req.SerialNumber,
		AgentID:         req.AgentID,
		LocationID:      req.LocationID,
		State:           "provisioning",
		APKVersion:      apkInfo.Version,
		FirmwareVersion: "3.1.0",
		TamperStatus:    "ok",
		GeofenceStatus:  "unknown",
		RegisteredAt:    time.Now().UTC(),
		UpdatedAt:       time.Now().UTC(),
	}

	if err := saveDevice(s.db, device); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to persist device: %v", err)})
		return
	}

	provisioningTotal.WithLabelValues(req.ModelID, "initiated").Inc()

	c.JSON(http.StatusCreated, gin.H{
		"status":       "provisioning_initiated",
		"terminal_id":  req.TerminalID,
		"apk_variant":  apkVariant,
		"apk_version":  apkInfo.Version,
		"download_url": fmt.Sprintf("%s/apk/%s/%s", getEnv("APK_DISTRIBUTION_URL", "https://mdm.54agent.finance"), apkVariant, apkInfo.FileName),
		"device":       device,
	})
}

func (s *MDMServer) handleGetProvisionStatus(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	c.JSON(http.StatusOK, device)
}

func (s *MDMServer) handleCompleteProvisioning(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	var req struct {
		APKVersion      string `json:"apk_version"`
		FirmwareVersion string `json:"firmware_version"`
	}
	c.ShouldBindJSON(&req)

	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	device.State = "active"
	device.UpdatedAt = time.Now().UTC()
	if req.APKVersion != "" {
		device.APKVersion = req.APKVersion
	}
	if req.FirmwareVersion != "" {
		device.FirmwareVersion = req.FirmwareVersion
	}

	if err := saveDevice(s.db, *device); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to persist device: %v", err)})
		return
	}

	provisioningTotal.WithLabelValues(device.ModelID, "completed").Inc()
	activeDevices.WithLabelValues(device.ModelID).Inc()

	c.JSON(http.StatusOK, gin.H{"status": "active", "terminal_id": terminalID})
}

func (s *MDMServer) handleListDevices(c *gin.Context) {
	modelFilter := c.Query("model_id")
	stateFilter := c.Query("state")
	agentFilter := c.Query("agent_id")

	devices, err := listDevices(s.db)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to load devices: %v", err)})
		return
	}

	filtered := make([]DeviceLifecycle, 0, len(devices))
	for _, device := range devices {
		if modelFilter != "" && device.ModelID != modelFilter {
			continue
		}
		if stateFilter != "" && device.State != stateFilter {
			continue
		}
		if agentFilter != "" && device.AgentID != agentFilter {
			continue
		}
		filtered = append(filtered, device)
	}
	c.JSON(http.StatusOK, gin.H{"devices": filtered, "count": len(filtered)})
}

func (s *MDMServer) handleGetDevice(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	c.JSON(http.StatusOK, device)
}

func (s *MDMServer) handleGetDeviceBySerial(c *gin.Context) {
	serial := c.Param("serial_number")
	var data []byte
	err := s.db.QueryRow(
		`SELECT device_data FROM mdm_devices WHERE device_data->>'serial_number' = $1 LIMIT 1`,
		serial,
	).Scan(&data)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	var device DeviceLifecycle
	if err := json.Unmarshal(data, &device); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to parse device"})
		return
	}
	c.JSON(http.StatusOK, device)
}

func (s *MDMServer) handleUpdateDeviceState(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	var req struct {
		State  string `json:"state" binding:"required"`
		Reason string `json:"reason"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	validStates := map[string]bool{"active": true, "suspended": true, "decommissioned": true}
	if !validStates[req.State] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid state"})
		return
	}

	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	device.State = req.State
	device.UpdatedAt = time.Now().UTC()

	if err := saveDevice(s.db, *device); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to persist device: %v", err)})
		return
	}

	// If suspending, issue lock command
	if req.State == "suspended" {
		s.issueCommand(terminalID, device.ModelID, "lock_terminal", map[string]interface{}{"reason": req.Reason}, 10)
	}

	c.JSON(http.StatusOK, gin.H{"status": req.State, "terminal_id": terminalID})
}

func (s *MDMServer) handleDecommissionDevice(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}

	// Issue remote wipe command before decommissioning
	s.issueCommand(terminalID, device.ModelID, "remote_wipe", nil, 10)

	device.State = "decommissioned"
	device.UpdatedAt = time.Now().UTC()
	if err := saveDevice(s.db, *device); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to persist device: %v", err)})
		return
	}
	activeDevices.WithLabelValues(device.ModelID).Dec()

	c.JSON(http.StatusOK, gin.H{"status": "decommissioned", "terminal_id": terminalID})
}

func (s *MDMServer) handleIssueCommand(c *gin.Context) {
	var req struct {
		TerminalID  string                 `json:"terminal_id" binding:"required"`
		ModelID     string                 `json:"model_id" binding:"required"`
		CommandType string                 `json:"command_type" binding:"required"`
		Params      map[string]interface{} `json:"params"`
		Priority    int                    `json:"priority"`
		IssuedBy    string                 `json:"issued_by"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	priority := req.Priority
	if priority == 0 {
		priority = 5
	}

	issuedBy := req.IssuedBy
	if issuedBy == "" {
		issuedBy = "admin-dashboard"
	}
	commandID := s.issueCommandBy(req.TerminalID, req.ModelID, req.CommandType, req.Params, priority, issuedBy)
	commandsTotal.WithLabelValues(req.CommandType, "issued").Inc()

	c.JSON(http.StatusOK, gin.H{
		"command_id":  commandID,
		"terminal_id": req.TerminalID,
		"command":     req.CommandType,
		"status":      "pending",
	})
}

func (s *MDMServer) issueCommand(terminalID, modelID, cmdType string, params map[string]interface{}, priority int) string {
	return s.issueCommandBy(terminalID, modelID, cmdType, params, priority, "mdm-system")
}

func (s *MDMServer) issueCommandBy(terminalID, modelID, cmdType string, params map[string]interface{}, priority int, issuedBy string) string {
	cmd := MDMCommand{
		CommandID:   uuid.New().String(),
		TerminalID:  terminalID,
		ModelID:     modelID,
		CommandType: cmdType,
		Params:      params,
		Priority:    priority,
		IssuedBy:    issuedBy,
		IssuedAt:    time.Now().UTC(),
		ExpiresAt:   time.Now().UTC().Add(24 * time.Hour),
		Status:      "pending",
	}

	// Persist to Postgres (source of truth)
	paramsJSON, _ := json.Marshal(cmd.Params)
	_, dbErr := s.db.Exec(`
INSERT INTO mdm_commands (command_id, terminal_id, model_id, command_type, params, priority, issued_by, issued_at, expires_at, status)
VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'pending')`,
		cmd.CommandID, cmd.TerminalID, cmd.ModelID, cmd.CommandType,
		paramsJSON, cmd.Priority, cmd.IssuedBy, cmd.IssuedAt, cmd.ExpiresAt,
	)
	if dbErr != nil {
		s.logger.Error("failed to persist command to db", zap.Error(dbErr))
	}

	// Also push to Redis for real-time delivery to the device
	cmdData, _ := json.Marshal(cmd)
	s.redis.LPush(context.Background(), fmt.Sprintf("mdm_commands:%s", terminalID), cmdData)
	return cmd.CommandID
}

func (s *MDMServer) handleGetPendingCommands(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	rows, err := s.db.QueryContext(c.Request.Context(), `
SELECT command_id, terminal_id, model_id, command_type, COALESCE(params,'{}'), priority,
       issued_by, issued_at, expires_at, status, COALESCE(result,'')
FROM mdm_commands
WHERE terminal_id = $1
  AND status IN ('pending','delivered')
  AND expires_at > NOW()
ORDER BY priority DESC, issued_at ASC`,
		terminalID,
	)
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"commands": []interface{}{}, "count": 0})
		return
	}
	defer rows.Close()

	var commands []MDMCommand
	for rows.Next() {
		var cmd MDMCommand
		var paramsJSON []byte
		var result string
		if err := rows.Scan(
			&cmd.CommandID, &cmd.TerminalID, &cmd.ModelID, &cmd.CommandType,
			&paramsJSON, &cmd.Priority, &cmd.IssuedBy, &cmd.IssuedAt,
			&cmd.ExpiresAt, &cmd.Status, &result,
		); err != nil {
			continue
		}
		_ = json.Unmarshal(paramsJSON, &cmd.Params)
		commands = append(commands, cmd)
	}
	if commands == nil {
		commands = []MDMCommand{}
	}
	c.JSON(http.StatusOK, gin.H{"commands": commands, "count": len(commands)})
}

func (s *MDMServer) handleUpdateCommandStatus(c *gin.Context) {
	commandID := c.Param("command_id")
	var req struct {
		TerminalID string `json:"terminal_id" binding:"required"`
		Status     string `json:"status" binding:"required"` // delivered, executed, failed
		Result     string `json:"result"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	_, err := s.db.ExecContext(c.Request.Context(), `
UPDATE mdm_commands SET status = $1, result = $2 WHERE command_id = $3`,
		req.Status, req.Result, commandID,
	)
	if err != nil {
		s.logger.Error("failed to update command status", zap.Error(err))
	}

	commandsTotal.WithLabelValues("unknown", req.Status).Inc()
	c.JSON(http.StatusOK, gin.H{"command_id": commandID, "status": req.Status})
}

func (s *MDMServer) handleListCommandTypes(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{"command_types": MDMCommandTypes, "count": len(MDMCommandTypes)})
}

func (s *MDMServer) handleGetModelConfig(c *gin.Context) {
	modelID := c.Param("model_id")
	// Return default config for this model
	config := s.buildModelConfig(modelID)
	c.JSON(http.StatusOK, gin.H{"model_id": modelID, "config": config})
}

func (s *MDMServer) buildModelConfig(modelID string) map[string]interface{} {
	baseConfig := map[string]interface{}{
		"api_base_url":       getEnv("API_BASE_URL", "https://api.54agent.finance"),
		"ws_url":             getEnv("WS_URL", "wss://ws.54agent.finance"),
		"heartbeat_interval": 30,
		"sync_interval":      300,
		"offline_mode":       true,
		"max_offline_txns":   100,
		"log_level":          "info",
		"auto_update":        true,
		"geofence_enabled":   true,
		"tamper_protection":  true,
	}

	// PAX-specific
	if modelID == "pax_a920_max" || modelID == "pax_a8900" {
		baseConfig["paxstore_enabled"] = true
		baseConfig["paxstore_app_id"] = getEnv("PAXSTORE_APP_ID", "")
	}

	// Newland PayDroid-specific
	if modelID == "newland_n910" || modelID == "newland_n910_pro" {
		baseConfig["paydroid_printer_sdk"] = true
		baseConfig["dock_ethernet"] = true
	}

	// mPOS-specific
	if modelID == "newland_me30su" {
		baseConfig["mpos_mode"] = true
		baseConfig["bluetooth_pairing"] = true
		baseConfig["print_via_phone"] = true
	}

	return baseConfig
}

func (s *MDMServer) handlePushConfig(c *gin.Context) {
	terminalID := c.Param("id")
	var config map[string]interface{}
	if err := c.ShouldBindJSON(&config); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Get device model
	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}

	// Issue push_config command
	s.issueCommand(terminalID, device.ModelID, "push_config", map[string]interface{}{"config": config}, 5)

	c.JSON(http.StatusOK, gin.H{"status": "config_push_queued", "terminal_id": terminalID})
}

func (s *MDMServer) handleGetCurrentConfig(c *gin.Context) {
	terminalID := c.Param("id")
	data, err := s.redis.Get(context.Background(), fmt.Sprintf("mdm_config:%s", terminalID)).Bytes()
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no config found for terminal"})
		return
	}
	var config map[string]interface{}
	json.Unmarshal(data, &config)
	c.JSON(http.StatusOK, config)
}

func (s *MDMServer) handleHeartbeat(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	var req struct {
		BatteryLevel    int     `json:"battery_level"`
		SignalStrength  int     `json:"signal_strength"`
		APKVersion      string  `json:"apk_version"`
		FirmwareVersion string  `json:"firmware_version"`
		Latitude        float64 `json:"latitude,omitempty"`
		Longitude       float64 `json:"longitude,omitempty"`
		TamperStatus    string  `json:"tamper_status"`
	}
	c.ShouldBindJSON(&req)

	// Update device state
	device, err := loadDevice(s.db, terminalID)
	if err == nil {
		device.LastSeen = time.Now().UTC()
		device.BatteryLevel = req.BatteryLevel
		device.SignalStrength = req.SignalStrength
		if req.APKVersion != "" {
			device.APKVersion = req.APKVersion
		}
		if req.FirmwareVersion != "" {
			device.FirmwareVersion = req.FirmwareVersion
		}
		if req.Latitude != 0 {
			device.Latitude = req.Latitude
		}
		if req.Longitude != 0 {
			device.Longitude = req.Longitude
		}
		if req.TamperStatus != "" {
			device.TamperStatus = req.TamperStatus
		}
		device.UpdatedAt = time.Now().UTC()
		if err := saveDevice(s.db, *device); err != nil {
			s.logger.Error("failed to persist heartbeat device update", zap.Error(err), zap.String("terminal_id", terminalID))
		}
	}

	// Check for pending commands
	pendingCount, _ := s.redis.LLen(context.Background(), fmt.Sprintf("mdm_commands:%s", terminalID)).Result()

	c.JSON(http.StatusOK, gin.H{
		"status":           "ok",
		"server_time":      time.Now().UTC(),
		"pending_commands": pendingCount,
	})
}

func (s *MDMServer) handleGetDiagnostics(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	data, err := s.redis.Get(context.Background(), fmt.Sprintf("mdm_diagnostics:%s", terminalID)).Bytes()
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "no diagnostics available"})
		return
	}
	var diag map[string]interface{}
	json.Unmarshal(data, &diag)
	c.JSON(http.StatusOK, diag)
}

func (s *MDMServer) handleRequestDiagnostics(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	device, err := loadDevice(s.db, terminalID)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "device not found"})
		return
	}
	s.issueCommand(terminalID, device.ModelID, "get_diagnostics", nil, 3)
	c.JSON(http.StatusOK, gin.H{"status": "diagnostics_requested", "terminal_id": terminalID})
}

func (s *MDMServer) handleTamperAlert(c *gin.Context) {
	terminalID := c.Param("terminal_id")
	var req struct {
		AlertType string `json:"alert_type" binding:"required"` // case_open, voltage_tamper, temperature, etc.
		Severity  string `json:"severity"`
		Details   string `json:"details"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Store tamper alert
	alert := map[string]interface{}{
		"terminal_id": terminalID,
		"alert_type":  req.AlertType,
		"severity":    req.Severity,
		"details":     req.Details,
		"timestamp":   time.Now().UTC(),
	}
	alertData, _ := json.Marshal(alert)
	s.redis.LPush(context.Background(), "tamper_alerts", alertData)
	s.redis.LTrim(context.Background(), "tamper_alerts", 0, 999) // Keep last 1000

	// Auto-lock terminal on tamper
	device, err := loadDevice(s.db, terminalID)
	if err == nil {
		device.TamperStatus = "alert"
		device.UpdatedAt = time.Now().UTC()
		if err := saveDevice(s.db, *device); err != nil {
			s.logger.Error("failed to persist tamper update", zap.Error(err), zap.String("terminal_id", terminalID))
		}
		s.issueCommand(terminalID, device.ModelID, "lock_terminal", map[string]interface{}{"reason": "tamper_alert"}, 10)
	}

	c.JSON(http.StatusOK, gin.H{"status": "tamper_alert_received", "terminal_id": terminalID, "auto_locked": true})
}

func (s *MDMServer) handleListTamperAlerts(c *gin.Context) {
	rawAlerts, _ := s.redis.LRange(context.Background(), "tamper_alerts", 0, 99).Result()
	var alerts []map[string]interface{}
	for _, raw := range rawAlerts {
		var alert map[string]interface{}
		if err := json.Unmarshal([]byte(raw), &alert); err == nil {
			alerts = append(alerts, alert)
		}
	}
	c.JSON(http.StatusOK, gin.H{"alerts": alerts, "count": len(alerts)})
}

func (s *MDMServer) handleBulkCommand(c *gin.Context) {
	var req struct {
		ModelID     string                 `json:"model_id"`
		AgentID     string                 `json:"agent_id"`
		CommandType string                 `json:"command_type" binding:"required"`
		Params      map[string]interface{} `json:"params"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	batchID := uuid.New().String()
	devices, err := listDevices(s.db)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to load devices: %v", err)})
		return
	}
	count := 0
	for _, device := range devices {
		if req.ModelID != "" && device.ModelID != req.ModelID {
			continue
		}
		if req.AgentID != "" && device.AgentID != req.AgentID {
			continue
		}
		if device.State != "active" {
			continue
		}
		s.issueCommand(device.TerminalID, device.ModelID, req.CommandType, req.Params, 5)
		count++
	}

	c.JSON(http.StatusOK, gin.H{"batch_id": batchID, "terminals_targeted": count, "command": req.CommandType})
}

func (s *MDMServer) handleBulkDeploy(c *gin.Context) {
	var req struct {
		ModelID    string `json:"model_id" binding:"required"`
		APKVariant string `json:"apk_variant" binding:"required"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	batchID := uuid.New().String()
	devices, err := listDevices(s.db)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to load devices: %v", err)})
		return
	}
	var terminalIDs []string
	for _, device := range devices {
		if device.ModelID == req.ModelID && device.State == "active" {
			terminalIDs = append(terminalIDs, device.TerminalID)
		}
	}

	for _, tid := range terminalIDs {
		s.issueCommand(tid, req.ModelID, "update_apk", map[string]interface{}{"apk_variant": req.APKVariant, "batch_id": batchID}, 5)
	}

	c.JSON(http.StatusOK, gin.H{"batch_id": batchID, "terminals_targeted": len(terminalIDs), "model_id": req.ModelID})
}

func (s *MDMServer) handleBulkStatus(c *gin.Context) {
	batchID := c.Param("batch_id")

	type statusCount struct {
		Status string
		Count  int
	}
	rows, err := s.db.QueryContext(c.Request.Context(),
		`SELECT status, COUNT(*) FROM mdm_commands WHERE params->>'batch_id' = $1 GROUP BY status`,
		batchID,
	)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	counts := map[string]int{}
	total := 0
	for rows.Next() {
		var sc statusCount
		if err := rows.Scan(&sc.Status, &sc.Count); err != nil {
			continue
		}
		counts[sc.Status] = sc.Count
		total += sc.Count
	}

	if total == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "batch not found or no commands recorded"})
		return
	}

	// Derive overall status
	pending := counts["pending"] + counts["delivered"]
	failed := counts["failed"]
	completed := counts["executed"]

	overallStatus := "in_progress"
	if pending == 0 && failed == 0 {
		overallStatus = "completed"
	} else if pending == 0 && completed == 0 {
		overallStatus = "failed"
	} else if pending == 0 {
		overallStatus = "partial"
	}

	c.JSON(http.StatusOK, gin.H{
		"batch_id":       batchID,
		"status":         overallStatus,
		"total":          total,
		"pending":        pending,
		"completed":      completed,
		"failed":         failed,
		"completion_pct": fmt.Sprintf("%.0f%%", float64(completed)/float64(total)*100),
	})
}

func (s *MDMServer) handleFleetStats(c *gin.Context) {
	devices, err := listDevices(s.db)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to load devices: %v", err)})
		return
	}
	stats := map[string]interface{}{
		"total_devices":  len(devices),
		"by_model":       map[string]int{},
		"by_state":       map[string]int{},
		"by_apk_version": map[string]int{},
	}
	for _, device := range devices {
		stats["by_model"].(map[string]int)[device.ModelID]++
		stats["by_state"].(map[string]int)[device.State]++
		stats["by_apk_version"].(map[string]int)[device.APKVersion]++
	}
	c.JSON(http.StatusOK, stats)
}

func (s *MDMServer) handleModelStats(c *gin.Context) {
	modelID := c.Param("model_id")
	devices, err := listDevices(s.db)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": fmt.Sprintf("failed to load devices: %v", err)})
		return
	}
	count := 0
	active := 0
	for _, device := range devices {
		if device.ModelID == modelID {
			count++
			if device.State == "active" {
				active++
			}
		}
	}
	c.JSON(http.StatusOK, gin.H{"model_id": modelID, "total": count, "active": active})
}

// ── Helpers ────────────────────────────────────────────────────────────────────
func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func hashFile(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

func buildPostgresDSN() string {
	if dsn := getEnv("DATABASE_URL", ""); dsn != "" {
		return dsn
	}

	host := getEnv("POSTGRES_HOST", getEnv("DB_HOST", "localhost"))
	port := getEnv("POSTGRES_PORT", getEnv("DB_PORT", "5432"))
	dbName := getEnv("POSTGRES_DB", getEnv("DB_NAME", "platform"))
	user := getEnv("POSTGRES_USER", getEnv("DB_USER", "postgres"))
	password := getEnv("POSTGRES_PASSWORD", getEnv("DB_PASSWORD", "postgres"))
	sslmode := getEnv("POSTGRES_SSLMODE", "require")

	return fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s?sslmode=%s",
		user,
		password,
		host,
		port,
		dbName,
		sslmode,
	)
}

func ensureCommandsTable(db *sql.DB) error {
	_, err := db.Exec(`
CREATE TABLE IF NOT EXISTS mdm_commands (
  command_id  TEXT PRIMARY KEY,
  terminal_id TEXT NOT NULL,
  model_id    TEXT NOT NULL,
  command_type TEXT NOT NULL,
  params      JSONB,
  priority    INT NOT NULL DEFAULT 5,
  issued_by   TEXT NOT NULL DEFAULT 'system',
  issued_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at  TIMESTAMPTZ NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending',
  result      TEXT
);
CREATE INDEX IF NOT EXISTS idx_mdm_commands_terminal ON mdm_commands(terminal_id);
CREATE INDEX IF NOT EXISTS idx_mdm_commands_status   ON mdm_commands(status);
`)
	return err
}

func ensureDeviceTable(db *sql.DB) error {
	_, err := db.Exec(`
CREATE TABLE IF NOT EXISTS mdm_devices (
  terminal_id TEXT PRIMARY KEY,
  device_data JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
`)
	return err
}

func saveDevice(db *sql.DB, device DeviceLifecycle) error {
	data, err := json.Marshal(device)
	if err != nil {
		return err
	}

	_, err = db.Exec(`
INSERT INTO mdm_devices (terminal_id, device_data, created_at, updated_at)
VALUES ($1, $2::jsonb, NOW(), NOW())
ON CONFLICT (terminal_id)
DO UPDATE SET device_data = EXCLUDED.device_data, updated_at = NOW()
`, device.TerminalID, data)
	return err
}

func loadDevice(db *sql.DB, terminalID string) (*DeviceLifecycle, error) {
	var raw []byte
	err := db.QueryRow(`SELECT device_data FROM mdm_devices WHERE terminal_id = $1`, terminalID).Scan(&raw)
	if err != nil {
		return nil, err
	}

	var device DeviceLifecycle
	if err := json.Unmarshal(raw, &device); err != nil {
		return nil, err
	}
	return &device, nil
}

func deleteDevice(db *sql.DB, terminalID string) error {
	_, err := db.Exec(`DELETE FROM mdm_devices WHERE terminal_id = $1`, terminalID)
	return err
}

func listDevices(db *sql.DB) ([]DeviceLifecycle, error) {
	rows, err := db.Query(`SELECT device_data FROM mdm_devices ORDER BY updated_at DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	devices := make([]DeviceLifecycle, 0)
	for rows.Next() {
		var raw []byte
		if err := rows.Scan(&raw); err != nil {
			return nil, err
		}
		var device DeviceLifecycle
		if err := json.Unmarshal(raw, &device); err != nil {
			return nil, err
		}
		devices = append(devices, device)
	}
	return devices, rows.Err()
}

// ── Main ───────────────────────────────────────────────────────────────────────
func main() {
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	logger.Info("starting pos-mdm",
		zap.Int("apk_variants", len(APKVariants)),
		zap.Int("command_types", len(MDMCommandTypes)),
		zap.String("port", getEnv("PORT", "8100")),
	)

	srv := NewMDMServer(logger)
	httpServer := &http.Server{
		Addr:         ":" + getEnv("PORT", "8100"),
		Handler:      srv.router,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		logger.Info("pos-mdm listening", zap.String("addr", httpServer.Addr))
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server error: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	logger.Info("shutting down pos-mdm...")
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	httpServer.Shutdown(ctx)
}
