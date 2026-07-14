package lakehouse

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"workflow-orchestrator/pkg/logger"
)

// Client represents a Lakehouse client for analytics data storage
type Client struct {
	httpClient *http.Client
	config     *Config
}

// Config holds Lakehouse configuration
type Config struct {
	APIURL   string
	S3Bucket string
	APIKey   string
}

// WorkflowEvent represents a workflow event for analytics
type WorkflowEvent struct {
	EventID      string                 `json:"event_id"`
	EventType    string                 `json:"event_type"`
	Timestamp    time.Time              `json:"timestamp"`
	WorkflowID   string                 `json:"workflow_id"`
	WorkflowType string                 `json:"workflow_type"`
	Status       string                 `json:"status"`
	TenantID     string                 `json:"tenant_id"`
	UserID       string                 `json:"user_id"`
	EntityID     string                 `json:"entity_id"`
	Duration     float64                `json:"duration_seconds"`
	StepCount    int                    `json:"step_count"`
	ErrorMessage string                 `json:"error_message,omitempty"`
	Metadata     map[string]interface{} `json:"metadata"`
}

// WorkflowMetrics represents aggregated workflow metrics
type WorkflowMetrics struct {
	WorkflowType    string  `json:"workflow_type"`
	TotalCount      int64   `json:"total_count"`
	SuccessCount    int64   `json:"success_count"`
	FailureCount    int64   `json:"failure_count"`
	AvgDuration     float64 `json:"avg_duration_seconds"`
	P50Duration     float64 `json:"p50_duration_seconds"`
	P95Duration     float64 `json:"p95_duration_seconds"`
	P99Duration     float64 `json:"p99_duration_seconds"`
	SuccessRate     float64 `json:"success_rate"`
}

// NewClient creates a new Lakehouse client
func NewClient(config *Config) (*Client, error) {
	return &Client{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		config: config,
	}, nil
}

// StreamWorkflowEvent streams a workflow event to the lakehouse
func (c *Client) StreamWorkflowEvent(ctx context.Context, event *WorkflowEvent) error {
	logger.Logger.Info("Streaming workflow event to Lakehouse",
		logger.String("workflow_id", event.WorkflowID),
		logger.String("event_type", event.EventType),
	)

	// Marshal event to JSON
	data, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(ctx, "POST", c.config.APIURL+"/api/v1/events", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to stream event to Lakehouse", logger.Error(err))
		return fmt.Errorf("failed to stream event: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("lakehouse returned error: %d - %s", resp.StatusCode, string(body))
	}

	logger.Logger.Info("Event streamed to Lakehouse successfully")
	return nil
}

// BatchStreamEvents streams multiple events in a single request
func (c *Client) BatchStreamEvents(ctx context.Context, events []*WorkflowEvent) error {
	logger.Logger.Info("Batch streaming workflow events to Lakehouse",
		logger.Int("count", len(events)),
	)

	// Marshal events to JSON
	data, err := json.Marshal(map[string]interface{}{
		"events": events,
	})
	if err != nil {
		return fmt.Errorf("failed to marshal events: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(ctx, "POST", c.config.APIURL+"/api/v1/events/batch", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to batch stream events to Lakehouse", logger.Error(err))
		return fmt.Errorf("failed to batch stream events: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("lakehouse returned error: %d - %s", resp.StatusCode, string(body))
	}

	logger.Logger.Info("Events batch streamed to Lakehouse successfully")
	return nil
}

// GetWorkflowMetrics retrieves aggregated workflow metrics
func (c *Client) GetWorkflowMetrics(ctx context.Context, workflowType string, startTime, endTime time.Time) (*WorkflowMetrics, error) {
	logger.Logger.Info("Getting workflow metrics from Lakehouse",
		logger.String("workflow_type", workflowType),
		logger.String("start_time", startTime.Format(time.RFC3339)),
		logger.String("end_time", endTime.Format(time.RFC3339)),
	)

	// Create HTTP request
	url := fmt.Sprintf("%s/api/v1/metrics/workflows?workflow_type=%s&start_time=%s&end_time=%s",
		c.config.APIURL,
		workflowType,
		startTime.Format(time.RFC3339),
		endTime.Format(time.RFC3339),
	)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to get metrics from Lakehouse", logger.Error(err))
		return nil, fmt.Errorf("failed to get metrics: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("lakehouse returned error: %d - %s", resp.StatusCode, string(body))
	}

	// Parse response
	var metrics WorkflowMetrics
	if err := json.NewDecoder(resp.Body).Decode(&metrics); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	logger.Logger.Info("Workflow metrics retrieved successfully")
	return &metrics, nil
}

// QueryWorkflowEvents queries workflow events with filters
func (c *Client) QueryWorkflowEvents(ctx context.Context, filters map[string]interface{}, limit int) ([]*WorkflowEvent, error) {
	logger.Logger.Info("Querying workflow events from Lakehouse",
		logger.Int("limit", limit),
	)

	// Create query payload
	payload := map[string]interface{}{
		"filters": filters,
		"limit":   limit,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal query: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(ctx, "POST", c.config.APIURL+"/api/v1/events/query", bytes.NewBuffer(data))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to query events from Lakehouse", logger.Error(err))
		return nil, fmt.Errorf("failed to query events: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("lakehouse returned error: %d - %s", resp.StatusCode, string(body))
	}

	// Parse response
	var result struct {
		Events []*WorkflowEvent `json:"events"`
		Count  int              `json:"count"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	logger.Logger.Info("Workflow events queried successfully",
		logger.Int("count", result.Count),
	)
	return result.Events, nil
}

// ExportToParquet exports workflow events to Parquet format
func (c *Client) ExportToParquet(ctx context.Context, filters map[string]interface{}, outputPath string) error {
	logger.Logger.Info("Exporting workflow events to Parquet",
		logger.String("output_path", outputPath),
	)

	// Create export payload
	payload := map[string]interface{}{
		"filters":     filters,
		"format":      "parquet",
		"output_path": outputPath,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal export request: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(ctx, "POST", c.config.APIURL+"/api/v1/events/export", bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to export events to Parquet", logger.Error(err))
		return fmt.Errorf("failed to export events: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusAccepted {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("lakehouse returned error: %d - %s", resp.StatusCode, string(body))
	}

	logger.Logger.Info("Export to Parquet initiated successfully")
	return nil
}

// Close closes the Lakehouse client
func (c *Client) Close() error {
	c.httpClient.CloseIdleConnections()
	return nil
}

