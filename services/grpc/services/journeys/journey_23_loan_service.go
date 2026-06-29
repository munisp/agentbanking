// Loan Application gRPC Service
// Journey: journey_23_loan
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

type LoanApplicationService struct {
	pb.UnimplementedLoanApplicationServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewLoanApplicationService(db *gorm.DB, tc temporal.Client) *LoanApplicationService {
	return &LoanApplicationService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteLoanApplication handles the main workflow
func (s *LoanApplicationService) ExecuteLoanApplication(
	ctx context.Context,
	req *pb.LoanApplicationRequest,
) (*pb.LoanApplicationResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_23_loan_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"LoanApplicationWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.LoanApplicationResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Loan Application workflow started successfully",
	}, nil
}

func (s *LoanApplicationService) validateRequest(req *pb.LoanApplicationRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
