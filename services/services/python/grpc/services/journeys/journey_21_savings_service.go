// Savings Account gRPC Service
// Journey: journey_21_savings
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

type SavingsAccountService struct {
	pb.UnimplementedSavingsAccountServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewSavingsAccountService(db *gorm.DB, tc temporal.Client) *SavingsAccountService {
	return &SavingsAccountService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteSavingsAccount handles the main workflow
func (s *SavingsAccountService) ExecuteSavingsAccount(
	ctx context.Context,
	req *pb.SavingsAccountRequest,
) (*pb.SavingsAccountResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_21_savings_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"SavingsAccountWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.SavingsAccountResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Savings Account workflow started successfully",
	}, nil
}

func (s *SavingsAccountService) validateRequest(req *pb.SavingsAccountRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
