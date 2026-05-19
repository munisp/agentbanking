// Package fluvio provides a Fluvio streaming client for the 54Link workflow orchestrator.
// Uses the Fluvio HTTP gateway API (no CGO required) so it compiles on all platforms.
package fluvio

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"workflow-orchestrator/pkg/logger"
	"workflow-orchestrator/pkg/metrics"
)

// Client represents a Fluvio client for real-time event streaming
type Client struct {
	httpClient *http.Client
	config     *Config
}

// Config holds Fluvio configuration
type Config struct {
	// SCAddr is the Fluvio HTTP gateway endpoint, e.g. http://fluvio-gateway:8080
	SCAddr              string
	TopicWorkflowEvents string
	// APIKey is the bearer token for the Fluvio HTTP gateway (optional)
	APIKey string
}

// WorkflowEvent represents a workflow lifecycle event
type WorkflowEvent struct {
	EventID      string                 `json:"event_id"`
	EventType    string                 `json:"event_type"`
	Timestamp    time.Time              `json:"timestamp"`
	WorkflowID   string                 `json:"workflow_id"`
	WorkflowType string                 `json:"workflow_type"`
	Status       string                 `json:"status"`
	TenantID     string                 `json:"tenant_id"`
	UserID       string                 `json:"user_id"`
	Data         map[string]interface{} `json:"data"`
}

// NewClient creates a new Fluvio client using the HTTP gateway
func NewClient(config *Config) (*Client, error) {
	if config.SCAddr == "" {
		return nil, fmt.Errorf("fluvio: SCAddr (HTTP gateway URL) is required")
	}
	return &Client{
		httpClient: &http.Client{Timeout: 10 * time.Second},
		config:     config,
	}, nil
}

// ProduceEvent publishes an event to the Fluvio topic via HTTP gateway
func (c *Client) ProduceEvent(ctx context.Context, event *WorkflowEvent) error {
	start := time.Now()

	data, err := json.Marshal(event)
	if err != nil {
		metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "error").Inc()
		return fmt.Errorf("fluvio: marshal error: %w", err)
	}

	url := fmt.Sprintf("%s/api/v1/topics/%s/produce", c.config.SCAddr, c.config.TopicWorkflowEvents)
	body := map[string]interface{}{
		"key":   event.WorkflowID,
		"value": string(data),
	}
	bodyBytes, _ := json.Marshal(body)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(bodyBytes))
	if err != nil {
		return fmt.Errorf("fluvio: request creation error: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.config.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.config.APIKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "error").Inc()
		return fmt.Errorf("fluvio: HTTP error: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "error").Inc()
		return fmt.Errorf("fluvio: gateway returned %d", resp.StatusCode)
	}

	metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "success").Inc()
	logger.Logger.Info("Event published to Fluvio",
		logger.String("topic", c.config.TopicWorkflowEvents),
		logger.String("workflow_id", event.WorkflowID),
		logger.Duration("duration", time.Since(start)),
	)
	return nil
}

// Close is a no-op for the HTTP client
func (c *Client) Close() error {
	return nil
}

// PublishWorkflowEvent is an alias for ProduceEvent for compatibility with the integration layer
func (c *Client) PublishWorkflowEvent(ctx context.Context, event *WorkflowEvent) error {
	return c.ProduceEvent(ctx, event)
}
