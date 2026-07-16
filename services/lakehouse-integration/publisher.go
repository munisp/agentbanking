package lakehouse

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"
)

// PublisherConfig holds configuration for the lakehouse publisher
type PublisherConfig struct {
	DaprHost          string
	DaprPort          string
	PubSubName        string
	KafkaBrokers      string
	BatchSize         int
	FlushInterval     time.Duration
	RetryAttempts     int
	RetryDelay        time.Duration
	EnableOutbox      bool
	OutboxTableName   string
}

// DefaultPublisherConfig returns default configuration
func DefaultPublisherConfig() *PublisherConfig {
	return &PublisherConfig{
		DaprHost:       getEnv("DAPR_HOST", "localhost"),
		DaprPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		PubSubName:     getEnv("PUBSUB_NAME", "lakehouse-pubsub"),
		KafkaBrokers:   getEnv("KAFKA_BROKERS", "localhost:9092"),
		BatchSize:      100,
		FlushInterval:  time.Second * 5,
		RetryAttempts:  3,
		RetryDelay:     time.Millisecond * 100,
		EnableOutbox:   true,
		OutboxTableName: "outbox_events",
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// LakehousePublisher publishes banking events to the lakehouse
type LakehousePublisher struct {
	config      *PublisherConfig
	httpClient  *http.Client
	eventBuffer []*BankingEvent
	bufferMu    sync.Mutex
	stopCh      chan struct{}
	wg          sync.WaitGroup
	
	// Metrics
	eventsSent     int64
	eventsDropped  int64
	lastFlushTime  time.Time
	
	// Outbox support
	outboxWriter   OutboxWriter
}

// OutboxWriter interface for writing to outbox table
type OutboxWriter interface {
	WriteEvent(ctx context.Context, event *BankingEvent) error
	MarkEventSent(ctx context.Context, eventID string) error
	GetPendingEvents(ctx context.Context, limit int) ([]*BankingEvent, error)
}

// NewLakehousePublisher creates a new lakehouse publisher
func NewLakehousePublisher(config *PublisherConfig) *LakehousePublisher {
	if config == nil {
		config = DefaultPublisherConfig()
	}

	return &LakehousePublisher{
		config: config,
		httpClient: &http.Client{
			Timeout: time.Second * 10,
		},
		eventBuffer: make([]*BankingEvent, 0, config.BatchSize),
		stopCh:      make(chan struct{}),
	}
}

// SetOutboxWriter sets the outbox writer for guaranteed delivery
func (p *LakehousePublisher) SetOutboxWriter(writer OutboxWriter) {
	p.outboxWriter = writer
}

// Start starts the background flush goroutine
func (p *LakehousePublisher) Start() {
	p.wg.Add(1)
	go p.flushLoop()
	log.Printf("Lakehouse publisher started with Dapr at %s:%s", p.config.DaprHost, p.config.DaprPort)
}

// Stop stops the publisher and flushes remaining events
func (p *LakehousePublisher) Stop() {
	close(p.stopCh)
	p.wg.Wait()
	p.flush(context.Background())
	log.Println("Lakehouse publisher stopped")
}

// Publish publishes a banking event
func (p *LakehousePublisher) Publish(ctx context.Context, event *BankingEvent) error {
	// If outbox is enabled, write to outbox first for guaranteed delivery
	if p.config.EnableOutbox && p.outboxWriter != nil {
		if err := p.outboxWriter.WriteEvent(ctx, event); err != nil {
			log.Printf("Failed to write event to outbox: %v", err)
			// Continue to try direct publish
		}
	}

	p.bufferMu.Lock()
	p.eventBuffer = append(p.eventBuffer, event)
	shouldFlush := len(p.eventBuffer) >= p.config.BatchSize
	p.bufferMu.Unlock()

	if shouldFlush {
		return p.flush(ctx)
	}

	return nil
}

// PublishTransaction publishes a transaction event
func (p *LakehousePublisher) PublishTransaction(ctx context.Context, eventType EventType, payload *TransactionPayload) error {
	event, err := NewBankingEvent(eventType, "transaction-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransactionID)
	event.WithIdempotencyKey(fmt.Sprintf("txn-%s-%s", payload.TransactionID, eventType))
	if payload.CustomerID != "" {
		event.WithPII()
	}
	return p.Publish(ctx, event)
}

// PublishRouting publishes a routing event
func (p *LakehousePublisher) PublishRouting(ctx context.Context, eventType EventType, payload *RoutingPayload) error {
	event, err := NewBankingEvent(eventType, "routing-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransferID)
	event.WithIdempotencyKey(fmt.Sprintf("route-%s-%s", payload.TransferID, eventType))
	return p.Publish(ctx, event)
}

// PublishFloat publishes a float event
func (p *LakehousePublisher) PublishFloat(ctx context.Context, eventType EventType, payload *FloatPayload) error {
	event, err := NewBankingEvent(eventType, "float-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.FloatID)
	event.WithIdempotencyKey(fmt.Sprintf("float-%s-%s", payload.FloatID, eventType))
	return p.Publish(ctx, event)
}

// PublishCommission publishes a commission event
func (p *LakehousePublisher) PublishCommission(ctx context.Context, eventType EventType, payload *CommissionPayload) error {
	event, err := NewBankingEvent(eventType, "commission-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransactionID)
	event.WithIdempotencyKey(fmt.Sprintf("comm-%s-%s", payload.CommissionID, eventType))
	return p.Publish(ctx, event)
}

// PublishFraud publishes a fraud detection event
func (p *LakehousePublisher) PublishFraud(ctx context.Context, eventType EventType, payload *FraudPayload) error {
	event, err := NewBankingEvent(eventType, "fraud-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransactionID)
	event.WithIdempotencyKey(fmt.Sprintf("fraud-%s-%s", payload.ScreeningID, eventType))
	return p.Publish(ctx, event)
}

// PublishLedger publishes a ledger event
func (p *LakehousePublisher) PublishLedger(ctx context.Context, eventType EventType, payload *LedgerPayload) error {
	event, err := NewBankingEvent(eventType, "ledger-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransactionID)
	event.WithIdempotencyKey(fmt.Sprintf("ledger-%s-%s", payload.PostingID, eventType))
	return p.Publish(ctx, event)
}

// PublishMojaloop publishes a Mojaloop event
func (p *LakehousePublisher) PublishMojaloop(ctx context.Context, eventType EventType, payload *MojaloopPayload) error {
	event, err := NewBankingEvent(eventType, "mojaloop-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.TransferID)
	event.WithIdempotencyKey(fmt.Sprintf("moja-%s-%s", payload.TransferID, eventType))
	return p.Publish(ctx, event)
}

// PublishAgent publishes an agent event
func (p *LakehousePublisher) PublishAgent(ctx context.Context, eventType EventType, payload *AgentPayload) error {
	event, err := NewBankingEvent(eventType, "agent-service", payload)
	if err != nil {
		return err
	}
	event.WithCorrelationID(payload.AgentID)
	event.WithIdempotencyKey(fmt.Sprintf("agent-%s-%s-%d", payload.AgentID, eventType, time.Now().UnixNano()))
	return p.Publish(ctx, event)
}

// flushLoop runs the periodic flush
func (p *LakehousePublisher) flushLoop() {
	defer p.wg.Done()
	ticker := time.NewTicker(p.config.FlushInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			if err := p.flush(context.Background()); err != nil {
				log.Printf("Flush error: %v", err)
			}
		case <-p.stopCh:
			return
		}
	}
}

// flush sends buffered events to the lakehouse
func (p *LakehousePublisher) flush(ctx context.Context) error {
	p.bufferMu.Lock()
	if len(p.eventBuffer) == 0 {
		p.bufferMu.Unlock()
		return nil
	}
	events := p.eventBuffer
	p.eventBuffer = make([]*BankingEvent, 0, p.config.BatchSize)
	p.bufferMu.Unlock()

	// Group events by topic
	eventsByTopic := make(map[string][]*BankingEvent)
	for _, event := range events {
		topic := GetTopicForEventType(event.EventType)
		eventsByTopic[topic] = append(eventsByTopic[topic], event)
	}

	// Publish to each topic
	var lastErr error
	for topic, topicEvents := range eventsByTopic {
		if err := p.publishToTopic(ctx, topic, topicEvents); err != nil {
			log.Printf("Failed to publish to topic %s: %v", topic, err)
			lastErr = err
			p.eventsDropped += int64(len(topicEvents))
		} else {
			p.eventsSent += int64(len(topicEvents))
		}
	}

	p.lastFlushTime = time.Now()
	return lastErr
}

// publishToTopic publishes events to a specific topic via Dapr
func (p *LakehousePublisher) publishToTopic(ctx context.Context, topic string, events []*BankingEvent) error {
	for _, event := range events {
		if err := p.publishSingleEvent(ctx, topic, event); err != nil {
			return err
		}
	}
	return nil
}

// publishSingleEvent publishes a single event with retry
func (p *LakehousePublisher) publishSingleEvent(ctx context.Context, topic string, event *BankingEvent) error {
	url := fmt.Sprintf("http://%s:%s/v1.0/publish/%s/%s",
		p.config.DaprHost, p.config.DaprPort, p.config.PubSubName, topic)

	eventJSON, err := event.ToJSON()
	if err != nil {
		return fmt.Errorf("failed to serialize event: %w", err)
	}

	var lastErr error
	for attempt := 0; attempt < p.config.RetryAttempts; attempt++ {
		req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(eventJSON))
		if err != nil {
			return fmt.Errorf("failed to create request: %w", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Idempotency-Key", event.IdempotencyKey)

		resp, err := p.httpClient.Do(req)
		if err != nil {
			lastErr = err
			time.Sleep(p.config.RetryDelay * time.Duration(attempt+1))
			continue
		}
		resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			// Mark event as sent in outbox
			if p.config.EnableOutbox && p.outboxWriter != nil {
				p.outboxWriter.MarkEventSent(ctx, event.EventID)
			}
			return nil
		}

		lastErr = fmt.Errorf("unexpected status code: %d", resp.StatusCode)
		time.Sleep(p.config.RetryDelay * time.Duration(attempt+1))
	}

	return fmt.Errorf("failed after %d attempts: %w", p.config.RetryAttempts, lastErr)
}

// GetMetrics returns publisher metrics
func (p *LakehousePublisher) GetMetrics() map[string]interface{} {
	p.bufferMu.Lock()
	bufferSize := len(p.eventBuffer)
	p.bufferMu.Unlock()

	return map[string]interface{}{
		"events_sent":     p.eventsSent,
		"events_dropped":  p.eventsDropped,
		"buffer_size":     bufferSize,
		"last_flush_time": p.lastFlushTime,
	}
}

// PostgresOutboxWriter implements OutboxWriter for PostgreSQL
type PostgresOutboxWriter struct {
	db        interface{} // *sql.DB or *pgxpool.Pool
	tableName string
}

// NewPostgresOutboxWriter creates a new PostgreSQL outbox writer
func NewPostgresOutboxWriter(db interface{}, tableName string) *PostgresOutboxWriter {
	return &PostgresOutboxWriter{
		db:        db,
		tableName: tableName,
	}
}

// WriteEvent writes an event to the outbox table
func (w *PostgresOutboxWriter) WriteEvent(ctx context.Context, event *BankingEvent) error {
	// Implementation depends on the database driver being used
	// This is a placeholder that should be implemented based on the actual DB driver
	log.Printf("Writing event %s to outbox", event.EventID)
	return nil
}

// MarkEventSent marks an event as sent in the outbox
func (w *PostgresOutboxWriter) MarkEventSent(ctx context.Context, eventID string) error {
	log.Printf("Marking event %s as sent", eventID)
	return nil
}

// GetPendingEvents retrieves pending events from the outbox
func (w *PostgresOutboxWriter) GetPendingEvents(ctx context.Context, limit int) ([]*BankingEvent, error) {
	return nil, nil
}

// Global publisher instance
var (
	globalPublisher *LakehousePublisher
	publisherOnce   sync.Once
)

// GetPublisher returns the global lakehouse publisher
func GetPublisher() *LakehousePublisher {
	publisherOnce.Do(func() {
		globalPublisher = NewLakehousePublisher(nil)
		globalPublisher.Start()
	})
	return globalPublisher
}

// PublishTransactionEvent is a convenience function for publishing transaction events
func PublishTransactionEvent(ctx context.Context, eventType EventType, payload *TransactionPayload) error {
	return GetPublisher().PublishTransaction(ctx, eventType, payload)
}

// PublishRoutingEvent is a convenience function for publishing routing events
func PublishRoutingEvent(ctx context.Context, eventType EventType, payload *RoutingPayload) error {
	return GetPublisher().PublishRouting(ctx, eventType, payload)
}

// PublishFloatEvent is a convenience function for publishing float events
func PublishFloatEvent(ctx context.Context, eventType EventType, payload *FloatPayload) error {
	return GetPublisher().PublishFloat(ctx, eventType, payload)
}

// PublishCommissionEvent is a convenience function for publishing commission events
func PublishCommissionEvent(ctx context.Context, eventType EventType, payload *CommissionPayload) error {
	return GetPublisher().PublishCommission(ctx, eventType, payload)
}

// PublishFraudEvent is a convenience function for publishing fraud events
func PublishFraudEvent(ctx context.Context, eventType EventType, payload *FraudPayload) error {
	return GetPublisher().PublishFraud(ctx, eventType, payload)
}

// PublishLedgerEvent is a convenience function for publishing ledger events
func PublishLedgerEvent(ctx context.Context, eventType EventType, payload *LedgerPayload) error {
	return GetPublisher().PublishLedger(ctx, eventType, payload)
}

// PublishMojaloopEvent is a convenience function for publishing Mojaloop events
func PublishMojaloopEvent(ctx context.Context, eventType EventType, payload *MojaloopPayload) error {
	return GetPublisher().PublishMojaloop(ctx, eventType, payload)
}

// PublishAgentEvent is a convenience function for publishing agent events
func PublishAgentEvent(ctx context.Context, eventType EventType, payload *AgentPayload) error {
	return GetPublisher().PublishAgent(ctx, eventType, payload)
}
