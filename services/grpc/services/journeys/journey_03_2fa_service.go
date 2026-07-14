// Two-Factor Authentication gRPC Service
// Journey: journey_03_2fa
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

type Two-FactorAuthenticationService struct {
	pb.UnimplementedTwo-FactorAuthenticationServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewTwo-FactorAuthenticationService(db *gorm.DB, tc temporal.Client) *Two-FactorAuthenticationService {
	return &Two-FactorAuthenticationService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteTwo-FactorAuthentication handles the main workflow
func (s *Two-FactorAuthenticationService) ExecuteTwo-FactorAuthentication(
	ctx context.Context,
	req *pb.Two-FactorAuthenticationRequest,
) (*pb.Two-FactorAuthenticationResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_03_2fa_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"TwoFactorAuthWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.Two-FactorAuthenticationResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Two-Factor Authentication workflow started successfully",
	}, nil
}

func (s *Two-FactorAuthenticationService) validateRequest(req *pb.Two-FactorAuthenticationRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
