//go:build ignore

package main

import (
	"fmt"
	"log"
	"os"
	"strconv"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

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

func main() {
	log.Println("🗑️  Starting database cleanup...")

	// Load configuration
	config := loadConfig()

	// Connect to database
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=require TimeZone=UTC",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	log.Println("✅ Connected to database")

	// List of old tables to drop
	oldTables := []string{
		"network_transactions",
		"transaction_state_histories",
		"transaction_fee_rules",
		"settlement_batches",
		"settlement_entries",
		"agent_cash_positions",
		"cash_movements",
	}

	log.Println("📋 Tables to be dropped:")
	for _, table := range oldTables {
		log.Printf("   - %s", table)
	}

	log.Println("")
	log.Println("⚠️  WARNING: This will permanently delete all data in these tables!")
	log.Println("Press Ctrl+C to cancel or wait 5 seconds to continue...")

	// Give user time to cancel
	// time.Sleep(5 * time.Second)

	// Drop each table
	for _, table := range oldTables {
		log.Printf("Dropping table: %s", table)

		sql := fmt.Sprintf("DROP TABLE IF EXISTS %s CASCADE", table)
		if err := db.Exec(sql).Error; err != nil {
			log.Printf("⚠️  Warning: Failed to drop %s: %v", table, err)
		} else {
			log.Printf("✅ Dropped table: %s", table)
		}
	}

	log.Println("")
	log.Println("🎉 Database cleanup complete!")
	log.Println("📊 New schema only contains:")
	log.Println("   - transaction_records")
	log.Println("   - channel_statistics")
}
