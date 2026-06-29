package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"remittance/float-management/handlers"
	"remittance/float-management/models"
	"remittance/float-management/services"
)

// FloatMetrics for monitoring
type FloatMetrics struct {
	FacilitiesCreated    prometheus.Counter
	FacilitiesApproved   prometheus.Counter
	FloatUtilizations    prometheus.Counter
	FloatSettlements     prometheus.Counter
	RiskAssessments      prometheus.Counter
	AlertsGenerated      prometheus.Counter
	ErrorCount           prometheus.Counter
	ResponseTime         prometheus.Histogram
	UtilizationGauge     prometheus.Gauge
	OutstandingFloatGauge prometheus.Gauge
}

// NewFloatMetrics creates new metrics
func NewFloatMetrics() *FloatMetrics {
	return &FloatMetrics{
		FacilitiesCreated: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_facilities_created_total",
			Help: "Total number of float facilities created",
		}),
		FacilitiesApproved: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_facilities_approved_total",
			Help: "Total number of float facilities approved",
		}),
		FloatUtilizations: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_utilizations_total",
			Help: "Total number of float utilizations",
		}),
		FloatSettlements: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_settlements_total",
			Help: "Total number of float settlements",
		}),
		RiskAssessments: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_risk_assessments_total",
			Help: "Total number of risk assessments performed",
		}),
		AlertsGenerated: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_alerts_generated_total",
			Help: "Total number of float alerts generated",
		}),
		ErrorCount: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "float_service_errors_total",
			Help: "Total number of float service errors",
		}),
		ResponseTime: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name: "float_service_response_time_seconds",
			Help: "Response time for float service operations",
		}),
		UtilizationGauge: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "float_utilization_rate",
			Help: "Current float utilization rate percentage",
		}),
		OutstandingFloatGauge: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "outstanding_float_amount",
			Help: "Total outstanding float amount",
		}),
	}
}

// RegisterMetrics registers metrics with Prometheus
func (m *FloatMetrics) RegisterMetrics() {
	prometheus.MustRegister(m.FacilitiesCreated)
	prometheus.MustRegister(m.FacilitiesApproved)
	prometheus.MustRegister(m.FloatUtilizations)
	prometheus.MustRegister(m.FloatSettlements)
	prometheus.MustRegister(m.RiskAssessments)
	prometheus.MustRegister(m.AlertsGenerated)
	prometheus.MustRegister(m.ErrorCount)
	prometheus.MustRegister(m.ResponseTime)
	prometheus.MustRegister(m.UtilizationGauge)
	prometheus.MustRegister(m.OutstandingFloatGauge)
}

func main() {
	// Initialize metrics
	metrics := NewFloatMetrics()
	metrics.RegisterMetrics()

	// Database connection
	db, err := initializeDatabase()
	if err != nil {
		log.Fatal("Failed to connect to database:", err)
	}

	// Redis connection
	redis := initializeRedis()

	// Float service configuration
	config := &services.FloatConfig{
		DefaultInterestRate:    0.030, // 3%
		DefaultFeeRate:        0.005, // 0.5%
		MaxFloatLimit:         10000000, // ₦10M
		MinCreditScore:        40.0,
		DefaultSettlementDays: 7,
		RiskEngineURL:         getEnv("RISK_ENGINE_URL", "http://localhost:8001"),
		SettlementEngineURL:   getEnv("SETTLEMENT_ENGINE_URL", "http://localhost:8002"),
	}

	// Initialize services
	floatService := services.NewFloatService(db, redis, config)
	floatHandler := handlers.NewFloatHandler(floatService)

	// Initialize Gin router
	router := gin.Default()

	// CORS middleware
	router.Use(cors.New(cors.Config{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"*"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	// Middleware for metrics
	router.Use(func(c *gin.Context) {
		timer := prometheus.NewTimer(metrics.ResponseTime)
		defer timer.ObserveDuration()
		c.Next()
	})

	// Health check endpoint
	router.GET("/health", func(c *gin.Context) {
		c.JSON(http.StatusOK, gin.H{
			"status":    "healthy",
			"service":   "float-management",
			"version":   "1.0.0",
			"timestamp": time.Now().UTC(),
		})
	})

	// Metrics endpoint
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))

	// API routes
	v1 := router.Group("/api/v1")
	{
		// Float facility management
		float := v1.Group("/float")
		{
			// Facility endpoints
			facilities := float.Group("/facilities")
			{
				facilities.POST("", floatHandler.CreateFloatFacility)
				facilities.GET("", floatHandler.ListFloatFacilities)
				facilities.GET("/:id", floatHandler.GetFloatFacility)
				facilities.PUT("/:id/approve", floatHandler.ApproveFloatFacility)
				facilities.PUT("/:id/suspend", floatHandler.SuspendFloatFacility)
				facilities.PUT("/:id/limit", floatHandler.UpdateFloatLimit)
			}

			// Agent-specific endpoints
			agents := float.Group("/agents")
			{
				agents.GET("/:agent_id/facility", floatHandler.GetAgentFloatFacility)
				agents.GET("/:agent_id/balance", floatHandler.GetFloatBalance)
				agents.PUT("/:agent_id/integration-model", floatHandler.SetIntegrationModel)
			}

			// Float operations
			float.POST("/utilize", floatHandler.UtilizeFloat)
			float.POST("/settle", floatHandler.SettleFloat)

			// Transaction management
			transactions := float.Group("/transactions")
			{
				transactions.GET("", floatHandler.ListFloatTransactions)
				transactions.GET("/:id", floatHandler.GetFloatTransaction)
			}

			// Settlement management
			settlements := float.Group("/settlements")
			{
				settlements.GET("", floatHandler.ListFloatSettlements)
			}

			// Risk assessment
			riskAssessments := float.Group("/risk-assessments")
			{
				riskAssessments.POST("", floatHandler.TriggerRiskAssessment)
				riskAssessments.GET("", floatHandler.ListRiskAssessments)
			}

			// Alert management
			alerts := float.Group("/alerts")
			{
				alerts.GET("", floatHandler.ListFloatAlerts)
				alerts.PUT("/:id/acknowledge", floatHandler.AcknowledgeAlert)
			}

			// Analytics and reporting
			float.GET("/analytics", floatHandler.GetFloatAnalytics)
			float.GET("/integration-models", floatHandler.GetIntegrationModels)
		}
	}

	// Start metrics updater
	go startMetricsUpdater(db, metrics)

	// Start background tasks
	go startBackgroundTasks(floatService)

	// Start server
	port := getEnv("PORT", "8097")
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	// Graceful shutdown
	go func() {
		log.Printf("Float Management Service starting on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Failed to start server: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down Float Management Service...")

	// Graceful shutdown with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Float Management Service stopped")
}

// initializeDatabase initializes database connection and runs migrations
func initializeDatabase() (*gorm.DB, error) {
	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=%s",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_USER", "postgres"),
		getEnv("DB_PASSWORD", "password"),
		getEnv("DB_NAME", "remittance"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_SSLMODE", "disable"),
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Run migrations
	if err := runMigrations(db); err != nil {
		return nil, fmt.Errorf("failed to run migrations: %w", err)
	}

	// Create default configurations
	if err := createDefaultConfigurations(db); err != nil {
		log.Printf("Warning: Failed to create default configurations: %v", err)
	}

	return db, nil
}

// initializeRedis initializes Redis connection
func initializeRedis() *redis.Client {
	rdb := redis.NewClient(&redis.Options{
		Addr:     getEnv("REDIS_ADDR", "localhost:6379"),
		Password: getEnv("REDIS_PASSWORD", ""),
		DB:       0,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Printf("Warning: Redis connection failed: %v", err)
	}

	return rdb
}

// runMigrations runs database migrations
func runMigrations(db *gorm.DB) error {
	// Create custom types first
	if err := db.Exec(`
		DO $$ BEGIN
			CREATE TYPE float_status AS ENUM ('pending', 'active', 'suspended', 'closed', 'frozen');
		EXCEPTION
			WHEN duplicate_object THEN null;
		END $$;
	`).Error; err != nil {
		return err
	}

	if err := db.Exec(`
		DO $$ BEGIN
			CREATE TYPE float_transaction_type AS ENUM ('advance', 'utilization', 'settlement', 'interest', 'fee', 'adjustment', 'reversal');
		EXCEPTION
			WHEN duplicate_object THEN null;
		END $$;
	`).Error; err != nil {
		return err
	}

	if err := db.Exec(`
		DO $$ BEGIN
			CREATE TYPE settlement_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'partial', 'cancelled');
		EXCEPTION
			WHEN duplicate_object THEN null;
		END $$;
	`).Error; err != nil {
		return err
	}

	if err := db.Exec(`
		DO $$ BEGIN
			CREATE TYPE risk_level AS ENUM ('low', 'medium', 'high', 'critical');
		EXCEPTION
			WHEN duplicate_object THEN null;
		END $$;
	`).Error; err != nil {
		return err
	}

	if err := db.Exec(`
		DO $$ BEGIN
			CREATE TYPE agent_tier AS ENUM ('basic', 'standard', 'premium', 'elite');
		EXCEPTION
			WHEN duplicate_object THEN null;
		END $$;
	`).Error; err != nil {
		return err
	}

	// Auto-migrate tables
	return db.AutoMigrate(
		&models.AgentFloat{},
		&models.FloatTransaction{},
		&models.FloatSettlement{},
		&models.RiskAssessment{},
		&models.FloatLimit{},
		&models.FloatAlert{},
		&models.FloatConfiguration{},
	)
}

// createDefaultConfigurations creates default system configurations
func createDefaultConfigurations(db *gorm.DB) error {
	configs := []models.FloatConfiguration{
		{
			ConfigKey:   "default_interest_rate",
			ConfigValue: "0.030",
			ConfigType:  "float",
			Description: "Default annual interest rate for float facilities",
			Category:    "rates",
			IsActive:    true,
		},
		{
			ConfigKey:   "default_fee_rate",
			ConfigValue: "0.005",
			ConfigType:  "float",
			Description: "Default fee rate for float management",
			Category:    "rates",
			IsActive:    true,
		},
		{
			ConfigKey:   "max_float_limit",
			ConfigValue: "10000000",
			ConfigType:  "float",
			Description: "Maximum float limit allowed",
			Category:    "limits",
			IsActive:    true,
		},
		{
			ConfigKey:   "min_credit_score",
			ConfigValue: "40.0",
			ConfigType:  "float",
			Description: "Minimum credit score required for float facility",
			Category:    "risk",
			IsActive:    true,
		},
		{
			ConfigKey:   "settlement_frequency",
			ConfigValue: "daily",
			ConfigType:  "string",
			Description: "Default settlement frequency",
			Category:    "settlement",
			IsActive:    true,
		},
		{
			ConfigKey:   "risk_assessment_interval_months",
			ConfigValue: "3",
			ConfigType:  "integer",
			Description: "Risk assessment interval in months",
			Category:    "risk",
			IsActive:    true,
		},
	}

	for _, config := range configs {
		var existingConfig models.FloatConfiguration
		if err := db.Where("config_key = ?", config.ConfigKey).First(&existingConfig).Error; err != nil {
			if err == gorm.ErrRecordNotFound {
				if err := db.Create(&config).Error; err != nil {
					return err
				}
			}
		}
	}

	return nil
}

// startMetricsUpdater starts a goroutine to update metrics
func startMetricsUpdater(db *gorm.DB, metrics *FloatMetrics) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		updateMetrics(db, metrics)
	}
}

// updateMetrics updates Prometheus metrics
func updateMetrics(db *gorm.DB, metrics *FloatMetrics) {
	// Update utilization rate
	var totalLimit, totalUtilized float64
	db.Model(&models.AgentFloat{}).Select("COALESCE(SUM(float_limit), 0)").Row().Scan(&totalLimit)
	db.Model(&models.AgentFloat{}).Select("COALESCE(SUM(utilized_amount), 0)").Row().Scan(&totalUtilized)

	if totalLimit > 0 {
		utilizationRate := (totalUtilized / totalLimit) * 100
		metrics.UtilizationGauge.Set(utilizationRate)
	}

	// Update outstanding float
	metrics.OutstandingFloatGauge.Set(totalUtilized)
}

// startBackgroundTasks starts background tasks
func startBackgroundTasks(floatService *services.FloatService) {
	// Start daily settlement checker
	go func() {
		ticker := time.NewTicker(1 * time.Hour)
		defer ticker.Stop()

		for range ticker.C {
			checkPendingSettlements(floatService)
		}
	}()

	// Start risk assessment scheduler
	go func() {
		ticker := time.NewTicker(24 * time.Hour)
		defer ticker.Stop()

		for range ticker.C {
			scheduleRiskAssessments(floatService)
		}
	}()

	// Start alert checker
	go func() {
		ticker := time.NewTicker(15 * time.Minute)
		defer ticker.Stop()

		for range ticker.C {
			checkFloatAlerts(floatService)
		}
	}()
}

// checkPendingSettlements checks for pending settlements
func checkPendingSettlements(floatService *services.FloatService) {
	log.Println("Checking pending settlements...")
	// Implementation would check for overdue settlements and trigger alerts
}

// scheduleRiskAssessments schedules periodic risk assessments
func scheduleRiskAssessments(floatService *services.FloatService) {
	log.Println("Scheduling risk assessments...")
	// Implementation would check for agents due for risk assessment
}

// checkFloatAlerts checks for float-related alerts
func checkFloatAlerts(floatService *services.FloatService) {
	log.Println("Checking float alerts...")
	// Implementation would check for various alert conditions
}

// getEnv gets environment variable with default value.
func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

// requireEnv returns the value of an environment variable or panics if not set.
// Use this for critical configuration like database passwords, API keys, etc.
func requireEnv(key string) string {
	value := os.Getenv(key)
	if value == "" {
		log.Fatalf("CRITICAL: Required environment variable %s is not set. Cannot start service.", key)
	}
	return value
}

