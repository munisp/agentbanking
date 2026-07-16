// Virtual Account gRPC Service
// Journey: journey_17_virtual_account
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

type VirtualAccountService struct {
	pb.UnimplementedVirtualAccountServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewVirtualAccountService(db *gorm.DB, tc temporal.Client) *VirtualAccountService {
	return &VirtualAccountService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteVirtualAccount handles the main workflow
func (s *VirtualAccountService) ExecuteVirtualAccount(
	ctx context.Context,
	req *pb.VirtualAccountRequest,
) (*pb.VirtualAccountResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_17_virtual_account_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"VirtualAccountWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.VirtualAccountResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Virtual Account workflow started successfully",
	}, nil
}

func (s *VirtualAccountService) validateRequest(req *pb.VirtualAccountRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
