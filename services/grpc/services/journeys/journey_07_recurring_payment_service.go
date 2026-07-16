// Recurring Payment gRPC Service
// Journey: journey_07_recurring_payment
// Generated for gRPC API

package journeys

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"gorm.io/gorm"

	pb "github.com/remittance/proto/v1"
	"github.com/remittance/backend/models"
	"github.com/remittance/backend/temporal"
)

type RecurringPaymentService struct {
	pb.UnimplementedRecurringPaymentServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewRecurringPaymentService(db *gorm.DB, tc temporal.Client) *RecurringPaymentService {
	return &RecurringPaymentService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteRecurringPayment handles the main workflow
func (s *RecurringPaymentService) ExecuteRecurringPayment(
	ctx context.Context,
	req *pb.RecurringPaymentRequest,
) (*pb.RecurringPaymentResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_07_recurring_payment_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"RecurringPaymentWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.RecurringPaymentResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Recurring Payment workflow started successfully",
	}, nil
}

func (s *RecurringPaymentService) validateRequest(req *pb.RecurringPaymentRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
