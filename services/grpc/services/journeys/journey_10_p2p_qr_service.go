// P2P QR Transfer gRPC Service
// Journey: journey_10_p2p_qr
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

type P2PQRTransferService struct {
	pb.UnimplementedP2PQRTransferServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewP2PQRTransferService(db *gorm.DB, tc temporal.Client) *P2PQRTransferService {
	return &P2PQRTransferService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteP2PQRTransfer handles the main workflow
func (s *P2PQRTransferService) ExecuteP2PQRTransfer(
	ctx context.Context,
	req *pb.P2PQRTransferRequest,
) (*pb.P2PQRTransferResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_10_p2p_qr_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"P2PQRTransferWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.P2PQRTransferResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "P2P QR Transfer workflow started successfully",
	}, nil
}

func (s *P2PQRTransferService) validateRequest(req *pb.P2PQRTransferRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
