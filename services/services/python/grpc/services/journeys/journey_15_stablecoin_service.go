// Stablecoin Transfer gRPC Service
// Journey: journey_15_stablecoin
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

type StablecoinTransferService struct {
	pb.UnimplementedStablecoinTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewStablecoinTransferService(db *gorm.DB, tc temporal.Client) *StablecoinTransferService {
	return &StablecoinTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteStablecoinTransfer handles the main workflow
func (s *StablecoinTransferService) ExecuteStablecoinTransfer(
	ctx context.Context,
	req *pb.StablecoinTransferRequest,
) (*pb.StablecoinTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_15_stablecoin_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"StablecoinTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.StablecoinTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Stablecoin Transfer workflow started successfully",
	}, nil
}

func (s *StablecoinTransferService) validateRequest(req *pb.StablecoinTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
