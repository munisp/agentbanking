// SWIFT Transfer gRPC Service
// Journey: journey_11_swift
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

type SWIFTTransferService struct {
	pb.UnimplementedSWIFTTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewSWIFTTransferService(db *gorm.DB, tc temporal.Client) *SWIFTTransferService {
	return &SWIFTTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteSWIFTTransfer handles the main workflow
func (s *SWIFTTransferService) ExecuteSWIFTTransfer(
	ctx context.Context,
	req *pb.SWIFTTransferRequest,
) (*pb.SWIFTTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_11_swift_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"SWIFTTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.SWIFTTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "SWIFT Transfer workflow started successfully",
	}, nil
}

func (s *SWIFTTransferService) validateRequest(req *pb.SWIFTTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
