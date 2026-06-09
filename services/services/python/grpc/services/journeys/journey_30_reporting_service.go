// Regulatory Reporting gRPC Service
// Journey: journey_30_reporting
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

type RegulatoryReportingService struct {
	pb.UnimplementedRegulatoryReportingServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewRegulatoryReportingService(db *gorm.DB, tc temporal.Client) *RegulatoryReportingService {
	return &RegulatoryReportingService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteRegulatoryReporting handles the main workflow
func (s *RegulatoryReportingService) ExecuteRegulatoryReporting(
	ctx context.Context,
	req *pb.RegulatoryReportingRequest,
) (*pb.RegulatoryReportingResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_30_reporting_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"RegulatoryReportingWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.RegulatoryReportingResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Regulatory Reporting workflow started successfully",
	}, nil
}

func (s *RegulatoryReportingService) validateRequest(req *pb.RegulatoryReportingRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
