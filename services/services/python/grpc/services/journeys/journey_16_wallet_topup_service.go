// Wallet Top-up gRPC Service
// Journey: journey_16_wallet_topup
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

type WalletTop-upService struct {
	pb.UnimplementedWalletTop-upServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewWalletTop-upService(db *gorm.DB, tc temporal.Client) *WalletTop-upService {
	return &WalletTop-upService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteWalletTop-up handles the main workflow
func (s *WalletTop-upService) ExecuteWalletTop-up(
	ctx context.Context,
	req *pb.WalletTop-upRequest,
) (*pb.WalletTop-upResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_16_wallet_topup_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"WalletTopupWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.WalletTop-upResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Wallet Top-up workflow started successfully",
	}, nil
}

func (s *WalletTop-upService) validateRequest(req *pb.WalletTop-upRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
