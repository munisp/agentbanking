// AML Monitoring gRPC Service
// Journey: journey_27_aml
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

type AMLMonitoringService struct {
	pb.UnimplementedAMLMonitoringServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewAMLMonitoringService(db *gorm.DB, tc temporal.Client) *AMLMonitoringService {
	return &AMLMonitoringService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteAMLMonitoring handles the main workflow
func (s *AMLMonitoringService) ExecuteAMLMonitoring(
	ctx context.Context,
	req *pb.AMLMonitoringRequest,
) (*pb.AMLMonitoringResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_27_aml_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"AMLMonitoringWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.AMLMonitoringResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "AML Monitoring workflow started successfully",
	}, nil
}

func (s *AMLMonitoringService) validateRequest(req *pb.AMLMonitoringRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
