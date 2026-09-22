package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"strings"
	"time"

	"github.com/segmentio/kafka-go"
)

type LoanEvent struct {
	Type      string                 `json:"type"`
	EntityID  string                 `json:"entity_id"`
	TenantID  string                 `json:"tenant_id"`
	Status    string                 `json:"status"`
	Timestamp time.Time              `json:"timestamp"`
	Metadata  map[string]interface{} `json:"metadata"`
}

type LoanKafkaClient struct {
	writer *kafka.Writer
}

func NewLoanKafkaClient() *LoanKafkaClient {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}
	topic := os.Getenv("KAFKA_LOAN_TOPIC")
	if topic == "" {
		topic = "loan-events"
	}
	return &LoanKafkaClient{
		writer: &kafka.Writer{
			Addr:     kafka.TCP(strings.Split(brokers, ",")...),
			Topic:    topic,
			Balancer: &kafka.LeastBytes{},
			// F17: async writer — WriteMessages returns after queueing instead
			// of paying up to +5s on the request path when Kafka is slow.
			Async:        true,
			BatchTimeout: 100 * time.Millisecond,
			Completion: func(messages []kafka.Message, err error) {
				if err != nil {
					log.Printf("Kafka async delivery error (%d messages): %v", len(messages), err)
				}
			},
		},
	}
}

func (c *LoanKafkaClient) PublishEvent(eventType string, event LoanEvent) {
	event.Type = eventType
	msgBytes, err := json.Marshal(event)
	if err != nil {
		log.Printf("Failed to marshal loan event: %v", err)
		return
	}
	// With Async:true this only waits for local queueing; the 5s context is a
	// safety bound, not the delivery path.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	err = c.writer.WriteMessages(ctx, kafka.Message{
		Key:   []byte(event.EntityID),
		Value: msgBytes,
	})
	if err != nil {
		log.Printf("Failed to publish loan event to Kafka: %v", err)
	} else {
		log.Printf("Published loan event to Kafka: %s", eventType)
	}
}

func (c *LoanKafkaClient) Close() error {
	return c.writer.Close()
}
