package enforcer_test

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"mdm-compliance-engine/internal/enforcer"
	"mdm-compliance-engine/internal/models"

	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// mockPublisher captures published messages for test assertions.
type mockPublisher struct {
	messages []publishedMsg
}

type publishedMsg struct {
	topic string
	key   string
	value []byte
}

func (m *mockPublisher) Publish(_ context.Context, topic, key string, value []byte) error {
	m.messages = append(m.messages, publishedMsg{topic: topic, key: key, value: value})
	return nil
}

func newTestEnforcer() (*enforcer.Enforcer, *mockPublisher) {
	pub := &mockPublisher{}
	log := logrus.New()
	log.SetLevel(logrus.ErrorLevel)
	return enforcer.New(pub, log), pub
}

func makeViolation(action models.EnforcementAction, severity models.ViolationSeverity) models.ComplianceViolation {
	return models.ComplianceViolation{
		ID:           "v-001",
		DeviceID:     "dev-001",
		SerialNumber: "SN-001",
		PolicyID:     "pol-001",
		PolicyName:   "Test Policy",
		PolicyType:   models.PolicyTypeRootDetect,
		Severity:     severity,
		Action:       action,
		Detail:       "Device is rooted",
		DetectedAt:   time.Now(),
	}
}

func TestEnforcer_CompliantResultNoMessages(t *testing.T) {
	e, pub := newTestEnforcer()
	result := models.EvaluationResult{
		DeviceID:    "dev-001",
		EvaluatedAt: time.Now(),
		Violations:  nil,
		Compliant:   true,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	assert.Empty(t, pub.messages)
}

func TestEnforcer_AlertActionPublishesToAlertAndViolationTopics(t *testing.T) {
	e, pub := newTestEnforcer()
	v := makeViolation(models.ActionAlert, models.SeverityWarning)
	result := models.EvaluationResult{
		DeviceID:    v.DeviceID,
		EvaluatedAt: time.Now(),
		Violations:  []models.ComplianceViolation{v},
		Compliant:   false,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	// Should publish to violation topic AND alert topic
	topics := make(map[string]bool)
	for _, m := range pub.messages {
		topics[m.topic] = true
	}
	assert.True(t, topics["mdm.compliance.violations"])
	assert.True(t, topics["mdm.compliance.alerts"])
}

func TestEnforcer_WipeOnlyForCritical(t *testing.T) {
	e, pub := newTestEnforcer()
	// WARNING severity WIPE should NOT issue a device command
	v := makeViolation(models.ActionWipe, models.SeverityWarning)
	result := models.EvaluationResult{
		DeviceID:   v.DeviceID,
		Violations: []models.ComplianceViolation{v},
		Compliant:  false,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	// Should only publish violation, no command
	for _, m := range pub.messages {
		assert.NotEqual(t, "mdm.device.commands", m.topic)
	}
}

func TestEnforcer_WipeForCriticalSeverity(t *testing.T) {
	e, pub := newTestEnforcer()
	v := makeViolation(models.ActionWipe, models.SeverityCritical)
	result := models.EvaluationResult{
		DeviceID:   v.DeviceID,
		Violations: []models.ComplianceViolation{v},
		Compliant:  false,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	// Should publish to commands topic
	var commandPublished bool
	for _, m := range pub.messages {
		if m.topic == "mdm.device.commands" {
			commandPublished = true
			var cmd models.EnforcementCommand
			require.NoError(t, json.Unmarshal(m.value, &cmd))
			assert.Equal(t, models.ActionWipe, cmd.Action)
			assert.Equal(t, "dev-001", cmd.DeviceID)
		}
	}
	assert.True(t, commandPublished, "WIPE command should be published for critical violation")
}

func TestEnforcer_RestrictActionPublishesCommand(t *testing.T) {
	e, pub := newTestEnforcer()
	v := makeViolation(models.ActionRestrict, models.SeverityWarning)
	result := models.EvaluationResult{
		DeviceID:   v.DeviceID,
		Violations: []models.ComplianceViolation{v},
		Compliant:  false,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	var commandPublished bool
	for _, m := range pub.messages {
		if m.topic == "mdm.device.commands" {
			commandPublished = true
			var cmd models.EnforcementCommand
			require.NoError(t, json.Unmarshal(m.value, &cmd))
			assert.Equal(t, models.ActionRestrict, cmd.Action)
		}
	}
	assert.True(t, commandPublished)
}

func TestEnforcer_MultipleViolationsAllProcessed(t *testing.T) {
	e, pub := newTestEnforcer()
	violations := []models.ComplianceViolation{
		makeViolation(models.ActionAlert, models.SeverityInfo),
		makeViolation(models.ActionWarn, models.SeverityWarning),
		makeViolation(models.ActionRestrict, models.SeverityCritical),
	}
	result := models.EvaluationResult{
		DeviceID:   "dev-001",
		Violations: violations,
		Compliant:  false,
	}
	err := e.Enforce(context.Background(), result)
	require.NoError(t, err)
	// Should have at least 3 violation messages + 1 alert + 2 commands
	assert.GreaterOrEqual(t, len(pub.messages), 5)
}
