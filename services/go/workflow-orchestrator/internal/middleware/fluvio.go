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
