// Package redis provides a Redis cache client for the 54agent workflow orchestrator.
// Used for agent session caching, fraud rule caching, rate-limit counters,
// and real-time leaderboards.
package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"workflow-orchestrator/pkg/logger"

	goredis "github.com/go-redis/redis/v8"
)

// Client wraps the go-redis client with domain-specific helpers
type Client struct {
	rdb    *goredis.Client
	config *Config
}

// Config holds Redis configuration
type Config struct {
	Addr     string // e.g. redis:6379
	Password string
	DB       int
	PoolSize int
}

// NewClient creates and connects a Redis client
func NewClient(config *Config) (*Client, error) {
	rdb := goredis.NewClient(&goredis.Options{
		Addr:         config.Addr,
		Password:     config.Password,
		DB:           config.DB,
		PoolSize:     config.PoolSize,
		MinIdleConns: 5,
		DialTimeout:  3 * time.Second,
		ReadTimeout:  2 * time.Second,
		WriteTimeout: 2 * time.Second,
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis: ping failed: %w", err)
	}

	logger.Logger.Info("Redis connected", logger.String("addr", config.Addr))
	return &Client{rdb: rdb, config: config}, nil
}

// Set stores a JSON-serialised value with an optional TTL
func (c *Client) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("redis: marshal error: %w", err)
	}
	return c.rdb.Set(ctx, key, data, ttl).Err()
}

// Get retrieves and deserialises a value. Returns false if the key does not exist.
func (c *Client) Get(ctx context.Context, key string, dest interface{}) (bool, error) {
	data, err := c.rdb.Get(ctx, key).Bytes()
	if err == goredis.Nil {
		return false, nil
	}
	if err != nil {
		return false, fmt.Errorf("redis: get error: %w", err)
	}
	if err := json.Unmarshal(data, dest); err != nil {
		return false, fmt.Errorf("redis: unmarshal error: %w", err)
	}
	return true, nil
}

// Del removes one or more keys
func (c *Client) Del(ctx context.Context, keys ...string) error {
	return c.rdb.Del(ctx, keys...).Err()
}

// Incr atomically increments a counter and returns the new value
func (c *Client) Incr(ctx context.Context, key string) (int64, error) {
	return c.rdb.Incr(ctx, key).Result()
}

// IncrWithExpiry increments a counter and sets TTL if the key is new
func (c *Client) IncrWithExpiry(ctx context.Context, key string, ttl time.Duration) (int64, error) {
	pipe := c.rdb.Pipeline()
	incr := pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, ttl)
	if _, err := pipe.Exec(ctx); err != nil {
		return 0, fmt.Errorf("redis: incr pipeline error: %w", err)
	}
	return incr.Val(), nil
}

// Publish publishes a message to a Redis pub/sub channel
func (c *Client) Publish(ctx context.Context, channel string, payload interface{}) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("redis: marshal error: %w", err)
	}
	return c.rdb.Publish(ctx, channel, data).Err()
}

// Subscribe subscribes to a Redis pub/sub channel and calls handler for each message
func (c *Client) Subscribe(ctx context.Context, channel string, handler func(payload []byte)) error {
	sub := c.rdb.Subscribe(ctx, channel)
	defer sub.Close()

	ch := sub.Channel()
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case msg, ok := <-ch:
			if !ok {
				return nil
			}
			handler([]byte(msg.Payload))
		}
	}
}

// Ping checks Redis connectivity
func (c *Client) Ping(ctx context.Context) error {
	return c.rdb.Ping(ctx).Err()
}

// Close closes the Redis connection
func (c *Client) Close() error {
	return c.rdb.Close()
}

// ─── Domain-specific helpers used by the integration layer ───────────────────

// CacheWorkflowState stores a workflow state map with a TTL in seconds
func (c *Client) CacheWorkflowState(ctx context.Context, key string, state map[string]interface{}, ttlSeconds int) error {
	return c.Set(ctx, key, state, time.Duration(ttlSeconds)*time.Second)
}

// GetWorkflowState retrieves a workflow state map. Returns nil, nil when not found.
func (c *Client) GetWorkflowState(ctx context.Context, key string) (map[string]interface{}, error) {
	var state map[string]interface{}
	found, err := c.Get(ctx, key, &state)
	if err != nil {
		return nil, err
	}
	if !found {
		return nil, nil
	}
	return state, nil
}

// AcquireLock attempts to acquire a distributed lock using SET NX EX.
// Returns true if the lock was acquired.
func (c *Client) AcquireLock(ctx context.Context, lockKey string, ttlSeconds int) (bool, error) {
	ok, err := c.rdb.SetNX(ctx, "lock:"+lockKey, "1", time.Duration(ttlSeconds)*time.Second).Result()
	if err != nil {
		return false, fmt.Errorf("redis: acquire lock error: %w", err)
	}
	return ok, nil
}

// ReleaseLock releases a distributed lock
func (c *Client) ReleaseLock(ctx context.Context, lockKey string) error {
	return c.rdb.Del(ctx, "lock:"+lockKey).Err()
}
