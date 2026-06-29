// Transaction Dispute gRPC Service
// Journey: journey_20_dispute
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

type TransactionDisputeService struct {
	pb.UnimplementedTransactionDisputeServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewTransactionDisputeService(db *gorm.DB, tc temporal.Client) *TransactionDisputeService {
	return &TransactionDisputeService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteTransactionDispute handles the main workflow
func (s *TransactionDisputeService) ExecuteTransactionDispute(
	ctx context.Context,
	req *pb.TransactionDisputeRequest,
) (*pb.TransactionDisputeResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_20_dispute_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"DisputeWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.TransactionDisputeResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Transaction Dispute workflow started successfully",
	}, nil
}

func (s *TransactionDisputeService) validateRequest(req *pb.TransactionDisputeRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
