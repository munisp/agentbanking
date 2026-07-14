// InvestmentWorkflow
// Journey: Investment Portfolio
// Temporal Workflow Implementation

package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

type InvestmentWorkflowInput struct {
	UserID      uint   `json:"user_id"`
	RequestData map[string]interface{} `json:"request_data"`
}

type InvestmentWorkflowResult struct {
	Success   bool   `json:"success"`
	Message   string `json:"message"`
	Data      map[string]interface{} `json:"data"`
}

// InvestmentWorkflow orchestrates the Investment Portfolio journey
func InvestmentWorkflow(ctx workflow.Context, input InvestmentWorkflowInput) (*InvestmentWorkflowResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("InvestmentWorkflow started", "user_id", input.UserID)

	// Activity options
	ao := workflow.ActivityOptions{
		StartToCloseTimeout: 5 * time.Minute,
		RetryPolicy: &temporal.RetryPolicy{
			InitialInterval: time.Second,
			MaximumInterval: time.Minute,
			MaximumAttempts: 3,
		},
	}
	ctx = workflow.WithActivityOptions(ctx, ao)

	result := &InvestmentWorkflowResult{
		Success: true,
		Data: make(map[string]interface{}),
	}

	// Step 1: Validate input
	var validateResult bool
	err := workflow.ExecuteActivity(ctx, "ValidateInput", input).Get(ctx, &validateResult)
	if err != nil {
		return nil, err
	}

	// Step 2: Execute business logic
	var businessResult map[string]interface{}
	err = workflow.ExecuteActivity(ctx, "ExecuteBusinessLogic", input).Get(ctx, &businessResult)
	if err != nil {
		return nil, err
	}
	result.Data = businessResult

	// Step 3: Send notification
	err = workflow.ExecuteActivity(ctx, "SendNotification", input.UserID, "success").Get(ctx, nil)
	if err != nil {
		logger.Warn("Failed to send notification", "error", err)
	}

	result.Message = "Investment Portfolio completed successfully"
	logger.Info("InvestmentWorkflow completed", "user_id", input.UserID)

	return result, nil
}
