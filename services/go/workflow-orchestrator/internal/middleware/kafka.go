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
