// Package evaluator implements the core compliance policy evaluation logic.
// It takes a DeviceHeartbeat and a set of CompliancePolicies and returns
// an EvaluationResult containing all detected violations.
package evaluator

import (
	"fmt"
	"math"
	"strconv"
	"strings"
	"time"

	"mdm-compliance-engine/internal/models"
)

// Evaluator evaluates device heartbeats against compliance policies.
type Evaluator struct{}

// New creates a new Evaluator.
func New() *Evaluator {
	return &Evaluator{}
}

// Evaluate checks a heartbeat against all provided policies and returns
// an EvaluationResult with any detected violations.
func (e *Evaluator) Evaluate(
	heartbeat models.DeviceHeartbeat,
	policies []models.CompliancePolicy,
) models.EvaluationResult {
	var violations []models.ComplianceViolation

	for _, policy := range policies {
		if !policy.Enabled {
			continue
		}
		if !appliesToDevice(policy, heartbeat) {
			continue
		}

		violation := e.evaluatePolicy(heartbeat, policy)
		if violation != nil {
			violations = append(violations, *violation)
		}
	}

	return models.EvaluationResult{
		DeviceID:     heartbeat.DeviceID,
		SerialNumber: heartbeat.SerialNumber,
		EvaluatedAt:  time.Now().UTC(),
		Violations:   violations,
		Compliant:    len(violations) == 0,
	}
}

// appliesToDevice checks whether a policy applies to a given device.
func appliesToDevice(policy models.CompliancePolicy, hb models.DeviceHeartbeat) bool {
	switch policy.AppliesTo {
	case "ALL", "":
		return true
	case "ANDROID":
		return strings.EqualFold(hb.DeviceType, "ANDROID")
	case "IOS":
		return strings.EqualFold(hb.DeviceType, "IOS")
	case "FREERTOS":
		return strings.EqualFold(hb.DeviceType, "FREERTOS")
	default:
		// Specific serial number
		return hb.SerialNumber == policy.AppliesTo
	}
}

// evaluatePolicy evaluates a single policy against a heartbeat.
// Returns a ComplianceViolation if violated, nil otherwise.
func (e *Evaluator) evaluatePolicy(
	hb models.DeviceHeartbeat,
	policy models.CompliancePolicy,
) *models.ComplianceViolation {
	var detail string

	switch policy.Type {
	case models.PolicyTypeOSVersion:
		detail = e.checkOSVersion(hb, policy)
	case models.PolicyTypeAppVersion:
		detail = e.checkAppVersion(hb, policy)
	case models.PolicyTypeBatteryLevel:
		detail = e.checkBatteryLevel(hb, policy)
	case models.PolicyTypeEncryption:
		detail = e.checkEncryption(hb, policy)
	case models.PolicyTypeScreenLock:
		detail = e.checkScreenLock(hb, policy)
	case models.PolicyTypeRootDetect:
		detail = e.checkRootDetect(hb, policy)
	case models.PolicyTypeWiFiOnly:
		detail = e.checkWiFiOnly(hb, policy)
	case models.PolicyTypeIdleTimeout:
		detail = e.checkIdleTimeout(hb, policy)
	case models.PolicyTypeGeofence:
		detail = e.checkGeofence(hb, policy)
	default:
		return nil
	}

	if detail == "" {
		return nil // No violation
	}

	return &models.ComplianceViolation{
		ID:           fmt.Sprintf("%s-%s-%d", hb.DeviceID, policy.ID, time.Now().UnixNano()),
		DeviceID:     hb.DeviceID,
		SerialNumber: hb.SerialNumber,
		PolicyID:     policy.ID,
		PolicyName:   policy.Name,
		PolicyType:   policy.Type,
		Severity:     policy.Severity,
		Action:       policy.Action,
		Detail:       detail,
		DetectedAt:   time.Now().UTC(),
		Resolved:     false,
	}
}

// checkOSVersion checks if the device OS version meets the minimum requirement.
// Threshold format: "10" (Android API level) or "14.0" (iOS version).
func (e *Evaluator) checkOSVersion(hb models.DeviceHeartbeat, policy models.CompliancePolicy) string {
	if hb.OSVersion == "" {
		return "OS version not reported"
	}
	minVer, err := parseVersion(policy.Threshold)
	if err != nil {
		return ""
	}
	devVer, err := parseVersion(hb.OSVersion)
	if err != nil {
		return fmt.Sprintf("Cannot parse device OS version: %s", hb.OSVersion)
	}
	if compareVersions(devVer, minVer) < 0 {
		return fmt.Sprintf("OS version %s is below minimum required %s", hb.OSVersion, policy.Threshold)
	}
	return ""
}

// checkAppVersion checks if the app version meets the minimum requirement.
func (e *Evaluator) checkAppVersion(hb models.DeviceHeartbeat, policy models.CompliancePolicy) string {
	if hb.AppVersion == "" {
		return "App version not reported"
	}
	minVer, err := parseVersion(policy.Threshold)
	if err != nil {
		return ""
	}
	devVer, err := parseVersion(hb.AppVersion)
	if err != nil {
		return fmt.Sprintf("Cannot parse app version: %s", hb.AppVersion)
	}
	if compareVersions(devVer, minVer) < 0 {
		return fmt.Sprintf("App version %s is below minimum required %s", hb.AppVersion, policy.Threshold)
	}
	return ""
}

// checkBatteryLevel checks if the battery is above the minimum threshold.
func (e *Evaluator) checkBatteryLevel(hb models.DeviceHeartbeat, policy models.CompliancePolicy) string {
	if hb.IsCharging {
		return "" // Charging devices are exempt
	}
	minLevel, err := strconv.Atoi(policy.Threshold)
	if err != nil {
		return ""
	}
	if hb.BatteryLevel < minLevel {
		return fmt.Sprintf("Battery level %d%% is below minimum %d%%", hb.BatteryLevel, minLevel)
	}
	return ""
}

// checkEncryption checks if device storage is encrypted.
func (e *Evaluator) checkEncryption(hb models.DeviceHeartbeat, _ models.CompliancePolicy) string {
	if !hb.IsEncrypted {
		return "Device storage is not encrypted"
	}
	return ""
}

// checkScreenLock checks if screen lock is enabled.
func (e *Evaluator) checkScreenLock(hb models.DeviceHeartbeat, _ models.CompliancePolicy) string {
	if !hb.IsScreenLocked {
		return "Screen lock is not enabled"
	}
	return ""
}

// checkRootDetect checks if the device is rooted/jailbroken.
func (e *Evaluator) checkRootDetect(hb models.DeviceHeartbeat, _ models.CompliancePolicy) string {
	if hb.IsRooted {
		return "Device is rooted or jailbroken"
	}
	return ""
}

// checkWiFiOnly checks if the device is connected to WiFi (for WiFi-only policies).
func (e *Evaluator) checkWiFiOnly(hb models.DeviceHeartbeat, _ models.CompliancePolicy) string {
	if !hb.WiFiConnected {
		return fmt.Sprintf("Device is not connected to WiFi (SSID: %s)", hb.WiFiSSID)
	}
	return ""
}

// checkIdleTimeout checks if the device has been idle too long.
func (e *Evaluator) checkIdleTimeout(hb models.DeviceHeartbeat, policy models.CompliancePolicy) string {
	maxIdle, err := strconv.Atoi(policy.Threshold)
	if err != nil {
		return ""
	}
	if hb.IdleSecs > maxIdle {
		return fmt.Sprintf("Device idle for %ds, exceeds maximum %ds", hb.IdleSecs, maxIdle)
	}
	return ""
}

// checkGeofence checks if the device is within the allowed geofence.
// Threshold format: "lat_e6,lon_e6,radius_meters" e.g. "6463000,3396000,500"
func (e *Evaluator) checkGeofence(hb models.DeviceHeartbeat, policy models.CompliancePolicy) string {
	parts := strings.Split(policy.Threshold, ",")
	if len(parts) != 3 {
		return ""
	}
	centerLatE6, err1 := strconv.ParseInt(strings.TrimSpace(parts[0]), 10, 64)
	centerLonE6, err2 := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64)
	radiusM, err3 := strconv.ParseFloat(strings.TrimSpace(parts[2]), 64)
	if err1 != nil || err2 != nil || err3 != nil {
		return ""
	}
	if hb.LatE6 == 0 && hb.LonE6 == 0 {
		return "Device location not available"
	}

	dist := haversineMeters(
		float64(hb.LatE6)/1e6,
		float64(hb.LonE6)/1e6,
		float64(centerLatE6)/1e6,
		float64(centerLonE6)/1e6,
	)
	if dist > radiusM {
		return fmt.Sprintf("Device is %.0fm outside allowed geofence (radius: %.0fm)", dist-radiusM, radiusM)
	}
	return ""
}

// ── Version parsing helpers ───────────────────────────────────────────────────

type version struct {
	parts []int
}

func parseVersion(s string) (version, error) {
	s = strings.TrimSpace(s)
	parts := strings.Split(s, ".")
	var v version
	for _, p := range parts {
		n, err := strconv.Atoi(strings.TrimSpace(p))
		if err != nil {
			return version{}, fmt.Errorf("invalid version part %q in %q", p, s)
		}
		v.parts = append(v.parts, n)
	}
	return v, nil
}

// compareVersions returns -1, 0, or 1.
func compareVersions(a, b version) int {
	maxLen := len(a.parts)
	if len(b.parts) > maxLen {
		maxLen = len(b.parts)
	}
	for i := 0; i < maxLen; i++ {
		ap, bp := 0, 0
		if i < len(a.parts) {
			ap = a.parts[i]
		}
		if i < len(b.parts) {
			bp = b.parts[i]
		}
		if ap < bp {
			return -1
		}
		if ap > bp {
			return 1
		}
	}
	return 0
}

// ── Geofence helper ───────────────────────────────────────────────────────────

// haversineMeters calculates the great-circle distance in meters between two
// WGS-84 coordinates using the Haversine formula.
func haversineMeters(lat1, lon1, lat2, lon2 float64) float64 {
	const earthRadiusM = 6_371_000.0
	dLat := (lat2 - lat1) * math.Pi / 180.0
	dLon := (lon2 - lon1) * math.Pi / 180.0
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*math.Pi/180.0)*math.Cos(lat2*math.Pi/180.0)*
			math.Sin(dLon/2)*math.Sin(dLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
	return earthRadiusM * c
}
