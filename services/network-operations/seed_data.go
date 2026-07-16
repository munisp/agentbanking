//go:build ignore

package main

import (
	"fmt"
	"log"
	"math/rand"
	"os"
	"strconv"
	"time"

	"github.com/google/uuid"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// Copy of models from main.go for seed script
type TransactionRecord struct {
	ID        string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Type      string    `json:"type" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"`
	Channel   string    `json:"channel" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"`
	Medium    string    `json:"medium" gorm:"type:varchar(50);not null;index:idx_type_channel_medium"`
	Status    string    `json:"status" gorm:"type:varchar(20);not null"`
	Amount    float64   `json:"amount" gorm:"type:decimal(15,2)"`
	AgentID   *string   `json:"agent_id" gorm:"type:uuid;index"`
	CreatedAt time.Time `json:"created_at" gorm:"autoCreateTime;index"`
}

type ChannelStatistics struct {
	ID                string    `json:"id" gorm:"type:uuid;primary_key;default:gen_random_uuid()"`
	Type              string    `json:"type" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	Channel           string    `json:"channel" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	Medium            string    `json:"medium" gorm:"type:varchar(50);not null;uniqueIndex:idx_stats_unique"`
	TotalTransactions int       `json:"total_transactions" gorm:"not null;default:0"`
	SuccessCount      int       `json:"success_count" gorm:"not null;default:0"`
	FailureCount      int       `json:"failure_count" gorm:"not null;default:0"`
	SuccessRate       float64   `json:"success_rate" gorm:"type:decimal(5,2);not null;default:0.00"`
	LastUpdated       time.Time `json:"last_updated" gorm:"autoUpdateTime"`
}

type Config struct {
	DBHost     string
	DBPort     string
	DBName     string
	DBUser     string
	DBPassword string
}

func loadConfig() *Config {
	return &Config{
		DBHost:     getEnv("DB_HOST", "localhost"),
		DBPort:     getEnv("DB_PORT", "5432"),
		DBName:     getEnv("DB_NAME", "link_core_banking"),
		DBUser:     getEnv("DB_USER", "postgres"),
		DBPassword: getEnv("DB_PASSWORD", "password"),
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func updateChannelStatistics(db *gorm.DB, txType, channel, medium string) error {
	var totalCount, successCount, failureCount int64

	db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ?", txType, channel, medium).
		Count(&totalCount)

	db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ? AND status = ?", txType, channel, medium, "success").
		Count(&successCount)

	db.Model(&TransactionRecord{}).
		Where("type = ? AND channel = ? AND medium = ? AND status = ?", txType, channel, medium, "failed").
		Count(&failureCount)

	successRate := 0.0
	if totalCount > 0 {
		successRate = (float64(successCount) / float64(totalCount)) * 100.0
	}

	stats := ChannelStatistics{
		Type:              txType,
		Channel:           channel,
		Medium:            medium,
		TotalTransactions: int(totalCount),
		SuccessCount:      int(successCount),
		FailureCount:      int(failureCount),
		SuccessRate:       successRate,
	}

	result := db.Where("type = ? AND channel = ? AND medium = ?", txType, channel, medium).
		Assign(stats).
		FirstOrCreate(&stats)

	return result.Error
}

// channelConfig defines a channel's expected behavior
type channelConfig struct {
	Type        string  // Transaction type
	Channel     string  // Channel name
	Medium      string  // Medium/provider name
	SuccessRate float64 // Expected success rate (0.0-1.0)
	SampleSize  int     // Number of sample transactions to generate
}

// Seed data generator for Nigerian banking channels
func main() {
	// Load configuration
	config := loadConfig()

	// Initialize database
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=require TimeZone=UTC",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	// Auto-migrate tables
	if err := db.AutoMigrate(&TransactionRecord{}, &ChannelStatistics{}); err != nil {
		log.Fatalf("Failed to migrate database: %v", err)
	}

	log.Println("🌱 Starting seed data generation...")

	// Define Nigerian banking and telecom channels
	channels := []channelConfig{
		// Bank POS Terminals - High Success Rates
		{Type: "transfer", Channel: "pos", Medium: "wema", SuccessRate: 0.92, SampleSize: 200},
		{Type: "transfer", Channel: "pos", Medium: "gtbank", SuccessRate: 0.95, SampleSize: 250},
		{Type: "transfer", Channel: "pos", Medium: "access", SuccessRate: 0.88, SampleSize: 180},
		{Type: "transfer", Channel: "pos", Medium: "first_bank", SuccessRate: 0.85, SampleSize: 220},
		{Type: "transfer", Channel: "pos", Medium: "zenith", SuccessRate: 0.91, SampleSize: 190},
		{Type: "transfer", Channel: "pos", Medium: "uba", SuccessRate: 0.87, SampleSize: 170},
		{Type: "transfer", Channel: "pos", Medium: "union_bank", SuccessRate: 0.82, SampleSize: 150},

		{Type: "withdrawal", Channel: "pos", Medium: "wema", SuccessRate: 0.89, SampleSize: 180},
		{Type: "withdrawal", Channel: "pos", Medium: "gtbank", SuccessRate: 0.93, SampleSize: 200},
		{Type: "withdrawal", Channel: "pos", Medium: "access", SuccessRate: 0.86, SampleSize: 160},

		// USSD Banking - Variable Success Rates
		{Type: "transfer", Channel: "ussd", Medium: "wema", SuccessRate: 0.78, SampleSize: 300},
		{Type: "transfer", Channel: "ussd", Medium: "gtbank", SuccessRate: 0.82, SampleSize: 350},
		{Type: "transfer", Channel: "ussd", Medium: "access", SuccessRate: 0.75, SampleSize: 280},
		{Type: "transfer", Channel: "ussd", Medium: "first_bank", SuccessRate: 0.71, SampleSize: 250},
		{Type: "transfer", Channel: "ussd", Medium: "zenith", SuccessRate: 0.80, SampleSize: 290},

		{Type: "balance_inquiry", Channel: "ussd", Medium: "wema", SuccessRate: 0.95, SampleSize: 150},
		{Type: "balance_inquiry", Channel: "ussd", Medium: "gtbank", SuccessRate: 0.97, SampleSize: 180},

		// Web Portal Banking - Good Success Rates
		{Type: "transfer", Channel: "web", Medium: "wema", SuccessRate: 0.94, SampleSize: 220},
		{Type: "transfer", Channel: "web", Medium: "gtbank", SuccessRate: 0.96, SampleSize: 280},
		{Type: "transfer", Channel: "web", Medium: "access", SuccessRate: 0.91, SampleSize: 200},
		{Type: "transfer", Channel: "web", Medium: "zenith", SuccessRate: 0.93, SampleSize: 230},

		{Type: "bill_payment", Channel: "web", Medium: "wema", SuccessRate: 0.89, SampleSize: 150},
		{Type: "bill_payment", Channel: "web", Medium: "gtbank", SuccessRate: 0.92, SampleSize: 170},

		// Mobile App Banking - Excellent Success Rates
		{Type: "transfer", Channel: "app", Medium: "wema", SuccessRate: 0.96, SampleSize: 300},
		{Type: "transfer", Channel: "app", Medium: "gtbank", SuccessRate: 0.98, SampleSize: 350},
		{Type: "transfer", Channel: "app", Medium: "access", SuccessRate: 0.94, SampleSize: 280},
		{Type: "transfer", Channel: "app", Medium: "first_bank", SuccessRate: 0.92, SampleSize: 260},
		{Type: "transfer", Channel: "app", Medium: "zenith", SuccessRate: 0.95, SampleSize: 290},

		// Telecom POS Terminals - Airtime Purchase
		{Type: "airtime", Channel: "pos", Medium: "mtn", SuccessRate: 0.98, SampleSize: 400},
		{Type: "airtime", Channel: "pos", Medium: "airtel", SuccessRate: 0.96, SampleSize: 350},
		{Type: "airtime", Channel: "pos", Medium: "glo", SuccessRate: 0.91, SampleSize: 280},
		{Type: "airtime", Channel: "pos", Medium: "9mobile", SuccessRate: 0.87, SampleSize: 200},

		// Telecom USSD - Airtime & Data
		{Type: "airtime", Channel: "ussd", Medium: "mtn", SuccessRate: 0.94, SampleSize: 450},
		{Type: "airtime", Channel: "ussd", Medium: "airtel", SuccessRate: 0.92, SampleSize: 380},
		{Type: "airtime", Channel: "ussd", Medium: "glo", SuccessRate: 0.85, SampleSize: 300},
		{Type: "airtime", Channel: "ussd", Medium: "9mobile", SuccessRate: 0.80, SampleSize: 220},

		{Type: "data", Channel: "ussd", Medium: "mtn", SuccessRate: 0.93, SampleSize: 380},
		{Type: "data", Channel: "ussd", Medium: "airtel", SuccessRate: 0.90, SampleSize: 320},
		{Type: "data", Channel: "ussd", Medium: "glo", SuccessRate: 0.82, SampleSize: 250},
		{Type: "data", Channel: "ussd", Medium: "9mobile", SuccessRate: 0.78, SampleSize: 180},

		// Telecom Web Portals - Data Purchase
		{Type: "data", Channel: "web", Medium: "mtn", SuccessRate: 0.99, SampleSize: 300},
		{Type: "data", Channel: "web", Medium: "airtel", SuccessRate: 0.97, SampleSize: 280},
		{Type: "data", Channel: "web", Medium: "glo", SuccessRate: 0.92, SampleSize: 220},
		{Type: "data", Channel: "web", Medium: "9mobile", SuccessRate: 0.88, SampleSize: 180},

		{Type: "airtime", Channel: "web", Medium: "mtn", SuccessRate: 0.99, SampleSize: 280},
		{Type: "airtime", Channel: "web", Medium: "airtel", SuccessRate: 0.98, SampleSize: 260},
		{Type: "airtime", Channel: "web", Medium: "glo", SuccessRate: 0.94, SampleSize: 210},

		// Telecom Mobile Apps - Excellent Success Rates
		{Type: "data", Channel: "app", Medium: "mtn", SuccessRate: 1.00, SampleSize: 350},
		{Type: "data", Channel: "app", Medium: "airtel", SuccessRate: 0.99, SampleSize: 320},
		{Type: "data", Channel: "app", Medium: "glo", SuccessRate: 0.95, SampleSize: 250},
		{Type: "data", Channel: "app", Medium: "9mobile", SuccessRate: 0.91, SampleSize: 200},

		{Type: "airtime", Channel: "app", Medium: "mtn", SuccessRate: 1.00, SampleSize: 330},
		{Type: "airtime", Channel: "app", Medium: "airtel", SuccessRate: 0.99, SampleSize: 300},
		{Type: "airtime", Channel: "app", Medium: "glo", SuccessRate: 0.96, SampleSize: 240},

		// Bill Payments
		{Type: "bill_payment", Channel: "pos", Medium: "dstv", SuccessRate: 0.90, SampleSize: 200},
		{Type: "bill_payment", Channel: "pos", Medium: "gotv", SuccessRate: 0.88, SampleSize: 180},
		{Type: "bill_payment", Channel: "pos", Medium: "ekedc", SuccessRate: 0.85, SampleSize: 160},
		{Type: "bill_payment", Channel: "pos", Medium: "ikedc", SuccessRate: 0.83, SampleSize: 150},

		{Type: "bill_payment", Channel: "app", Medium: "dstv", SuccessRate: 0.95, SampleSize: 250},
		{Type: "bill_payment", Channel: "app", Medium: "gotv", SuccessRate: 0.93, SampleSize: 220},
		{Type: "bill_payment", Channel: "app", Medium: "ekedc", SuccessRate: 0.91, SampleSize: 200},
		{Type: "bill_payment", Channel: "app", Medium: "bet9ja", SuccessRate: 0.97, SampleSize: 280},
	}

	totalRecords := 0
	rand.Seed(time.Now().UnixNano())

	// Generate transaction records for each channel
	for _, ch := range channels {
		successCount := int(float64(ch.SampleSize) * ch.SuccessRate)
		failureCount := ch.SampleSize - successCount

		log.Printf("Generating %d success + %d failed transactions for %s/%s/%s (%.0f%% success rate)",
			successCount, failureCount, ch.Type, ch.Channel, ch.Medium, ch.SuccessRate*100)

		// Generate successful transactions
		for i := 0; i < successCount; i++ {
			record := TransactionRecord{
				ID:        uuid.New().String(),
				Type:      ch.Type,
				Channel:   ch.Channel,
				Medium:    ch.Medium,
				Status:    "success",
				Amount:    randomAmount(ch.Type),
				CreatedAt: randomTimestamp(30), // Random time within last 30 days
			}

			if err := db.Create(&record).Error; err != nil {
				log.Printf("Error creating success record: %v", err)
				continue
			}
			totalRecords++
		}

		// Generate failed transactions
		for i := 0; i < failureCount; i++ {
			record := TransactionRecord{
				ID:        uuid.New().String(),
				Type:      ch.Type,
				Channel:   ch.Channel,
				Medium:    ch.Medium,
				Status:    "failed",
				Amount:    randomAmount(ch.Type),
				CreatedAt: randomTimestamp(30),
			}

			if err := db.Create(&record).Error; err != nil {
				log.Printf("Error creating failed record: %v", err)
				continue
			}
			totalRecords++
		}

		// Update statistics for this channel
		if err := updateChannelStatistics(db, ch.Type, ch.Channel, ch.Medium); err != nil {
			log.Printf("Warning: Failed to update statistics for %s/%s/%s: %v",
				ch.Type, ch.Channel, ch.Medium, err)
		}
	}

	log.Printf("✅ Seed data generation complete!")
	log.Printf("📊 Generated %d transaction records", totalRecords)
	log.Printf("📈 Statistics calculated for %d channel combinations", len(channels))
	log.Println("")
	log.Println("🔍 Sample queries you can try:")
	log.Println("   GET /api/v1/predictions")
	log.Println("   GET /api/v1/predictions?type=transfer")
	log.Println("   GET /api/v1/predictions?channel=pos")
	log.Println("   GET /api/v1/predictions?medium=mtn")
	log.Println("   GET /api/v1/predictions?type=data&channel=app")
}

// randomAmount generates realistic amounts in Naira based on transaction type
func randomAmount(txType string) float64 {
	switch txType {
	case "airtime":
		// N100 - N5,000
		return float64(rand.Intn(49)*100 + 100)
	case "data":
		// N500 - N10,000
		return float64(rand.Intn(95)*100 + 500)
	case "transfer":
		// N1,000 - N500,000
		amounts := []float64{1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000}
		return amounts[rand.Intn(len(amounts))]
	case "bill_payment":
		// N1,000 - N50,000
		return float64(rand.Intn(490)*100 + 1000)
	case "withdrawal":
		// N5,000 - N100,000
		return float64(rand.Intn(19)*5000 + 5000)
	default:
		return float64(rand.Intn(50)*1000 + 1000)
	}
}

// randomTimestamp generates a random timestamp within the last N days
func randomTimestamp(daysAgo int) time.Time {
	now := time.Now()
	randomDays := rand.Intn(daysAgo)
	randomHours := rand.Intn(24)
	randomMinutes := rand.Intn(60)
	randomSeconds := rand.Intn(60)

	return now.AddDate(0, 0, -randomDays).
		Add(-time.Duration(randomHours) * time.Hour).
		Add(-time.Duration(randomMinutes) * time.Minute).
		Add(-time.Duration(randomSeconds) * time.Second)
}
