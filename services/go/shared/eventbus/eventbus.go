package eventbus

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"
)

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

type Event struct {
	Topic     string      `json:"topic"`
	Source    string      `json:"source"`
	Data     interface{} `json:"data"`
	Key      string      `json:"key,omitempty"`
	Timestamp string     `json:"timestamp"`
	Version  string      `json:"version"`
}

type EventBus struct {
	kafkaEndpoint  string
	daprPort       string
	fluvioEndpoint string
	serviceName    string
	client         *http.Client
}

func New(serviceName string) *EventBus {
	return &EventBus{
		kafkaEndpoint:  getEnv("KAFKA_REST_ENDPOINT", "http://localhost:8082"),
		daprPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		fluvioEndpoint: getEnv("FLUVIO_ENDPOINT", "http://localhost:9003"),
		serviceName:    serviceName,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

func (eb *EventBus) Publish(topic string, data interface{}, key string) error {
	event := Event{
		Topic:     topic,
		Source:    eb.serviceName,
		Data:     data,
		Key:      key,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Version:  "1.0",
	}

	if err := eb.publishKafka(topic, event); err == nil {
		return nil
	}
	log.Printf("[eventbus] Kafka failed, trying Dapr for topic=%s", topic)

	if err := eb.publishDapr(topic, event); err == nil {
		return nil
	}
	log.Printf("[eventbus] Dapr failed, trying Fluvio for topic=%s", topic)

	if err := eb.publishFluvio(topic, event); err == nil {
		return nil
	}

	return fmt.Errorf("all event bus backends failed for topic=%s", topic)
}

func (eb *EventBus) publishKafka(topic string, event Event) error {
	payload := map[string]interface{}{
		"records": []map[string]interface{}{
			{"key": event.Key, "value": event},
		},
	}
	body, _ := json.Marshal(payload)
	url := fmt.Sprintf("%s/topics/%s", eb.kafkaEndpoint, topic)
	req, _ := http.NewRequest("POST", url, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/vnd.kafka.json.v2+json")
	resp, err := eb.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("kafka HTTP %d", resp.StatusCode)
	}
	return nil
}

func (eb *EventBus) publishDapr(topic string, event Event) error {
	body, _ := json.Marshal(event)
	url := fmt.Sprintf("http://localhost:%s/v1.0/publish/pubsub/%s", eb.daprPort, topic)
	resp, err := eb.client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("dapr HTTP %d", resp.StatusCode)
	}
	return nil
}

func (eb *EventBus) publishFluvio(topic string, event Event) error {
	body, _ := json.Marshal(map[string]interface{}{
		"topic": topic,
		"key":   event.Key,
		"value": event,
	})
	url := fmt.Sprintf("%s/api/v1/produce", eb.fluvioEndpoint)
	resp, err := eb.client.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("fluvio HTTP %d", resp.StatusCode)
	}
	return nil
}
