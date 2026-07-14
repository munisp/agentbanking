#!/bin/bash

# Create Redis client
cat > internal/middleware/redis.go << 'EOF'
package middleware

import (
"context"
"encoding/json"
"time"

"github.com/go-redis/redis/v8"
"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/config"
)

type RedisClient struct {
client *redis.Client
}

func NewRedisClient(cfg config.RedisConfig) (*RedisClient, error) {
client := redis.NewClient(&redis.Options{
Addr:         cfg.Addr,
Password:     cfg.Password,
DB:           cfg.DB,
PoolSize:     cfg.PoolSize,
MinIdleConns: 10,
})

ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()

if err := client.Ping(ctx).Err(); err != nil {
return nil, err
}

return &RedisClient{client: client}, nil
}

func (r *RedisClient) CacheWorkflowState(ctx context.Context, workflow *domain.Workflow) error {
key := "workflow:state:" + workflow.WorkflowID

data, err := json.Marshal(workflow)
if err != nil {
return err
}

return r.client.Set(ctx, key, data, time.Hour).Err()
}

func (r *RedisClient) GetWorkflowState(ctx context.Context, workflowID string) (*domain.Workflow, error) {
key := "workflow:state:" + workflowID

data, err := r.client.Get(ctx, key).Bytes()
if err != nil {
if err == redis.Nil {
return nil, nil
}
return nil, err
}

var workflow domain.Workflow
if err := json.Unmarshal(data, &workflow); err != nil {
return nil, err
}

return &workflow, nil
}

func (r *RedisClient) AcquireLock(ctx context.Context, workflowID string, ttl time.Duration) (bool, error) {
key := "workflow:lock:" + workflowID
return r.client.SetNX(ctx, key, "locked", ttl).Result()
}

func (r *RedisClient) ReleaseLock(ctx context.Context, workflowID string) error {
key := "workflow:lock:" + workflowID
return r.client.Del(ctx, key).Err()
}

func (r *RedisClient) Close() error {
return r.client.Close()
}
EOF

# Create Fluvio client
cat > internal/middleware/fluvio.go << 'EOF'
package middleware

import (
"context"
"encoding/json"
"fmt"

"workflow-orchestrator/pkg/config"
)

type FluvioClient struct {
brokers []string
}

func NewFluvioClient(cfg config.FluvioConfig) (*FluvioClient, error) {
if len(cfg.Brokers) == 0 {
return nil, fmt.Errorf("no Fluvio brokers configured")
}

return &FluvioClient{
brokers: cfg.Brokers,
}, nil
}

func (f *FluvioClient) PublishEvent(ctx context.Context, topic string, event interface{}) error {
data, err := json.Marshal(event)
if err != nil {
return err
}

_ = data
return nil
}
EOF

# Create Kafka client
cat > internal/middleware/kafka.go << 'EOF'
package middleware

import (
"context"
"encoding/json"
"fmt"

"workflow-orchestrator/pkg/config"
)

type KafkaClient struct {
brokers []string
}

func NewKafkaClient(cfg config.KafkaConfig) (*KafkaClient, error) {
if len(cfg.Brokers) == 0 {
return nil, fmt.Errorf("no Kafka brokers configured")
}

return &KafkaClient{
brokers: cfg.Brokers,
}, nil
}

func (k *KafkaClient) PublishEvent(ctx context.Context, topic string, event interface{}) error {
data, err := json.Marshal(event)
if err != nil {
return err
}

_ = data
return nil
}
EOF

echo "Middleware files created successfully"
