package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	kafkago "github.com/segmentio/kafka-go"
	"workflow-orchestrator/pkg/logger"
	"workflow-orchestrator/pkg/metrics"
)

// Client represents a Kafka client for workflow events
type Client struct {
	writer *kafkago.Writer
	config *Config
}

// Config holds Kafka configuration
type Config struct {
	Brokers              []string
	TopicWorkflowEvents  string
	TopicWorkflowTasks   string
	ConsumerGroup        string
	EnableAutoCommit     bool
	SessionTimeoutMs     int
	MaxPollIntervalMs    int
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

// NewClient creates a new Kafka client using segmentio/kafka-go (pure Go, no CGO)
func NewClient(config *Config) (*Client, error) {
	writer := &kafkago.Writer{
		Addr:                   kafkago.TCP(config.Brokers...),
		Balancer:               &kafkago.LeastBytes{},
		BatchTimeout:           10 * time.Millisecond,
		BatchSize:              100,
		RequiredAcks:           kafkago.RequireAll,
		MaxAttempts:            3,
		AllowAutoTopicCreation: true,
		Compression:            kafkago.Snappy,
	}

	return &Client{
		writer: writer,
		config: config,
	}, nil
}

// PublishWorkflowEvent publishes a workflow lifecycle event to Kafka
func (c *Client) PublishWorkflowEvent(ctx context.Context, event *WorkflowEvent) error {
	start := time.Now()

	data, err := json.Marshal(event)
	if err != nil {
		metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "error").Inc()
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	msg := kafkago.Message{
		Topic: c.config.TopicWorkflowEvents,
		Key:   []byte(event.WorkflowID),
		Value: data,
		Headers: []kafkago.Header{
			{Key: "event_type", Value: []byte(event.EventType)},
			{Key: "workflow_type", Value: []byte(event.WorkflowType)},
		},
	}

	if err := c.writer.WriteMessages(ctx, msg); err != nil {
		metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "error").Inc()
		return fmt.Errorf("failed to publish event: %w", err)
	}

	metrics.EventsPublished.WithLabelValues(c.config.TopicWorkflowEvents, "success").Inc()
	logger.Logger.Info("Event published to Kafka",
		logger.String("topic", c.config.TopicWorkflowEvents),
		logger.String("workflow_id", event.WorkflowID),
		logger.Duration("duration", time.Since(start)),
	)
	return nil
}

// PublishWorkflowTask publishes a workflow task to Kafka for asynchronous processing
func (c *Client) PublishWorkflowTask(ctx context.Context, task map[string]interface{}) error {
	data, err := json.Marshal(task)
	if err != nil {
		return fmt.Errorf("failed to marshal task: %w", err)
	}

	msg := kafkago.Message{
		Topic: c.config.TopicWorkflowTasks,
		Value: data,
	}

	if err := c.writer.WriteMessages(ctx, msg); err != nil {
		return fmt.Errorf("failed to publish task: %w", err)
	}
	return nil
}

// ConsumeWorkflowEvents consumes workflow events from Kafka
func (c *Client) ConsumeWorkflowEvents(ctx context.Context, handler func(*WorkflowEvent) error) error {
	reader := kafkago.NewReader(kafkago.ReaderConfig{
		Brokers:        c.config.Brokers,
		Topic:          c.config.TopicWorkflowEvents,
		GroupID:        c.config.ConsumerGroup,
		MinBytes:       1,
		MaxBytes:       10e6,
		CommitInterval: time.Second,
		StartOffset:    kafkago.LastOffset,
	})
	defer reader.Close()

	logger.Logger.Info("Started consuming workflow events from Kafka",
		logger.String("topic", c.config.TopicWorkflowEvents),
		logger.String("group", c.config.ConsumerGroup),
	)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
			msg, err := reader.ReadMessage(ctx)
			if err != nil {
				if ctx.Err() != nil {
					return ctx.Err()
				}
				logger.Logger.Error("Error reading message", logger.Error(err))
				continue
			}

			var event WorkflowEvent
			if err := json.Unmarshal(msg.Value, &event); err != nil {
				logger.Logger.Error("Failed to unmarshal event", logger.Error(err))
				continue
			}

			if err := handler(&event); err != nil {
				logger.Logger.Error("Failed to handle event",
					logger.String("workflow_id", event.WorkflowID),
					logger.Error(err),
				)
			}
		}
	}
}

// Flush flushes any pending messages in the writer
func (c *Client) Flush(timeout time.Duration) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	_ = c.writer.Close()
	_ = ctx
}

// Close closes the Kafka client
func (c *Client) Close() error {
	return c.writer.Close()
}

// Helper function to join broker addresses
func joinBrokers(brokers []string) string {
	return strings.Join(brokers, ",")
}
