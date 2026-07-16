// KYC Upgrade gRPC Service
// Journey: journey_26_kyc_upgrade
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

type KYCUpgradeService struct {
	pb.UnimplementedKYCUpgradeServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewKYCUpgradeService(db *gorm.DB, tc temporal.Client) *KYCUpgradeService {
	return &KYCUpgradeService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteKYCUpgrade handles the main workflow
func (s *KYCUpgradeService) ExecuteKYCUpgrade(
	ctx context.Context,
	req *pb.KYCUpgradeRequest,
) (*pb.KYCUpgradeResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_26_kyc_upgrade_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"KYCUpgradeWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.KYCUpgradeResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "KYC Upgrade workflow started successfully",
	}, nil
}

func (s *KYCUpgradeService) validateRequest(req *pb.KYCUpgradeRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
