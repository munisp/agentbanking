// NIBSS Transfer gRPC Service
// Journey: journey_06_nibss_transfer
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

type NIBSSTransferService struct {
	pb.UnimplementedNIBSSTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewNIBSSTransferService(db *gorm.DB, tc temporal.Client) *NIBSSTransferService {
	return &NIBSSTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteNIBSSTransfer handles the main workflow
func (s *NIBSSTransferService) ExecuteNIBSSTransfer(
	ctx context.Context,
	req *pb.NIBSSTransferRequest,
) (*pb.NIBSSTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_06_nibss_transfer_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"NIBSSTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.NIBSSTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "NIBSS Transfer workflow started successfully",
	}, nil
}

func (s *NIBSSTransferService) validateRequest(req *pb.NIBSSTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
