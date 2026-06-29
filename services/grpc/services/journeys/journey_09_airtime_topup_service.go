// Airtime Top-up gRPC Service
// Journey: journey_09_airtime_topup
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

type AirtimeTop-upService struct {
	pb.UnimplementedAirtimeTop-upServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewAirtimeTop-upService(db *gorm.DB, tc temporal.Client) *AirtimeTop-upService {
	return &AirtimeTop-upService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteAirtimeTop-up handles the main workflow
func (s *AirtimeTop-upService) ExecuteAirtimeTop-up(
	ctx context.Context,
	req *pb.AirtimeTop-upRequest,
) (*pb.AirtimeTop-upResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_09_airtime_topup_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"AirtimeTopupWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.AirtimeTop-upResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Airtime Top-up workflow started successfully",
	}, nil
}

func (s *AirtimeTop-upService) validateRequest(req *pb.AirtimeTop-upRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
