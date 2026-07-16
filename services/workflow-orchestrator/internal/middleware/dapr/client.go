package dapr

import (
	"context"
	"encoding/json"
	"fmt"

	dapr "github.com/dapr/go-sdk/client"
	"workflow-orchestrator/pkg/logger"
)

// Client represents a Dapr client for service invocation and state management
type Client struct {
	client dapr.Client
	config *Config
}

// Config holds Dapr configuration
type Config struct {
	HTTPPort int
	GRPCPort int
}

// NewClient creates a new Dapr client
func NewClient(config *Config) (*Client, error) {
	client, err := dapr.NewClient()
	if err != nil {
		return nil, fmt.Errorf("failed to create Dapr client: %w", err)
	}

	return &Client{
		client: client,
		config: config,
	}, nil
}

// InvokeService invokes a service method via Dapr sidecar
func (c *Client) InvokeService(ctx context.Context, appID, method string, data interface{}) ([]byte, error) {
	logger.Logger.Info("Invoking service via Dapr",
		logger.String("app_id", appID),
		logger.String("method", method),
	)

	// Marshal data to JSON bytes
	var dataBytes []byte
	switch v := data.(type) {
	case []byte:
		dataBytes = v
	default:
		var err2 error
		dataBytes, err2 = json.Marshal(data)
		if err2 != nil {
			return nil, fmt.Errorf("failed to marshal data: %w", err2)
		}
	}

	// Invoke service using Dapr
	resp, err := c.client.InvokeMethodWithContent(ctx, appID, method, "post", &dapr.DataContent{
		ContentType: "application/json",
		Data:        dataBytes,
	})
	if err != nil {
		logger.Logger.Error("Failed to invoke service",
			logger.String("app_id", appID),
			logger.String("method", method),
			logger.Error(err),
		)
		return nil, fmt.Errorf("service invocation failed: %w", err)
	}

	return resp, nil
}

// SaveState saves workflow state to Dapr state store
func (c *Client) SaveState(ctx context.Context, storeName, key string, value interface{}) error {
	logger.Logger.Info("Saving state via Dapr",
		logger.String("store", storeName),
		logger.String("key", key),
	)

	var valueBytes []byte
	switch v := value.(type) {
	case []byte:
		valueBytes = v
	default:
		var err2 error
		valueBytes, err2 = json.Marshal(value)
		if err2 != nil {
			return fmt.Errorf("failed to marshal value: %w", err2)
		}
	}

	err := c.client.SaveState(ctx, storeName, key, valueBytes, nil)
	if err != nil {
		logger.Logger.Error("Failed to save state",
			logger.String("store", storeName),
			logger.String("key", key),
			logger.Error(err),
		)
		return fmt.Errorf("save state failed: %w", err)
	}

	return nil
}

// GetState retrieves workflow state from Dapr state store
func (c *Client) GetState(ctx context.Context, storeName, key string) ([]byte, error) {
	logger.Logger.Info("Getting state via Dapr",
		logger.String("store", storeName),
		logger.String("key", key),
	)

	item, err := c.client.GetState(ctx, storeName, key, nil)
	if err != nil {
		logger.Logger.Error("Failed to get state",
			logger.String("store", storeName),
			logger.String("key", key),
			logger.Error(err),
		)
		return nil, fmt.Errorf("get state failed: %w", err)
	}

	return item.Value, nil
}

// DeleteState deletes workflow state from Dapr state store
func (c *Client) DeleteState(ctx context.Context, storeName, key string) error {
	logger.Logger.Info("Deleting state via Dapr",
		logger.String("store", storeName),
		logger.String("key", key),
	)

	err := c.client.DeleteState(ctx, storeName, key, nil)
	if err != nil {
		logger.Logger.Error("Failed to delete state",
			logger.String("store", storeName),
			logger.String("key", key),
			logger.Error(err),
		)
		return fmt.Errorf("delete state failed: %w", err)
	}

	return nil
}

// PublishEvent publishes an event to Dapr pub/sub
func (c *Client) PublishEvent(ctx context.Context, pubsubName, topic string, data interface{}) error {
	logger.Logger.Info("Publishing event via Dapr",
		logger.String("pubsub", pubsubName),
		logger.String("topic", topic),
	)

	err := c.client.PublishEvent(ctx, pubsubName, topic, data)
	if err != nil {
		logger.Logger.Error("Failed to publish event",
			logger.String("pubsub", pubsubName),
			logger.String("topic", topic),
			logger.Error(err),
		)
		return fmt.Errorf("publish event failed: %w", err)
	}

	return nil
}

// GetSecret retrieves a secret from Dapr secret store
func (c *Client) GetSecret(ctx context.Context, storeName, key string) (map[string]string, error) {
	logger.Logger.Info("Getting secret via Dapr",
		logger.String("store", storeName),
		logger.String("key", key),
	)

	secret, err := c.client.GetSecret(ctx, storeName, key, nil)
	if err != nil {
		logger.Logger.Error("Failed to get secret",
			logger.String("store", storeName),
			logger.String("key", key),
			logger.Error(err),
		)
		return nil, fmt.Errorf("get secret failed: %w", err)
	}

	return secret, nil
}

// Close closes the Dapr client
func (c *Client) Close() error {
	c.client.Close()
	return nil
}

