package engine

import (
"bytes"
"context"
"encoding/json"
"fmt"
"io"
"net/http"
"time"

"workflow-orchestrator/internal/domain"
"workflow-orchestrator/pkg/logger"
)

type StepExecutor struct {
httpClient *http.Client
maxRetries int
}

func NewStepExecutor(maxRetries int) *StepExecutor {
return &StepExecutor{
httpClient: &http.Client{
Timeout: 30 * time.Second,
Transport: &http.Transport{
MaxIdleConns:        1000,
MaxIdleConnsPerHost: 100,
MaxConnsPerHost:     100,
IdleConnTimeout:     90 * time.Second,
DisableKeepAlives:   false,
},
},
maxRetries: maxRetries,
}
}

func (s *StepExecutor) Execute(ctx context.Context, step *domain.WorkflowStep) error {
log := logger.Logger.With(
logger.String("workflow_id", step.WorkflowID),
logger.String("step", step.StepName),
)

step.Status = domain.StepRunning
now := time.Now()
step.StartedAt = &now

var lastErr error

for attempt := 0; attempt <= s.maxRetries; attempt++ {
if attempt > 0 {
step.Status = domain.StepRetrying
step.RetryCount = attempt

backoff := time.Duration(1<<uint(attempt-1)) * time.Second
log.Info("Retrying step", logger.Int("attempt", attempt), logger.Duration("backoff", backoff))

select {
case <-time.After(backoff):
case <-ctx.Done():
return ctx.Err()
}
}

var err error
switch step.StepType {
case "service_call":
step.OutputData, err = s.executeServiceCall(ctx, step)
case "notification":
step.OutputData, err = s.executeNotification(ctx, step)
case "event_publish":
step.OutputData, err = s.executeEventPublish(ctx, step)
default:
err = fmt.Errorf("unknown step type: %s", step.StepType)
}

if err == nil {
step.Status = domain.StepCompleted
now := time.Now()
step.CompletedAt = &now
step.DurationSeconds = now.Sub(*step.StartedAt).Seconds()
log.Info("Step completed", logger.Float64("duration", step.DurationSeconds))
return nil
}

lastErr = err
log.Warn("Step attempt failed", logger.Int("attempt", attempt), logger.Error(err))
}

step.Status = domain.StepFailed
step.ErrorMessage = lastErr.Error()
now = time.Now()
step.CompletedAt = &now
step.DurationSeconds = now.Sub(*step.StartedAt).Seconds()

return lastErr
}

func (s *StepExecutor) executeServiceCall(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
body, err := json.Marshal(step.InputData)
if err != nil {
return nil, fmt.Errorf("failed to marshal input: %w", err)
}

url := step.ServiceURL + step.Endpoint
req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewReader(body))
if err != nil {
return nil, fmt.Errorf("failed to create request: %w", err)
}

req.Header.Set("Content-Type", "application/json")

resp, err := s.httpClient.Do(req)
if err != nil {
return nil, fmt.Errorf("failed to execute request: %w", err)
}
defer resp.Body.Close()

if resp.StatusCode >= 400 {
body, _ := io.ReadAll(resp.Body)
return nil, fmt.Errorf("service returned error %d: %s", resp.StatusCode, string(body))
}

var result map[string]interface{}
if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
return nil, fmt.Errorf("failed to decode response: %w", err)
}

return result, nil
}

func (s *StepExecutor) executeNotification(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
return map[string]interface{}{
"notification_sent": true,
"channel":           "sms",
}, nil
}

func (s *StepExecutor) executeEventPublish(ctx context.Context, step *domain.WorkflowStep) (map[string]interface{}, error) {
return map[string]interface{}{
"event_published": true,
}, nil
}
