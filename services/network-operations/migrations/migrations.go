// File: services/network-operations/migrations/migrations.go
// Database migration utilities for network-operations service

package migrations

import (
	"embed"
	"fmt"
	"log"

	"gorm.io/gorm"
)

//go:embed *.sql
var migrationFiles embed.FS

// RunMigrations executes all SQL migration files
// Use this in main.go during service initialization
func RunMigrations(db *gorm.DB) error {
	log.Println("Running database migrations...")

	// Read and execute 001_create_operations_tables.sql
	sqlBytes, err := migrationFiles.ReadFile("001_create_operations_tables.sql")
	if err != nil {
		return fmt.Errorf("failed to read migration file: %w", err)
	}

	if err := db.Exec(string(sqlBytes)).Error; err != nil {
		return fmt.Errorf("failed to execute migration: %w", err)
	}

	log.Println("✓ Database migrations completed successfully")
	return nil
}

// DropAllOperationsTables drops all operations-related tables (use with caution!)
func DropAllOperationsTables(db *gorm.DB) error {
	log.Println("⚠️  Dropping all operations tables...")

	if err := db.Exec("DROP TABLE IF EXISTS incident_updates CASCADE").Error; err != nil {
		return err
	}
	if err := db.Exec("DROP TABLE IF EXISTS incidents CASCADE").Error; err != nil {
		return err
	}
	if err := db.Exec("DROP TABLE IF EXISTS ab_tests CASCADE").Error; err != nil {
		return err
	}
	if err := db.Exec("DROP TABLE IF EXISTS canary_releases CASCADE").Error; err != nil {
		return err
	}

	log.Println("✓ All operations tables dropped")
	return nil
}
