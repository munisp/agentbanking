// NIBSSTransferWorkflow
// Journey: NIBSS Transfer
// Temporal Workflow Implementation

package workflows

import (
	"time"

	"go.temporal.io/sdk/workflow"
)

type NIBSSTransferWorkflowInput struct {
	UserID      uint   `json:"user_id"`
	RequestData map[string]interface{} `json:"request_data"`
}

type NIBSSTransferWorkflowResult struct {
	Success   bool   `json:"success"`
	Message   string `json:"message"`
	Data      map[string]interface{} `json:"data"`
}

// NIBSSTransferWorkflow orchestrates the NIBSS Transfer journey
func NIBSSTransferWorkflow(ctx workflow.Context, input NIBSSTransferWorkflowInput) (*NIBSSTransferWorkflowResult, error) {
	logger := workflow.GetLogger(ctx)
	logger.Info("NIBSSTransferWorkflow started", "user_id", input.UserID)

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

	result := &NIBSSTransferWorkflowResult{
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

	result.Message = "NIBSS Transfer completed successfully"
	logger.Info("NIBSSTransferWorkflow completed", "user_id", input.UserID)

	return result, nil
}
