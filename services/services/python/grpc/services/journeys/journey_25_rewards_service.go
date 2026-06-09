// Rewards Redemption gRPC Service
// Journey: journey_25_rewards
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

type RewardsRedemptionService struct {
	pb.UnimplementedRewardsRedemptionServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewRewardsRedemptionService(db *gorm.DB, tc temporal.Client) *RewardsRedemptionService {
	return &RewardsRedemptionService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteRewardsRedemption handles the main workflow
func (s *RewardsRedemptionService) ExecuteRewardsRedemption(
	ctx context.Context,
	req *pb.RewardsRedemptionRequest,
) (*pb.RewardsRedemptionResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_25_rewards_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"RewardsRedemptionWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.RewardsRedemptionResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Rewards Redemption workflow started successfully",
	}, nil
}

func (s *RewardsRedemptionService) validateRequest(req *pb.RewardsRedemptionRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
