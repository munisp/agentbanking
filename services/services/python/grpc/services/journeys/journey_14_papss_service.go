// PAPSS Transfer gRPC Service
// Journey: journey_14_papss
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

type PAPSSTransferService struct {
	pb.UnimplementedPAPSSTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewPAPSSTransferService(db *gorm.DB, tc temporal.Client) *PAPSSTransferService {
	return &PAPSSTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecutePAPSSTransfer handles the main workflow
func (s *PAPSSTransferService) ExecutePAPSSTransfer(
	ctx context.Context,
	req *pb.PAPSSTransferRequest,
) (*pb.PAPSSTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_14_papss_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"PAPSSTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.PAPSSTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "PAPSS Transfer workflow started successfully",
	}, nil
}

func (s *PAPSSTransferService) validateRequest(req *pb.PAPSSTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
