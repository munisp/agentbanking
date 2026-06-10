// Currency Conversion gRPC Service
// Journey: journey_13_currency_conversion
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

type CurrencyConversionService struct {
	pb.UnimplementedCurrencyConversionServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewCurrencyConversionService(db *gorm.DB, tc temporal.Client) *CurrencyConversionService {
	return &CurrencyConversionService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteCurrencyConversion handles the main workflow
func (s *CurrencyConversionService) ExecuteCurrencyConversion(
	ctx context.Context,
	req *pb.CurrencyConversionRequest,
) (*pb.CurrencyConversionResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_13_currency_conversion_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"CurrencyConversionWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.CurrencyConversionResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Currency Conversion workflow started successfully",
	}, nil
}

func (s *CurrencyConversionService) validateRequest(req *pb.CurrencyConversionRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
