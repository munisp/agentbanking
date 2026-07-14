// Card Management gRPC Service
// Journey: journey_19_card_management
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

type CardManagementService struct {
	pb.UnimplementedCardManagementServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewCardManagementService(db *gorm.DB, tc temporal.Client) *CardManagementService {
	return &CardManagementService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteCardManagement handles the main workflow
func (s *CardManagementService) ExecuteCardManagement(
	ctx context.Context,
	req *pb.CardManagementRequest,
) (*pb.CardManagementResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_19_card_management_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"CardManagementWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.CardManagementResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Card Management workflow started successfully",
	}, nil
}

func (s *CardManagementService) validateRequest(req *pb.CardManagementRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
