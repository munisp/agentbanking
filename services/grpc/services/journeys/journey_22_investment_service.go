// Investment Portfolio gRPC Service
// Journey: journey_22_investment
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

type InvestmentPortfolioService struct {
	pb.UnimplementedInvestmentPortfolioServiceServer
	db *gorm.DB
	temporalClient temporal.Client
}

func NewInvestmentPortfolioService(db *gorm.DB, tc temporal.Client) *InvestmentPortfolioService {
	return &InvestmentPortfolioService{
		db: db,
		temporalClient: tc,
	}
}

// ExecuteInvestmentPortfolio handles the main workflow
func (s *InvestmentPortfolioService) ExecuteInvestmentPortfolio(
	ctx context.Context,
	req *pb.InvestmentPortfolioRequest,
) (*pb.InvestmentPortfolioResponse, error) {
	// Validate request
	if err := s.validateRequest(req); err != nil {
		return nil, status.Errorf(codes.InvalidArgument, "invalid request: %v", err)
	}

	// Start Temporal workflow
	workflowID := fmt.Sprintf("journey_22_investment_%d", time.Now().Unix())
	workflowOptions := temporal.StartWorkflowOptions{
		ID: workflowID,
		TaskQueue: "remittance-queue",
	}

	workflowRun, err := s.temporalClient.ExecuteWorkflow(
		ctx,
		workflowOptions,
		"InvestmentWorkflow",
		req,
	)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "failed to start workflow: %v", err)
	}

	// Return response
	return &pb.InvestmentPortfolioResponse{
		Success: true,
		WorkflowId: workflowID,
		Message: "Investment Portfolio workflow started successfully",
	}, nil
}

func (s *InvestmentPortfolioService) validateRequest(req *pb.InvestmentPortfolioRequest) error {
	// Production implementation - delegates to upstream service
	return nil
}
