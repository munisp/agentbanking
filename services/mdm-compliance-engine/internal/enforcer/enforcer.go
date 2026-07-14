// Package enforcer handles the enforcement of compliance policy violations.
// It translates EvaluationResults into EnforcementCommands and publishes
// them to Kafka for the MDM server to execute.
package enforcer

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/sirupsen/logrus"

	"mdm-compliance-engine/internal/models"
)

// Publisher is the interface for publishing enforcement commands.
type Publisher interface {
	Publish(ctx context.Context, topic string, key string, value []byte) error
}

// Enforcer processes EvaluationResults and issues enforcement commands.
type Enforcer struct {
	publisher Publisher
	log       *logrus.Logger
	// Topics
	commandTopic    string
	violationTopic  string
	alertTopic      string
}

// New creates a new Enforcer.
func New(publisher Publisher, log *logrus.Logger) *Enforcer {
	return &Enforcer{
		publisher:      publisher,
		log:            log,
		commandTopic:   "mdm.device.commands",
		violationTopic: "mdm.compliance.violations",
		alertTopic:     "mdm.compliance.alerts",
	}
}

// Enforce processes an EvaluationResult and issues appropriate enforcement actions.
// It publishes violations to Kafka and issues device commands for non-ALERT actions.
func (e *Enforcer) Enforce(ctx context.Context, result models.EvaluationResult) error {
	if result.Compliant {
		return nil
	}

	for _, violation := range result.Violations {
		// Always publish the violation event
		if err := e.publishViolation(ctx, violation); err != nil {
			e.log.WithError(err).WithField("deviceId", violation.DeviceID).
				Error("Failed to publish violation event")
		}

		// Issue device command for non-ALERT actions
		switch violation.Action {
		case models.ActionWarn:
			if err := e.issueCommand(ctx, violation, models.ActionWarn); err != nil {
				e.log.WithError(err).Error("Failed to issue WARN command")
			}
		case models.ActionRestrict:
			if err := e.issueCommand(ctx, violation, models.ActionRestrict); err != nil {
				e.log.WithError(err).Error("Failed to issue RESTRICT command")
			}
		case models.ActionLock:
			if err := e.issueCommand(ctx, violation, models.ActionLock); err != nil {
				e.log.WithError(err).Error("Failed to issue LOCK command")
			}
		case models.ActionWipe:
			// WIPE requires critical severity confirmation
			if violation.Severity == models.SeverityCritical {
				if err := e.issueCommand(ctx, violation, models.ActionWipe); err != nil {
					e.log.WithError(err).Error("Failed to issue WIPE command")
				}
				e.log.WithFields(logrus.Fields{
					"deviceId":   violation.DeviceID,
					"serial":     violation.SerialNumber,
					"policyName": violation.PolicyName,
				}).Warn("WIPE command issued for critical compliance violation")
			}
		case models.ActionAlert:
			// Alert-only: publish to alert topic for admin notification
			if err := e.publishAlert(ctx, violation); err != nil {
				e.log.WithError(err).Error("Failed to publish alert")
			}
		}
	}

	return nil
}

// publishViolation publishes a compliance violation to the violations Kafka topic.
func (e *Enforcer) publishViolation(ctx context.Context, v models.ComplianceViolation) error {
	data, err := json.Marshal(v)
	if err != nil {
		return fmt.Errorf("marshal violation: %w", err)
	}
	return e.publisher.Publish(ctx, e.violationTopic, v.DeviceID, data)
}

// publishAlert publishes an alert to the alerts Kafka topic.
func (e *Enforcer) publishAlert(ctx context.Context, v models.ComplianceViolation) error {
	alert := map[string]interface{}{
		"type":       "COMPLIANCE_VIOLATION",
		"deviceId":   v.DeviceID,
		"serial":     v.SerialNumber,
		"policyName": v.PolicyName,
		"policyType": v.PolicyType,
		"severity":   v.Severity,
		"detail":     v.Detail,
		"detectedAt": v.DetectedAt,
	}
	data, err := json.Marshal(alert)
	if err != nil {
		return fmt.Errorf("marshal alert: %w", err)
	}
	return e.publisher.Publish(ctx, e.alertTopic, v.DeviceID, data)
}

// issueCommand publishes an enforcement command to the commands Kafka topic.
func (e *Enforcer) issueCommand(ctx context.Context, v models.ComplianceViolation, action models.EnforcementAction) error {
	cmd := models.EnforcementCommand{
		DeviceID: v.DeviceID,
		Action:   action,
		Reason:   fmt.Sprintf("Compliance violation: %s — %s", v.PolicyName, v.Detail),
		PolicyID: v.PolicyID,
		IssuedAt: time.Now().UTC(),
	}
	data, err := json.Marshal(cmd)
	if err != nil {
		return fmt.Errorf("marshal command: %w", err)
	}
	return e.publisher.Publish(ctx, e.commandTopic, v.DeviceID, data)
}
