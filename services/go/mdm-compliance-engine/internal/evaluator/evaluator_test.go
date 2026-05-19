package evaluator_test

import (
	"testing"
	"time"

	"mdm-compliance-engine/internal/evaluator"
	"mdm-compliance-engine/internal/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// baseHeartbeat returns a fully compliant device heartbeat for testing.
func baseHeartbeat() models.DeviceHeartbeat {
	return models.DeviceHeartbeat{
		DeviceID:       "dev-001",
		SerialNumber:   "SN-PAX-001",
		AgentCode:      "AGT001",
		OSVersion:      "14",
		AppVersion:     "2.5.0",
		BatteryLevel:   80,
		IsCharging:     false,
		IsEncrypted:    true,
		IsScreenLocked: true,
		IsRooted:       false,
		WiFiConnected:  true,
		WiFiSSID:       "54Link-Office-5G",
		LatE6:          6463000,
		LonE6:          3396000,
		IdleSecs:       30,
		DeviceType:     "ANDROID",
		Timestamp:      time.Now(),
	}
}

func basePolicy(pType models.PolicyType, threshold string) models.CompliancePolicy {
	return models.CompliancePolicy{
		ID:          "pol-001",
		Name:        "Test Policy",
		Type:        pType,
		Enabled:     true,
		Severity:    models.SeverityWarning,
		Action:      models.ActionAlert,
		Threshold:   threshold,
		AppliesTo:   "ALL",
	}
}

func TestEvaluator_FullyCompliantDevice(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	policies := []models.CompliancePolicy{
		basePolicy(models.PolicyTypeOSVersion, "10"),
		basePolicy(models.PolicyTypeAppVersion, "2.0.0"),
		basePolicy(models.PolicyTypeBatteryLevel, "15"),
		basePolicy(models.PolicyTypeEncryption, ""),
		basePolicy(models.PolicyTypeScreenLock, ""),
		basePolicy(models.PolicyTypeRootDetect, ""),
		basePolicy(models.PolicyTypeWiFiOnly, ""),
		basePolicy(models.PolicyTypeIdleTimeout, "300"),
		// Geofence: Lagos Island, 1km radius
		basePolicy(models.PolicyTypeGeofence, "6463000,3396000,1000"),
	}
	result := e.Evaluate(hb, policies)
	assert.True(t, result.Compliant)
	assert.Empty(t, result.Violations)
}

func TestEvaluator_OSVersionViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.OSVersion = "9"
	policy := basePolicy(models.PolicyTypeOSVersion, "10")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Equal(t, models.PolicyTypeOSVersion, result.Violations[0].PolicyType)
	assert.Contains(t, result.Violations[0].Detail, "below minimum")
}

func TestEvaluator_AppVersionViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.AppVersion = "1.9.9"
	policy := basePolicy(models.PolicyTypeAppVersion, "2.0.0")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Equal(t, models.PolicyTypeAppVersion, result.Violations[0].PolicyType)
}

func TestEvaluator_BatteryViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.BatteryLevel = 10
	hb.IsCharging = false
	policy := basePolicy(models.PolicyTypeBatteryLevel, "15")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Contains(t, result.Violations[0].Detail, "10%")
}

func TestEvaluator_BatteryExemptWhenCharging(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.BatteryLevel = 5
	hb.IsCharging = true
	policy := basePolicy(models.PolicyTypeBatteryLevel, "15")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	assert.True(t, result.Compliant)
}

func TestEvaluator_EncryptionViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IsEncrypted = false
	policy := basePolicy(models.PolicyTypeEncryption, "")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Contains(t, result.Violations[0].Detail, "not encrypted")
}

func TestEvaluator_ScreenLockViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IsScreenLocked = false
	policy := basePolicy(models.PolicyTypeScreenLock, "")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
}

func TestEvaluator_RootDetectViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IsRooted = true
	policy := basePolicy(models.PolicyTypeRootDetect, "")
	policy.Severity = models.SeverityCritical
	policy.Action = models.ActionWipe
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Equal(t, models.ActionWipe, result.Violations[0].Action)
}

func TestEvaluator_WiFiOnlyViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.WiFiConnected = false
	policy := basePolicy(models.PolicyTypeWiFiOnly, "")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
}

func TestEvaluator_IdleTimeoutViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IdleSecs = 600
	policy := basePolicy(models.PolicyTypeIdleTimeout, "300")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Contains(t, result.Violations[0].Detail, "600s")
}

func TestEvaluator_GeofenceViolation(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	// Move device 5km away from Lagos Island
	hb.LatE6 = 6508000 // ~5km north
	hb.LonE6 = 3396000
	// Geofence: Lagos Island, 1km radius
	policy := basePolicy(models.PolicyTypeGeofence, "6463000,3396000,1000")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	require.Len(t, result.Violations, 1)
	assert.Contains(t, result.Violations[0].Detail, "outside allowed geofence")
}

func TestEvaluator_GeofenceCompliant(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	// Device is within 500m of center
	policy := basePolicy(models.PolicyTypeGeofence, "6463000,3396000,1000")
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	assert.True(t, result.Compliant)
}

func TestEvaluator_DisabledPolicySkipped(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IsRooted = true
	policy := basePolicy(models.PolicyTypeRootDetect, "")
	policy.Enabled = false
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	assert.True(t, result.Compliant)
}

func TestEvaluator_AppliesToAndroidOnly(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.DeviceType = "FREERTOS"
	hb.IsRooted = true
	policy := basePolicy(models.PolicyTypeRootDetect, "")
	policy.AppliesTo = "ANDROID"
	result := e.Evaluate(hb, []models.CompliancePolicy{policy})
	// FreeRTOS device should not be evaluated by Android-only policy
	assert.True(t, result.Compliant)
}

func TestEvaluator_MultipleViolations(t *testing.T) {
	e := evaluator.New()
	hb := baseHeartbeat()
	hb.IsEncrypted = false
	hb.IsRooted = true
	hb.BatteryLevel = 5
	policies := []models.CompliancePolicy{
		basePolicy(models.PolicyTypeEncryption, ""),
		basePolicy(models.PolicyTypeRootDetect, ""),
		basePolicy(models.PolicyTypeBatteryLevel, "15"),
	}
	result := e.Evaluate(hb, policies)
	assert.False(t, result.Compliant)
	assert.Len(t, result.Violations, 3)
}
