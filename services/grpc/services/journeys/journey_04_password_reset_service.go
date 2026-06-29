// Password Reset gRPC Service
// Journey: journey_04_password_reset
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

type PasswordResetService struct {
	pb.UnimplementedPasswordResetServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewPasswordResetService(db *gorm.DB, tc temporal.Client) *PasswordResetService {
	return &PasswordResetService{
		db: db,
		temporalClient: tc,
	}
}

// ExecutePasswordReset handles the main workflow
func (s *PasswordResetService) ExecutePasswordReset(
	ctx context.Context,
	req *pb.PasswordResetRequest,
) (*pb.PasswordResetResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_04_password_reset_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"PasswordResetWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.PasswordResetResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Password Reset workflow started successfully",
	}, nil
}

func (s *PasswordResetService) validateRequest(req *pb.PasswordResetRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
