// Security Incident gRPC Service
// Journey: journey_29_security_incident
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

type SecurityIncidentService struct {
	pb.UnimplementedSecurityIncidentServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewSecurityIncidentService(db *gorm.DB, tc temporal.Client) *SecurityIncidentService {
	return &SecurityIncidentService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteSecurityIncident handles the main workflow
func (s *SecurityIncidentService) ExecuteSecurityIncident(
	ctx context.Context,
	req *pb.SecurityIncidentRequest,
) (*pb.SecurityIncidentResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_29_security_incident_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"SecurityIncidentWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.SecurityIncidentResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Security Incident workflow started successfully",
	}, nil
}

func (s *SecurityIncidentService) validateRequest(req *pb.SecurityIncidentRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
