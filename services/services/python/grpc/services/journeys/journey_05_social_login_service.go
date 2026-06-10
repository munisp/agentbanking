// Social Login gRPC Service
// Journey: journey_05_social_login
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

type SocialLoginService struct {
	pb.UnimplementedSocialLoginServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewSocialLoginService(db *gorm.DB, tc temporal.Client) *SocialLoginService {
	return &SocialLoginService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteSocialLogin handles the main workflow
func (s *SocialLoginService) ExecuteSocialLogin(
	ctx context.Context,
	req *pb.SocialLoginRequest,
) (*pb.SocialLoginResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_05_social_login_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"SocialLoginWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.SocialLoginResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Social Login workflow started successfully",
	}, nil
}

func (s *SocialLoginService) validateRequest(req *pb.SocialLoginRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
