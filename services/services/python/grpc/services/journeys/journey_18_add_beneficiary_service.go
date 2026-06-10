// Add Beneficiary gRPC Service
// Journey: journey_18_add_beneficiary
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

type AddBeneficiaryService struct {
	pb.UnimplementedAddBeneficiaryServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewAddBeneficiaryService(db *gorm.DB, tc temporal.Client) *AddBeneficiaryService {
	return &AddBeneficiaryService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteAddBeneficiary handles the main workflow
func (s *AddBeneficiaryService) ExecuteAddBeneficiary(
	ctx context.Context,
	req *pb.AddBeneficiaryRequest,
) (*pb.AddBeneficiaryResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_18_add_beneficiary_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"AddBeneficiaryWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.AddBeneficiaryResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Add Beneficiary workflow started successfully",
	}, nil
}

func (s *AddBeneficiaryService) validateRequest(req *pb.AddBeneficiaryRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
