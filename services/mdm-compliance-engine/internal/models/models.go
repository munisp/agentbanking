// Package models defines the domain types for the MDM Compliance Policy Engine.
// All structs are JSON-serializable for Kafka and REST API use.
package models

import "time"

// PolicyType categorises what a compliance rule checks.
type PolicyType string

const (
	PolicyTypeOSVersion    PolicyType = "OS_VERSION"
	PolicyTypeAppVersion   PolicyType = "APP_VERSION"
	PolicyTypeBatteryLevel PolicyType = "BATTERY_LEVEL"
	PolicyTypeEncryption   PolicyType = "ENCRYPTION"
	PolicyTypeScreenLock   PolicyType = "SCREEN_LOCK"
	PolicyTypeGeofence     PolicyType = "GEOFENCE"
	PolicyTypeWiFiOnly     PolicyType = "WIFI_ONLY"
	PolicyTypeRootDetect   PolicyType = "ROOT_DETECT"
	PolicyTypeIdleTimeout  PolicyType = "IDLE_TIMEOUT"
	PolicyTypeCustom       PolicyType = "CUSTOM"
)

// EnforcementAction defines what happens when a violation is detected.
type EnforcementAction string

const (
	ActionAlert    EnforcementAction = "ALERT"    // Notify admin only
	ActionWarn     EnforcementAction = "WARN"      // Warn agent on device
	ActionRestrict EnforcementAction = "RESTRICT"  // Block transactions
	ActionWipe     EnforcementAction = "WIPE"      // Remote wipe device
	ActionLock     EnforcementAction = "LOCK"      // Lock device screen
)

// ViolationSeverity indicates how critical a violation is.
type ViolationSeverity string

const (
	SeverityInfo     ViolationSeverity = "INFO"
	SeverityWarning  ViolationSeverity = "WARNING"
	SeverityCritical ViolationSeverity = "CRITICAL"
)

// CompliancePolicy defines a single compliance rule that applies to devices.
type CompliancePolicy struct {
	ID          string            `json:"id"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Type        PolicyType        `json:"type"`
	Enabled     bool              `json:"enabled"`
	Severity    ViolationSeverity `json:"severity"`
	Action      EnforcementAction `json:"action"`
	// Threshold is the policy-specific threshold value.
	// For OS_VERSION: minimum required OS version string (e.g. "10")
	// For APP_VERSION: minimum required app version string (e.g. "2.1.0")
	// For BATTERY_LEVEL: minimum battery percentage (e.g. "15")
	// For IDLE_TIMEOUT: maximum idle seconds (e.g. "300")
	Threshold   string            `json:"threshold"`
	// AppliesTo: "ALL", "ANDROID", "IOS", "FREERTOS", or specific device serial
	AppliesTo   string            `json:"appliesTo"`
	CreatedAt   time.Time         `json:"createdAt"`
	UpdatedAt   time.Time         `json:"updatedAt"`
}

// DeviceHeartbeat is the payload received from an MDM device heartbeat.
// This is the canonical struct used by the evaluator.
type DeviceHeartbeat struct {
	DeviceID       string    `json:"deviceId"`
	SerialNumber   string    `json:"serialNumber"`
	AgentCode      string    `json:"agentCode"`
	OSVersion      string    `json:"osVersion"`
	AppVersion     string    `json:"appVersion"`
	BatteryLevel   int       `json:"batteryLevel"`   // 0–100
	IsCharging     bool      `json:"isCharging"`
	IsEncrypted    bool      `json:"isEncrypted"`
	IsScreenLocked bool      `json:"isScreenLocked"`
	IsRooted       bool      `json:"isRooted"`
	WiFiConnected  bool      `json:"wifiConnected"`
	WiFiSSID       string    `json:"wifiSsid"`
	LatE6          int64     `json:"latE6"`          // Latitude × 10^6
	LonE6          int64     `json:"lonE6"`          // Longitude × 10^6
	IdleSecs       int       `json:"idleSecs"`
	DeviceType     string    `json:"deviceType"`     // "ANDROID", "IOS", "FREERTOS"
	Timestamp      time.Time `json:"timestamp"`
}

// ComplianceViolation records a detected policy violation.
type ComplianceViolation struct {
	ID           string            `json:"id"`
	DeviceID     string            `json:"deviceId"`
	SerialNumber string            `json:"serialNumber"`
	PolicyID     string            `json:"policyId"`
	PolicyName   string            `json:"policyName"`
	PolicyType   PolicyType        `json:"policyType"`
	Severity     ViolationSeverity `json:"severity"`
	Action       EnforcementAction `json:"action"`
	Detail       string            `json:"detail"`
	DetectedAt   time.Time         `json:"detectedAt"`
	ResolvedAt   *time.Time        `json:"resolvedAt,omitempty"`
	Resolved     bool              `json:"resolved"`
}

// EvaluationResult is the output of evaluating a heartbeat against all policies.
type EvaluationResult struct {
	DeviceID     string                `json:"deviceId"`
	SerialNumber string                `json:"serialNumber"`
	EvaluatedAt  time.Time             `json:"evaluatedAt"`
	Violations   []ComplianceViolation `json:"violations"`
	Compliant    bool                  `json:"compliant"`
}

// EnforcementCommand is sent to the MDM server to execute an action on a device.
type EnforcementCommand struct {
	DeviceID   string            `json:"deviceId"`
	Action     EnforcementAction `json:"action"`
	Reason     string            `json:"reason"`
	PolicyID   string            `json:"policyId"`
	IssuedAt   time.Time         `json:"issuedAt"`
}
