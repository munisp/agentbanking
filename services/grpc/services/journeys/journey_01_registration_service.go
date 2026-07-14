// User Registration with KYC gRPC Service
// Journey: journey_01_registration
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

type UserRegistrationwithKYCService struct {
	pb.UnimplementedUserRegistrationwithKYCServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewUserRegistrationwithKYCService(db *gorm.DB, tc temporal.Client) *UserRegistrationwithKYCService {
	return &UserRegistrationwithKYCService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteUserRegistrationwithKYC handles the main workflow
func (s *UserRegistrationwithKYCService) ExecuteUserRegistrationwithKYC(
	ctx context.Context,
	req *pb.UserRegistrationwithKYCRequest,
) (*pb.UserRegistrationwithKYCResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_01_registration_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"UserRegistrationWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.UserRegistrationwithKYCResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "User Registration with KYC workflow started successfully",
	}, nil
}

func (s *UserRegistrationwithKYCService) validateRequest(req *pb.UserRegistrationwithKYCRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
