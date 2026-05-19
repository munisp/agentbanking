package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// WorkflowsTotal counts total workflows executed by type and status
	WorkflowsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "workflows_total",
			Help: "Total number of workflows executed",
		},
		[]string{"type", "status"},
	)

	// WorkflowDuration tracks workflow execution duration
	WorkflowDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "workflow_duration_seconds",
			Help:    "Workflow execution duration in seconds",
			Buckets: prometheus.ExponentialBuckets(0.01, 2, 12), // 10ms to ~40s
		},
		[]string{"type"},
	)

	// StepDuration tracks step execution duration
	StepDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "step_duration_seconds",
			Help:    "Step execution duration in seconds",
			Buckets: prometheus.ExponentialBuckets(0.001, 2, 12), // 1ms to ~4s
		},
		[]string{"workflow_type", "step_name"},
	)

	// ActiveWorkflows tracks currently executing workflows
	ActiveWorkflows = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "active_workflows",
			Help: "Number of currently executing workflows",
		},
	)

	// WorkflowStepsTotal counts total steps executed
	WorkflowStepsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "workflow_steps_total",
			Help: "Total number of workflow steps executed",
		},
		[]string{"workflow_type", "step_name", "status"},
	)

	// WorkflowRetries counts workflow retry attempts
	WorkflowRetries = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "workflow_retries_total",
			Help: "Total number of workflow retry attempts",
		},
		[]string{"workflow_type"},
	)

	// HTTPRequestDuration tracks HTTP request duration
	HTTPRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path", "status"},
	)

	// HTTPRequestsTotal counts total HTTP requests
	HTTPRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		},
		[]string{"method", "path", "status"},
	)

	// DatabaseQueryDuration tracks database query duration
	DatabaseQueryDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "database_query_duration_seconds",
			Help:    "Database query duration in seconds",
			Buckets: prometheus.ExponentialBuckets(0.0001, 2, 12), // 0.1ms to ~400ms
		},
		[]string{"operation"},
	)

	// RedisOperationDuration tracks Redis operation duration
	RedisOperationDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "redis_operation_duration_seconds",
			Help:    "Redis operation duration in seconds",
			Buckets: prometheus.ExponentialBuckets(0.0001, 2, 10), // 0.1ms to ~100ms
		},
		[]string{"operation"},
	)

	// EventsPublished counts events published to message brokers
	EventsPublished = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "events_published_total",
			Help: "Total number of events published",
		},
		[]string{"topic", "status"},
	)
)

