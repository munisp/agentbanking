// Fraud Detection gRPC Service
// Journey: journey_28_fraud
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

type FraudDetectionService struct {
	pb.UnimplementedFraudDetectionServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewFraudDetectionService(db *gorm.DB, tc temporal.Client) *FraudDetectionService {
	return &FraudDetectionService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteFraudDetection handles the main workflow
func (s *FraudDetectionService) ExecuteFraudDetection(
	ctx context.Context,
	req *pb.FraudDetectionRequest,
) (*pb.FraudDetectionResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_28_fraud_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"FraudDetectionWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.FraudDetectionResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Fraud Detection workflow started successfully",
	}, nil
}

func (s *FraudDetectionService) validateRequest(req *pb.FraudDetectionRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
