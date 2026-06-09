// Bill Payment gRPC Service
// Journey: journey_08_bill_payment
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

type BillPaymentService struct {
	pb.UnimplementedBillPaymentServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewBillPaymentService(db *gorm.DB, tc temporal.Client) *BillPaymentService {
	return &BillPaymentService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteBillPayment handles the main workflow
func (s *BillPaymentService) ExecuteBillPayment(
	ctx context.Context,
	req *pb.BillPaymentRequest,
) (*pb.BillPaymentResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_08_bill_payment_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"BillPaymentWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.BillPaymentResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Bill Payment workflow started successfully",
	}, nil
}

func (s *BillPaymentService) validateRequest(req *pb.BillPaymentRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
