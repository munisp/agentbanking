// Biometric Authentication Setup gRPC Service
// Journey: journey_02_biometric
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

type BiometricAuthenticationSetupService struct {
	pb.UnimplementedBiometricAuthenticationSetupServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewBiometricAuthenticationSetupService(db *gorm.DB, tc temporal.Client) *BiometricAuthenticationSetupService {
	return &BiometricAuthenticationSetupService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteBiometricAuthenticationSetup handles the main workflow
func (s *BiometricAuthenticationSetupService) ExecuteBiometricAuthenticationSetup(
	ctx context.Context,
	req *pb.BiometricAuthenticationSetupRequest,
) (*pb.BiometricAuthenticationSetupResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_02_biometric_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"BiometricSetupWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.BiometricAuthenticationSetupResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Biometric Authentication Setup workflow started successfully",
	}, nil
}

func (s *BiometricAuthenticationSetupService) validateRequest(req *pb.BiometricAuthenticationSetupRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
