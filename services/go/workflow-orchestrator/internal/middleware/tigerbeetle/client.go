package tigerbeetle

import (
	"context"
	"fmt"
	"time"

	tb "github.com/tigerbeetle/tigerbeetle-go"
	"github.com/tigerbeetle/tigerbeetle-go/pkg/types"
	"workflow-orchestrator/pkg/logger"
)

// Client represents a TigerBeetle client for financial ledger operations
type Client struct {
	client tb.Client
	config *Config
}

// Config holds TigerBeetle configuration
type Config struct {
	ClusterID types.Uint128
	Addresses []string
}

// NewClient creates a new TigerBeetle client
func NewClient(config *Config) (*Client, error) {
	// Create TigerBeetle client
	client, err := tb.NewClient(config.ClusterID, config.Addresses)
	if err != nil {
		return nil, fmt.Errorf("failed to create TigerBeetle client: %w", err)
	}

	return &Client{
		client: client,
		config: config,
	}, nil
}

// CreateAccount creates a new account in TigerBeetle
func (c *Client) CreateAccount(ctx context.Context, accountID types.Uint128, ledger uint32, code uint16) error {
	logger.Logger.Info("Creating TigerBeetle account",
		logger.String("account_id", fmt.Sprintf("%x", accountID)),
		logger.Int("ledger", int(ledger)),
	)

	accounts := []types.Account{
		{
			ID:     accountID,
			Ledger: ledger,
			Code:   code,
			Flags:  0,
		},
	}

	results, err := c.client.CreateAccounts(accounts)
	if err != nil {
		logger.Logger.Error("Failed to create account", logger.Error(err))
		return fmt.Errorf("failed to create account: %w", err)
	}

	if len(results) > 0 {
		return fmt.Errorf("account creation failed: %v", results[0].Result)
	}

	logger.Logger.Info("Account created successfully")
	return nil
}

// CreateTransfer creates a transfer between two accounts
func (c *Client) CreateTransfer(ctx context.Context, transferID, debitAccountID, creditAccountID types.Uint128, amount uint64, ledger uint32, code uint16) error {
	logger.Logger.Info("Creating TigerBeetle transfer",
		logger.String("transfer_id", fmt.Sprintf("%x", transferID)),
		logger.String("debit_account", fmt.Sprintf("%x", debitAccountID)),
		logger.String("credit_account", fmt.Sprintf("%x", creditAccountID)),
		logger.Int("amount", int(amount)),
	)

	transfers := []types.Transfer{
		{
			ID:              transferID,
			DebitAccountID:  debitAccountID,
			CreditAccountID: creditAccountID,
			Amount:          types.ToUint128(amount),
			Ledger:          ledger,
			Code:            code,
			Flags:           0,
		},
	}

	results, err := c.client.CreateTransfers(transfers)
	if err != nil {
		logger.Logger.Error("Failed to create transfer", logger.Error(err))
		return fmt.Errorf("failed to create transfer: %w", err)
	}

	if len(results) > 0 {
		return fmt.Errorf("transfer creation failed: %v", results[0].Result)
	}

	logger.Logger.Info("Transfer created successfully")
	return nil
}

// CreatePendingTransfer creates a pending transfer (two-phase commit)
func (c *Client) CreatePendingTransfer(ctx context.Context, transferID, debitAccountID, creditAccountID types.Uint128, amount uint64, ledger uint32, code uint16, timeout uint32) error {
	logger.Logger.Info("Creating pending TigerBeetle transfer",
		logger.String("transfer_id", fmt.Sprintf("%x", transferID)),
		logger.Int("timeout", int(timeout)),
	)

	transfers := []types.Transfer{
		{
			ID:              transferID,
			DebitAccountID:  debitAccountID,
			CreditAccountID: creditAccountID,
			Amount:          types.ToUint128(amount),
			Ledger:          ledger,
			Code:            code,
			Flags:           types.TransferFlags{Pending: true}.ToUint16(),
			Timeout:         timeout,
		},
	}

	results, err := c.client.CreateTransfers(transfers)
	if err != nil {
		logger.Logger.Error("Failed to create pending transfer", logger.Error(err))
		return fmt.Errorf("failed to create pending transfer: %w", err)
	}

	if len(results) > 0 {
		return fmt.Errorf("pending transfer creation failed: %v", results[0].Result)
	}

	logger.Logger.Info("Pending transfer created successfully")
	return nil
}

// PostPendingTransfer posts (commits) a pending transfer
func (c *Client) PostPendingTransfer(ctx context.Context, transferID, pendingTransferID types.Uint128, ledger uint32, code uint16) error {
	logger.Logger.Info("Posting pending TigerBeetle transfer",
		logger.String("transfer_id", fmt.Sprintf("%x", transferID)),
		logger.String("pending_id", fmt.Sprintf("%x", pendingTransferID)),
	)

	transfers := []types.Transfer{
		{
			ID:        transferID,
			PendingID: pendingTransferID,
			Ledger:    ledger,
			Code:      code,
			Flags:     types.TransferFlags{PostPendingTransfer: true}.ToUint16(),
			Timestamp: uint64(time.Now().UnixNano()),
		},
	}

	results, err := c.client.CreateTransfers(transfers)
	if err != nil {
		logger.Logger.Error("Failed to post pending transfer", logger.Error(err))
		return fmt.Errorf("failed to post pending transfer: %w", err)
	}

	if len(results) > 0 {
		return fmt.Errorf("post pending transfer failed: %v", results[0].Result)
	}

	logger.Logger.Info("Pending transfer posted successfully")
	return nil
}

// VoidPendingTransfer voids (cancels) a pending transfer
func (c *Client) VoidPendingTransfer(ctx context.Context, transferID, pendingTransferID types.Uint128, ledger uint32, code uint16) error {
	logger.Logger.Info("Voiding pending TigerBeetle transfer",
		logger.String("transfer_id", fmt.Sprintf("%x", transferID)),
		logger.String("pending_id", fmt.Sprintf("%x", pendingTransferID)),
	)

	transfers := []types.Transfer{
		{
			ID:        transferID,
			PendingID: pendingTransferID,
			Ledger:    ledger,
			Code:      code,
			Flags:     types.TransferFlags{VoidPendingTransfer: true}.ToUint16(),
			Timestamp: uint64(time.Now().UnixNano()),
		},
	}

	results, err := c.client.CreateTransfers(transfers)
	if err != nil {
		logger.Logger.Error("Failed to void pending transfer", logger.Error(err))
		return fmt.Errorf("failed to void pending transfer: %w", err)
	}

	if len(results) > 0 {
		return fmt.Errorf("void pending transfer failed: %v", results[0].Result)
	}

	logger.Logger.Info("Pending transfer voided successfully")
	return nil
}

// LookupAccounts retrieves account information
func (c *Client) LookupAccounts(ctx context.Context, accountIDs []types.Uint128) ([]types.Account, error) {
	logger.Logger.Info("Looking up TigerBeetle accounts",
		logger.Int("count", len(accountIDs)),
	)

	accounts, err := c.client.LookupAccounts(accountIDs)
	if err != nil {
		logger.Logger.Error("Failed to lookup accounts", logger.Error(err))
		return nil, fmt.Errorf("failed to lookup accounts: %w", err)
	}

	return accounts, nil
}

// LookupTransfers retrieves transfer information
func (c *Client) LookupTransfers(ctx context.Context, transferIDs []types.Uint128) ([]types.Transfer, error) {
	logger.Logger.Info("Looking up TigerBeetle transfers",
		logger.Int("count", len(transferIDs)),
	)

	transfers, err := c.client.LookupTransfers(transferIDs)
	if err != nil {
		logger.Logger.Error("Failed to lookup transfers", logger.Error(err))
		return nil, fmt.Errorf("failed to lookup transfers: %w", err)
	}

	return transfers, nil
}

// ProcessPayment processes a payment workflow with TigerBeetle
func (c *Client) ProcessPayment(ctx context.Context, paymentID string, fromAccountID, toAccountID types.Uint128, amount uint64) error {
	logger.Logger.Info("Processing payment",
		logger.String("payment_id", paymentID),
		logger.Int("amount", int(amount)),
	)

	// Generate transfer ID from payment ID
	transferID := stringToUint128(paymentID)

	// Create transfer
	err := c.CreateTransfer(ctx, transferID, fromAccountID, toAccountID, amount, 1, 1)
	if err != nil {
		return fmt.Errorf("payment failed: %w", err)
	}

	logger.Logger.Info("Payment processed successfully")
	return nil
}

// Close closes the TigerBeetle client
func (c *Client) Close() error {
	// TigerBeetle Go client doesn't have explicit close method
	return nil
}

// Helper function to convert string to types.Uint128
func stringToUint128(s string) types.Uint128 {
	var result types.Uint128
	copy(result[:], []byte(s))
	return result
}

