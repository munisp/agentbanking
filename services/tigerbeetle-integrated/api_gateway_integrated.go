package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"
)

// TigerBeetleIntegratedAPIGateway provides intelligent routing to TigerBeetle services
type TigerBeetleIntegratedAPIGateway struct {
	// Service endpoints
	tigerbeetleZigEndpoint   string
	tigerbeetleEdgeEndpoint  string
	paymentServiceEndpoint   string
	accountServiceEndpoint   string
	transactionServiceEndpoint string
	
	// Load balancing and health
	serviceHealth    map[string]bool
	healthMutex      sync.RWMutex
	circuitBreakers  map[string]*CircuitBreaker
	
	// Redis for caching and coordination
	redis *redis.Client
	
	// HTTP clients with different timeouts
	fastClient   *http.Client  // For balance queries
	normalClient *http.Client  // For standard operations
	slowClient   *http.Client  // For batch operations
	
	// Metrics
	requestsTotal     *prometheus.CounterVec
	requestDuration   *prometheus.HistogramVec
	serviceHealthGauge     *prometheus.GaugeVec
	circuitBreakerState *prometheus.GaugeVec
	cacheHits         prometheus.Counter
	cacheMisses       prometheus.Counter
}

// CircuitBreaker implements circuit breaker pattern for service resilience
type CircuitBreaker struct {
	name           string
	failureCount   int
	successCount   int
	lastFailureTime time.Time
	state          string // "closed", "open", "half-open"
	threshold      int
	timeout        time.Duration
	mutex          sync.RWMutex
}

// ServiceRoute defines routing rules for different request types
type ServiceRoute struct {
	Pattern     string
	Method      string
	Service     string
	Priority    int
	CacheEnabled bool
	CacheTTL    time.Duration
	Timeout     time.Duration
}

// RequestContext contains routing context information
type RequestContext struct {
	RequestID    string
	UserID       string
	AccountID    string
	TransactionType string
	Amount       float64
	Priority     string
	Source       string
	Timestamp    time.Time
}

// HealthCheck represents service health status
type HealthCheck struct {
	Service   string    `json:"service"`
	Status    string    `json:"status"`
	Latency   int64     `json:"latency_ms"`
	Timestamp time.Time `json:"timestamp"`
	Error     string    `json:"error,omitempty"`
}

// NewTigerBeetleIntegratedAPIGateway creates a new integrated API gateway
func NewTigerBeetleIntegratedAPIGateway(config GatewayConfig) (*TigerBeetleIntegratedAPIGateway, error) {
	// Connect to Redis
	opt, err := redis.ParseURL(config.RedisURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse Redis URL: %v", err)
	}
	redisClient := redis.NewClient(opt)
	
	// Initialize metrics
	requestsTotal := prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "api_gateway_requests_total",
			Help: "Total number of API requests",
		},
		[]string{"service", "method", "status"},
	)
	
	requestDuration := prometheus.NewHistogramVec(
		prometheus.HistogramOpts{
			Name: "api_gateway_request_duration_seconds",
			Help: "API request duration in seconds",
		},
		[]string{"service", "method"},
	)
	
	serviceHealthGauge := prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "api_gateway_service_health",
			Help: "Service health status (1=healthy, 0=unhealthy)",
		},
		[]string{"service"},
	)
	
	circuitBreakerGauge := prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "api_gateway_circuit_breaker_state",
			Help: "Circuit breaker state (0=closed, 1=open, 2=half-open)",
		},
		[]string{"service"},
	)
	
	cacheHits := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "api_gateway_cache_hits_total",
		Help: "Total number of cache hits",
	})
	
	cacheMisses := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "api_gateway_cache_misses_total",
		Help: "Total number of cache misses",
	})
	
	prometheus.MustRegister(requestsTotal, requestDuration, serviceHealthGauge, circuitBreakerGauge, cacheHits, cacheMisses)
	
	gateway := &TigerBeetleIntegratedAPIGateway{
		tigerbeetleZigEndpoint:     config.TigerBeetleZigEndpoint,
		tigerbeetleEdgeEndpoint:    config.TigerBeetleEdgeEndpoint,
		paymentServiceEndpoint:     config.PaymentServiceEndpoint,
		accountServiceEndpoint:     config.AccountServiceEndpoint,
		transactionServiceEndpoint: config.TransactionServiceEndpoint,
		serviceHealth:              make(map[string]bool),
		circuitBreakers:            make(map[string]*CircuitBreaker),
		redis:                      redisClient,
		fastClient:                 &http.Client{Timeout: 5 * time.Second},
		normalClient:               &http.Client{Timeout: 30 * time.Second},
		slowClient:                 &http.Client{Timeout: 120 * time.Second},
		requestsTotal:              requestsTotal,
		requestDuration:            requestDuration,
		serviceHealthGauge:              serviceHealthGauge,
		circuitBreakerState:        circuitBreakerGauge,
		cacheHits:                  cacheHits,
		cacheMisses:                cacheMisses,
	}
	
	// Initialize circuit breakers
	gateway.initCircuitBreakers()
	
	// Start health monitoring
	go gateway.healthMonitor()
	
	return gateway, nil
}

type GatewayConfig struct {
	TigerBeetleZigEndpoint     string
	TigerBeetleEdgeEndpoint    string
	PaymentServiceEndpoint     string
	AccountServiceEndpoint     string
	TransactionServiceEndpoint string
	RedisURL                   string
}

// initCircuitBreakers initializes circuit breakers for all services
func (gw *TigerBeetleIntegratedAPIGateway) initCircuitBreakers() {
	services := []string{
		"tigerbeetle-zig",
		"tigerbeetle-edge", 
		"payment-service",
		"account-service",
		"transaction-service",
	}
	
	for _, service := range services {
		gw.circuitBreakers[service] = &CircuitBreaker{
			name:      service,
			state:     "closed",
			threshold: 5,
			timeout:   30 * time.Second,
		}
	}
}

// setupRoutes configures intelligent routing rules
func (gw *TigerBeetleIntegratedAPIGateway) setupRoutes() *gin.Engine {
	router := gin.Default()
	
	// Add middleware
	router.Use(gw.requestIDMiddleware())
	router.Use(gw.rateLimitMiddleware())
	router.Use(gw.authenticationMiddleware())
	router.Use(gw.loggingMiddleware())
	
	// Health and metrics endpoints
	router.GET("/health", gw.healthHandler)
	router.GET("/metrics", gin.WrapH(promhttp.Handler()))
	router.GET("/services/health", gw.servicesHealthHandler)
	
	// TigerBeetle direct access (for advanced users)
	tigerbeetle := router.Group("/tigerbeetle")
	{
		tigerbeetle.Any("/zig/*path", gw.proxyToTigerBeetleZig)
		tigerbeetle.Any("/edge/*path", gw.proxyToTigerBeetleEdge)
	}
	
	// Financial operations with intelligent routing
	api := router.Group("/api/v1")
	{
		// Account operations - route to account service with TigerBeetle integration
		accounts := api.Group("/accounts")
		{
			accounts.POST("", gw.routeToAccountService)
			accounts.GET("/:id", gw.routeToAccountService)
			accounts.GET("/:id/balance", gw.routeToBalanceQuery)  // Optimized balance queries
			accounts.PUT("/:id/status", gw.routeToAccountService)
			accounts.GET("/:id/transactions", gw.routeToAccountService)
			accounts.POST("/bulk", gw.routeToAccountService)
			accounts.GET("/search", gw.routeToAccountService)
		}
		
		// Payment operations - route to payment service with TigerBeetle integration
		payments := api.Group("/payments")
		{
			payments.POST("", gw.routeToPaymentService)
			payments.GET("/:id", gw.routeToPaymentService)
			payments.GET("/:id/status", gw.routeToPaymentService)
			payments.POST("/agent", gw.routeToPaymentService)
		}
		
		// Transaction operations - route to transaction service with TigerBeetle integration
		transactions := api.Group("/transactions")
		{
			transactions.POST("", gw.routeToTransactionService)
			transactions.GET("/:id", gw.routeToTransactionService)
			transactions.POST("/:id/reverse", gw.routeToTransactionService)
			transactions.POST("/batch", gw.routeToTransactionServiceSlow) // Use slow client for batches
			transactions.GET("/search", gw.routeToTransactionService)
		}
		
		// Batch operations
		batches := api.Group("/batches")
		{
			batches.POST("", gw.routeToTransactionServiceSlow)
			batches.GET("/:id", gw.routeToTransactionService)
		}
		
		// Reconciliation operations
		reconciliation := api.Group("/reconciliation")
		{
			reconciliation.GET("/pending", gw.routeToTransactionService)
			reconciliation.POST("/:id/resolve", gw.routeToTransactionService)
		}
	}
	
	// Legacy API support (redirect to new endpoints)
	legacy := router.Group("/legacy")
	{
		legacy.Any("/*path", gw.legacyRedirectHandler)
	}
	
	return router
}

// Intelligent routing methods

func (gw *TigerBeetleIntegratedAPIGateway) routeToBalanceQuery(c *gin.Context) {
	// Balance queries are optimized for speed - try edge first, then zig
	accountID := c.Param("id")
	
	// Check cache first
	cacheKey := fmt.Sprintf("balance:%s", accountID)
	if cached, err := gw.redis.Get(context.Background(), cacheKey).Result(); err == nil {
		gw.cacheHits.Inc()
		c.Header("X-Cache", "HIT")
		c.Header("Content-Type", "application/json")
		c.String(http.StatusOK, cached)
		return
	}
	gw.cacheMisses.Inc()
	
	// Try TigerBeetle edge first for better performance
	if gw.isServiceHealthy("tigerbeetle-edge") {
		if gw.proxyBalanceQuery(c, gw.tigerbeetleEdgeEndpoint, accountID) {
			return
		}
	}
	
	// Fallback to TigerBeetle Zig
	if gw.isServiceHealthy("tigerbeetle-zig") {
		if gw.proxyBalanceQuery(c, gw.tigerbeetleZigEndpoint, accountID) {
			return
		}
	}
	
	// Final fallback to account service
	gw.proxyToService(c, gw.accountServiceEndpoint, "account-service", gw.fastClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) proxyBalanceQuery(c *gin.Context, endpoint, accountID string) bool {
	url := fmt.Sprintf("%s/accounts/%s/balance", endpoint, accountID)
	
	resp, err := gw.fastClient.Get(url)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return false
	}
	
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return false
	}
	
	// Cache the result for 30 seconds
	cacheKey := fmt.Sprintf("balance:%s", accountID)
	gw.redis.Set(context.Background(), cacheKey, string(body), 30*time.Second)
	
	c.Header("X-Cache", "MISS")
	c.Header("Content-Type", "application/json")
	c.String(resp.StatusCode, string(body))
	return true
}

func (gw *TigerBeetleIntegratedAPIGateway) routeToAccountService(c *gin.Context) {
	gw.proxyToService(c, gw.accountServiceEndpoint, "account-service", gw.normalClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) routeToPaymentService(c *gin.Context) {
	gw.proxyToService(c, gw.paymentServiceEndpoint, "payment-service", gw.normalClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) routeToTransactionService(c *gin.Context) {
	gw.proxyToService(c, gw.transactionServiceEndpoint, "transaction-service", gw.normalClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) routeToTransactionServiceSlow(c *gin.Context) {
	gw.proxyToService(c, gw.transactionServiceEndpoint, "transaction-service", gw.slowClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) proxyToTigerBeetleZig(c *gin.Context) {
	path := c.Param("path")
	targetURL := gw.tigerbeetleZigEndpoint + path
	gw.proxyToURL(c, targetURL, "tigerbeetle-zig", gw.normalClient)
}

func (gw *TigerBeetleIntegratedAPIGateway) proxyToTigerBeetleEdge(c *gin.Context) {
	path := c.Param("path")
	targetURL := gw.tigerbeetleEdgeEndpoint + path
	gw.proxyToURL(c, targetURL, "tigerbeetle-edge", gw.normalClient)
}

// Core proxy functionality

func (gw *TigerBeetleIntegratedAPIGateway) proxyToService(c *gin.Context, serviceEndpoint, serviceName string, client *http.Client) {
	if !gw.isServiceHealthy(serviceName) {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": fmt.Sprintf("Service %s is currently unavailable", serviceName),
			"code":  "SERVICE_UNAVAILABLE",
		})
		return
	}
	
	if !gw.checkCircuitBreaker(serviceName) {
		c.JSON(http.StatusServiceUnavailable, gin.H{
			"error": fmt.Sprintf("Circuit breaker open for service %s", serviceName),
			"code":  "CIRCUIT_BREAKER_OPEN",
		})
		return
	}
	
	targetURL := serviceEndpoint + c.Request.URL.Path
	if c.Request.URL.RawQuery != "" {
		targetURL += "?" + c.Request.URL.RawQuery
	}
	
	gw.proxyToURL(c, targetURL, serviceName, client)
}

func (gw *TigerBeetleIntegratedAPIGateway) proxyToURL(c *gin.Context, targetURL, serviceName string, client *http.Client) {
	timer := prometheus.NewTimer(gw.requestDuration.WithLabelValues(serviceName, c.Request.Method))
	defer timer.ObserveDuration()
	
	// Create request
	req, err := http.NewRequest(c.Request.Method, targetURL, c.Request.Body)
	if err != nil {
		gw.recordCircuitBreakerFailure(serviceName)
		gw.requestsTotal.WithLabelValues(serviceName, c.Request.Method, "error").Inc()
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create request"})
		return
	}
	
	// Copy headers
	for key, values := range c.Request.Header {
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}
	
	// Add tracing headers
	req.Header.Set("X-Request-ID", c.GetString("request_id"))
	req.Header.Set("X-Forwarded-For", c.ClientIP())
	req.Header.Set("X-Gateway-Service", serviceName)
	
	// Execute request
	resp, err := client.Do(req)
	if err != nil {
		gw.recordCircuitBreakerFailure(serviceName)
		gw.requestsTotal.WithLabelValues(serviceName, c.Request.Method, "error").Inc()
		c.JSON(http.StatusBadGateway, gin.H{
			"error": "Service request failed",
			"code":  "GATEWAY_ERROR",
		})
		return
	}
	defer resp.Body.Close()
	
	// Record success
	gw.recordCircuitBreakerSuccess(serviceName)
	gw.requestsTotal.WithLabelValues(serviceName, c.Request.Method, strconv.Itoa(resp.StatusCode)).Inc()
	
	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Header(key, value)
		}
	}
	
	// Add gateway headers
	c.Header("X-Gateway-Service", serviceName)
	c.Header("X-Gateway-Timestamp", time.Now().Format(time.RFC3339))
	
	// Copy response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read response"})
		return
	}
	
	c.Data(resp.StatusCode, resp.Header.Get("Content-Type"), body)
}

// Circuit breaker implementation

func (cb *CircuitBreaker) checkState() bool {
	cb.mutex.RLock()
	defer cb.mutex.RUnlock()
	
	switch cb.state {
	case "closed":
		return true
	case "open":
		if time.Since(cb.lastFailureTime) > cb.timeout {
			cb.state = "half-open"
			return true
		}
		return false
	case "half-open":
		return true
	default:
		return false
	}
}

func (cb *CircuitBreaker) recordSuccess() {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()
	
	cb.successCount++
	cb.failureCount = 0
	
	if cb.state == "half-open" && cb.successCount >= 3 {
		cb.state = "closed"
		cb.successCount = 0
	}
}

func (cb *CircuitBreaker) recordFailure() {
	cb.mutex.Lock()
	defer cb.mutex.Unlock()
	
	cb.failureCount++
	cb.lastFailureTime = time.Now()
	
	if cb.failureCount >= cb.threshold {
		cb.state = "open"
		cb.successCount = 0
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) checkCircuitBreaker(serviceName string) bool {
	if cb, exists := gw.circuitBreakers[serviceName]; exists {
		return cb.checkState()
	}
	return true
}

func (gw *TigerBeetleIntegratedAPIGateway) recordCircuitBreakerSuccess(serviceName string) {
	if cb, exists := gw.circuitBreakers[serviceName]; exists {
		cb.recordSuccess()
		gw.updateCircuitBreakerMetric(serviceName, cb.state)
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) recordCircuitBreakerFailure(serviceName string) {
	if cb, exists := gw.circuitBreakers[serviceName]; exists {
		cb.recordFailure()
		gw.updateCircuitBreakerMetric(serviceName, cb.state)
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) updateCircuitBreakerMetric(serviceName, state string) {
	var value float64
	switch state {
	case "closed":
		value = 0
	case "open":
		value = 1
	case "half-open":
		value = 2
	}
	gw.circuitBreakerState.WithLabelValues(serviceName).Set(value)
}

// Health monitoring

func (gw *TigerBeetleIntegratedAPIGateway) healthMonitor() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			gw.checkAllServicesHealth()
		}
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) checkAllServicesHealth() {
	services := map[string]string{
		"tigerbeetle-zig":     gw.tigerbeetleZigEndpoint,
		"tigerbeetle-edge":    gw.tigerbeetleEdgeEndpoint,
		"payment-service":     gw.paymentServiceEndpoint,
		"account-service":     gw.accountServiceEndpoint,
		"transaction-service": gw.transactionServiceEndpoint,
	}
	
	for serviceName, endpoint := range services {
		healthy := gw.checkServiceHealth(endpoint)
		gw.updateServiceHealth(serviceName, healthy)
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) checkServiceHealth(endpoint string) bool {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(endpoint + "/health")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	
	return resp.StatusCode == http.StatusOK
}

func (gw *TigerBeetleIntegratedAPIGateway) updateServiceHealth(serviceName string, healthy bool) {
	gw.healthMutex.Lock()
	gw.serviceHealth[serviceName] = healthy
	gw.healthMutex.Unlock()
	
	var value float64
	if healthy {
		value = 1
	}
	gw.serviceHealthGauge.WithLabelValues(serviceName).Set(value)
}

func (gw *TigerBeetleIntegratedAPIGateway) isServiceHealthy(serviceName string) bool {
	gw.healthMutex.RLock()
	defer gw.healthMutex.RUnlock()
	
	healthy, exists := gw.serviceHealth[serviceName]
	return exists && healthy
}

// Middleware

func (gw *TigerBeetleIntegratedAPIGateway) requestIDMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		requestID := c.GetHeader("X-Request-ID")
		if requestID == "" {
			requestID = fmt.Sprintf("gw-%d", time.Now().UnixNano())
		}
		c.Set("request_id", requestID)
		c.Header("X-Request-ID", requestID)
		c.Next()
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) rateLimitMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Implement rate limiting logic here
		// For now, just pass through
		c.Next()
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) authenticationMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		// Implement authentication logic here
		// For now, just pass through
		c.Next()
	}
}

func (gw *TigerBeetleIntegratedAPIGateway) loggingMiddleware() gin.HandlerFunc {
	return gin.LoggerWithFormatter(func(param gin.LogFormatterParams) string {
		return fmt.Sprintf("%s - [%s] \"%s %s %s %d %s \"%s\" %s\"\n",
			param.ClientIP,
			param.TimeStamp.Format(time.RFC1123),
			param.Method,
			param.Path,
			param.Request.Proto,
			param.StatusCode,
			param.Latency,
			param.Request.UserAgent(),
			param.ErrorMessage,
		)
	})
}

// HTTP Handlers

func (gw *TigerBeetleIntegratedAPIGateway) healthHandler(c *gin.Context) {
	gw.healthMutex.RLock()
	defer gw.healthMutex.RUnlock()
	
	allHealthy := true
	healthChecks := make(map[string]bool)
	
	for service, healthy := range gw.serviceHealth {
		healthChecks[service] = healthy
		if !healthy {
			allHealthy = false
		}
	}
	
	status := "healthy"
	httpStatus := http.StatusOK
	if !allHealthy {
		status = "degraded"
		httpStatus = http.StatusServiceUnavailable
	}
	
	c.JSON(httpStatus, gin.H{
		"status":    status,
		"timestamp": time.Now(),
		"services":  healthChecks,
		"version":   "1.0.0",
	})
}

func (gw *TigerBeetleIntegratedAPIGateway) servicesHealthHandler(c *gin.Context) {
	gw.healthMutex.RLock()
	defer gw.healthMutex.RUnlock()
	
	var healthChecks []HealthCheck
	
	for service, healthy := range gw.serviceHealth {
		status := "unhealthy"
		if healthy {
			status = "healthy"
		}
		
		healthCheck := HealthCheck{
			Service:   service,
			Status:    status,
			Timestamp: time.Now(),
		}
		
		healthChecks = append(healthChecks, healthCheck)
	}
	
	c.JSON(http.StatusOK, gin.H{
		"health_checks": healthChecks,
		"timestamp":     time.Now(),
	})
}

func (gw *TigerBeetleIntegratedAPIGateway) legacyRedirectHandler(c *gin.Context) {
	path := c.Param("path")
	newPath := "/api/v1" + path
	
	c.JSON(http.StatusMovedPermanently, gin.H{
		"message":  "This endpoint has moved",
		"new_path": newPath,
		"code":     "ENDPOINT_MOVED",
	})
}

func api_gateway_integratedMain() {
	config := GatewayConfig{
		TigerBeetleZigEndpoint:     "http://localhost:3000",
		TigerBeetleEdgeEndpoint:    "http://localhost:3001",
		PaymentServiceEndpoint:     "http://localhost:8080",
		AccountServiceEndpoint:     "http://localhost:8081",
		TransactionServiceEndpoint: "http://localhost:8082",
		RedisURL:                   "redis://localhost:6379",
	}
	
	gateway, err := NewTigerBeetleIntegratedAPIGateway(config)
	if err != nil {
		log.Fatal("Failed to initialize API gateway:", err)
	}
	
	router := gateway.setupRoutes()
	
	port := ":8000"
	log.Printf("Starting TigerBeetle Integrated API Gateway on port %s", port)
	log.Fatal(router.Run(port))
}

