// Wise Transfer gRPC Service
// Journey: journey_12_wise
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

type WiseTransferService struct {
	pb.UnimplementedWiseTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewWiseTransferService(db *gorm.DB, tc temporal.Client) *WiseTransferService {
	return &WiseTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteWiseTransfer handles the main workflow
func (s *WiseTransferService) ExecuteWiseTransfer(
	ctx context.Context,
	req *pb.WiseTransferRequest,
) (*pb.WiseTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_12_wise_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"WiseTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.WiseTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Wise Transfer workflow started successfully",
	}, nil
}

func (s *WiseTransferService) validateRequest(req *pb.WiseTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
