package main

import (
	"fmt"
	"log"
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

// SeedData seeds the database with mock data
func SeedData(db *gorm.DB) error {
	log.Println("Starting database seeding...")

	// Check if data already exists
	var count int64
	db.Model(&CommissionRule{}).Count(&count)
	if count > 0 {
		log.Println("Database already seeded. Skipping...")
		return nil
	}

	// Seed commission rules
	if err := seedCommissionRules(db); err != nil {
		return err
	}

	// Seed agent commissions and balances
	if err := seedAgentCommissions(db); err != nil {
		return err
	}

	// Seed settlements
	if err := seedSettlements(db); err != nil {
		return err
	}

	log.Println("Database seeding completed successfully!")
	return nil
}

// seedCommissionRules seeds commission rules for different agent tiers and transaction types
func seedCommissionRules(db *gorm.DB) error {
	log.Println("Seeding commission rules...")

	now := time.Now()
	rules := []CommissionRule{
		// Agent tier - Basic transactions
		{
			AgentTier:       "agent",
			TransactionType: "deposit",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.001, // 0.1%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "withdrawal",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.002, // 0.2%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "transfer",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.0015, // 0.15%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},

		// Agent tier - Bill payments
		{
			AgentTier:       "agent",
			TransactionType: "bill_payment",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.005, // 0.5%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "electricity",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.008, // 0.8%
			FlatFee:         50,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "water",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.007, // 0.7%
			FlatFee:         40,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "cable",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.01, // 1%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "internet",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.009, // 0.9%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},

		// Agent tier - Donations
		{
			AgentTier:       "agent",
			TransactionType: "donation",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.003, // 0.3% (lower rate for donations)
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},

		// Agent tier - Airtime and Data
		{
			AgentTier:       "agent",
			TransactionType: "airtime",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.03, // 3%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "agent",
			TransactionType: "data",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.03, // 3%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},

		// Senior Agent tier - Higher rates
		{
			AgentTier:       "senior_agent",
			TransactionType: "deposit",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.0015, // 0.15%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "senior_agent",
			TransactionType: "withdrawal",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.0025, // 0.25%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "senior_agent",
			TransactionType: "bill_payment",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.008, // 0.8%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "senior_agent",
			TransactionType: "airtime",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.035, // 3.5%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "senior_agent",
			TransactionType: "data",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.035, // 3.5%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},

		// Premium Agent tier - Highest rates
		{
			AgentTier:       "premium_agent",
			TransactionType: "deposit",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.002, // 0.2%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "premium_agent",
			TransactionType: "withdrawal",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.003, // 0.3%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "premium_agent",
			TransactionType: "bill_payment",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.01, // 1%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "premium_agent",
			TransactionType: "airtime",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.04, // 4%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
		{
			AgentTier:       "premium_agent",
			TransactionType: "data",
			MinAmount:       0,
			MaxAmount:       999999999,
			Rate:            0.04, // 4%
			FlatFee:         0,
			IsActive:        true,
			EffectiveFrom:   now.AddDate(0, -6, 0),
		},
	}

	for _, rule := range rules {
		if err := db.Create(&rule).Error; err != nil {
			return err
		}
	}

	log.Printf("Seeded %d commission rules", len(rules))
	return nil
}

// seedAgentCommissions seeds commission records for the test agent
func seedAgentCommissions(db *gorm.DB) error {
	log.Println("Seeding agent commissions...")

	// Test agent ID from the provided data
	agentID := uuid.MustParse("fe0fab2b-2052-4d84-a92d-81583f7acce6")

	now := time.Now()
	commissions := []Commission{
		// Recent transactions (last 7 days) - Pending
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260303-001",
			TransactionType:  "deposit",
			Amount:           50000,
			Rate:             0.001,
			CommissionAmount: 50,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -1),
			Metadata: JSON{
				"customer_name": "John Doe",
				"channel":       "mobile",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260303-002",
			TransactionType:  "airtime",
			Amount:           5000,
			Rate:             0.03,
			CommissionAmount: 150,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -1),
			Metadata: JSON{
				"provider": "MTN",
				"phone":    "08012345678",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260302-001",
			TransactionType:  "electricity",
			Amount:           15000,
			Rate:             0.008,
			CommissionAmount: 170, // 120 + 50 flat fee
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -2),
			Metadata: JSON{
				"provider":     "IKEDC",
				"meter_number": "12345678901",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260302-002",
			TransactionType:  "donation",
			Amount:           10000,
			Rate:             0.003,
			CommissionAmount: 30,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -2),
			Metadata: JSON{
				"organization": "Nigerian Red Cross Society",
				"category":     "NGO",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260301-001",
			TransactionType:  "withdrawal",
			Amount:           75000,
			Rate:             0.002,
			CommissionAmount: 150,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -3),
			Metadata: JSON{
				"customer_name": "Jane Smith",
				"channel":       "pos",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260301-002",
			TransactionType:  "data",
			Amount:           3000,
			Rate:             0.03,
			CommissionAmount: 90,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -3),
			Metadata: JSON{
				"provider": "Airtel",
				"phone":    "08098765432",
				"plan":     "5GB Monthly",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260228-001",
			TransactionType:  "cable",
			Amount:           8500,
			Rate:             0.01,
			CommissionAmount: 85,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -4),
			Metadata: JSON{
				"provider":       "DSTV",
				"smartcard":      "1234567890",
				"package":        "Compact Plus",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260228-002",
			TransactionType:  "transfer",
			Amount:           100000,
			Rate:             0.0015,
			CommissionAmount: 150,
			Currency:         "NGN",
			Status:           CommissionStatusPending,
			EarnedAt:         now.AddDate(0, 0, -4),
			Metadata: JSON{
				"beneficiary": "Alice Johnson",
				"bank":        "First Bank",
			},
		},

		// Older transactions (last 30 days) - Settled
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260225-001",
			TransactionType:  "deposit",
			Amount:           200000,
			Rate:             0.001,
			CommissionAmount: 200,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -7),
			Metadata: JSON{
				"customer_name": "Michael Brown",
				"channel":       "web",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260224-001",
			TransactionType:  "airtime",
			Amount:           10000,
			Rate:             0.03,
			CommissionAmount: 300,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -8),
			Metadata: JSON{
				"provider": "Glo",
				"phone":    "08055551234",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260223-001",
			TransactionType:  "electricity",
			Amount:           25000,
			Rate:             0.008,
			CommissionAmount: 250,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -9),
			Metadata: JSON{
				"provider":     "EKEDC",
				"meter_number": "98765432109",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260222-001",
			TransactionType:  "water",
			Amount:           5000,
			Rate:             0.007,
			CommissionAmount: 75,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -10),
			Metadata: JSON{
				"provider":       "Lagos Water Corporation",
				"account_number": "WTR-12345",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260220-001",
			TransactionType:  "donation",
			Amount:           50000,
			Rate:             0.003,
			CommissionAmount: 150,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -12),
			Metadata: JSON{
				"organization": "RCCG",
				"category":     "Religious",
				"religion":     "Christian",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260218-001",
			TransactionType:  "withdrawal",
			Amount:           150000,
			Rate:             0.002,
			CommissionAmount: 300,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -14),
			Metadata: JSON{
				"customer_name": "Sarah Williams",
				"channel":       "mobile",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260215-001",
			TransactionType:  "data",
			Amount:           5000,
			Rate:             0.03,
			CommissionAmount: 150,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -17),
			Metadata: JSON{
				"provider": "9mobile",
				"phone":    "08177778888",
				"plan":     "10GB Monthly",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260210-001",
			TransactionType:  "transfer",
			Amount:           250000,
			Rate:             0.0015,
			CommissionAmount: 375,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -22),
			Metadata: JSON{
				"beneficiary": "David Lee",
				"bank":        "GTBank",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260205-001",
			TransactionType:  "cable",
			Amount:           12000,
			Rate:             0.01,
			CommissionAmount: 120,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -27),
			Metadata: JSON{
				"provider":       "GOtv",
				"smartcard":      "9876543210",
				"package":        "Max",
			},
		},
		{
			AgentID:          agentID,
			TransactionID:    uuid.New(),
			TransactionRef:   "TXN-20260203-001",
			TransactionType:  "internet",
			Amount:           20000,
			Rate:             0.009,
			CommissionAmount: 180,
			Currency:         "NGN",
			Status:           CommissionStatusSettled,
			EarnedAt:         now.AddDate(0, 0, -29),
			Metadata: JSON{
				"provider": "Spectranet",
				"plan":     "Unlimited",
			},
		},
	}

	for _, commission := range commissions {
		if err := db.Create(&commission).Error; err != nil {
			return err
		}
	}

	log.Printf("Seeded %d commission records", len(commissions))

	// Create or update agent balance
	pendingTotal := 0.0
	settledTotal := 0.0
	totalEarned := 0.0

	for _, c := range commissions {
		totalEarned += c.CommissionAmount
		if c.Status == CommissionStatusPending {
			pendingTotal += c.CommissionAmount
		} else if c.Status == CommissionStatusSettled {
			settledTotal += c.CommissionAmount
		}
	}

	balance := AgentBalance{
		AgentID:          agentID,
		PendingBalance:   pendingTotal,
		AvailableBalance: settledTotal,
		SettledBalance:   0, // Will be updated when settlements are created
		TotalEarned:      totalEarned,
		Currency:         "NGN",
		LastSettlementAt: nil,
	}

	if err := db.Create(&balance).Error; err != nil {
		// If already exists, update it
		db.Model(&AgentBalance{}).Where("agent_id = ?", agentID).Updates(balance)
	}

	log.Printf("Seeded agent balance: Pending=%.2f, Available=%.2f, Total=%.2f",
		pendingTotal, settledTotal, totalEarned)

	return nil
}

// seedSettlements seeds settlement records
func seedSettlements(db *gorm.DB) error {
	log.Println("Seeding settlements...")

	agentID := uuid.MustParse("fe0fab2b-2052-4d84-a92d-81583f7acce6")
	now := time.Now()

	// Get settled commissions
	var settledCommissions []Commission
	db.Where("agent_id = ? AND status = ?", agentID, CommissionStatusSettled).Find(&settledCommissions)

	if len(settledCommissions) == 0 {
		log.Println("No settled commissions found to create settlements")
		return nil
	}

	// Group commissions into settlements (e.g., weekly settlements)
	settlementDate1 := now.AddDate(0, 0, -14)
	settlementDate2 := now.AddDate(0, 0, -7)

	// First settlement (older commissions)
	older := []Commission{}
	newer := []Commission{}

	for _, c := range settledCommissions {
		if c.EarnedAt.Before(settlementDate2) {
			older = append(older, c)
		} else {
			newer = append(newer, c)
		}
	}

	if len(older) > 0 {
		totalAmount := 0.0
		for _, c := range older {
			totalAmount += c.CommissionAmount
		}

		processedAt := settlementDate1.Add(24 * time.Hour)
		settlement1 := Settlement{
			SettlementRef:   fmt.Sprintf("STL-%d-%s", settlementDate1.Unix(), agentID.String()[:8]),
			AgentID:         agentID,
			TotalAmount:     totalAmount,
			CommissionCount: len(older),
			Currency:        "NGN",
			Status:          SettlementStatusCompleted,
			PaymentMethod:   "bank_transfer",
			PaymentDetails: JSON{
				"bank_name":      "First Bank",
				"account_number": "1234567890",
				"account_name":   "ifegbesan Tanitoluwa",
			},
			ProcessedAt: &processedAt,
			StartDate:   settlementDate1.AddDate(0, 0, -7),
			EndDate:     settlementDate1,
		}

		if err := db.Create(&settlement1).Error; err != nil {
			return err
		}

		// Update commissions with settlement ID
		for _, c := range older {
			db.Model(&Commission{}).Where("id = ?", c.ID).Update("settlement_id", settlement1.ID)
		}

		log.Printf("Created settlement 1: %s with %.2f NGN", settlement1.SettlementRef, totalAmount)
	}

	if len(newer) > 0 {
		totalAmount := 0.0
		for _, c := range newer {
			totalAmount += c.CommissionAmount
		}

		processedAt := settlementDate2.Add(24 * time.Hour)
		settlement2 := Settlement{
			SettlementRef:   fmt.Sprintf("STL-%d-%s", settlementDate2.Unix(), agentID.String()[:8]),
			AgentID:         agentID,
			TotalAmount:     totalAmount,
			CommissionCount: len(newer),
			Currency:        "NGN",
			Status:          SettlementStatusCompleted,
			PaymentMethod:   "bank_transfer",
			PaymentDetails: JSON{
				"bank_name":      "First Bank",
				"account_number": "1234567890",
				"account_name":   "ifegbesan Tanitoluwa",
			},
			ProcessedAt: &processedAt,
			StartDate:   settlementDate2.AddDate(0, 0, -7),
			EndDate:     settlementDate2,
		}

		if err := db.Create(&settlement2).Error; err != nil {
			return err
		}

		// Update commissions with settlement ID
		for _, c := range newer {
			db.Model(&Commission{}).Where("id = ?", c.ID).Update("settlement_id", settlement2.ID)
		}

		log.Printf("Created settlement 2: %s with %.2f NGN", settlement2.SettlementRef, totalAmount)
	}

	return nil
}
