package main

import "github.com/gin-gonic/gin"

// GetChaosExperiments handles GET /api/v1/chaos/experiments
func (h *NetworkOperationsHandler) GetChaosExperiments(c *gin.Context) {
	c.JSON(200, gin.H{"experiments": []gin.H{
		{"id": "ce-001", "name": "Payment Service Latency Spike", "type": "latency", "targetService": "payment-svc", "status": "completed", "lastRun": "2025-04-30 14:22", "blastRadius": "Low"},
		{"id": "ce-002", "name": "Auth Pod Kill", "type": "pod-kill", "targetService": "auth-svc", "status": "idle", "lastRun": "2025-04-28 09:10", "blastRadius": "Med"},
		{"id": "ce-003", "name": "Ledger Fault Injection", "type": "fault-injection", "targetService": "ledger-svc", "status": "idle", "lastRun": "2025-04-25 16:45", "blastRadius": "High"},
		{"id": "ce-004", "name": "Core Network Partition", "type": "network-partition", "targetService": "core-banking", "status": "idle", "lastRun": "2025-04-20 11:00", "blastRadius": "High"},
		{"id": "ce-005", "name": "Notification Latency", "type": "latency", "targetService": "notification-svc", "status": "completed", "lastRun": "2025-05-01 08:30", "blastRadius": "Low"},
	}})
}

// RunChaosExperiment handles POST /api/v1/chaos/experiments/:id/run
func (h *NetworkOperationsHandler) RunChaosExperiment(c *gin.Context) {
	c.JSON(200, gin.H{"message": "Experiment started", "id": c.Param("id")})
}

// GetLoadTests handles GET /api/v1/load-tests
func (h *NetworkOperationsHandler) GetLoadTests(c *gin.Context) {
	c.JSON(200, gin.H{"runs": []gin.H{
		{"id": "lt-001", "name": "Baseline — Payment API", "date": "2025-04-28", "peakRPS": 420, "p95ms": 182, "errorPct": 0.4, "virtualUsers": 200, "durationSec": 300},
		{"id": "lt-002", "name": "Stress — Auth Service", "date": "2025-04-25", "peakRPS": 850, "p95ms": 374, "errorPct": 2.1, "virtualUsers": 500, "durationSec": 600},
		{"id": "lt-003", "name": "Soak — Ledger Write", "date": "2025-04-20", "peakRPS": 210, "p95ms": 143, "errorPct": 0.1, "virtualUsers": 100, "durationSec": 3600},
		{"id": "lt-004", "name": "Spike — Transfer Endpoint", "date": "2025-05-01", "peakRPS": 1200, "p95ms": 612, "errorPct": 5.8, "virtualUsers": 1000, "durationSec": 60},
	}})
}

// CreateLoadTest handles POST /api/v1/load-tests
func (h *NetworkOperationsHandler) CreateLoadTest(c *gin.Context) {
	c.JSON(201, gin.H{"message": "Load test queued", "id": "lt-005"})
}

// GetCache handles GET /api/v1/cache
func (h *NetworkOperationsHandler) GetCache(c *gin.Context) {
	c.JSON(200, gin.H{
		"summary": gin.H{"hitRate": 87.4, "missRate": 12.6, "totalKeys": 48320, "memoryUsedMB": 312},
		"namespaces": []gin.H{
			{"namespace": "session", "keys": 18200, "avgTTL": 1800, "hitRate": 94.1},
			{"namespace": "kyc-profiles", "keys": 9800, "avgTTL": 86400, "hitRate": 88.3},
			{"namespace": "exchange-rates", "keys": 42, "avgTTL": 300, "hitRate": 99.7},
			{"namespace": "agent-limits", "keys": 12400, "avgTTL": 3600, "hitRate": 81.5},
			{"namespace": "otp-codes", "keys": 7878, "avgTTL": 120, "hitRate": 72.0},
		},
		"memory": []gin.H{
			{"time": "0m", "memoryMB": 290}, {"time": "6m", "memoryMB": 295}, {"time": "12m", "memoryMB": 298},
			{"time": "18m", "memoryMB": 302}, {"time": "24m", "memoryMB": 308}, {"time": "30m", "memoryMB": 312},
			{"time": "36m", "memoryMB": 306}, {"time": "42m", "memoryMB": 310}, {"time": "48m", "memoryMB": 315},
			{"time": "54m", "memoryMB": 312},
		},
	})
}

// CacheLookup handles GET /api/v1/cache/lookup
func (h *NetworkOperationsHandler) CacheLookup(c *gin.Context) {
	c.JSON(200, gin.H{"count": 142, "pattern": c.Query("pattern")})
}

// FlushCache handles DELETE /api/v1/cache/:ns/flush
func (h *NetworkOperationsHandler) FlushCache(c *gin.Context) {
	c.JSON(200, gin.H{"message": "Namespace flushed", "namespace": c.Param("ns")})
}

// GetRetryQueue handles GET /api/v1/retry-queue
func (h *NetworkOperationsHandler) GetRetryQueue(c *gin.Context) {
	c.JSON(200, gin.H{"items": []gin.H{
		{"id": "RQ-001", "operationType": "payment", "payloadSummary": "NGN 5,000 → AGT-012", "attemptCount": 2, "nextRetryTime": "2026-05-02 10:15", "originalError": "Connection timeout to core banking"},
		{"id": "RQ-002", "operationType": "webhook", "payloadSummary": "POST https://partner.example.com/hook", "attemptCount": 4, "nextRetryTime": "2026-05-02 10:30", "originalError": "HTTP 503 from upstream"},
		{"id": "RQ-003", "operationType": "notification", "payloadSummary": "SMS to +2348012345678", "attemptCount": 1, "nextRetryTime": "2026-05-02 10:10", "originalError": "SMS gateway rate limit exceeded"},
		{"id": "RQ-004", "operationType": "settlement", "payloadSummary": "Batch settle 312 txns", "attemptCount": 3, "nextRetryTime": "2026-05-02 11:00", "originalError": "Insufficient settlement float"},
		{"id": "RQ-005", "operationType": "payment", "payloadSummary": "GHS 200 → AGT-088", "attemptCount": 1, "nextRetryTime": "2026-05-02 10:05", "originalError": "Invalid account number"},
	}})
}

// CancelRetryItem handles DELETE /api/v1/retry-queue/:id
func (h *NetworkOperationsHandler) CancelRetryItem(c *gin.Context) {
	c.JSON(200, gin.H{"message": "Item cancelled", "id": c.Param("id")})
}

// GetSIMs handles GET /api/v1/sims
func (h *NetworkOperationsHandler) GetSIMs(c *gin.Context) {
	c.JSON(200, gin.H{"sims": []gin.H{
		{"id": "SIM-0001", "carrier": "MTN", "status": "active", "signalStrength": 92, "dataUsageMB": 1420, "lastPing": "2025-05-02 10:44:30"},
		{"id": "SIM-0002", "carrier": "Airtel", "status": "active", "signalStrength": 85, "dataUsageMB": 980, "lastPing": "2025-05-02 10:44:31"},
		{"id": "SIM-0003", "carrier": "Glo", "status": "idle", "signalStrength": 60, "dataUsageMB": 220, "lastPing": "2025-05-02 10:30:05"},
		{"id": "SIM-0004", "carrier": "9Mobile", "status": "failed", "signalStrength": 0, "dataUsageMB": 0, "lastPing": "2025-05-01 22:10:00"},
		{"id": "SIM-0005", "carrier": "MTN", "status": "active", "signalStrength": 88, "dataUsageMB": 1750, "lastPing": "2025-05-02 10:44:29"},
		{"id": "SIM-0006", "carrier": "Airtel", "status": "idle", "signalStrength": 72, "dataUsageMB": 540, "lastPing": "2025-05-02 10:38:14"},
		{"id": "SIM-0007", "carrier": "Glo", "status": "active", "signalStrength": 78, "dataUsageMB": 890, "lastPing": "2025-05-02 10:44:28"},
		{"id": "SIM-0008", "carrier": "MTN", "status": "active", "signalStrength": 95, "dataUsageMB": 2100, "lastPing": "2025-05-02 10:44:33"},
	}})
}

// SIMAction handles POST /api/v1/sims/:id/:action
func (h *NetworkOperationsHandler) SIMAction(c *gin.Context) {
	c.JSON(200, gin.H{"message": "Action applied", "id": c.Param("id"), "action": c.Param("action")})
}

// GetMeshServices handles GET /api/v1/mesh/services
func (h *NetworkOperationsHandler) GetMeshServices(c *gin.Context) {
	c.JSON(200, gin.H{
		"services": []gin.H{
			{"id": "svc-01", "name": "payment-svc", "replicas": 3, "requestsPerMin": 8420, "errorRate": 0.3, "p99LatencyMs": 142, "mtlsEnabled": true},
			{"id": "svc-02", "name": "auth-svc", "replicas": 2, "requestsPerMin": 15200, "errorRate": 0.1, "p99LatencyMs": 38, "mtlsEnabled": true},
			{"id": "svc-03", "name": "ledger-svc", "replicas": 4, "requestsPerMin": 6310, "errorRate": 0.6, "p99LatencyMs": 215, "mtlsEnabled": true},
			{"id": "svc-04", "name": "agent-svc", "replicas": 3, "requestsPerMin": 4900, "errorRate": 1.2, "p99LatencyMs": 88, "mtlsEnabled": false},
			{"id": "svc-05", "name": "notification-svc", "replicas": 2, "requestsPerMin": 3100, "errorRate": 0.2, "p99LatencyMs": 55, "mtlsEnabled": true},
			{"id": "svc-06", "name": "kyc-svc", "replicas": 2, "requestsPerMin": 1200, "errorRate": 0.8, "p99LatencyMs": 330, "mtlsEnabled": false},
		},
		"circuitBreakers": []gin.H{
			{"source": "payment-svc", "destination": "ledger-svc", "state": "closed", "failureRate": 0.6, "lastTripped": "2025-04-29 11:22"},
			{"source": "agent-svc", "destination": "payment-svc", "state": "half-open", "failureRate": 4.2, "lastTripped": "2025-05-01 08:14"},
			{"source": "auth-svc", "destination": "kyc-svc", "state": "open", "failureRate": 12.5, "lastTripped": "2025-05-02 07:05"},
			{"source": "notification-svc", "destination": "auth-svc", "state": "closed", "failureRate": 0.1, "lastTripped": "2025-04-20 15:00"},
		},
	})
}

// GetSchema handles GET /api/v1/schema
func (h *NetworkOperationsHandler) GetSchema(c *gin.Context) {
	c.JSON(200, gin.H{"tables": []gin.H{
		{
			"name": "agents", "rowCount": 48200, "sizeKB": 9840,
			"columns": []gin.H{
				{"name": "id", "type": "uuid", "nullable": false, "defaultValue": "gen_random_uuid()", "index": true},
				{"name": "tenant_id", "type": "uuid", "nullable": false, "defaultValue": nil, "index": true},
				{"name": "phone", "type": "varchar(20)", "nullable": false, "defaultValue": nil, "index": true},
				{"name": "status", "type": "varchar(20)", "nullable": false, "defaultValue": "'active'", "index": false},
				{"name": "created_at", "type": "timestamptz", "nullable": false, "defaultValue": "now()", "index": false},
			},
			"foreignKeys": []gin.H{{"column": "tenant_id", "referencesTable": "tenants", "referencesColumn": "id"}},
		},
		{
			"name": "transactions", "rowCount": 4820000, "sizeKB": 1024000,
			"columns": []gin.H{
				{"name": "id", "type": "uuid", "nullable": false, "defaultValue": "gen_random_uuid()", "index": true},
				{"name": "agent_id", "type": "uuid", "nullable": false, "defaultValue": nil, "index": true},
				{"name": "amount", "type": "numeric(18,2)", "nullable": false, "defaultValue": nil, "index": false},
				{"name": "currency", "type": "char(3)", "nullable": false, "defaultValue": "'NGN'", "index": false},
				{"name": "type", "type": "varchar(30)", "nullable": false, "defaultValue": nil, "index": true},
				{"name": "status", "type": "varchar(20)", "nullable": false, "defaultValue": "'pending'", "index": true},
				{"name": "created_at", "type": "timestamptz", "nullable": false, "defaultValue": "now()", "index": false},
			},
			"foreignKeys": []gin.H{{"column": "agent_id", "referencesTable": "agents", "referencesColumn": "id"}},
		},
		{
			"name": "settlements", "rowCount": 182400, "sizeKB": 38200,
			"columns": []gin.H{
				{"name": "id", "type": "uuid", "nullable": false, "defaultValue": "gen_random_uuid()", "index": true},
				{"name": "batch_id", "type": "varchar(50)", "nullable": false, "defaultValue": nil, "index": true},
				{"name": "amount", "type": "numeric(18,2)", "nullable": false, "defaultValue": nil, "index": false},
				{"name": "status", "type": "varchar(20)", "nullable": false, "defaultValue": "'pending'", "index": true},
				{"name": "settled_at", "type": "timestamptz", "nullable": true, "defaultValue": nil, "index": false},
			},
			"foreignKeys": []gin.H{},
		},
	}})
}

// GetMQTTStats handles GET /api/v1/mqtt/stats
func (h *NetworkOperationsHandler) GetMQTTStats(c *gin.Context) {
	c.JSON(200, gin.H{
		"stats": gin.H{
			"connectedClients": 342, "messagesPerSec": 1840, "topicsCount": 56,
			"queueDepth": 128, "brokerStatus": "Connected",
		},
		"topics": []gin.H{
			{"topic": "agent/transactions/cash-in", "subscribers": 84, "messagesPerSec": 320, "lastMessage": "2025-05-02 10:44:31"},
			{"topic": "agent/transactions/cash-out", "subscribers": 84, "messagesPerSec": 280, "lastMessage": "2025-05-02 10:44:32"},
			{"topic": "agent/status/heartbeat", "subscribers": 210, "messagesPerSec": 700, "lastMessage": "2025-05-02 10:44:33"},
			{"topic": "payments/settlement/events", "subscribers": 12, "messagesPerSec": 45, "lastMessage": "2025-05-02 10:44:28"},
			{"topic": "kyc/verification/results", "subscribers": 6, "messagesPerSec": 18, "lastMessage": "2025-05-02 10:44:20"},
			{"topic": "notifications/push/dispatch", "subscribers": 48, "messagesPerSec": 210, "lastMessage": "2025-05-02 10:44:33"},
			{"topic": "system/alerts/critical", "subscribers": 5, "messagesPerSec": 2, "lastMessage": "2025-05-02 09:10:05"},
		},
	})
}

// GetOtelConfig handles GET /api/v1/otel-config
func (h *NetworkOperationsHandler) GetOtelConfig(c *gin.Context) {
	c.JSON(200, gin.H{
		"summary": gin.H{
			"tracesEnabled": true, "tracesExporter": "https://otel.54agent.upi.dev:4317", "samplingRate": 10,
			"metricsEnabled": true, "scrapeIntervalSeconds": 15,
			"logsEnabled": true, "logLevel": "info",
		},
		"exporters": []gin.H{
			{"name": "primary-otlp", "type": "OTLP", "endpoint": "https://otel.54agent.upi.dev:4317", "status": "active"},
			{"name": "jaeger-tracing", "type": "Jaeger", "endpoint": "http://jaeger.internal:14268/api/traces", "status": "active"},
			{"name": "prometheus-metrics", "type": "Prometheus", "endpoint": "http://prometheus.internal:9090/metrics", "status": "active"},
			{"name": "backup-otlp", "type": "OTLP", "endpoint": "https://backup-otel.54agent.upi.dev:4317", "status": "error"},
		},
		"services": []gin.H{
			{"service": "core-banking-api", "traceVolume": 142000},
			{"service": "agent-service", "traceVolume": 88400},
			{"service": "kyc-service", "traceVolume": 21300},
			{"service": "notification-service", "traceVolume": 64800},
			{"service": "settlement-worker", "traceVolume": 9200},
			{"service": "webhook-dispatcher", "traceVolume": 18700},
		},
	})
}

// TestOtelExporter handles POST /api/v1/otel-config/exporters/:name/test
func (h *NetworkOperationsHandler) TestOtelExporter(c *gin.Context) {
	c.JSON(200, gin.H{"status": "ok", "name": c.Param("name")})
}

// GetConnectionPools handles GET /api/v1/connection-pools
func (h *NetworkOperationsHandler) GetConnectionPools(c *gin.Context) {
	c.JSON(200, gin.H{
		"pools": []gin.H{
			{"dbName": "core-banking", "poolSize": 20, "activeConnections": 14, "idleConnections": 6, "waitingRequests": 0, "maxOverflow": 10},
			{"dbName": "audit-logs", "poolSize": 10, "activeConnections": 3, "idleConnections": 7, "waitingRequests": 0, "maxOverflow": 5},
			{"dbName": "kyc-store", "poolSize": 15, "activeConnections": 11, "idleConnections": 2, "waitingRequests": 3, "maxOverflow": 8},
			{"dbName": "analytics", "poolSize": 8, "activeConnections": 8, "idleConnections": 0, "waitingRequests": 7, "maxOverflow": 4},
		},
		"peaks": []gin.H{
			{"dbName": "core-banking", "peakActive": 18, "peakTime": "2026-05-01 09:14", "utilization": 90},
			{"dbName": "kyc-store", "peakActive": 14, "peakTime": "2026-04-30 14:22", "utilization": 93},
			{"dbName": "analytics", "peakActive": 8, "peakTime": "2026-05-02 08:00", "utilization": 100},
			{"dbName": "audit-logs", "peakActive": 6, "peakTime": "2026-04-28 11:05", "utilization": 60},
		},
	})
}

// GetConnectionQuality handles GET /api/v1/connection-quality
func (h *NetworkOperationsHandler) GetConnectionQuality(c *gin.Context) {
	c.JSON(200, gin.H{
		"metrics": gin.H{"avgLatency": 124, "packetLoss": 0.8, "jitter": 18, "successRate": 99.2},
		"agents": []gin.H{
			{"agentId": "AGT-001", "location": "Lagos, NG", "qualityScore": "Excellent", "lastSeen": "2s ago"},
			{"agentId": "AGT-002", "location": "Abuja, NG", "qualityScore": "Good", "lastSeen": "15s ago"},
			{"agentId": "AGT-003", "location": "Kano, NG", "qualityScore": "Poor", "lastSeen": "2m ago"},
			{"agentId": "AGT-004", "location": "Accra, GH", "qualityScore": "Excellent", "lastSeen": "1s ago"},
			{"agentId": "AGT-005", "location": "Nairobi, KE", "qualityScore": "Offline", "lastSeen": "18m ago"},
			{"agentId": "AGT-006", "location": "Dar es Salaam, TZ", "qualityScore": "Good", "lastSeen": "30s ago"},
		},
		"chart": []gin.H{
			{"time": "0m", "latency": 112, "packetLoss": 0.4}, {"time": "5m", "latency": 118, "packetLoss": 0.6},
			{"time": "10m", "latency": 124, "packetLoss": 0.9}, {"time": "15m", "latency": 131, "packetLoss": 1.1},
			{"time": "20m", "latency": 119, "packetLoss": 0.7}, {"time": "25m", "latency": 126, "packetLoss": 0.8},
			{"time": "30m", "latency": 122, "packetLoss": 0.5}, {"time": "35m", "latency": 135, "packetLoss": 1.3},
			{"time": "40m", "latency": 128, "packetLoss": 0.9}, {"time": "45m", "latency": 124, "packetLoss": 0.8},
			{"time": "50m", "latency": 120, "packetLoss": 0.6}, {"time": "55m", "latency": 117, "packetLoss": 0.4},
		},
	})
}

// GetCarriers handles GET /api/v1/carriers
func (h *NetworkOperationsHandler) GetCarriers(c *gin.Context) {
	c.JSON(200, gin.H{
		"costs": []gin.H{
			{"carrier": "MTN", "perSMSCost": 4.5, "perCallCost": 22, "monthlyMin": 50000, "totalSpend": 182400},
			{"carrier": "Airtel", "perSMSCost": 4.0, "perCallCost": 20, "monthlyMin": 30000, "totalSpend": 98700},
			{"carrier": "Glo", "perSMSCost": 3.8, "perCallCost": 18, "monthlyMin": 20000, "totalSpend": 67200},
			{"carrier": "9Mobile", "perSMSCost": 4.2, "perCallCost": 21, "monthlyMin": 15000, "totalSpend": 41500},
		},
		"slas": []gin.H{
			{"carrier": "MTN", "uptimeTarget": 99.9, "uptimeActual": 99.7, "deliveryTarget": 98, "deliveryActual": 97.2, "latencyTargetMs": 300, "latencyActualMs": 284},
			{"carrier": "Airtel", "uptimeTarget": 99.5, "uptimeActual": 99.6, "deliveryTarget": 97, "deliveryActual": 98.1, "latencyTargetMs": 350, "latencyActualMs": 320},
			{"carrier": "Glo", "uptimeTarget": 99.0, "uptimeActual": 98.4, "deliveryTarget": 95, "deliveryActual": 94.1, "latencyTargetMs": 400, "latencyActualMs": 445},
			{"carrier": "9Mobile", "uptimeTarget": 99.0, "uptimeActual": 99.1, "deliveryTarget": 96, "deliveryActual": 95.8, "latencyTargetMs": 380, "latencyActualMs": 362},
		},
		"rules": []gin.H{
			{"id": "rule-01", "fromCarrier": "MTN", "condition": "error_rate > ", "threshold": 5, "toCarrier": "Airtel", "enabled": true},
			{"id": "rule-02", "fromCarrier": "Airtel", "condition": "error_rate > ", "threshold": 8, "toCarrier": "Glo", "enabled": true},
			{"id": "rule-03", "fromCarrier": "Glo", "condition": "latency_ms > ", "threshold": 500, "toCarrier": "MTN", "enabled": false},
		},
	})
}

// GetArchival handles GET /api/v1/archival
func (h *NetworkOperationsHandler) GetArchival(c *gin.Context) {
	c.JSON(200, gin.H{
		"policies": []gin.H{
			{"entityType": "transactions", "retentionDays": 365, "archiveAfterDays": 180, "storageTarget": "S3", "lastRun": "2026-05-01 02:00", "recordsArchived": 142800},
			{"entityType": "audit-logs", "retentionDays": 730, "archiveAfterDays": 365, "storageTarget": "cold-storage", "lastRun": "2026-04-30 03:00", "recordsArchived": 980200},
			{"entityType": "kyc-docs", "retentionDays": 2555, "archiveAfterDays": 730, "storageTarget": "S3", "lastRun": "2026-04-15 01:00", "recordsArchived": 12400},
		},
		"jobs": []gin.H{
			{"name": "transactions-archive-20260501", "started": "2026-05-01 02:00", "completed": "2026-05-01 02:48", "recordsMoved": 142800, "sizeMB": 2840},
			{"name": "audit-logs-archive-20260430", "started": "2026-04-30 03:00", "completed": "2026-04-30 04:21", "recordsMoved": 980200, "sizeMB": 9802},
			{"name": "kyc-docs-archive-20260415", "started": "2026-04-15 01:00", "completed": "2026-04-15 01:12", "recordsMoved": 12400, "sizeMB": 18600},
		},
	})
}

// RunArchivalJob handles POST /api/v1/archival/:entityType/run
func (h *NetworkOperationsHandler) RunArchivalJob(c *gin.Context) {
	c.JSON(200, gin.H{"message": "Archival job started", "entityType": c.Param("entityType")})
}

// GetBillers handles GET /api/v1/billers
func (h *NetworkOperationsHandler) GetBillers(c *gin.Context) {
	billers := []gin.H{
		{"id": "dstv", "name": "DStv", "category": "cable", "provider": "multichoice", "active": true},
		{"id": "gotv", "name": "GOtv", "category": "cable", "provider": "multichoice", "active": true},
		{"id": "startimes", "name": "Startimes", "category": "cable", "provider": "startimes", "active": true},
		{"id": "aedc", "name": "AEDC (Abuja Electric)", "category": "electricity", "provider": "aedc", "active": true},
		{"id": "ikedc", "name": "IKEDC (Ikeja Electric)", "category": "electricity", "provider": "ikedc", "active": true},
		{"id": "ekedc", "name": "EKEDC (Eko Electric)", "category": "electricity", "provider": "ekedc", "active": true},
		{"id": "bedc", "name": "BEDC (Benin Electric)", "category": "electricity", "provider": "bedc", "active": true},
		{"id": "kedco", "name": "KEDCO (Kano Electric)", "category": "electricity", "provider": "kedco", "active": true},
		{"id": "phcn-prepaid", "name": "PHCN Prepaid Meter", "category": "electricity", "provider": "phcn", "active": true},
		{"id": "lawma", "name": "LAWMA (Lagos Water)", "category": "water", "provider": "lawma", "active": true},
		{"id": "fct-water", "name": "FCT Water Board", "category": "water", "provider": "fct-water", "active": true},
		{"id": "remita", "name": "Remita (Govt Payments)", "category": "government", "provider": "remita", "active": true},
		{"id": "mtn-airtime", "name": "MTN Airtime", "category": "airtime", "provider": "mtn", "active": true},
		{"id": "airtel-airtime", "name": "Airtel Airtime", "category": "airtime", "provider": "airtel", "active": true},
		{"id": "glo-airtime", "name": "Glo Airtime", "category": "airtime", "provider": "glo", "active": true},
		{"id": "9mobile-airtime", "name": "9mobile Airtime", "category": "airtime", "provider": "9mobile", "active": true},
	}
	c.JSON(200, gin.H{"billers": billers, "total": len(billers)})
}

// GetBillersByCategory handles GET /api/v1/billers/:category
func (h *NetworkOperationsHandler) GetBillersByCategory(c *gin.Context) {
	category := c.Param("category")
	allBillers := []gin.H{
		{"id": "dstv", "name": "DStv", "category": "cable", "provider": "multichoice", "active": true},
		{"id": "gotv", "name": "GOtv", "category": "cable", "provider": "multichoice", "active": true},
		{"id": "startimes", "name": "Startimes", "category": "cable", "provider": "startimes", "active": true},
		{"id": "aedc", "name": "AEDC (Abuja Electric)", "category": "electricity", "provider": "aedc", "active": true},
		{"id": "ikedc", "name": "IKEDC (Ikeja Electric)", "category": "electricity", "provider": "ikedc", "active": true},
		{"id": "ekedc", "name": "EKEDC (Eko Electric)", "category": "electricity", "provider": "ekedc", "active": true},
		{"id": "bedc", "name": "BEDC (Benin Electric)", "category": "electricity", "provider": "bedc", "active": true},
		{"id": "kedco", "name": "KEDCO (Kano Electric)", "category": "electricity", "provider": "kedco", "active": true},
		{"id": "phcn-prepaid", "name": "PHCN Prepaid Meter", "category": "electricity", "provider": "phcn", "active": true},
		{"id": "lawma", "name": "LAWMA (Lagos Water)", "category": "water", "provider": "lawma", "active": true},
		{"id": "fct-water", "name": "FCT Water Board", "category": "water", "provider": "fct-water", "active": true},
		{"id": "remita", "name": "Remita (Govt Payments)", "category": "government", "provider": "remita", "active": true},
		{"id": "mtn-airtime", "name": "MTN Airtime", "category": "airtime", "provider": "mtn", "active": true},
		{"id": "airtel-airtime", "name": "Airtel Airtime", "category": "airtime", "provider": "airtel", "active": true},
		{"id": "glo-airtime", "name": "Glo Airtime", "category": "airtime", "provider": "glo", "active": true},
		{"id": "9mobile-airtime", "name": "9mobile Airtime", "category": "airtime", "provider": "9mobile", "active": true},
		{"id": "mtn-data", "name": "MTN Data", "category": "data", "provider": "mtn", "active": true},
		{"id": "airtel-data", "name": "Airtel Data", "category": "data", "provider": "airtel", "active": true},
		{"id": "glo-data", "name": "Glo Data", "category": "data", "provider": "glo", "active": true},
		{"id": "9mobile-data", "name": "9mobile Data", "category": "data", "provider": "9mobile", "active": true},
	}
	filtered := []gin.H{}
	for _, b := range allBillers {
		if b["category"] == category || category == "all" {
			filtered = append(filtered, b)
		}
	}
	c.JSON(200, gin.H{"billers": filtered, "category": category, "total": len(filtered)})
}

// GetProviders handles GET /api/v1/providers
func (h *NetworkOperationsHandler) GetProviders(c *gin.Context) {
	providers := []gin.H{
		{"id": "mtn", "name": "MTN", "color": "#FFCC00", "prefixes": "0803, 0806, 0813, 0816, 0703, 0706", "active": true, "type": "mobile"},
		{"id": "airtel", "name": "Airtel", "color": "#FF0000", "prefixes": "0802, 0808, 0812, 0701, 0708", "active": true, "type": "mobile"},
		{"id": "glo", "name": "Glo", "color": "#00A651", "prefixes": "0805, 0807, 0815, 0811, 0705", "active": true, "type": "mobile"},
		{"id": "9mobile", "name": "9mobile", "color": "#006633", "prefixes": "0809, 0817, 0818, 0909, 0908", "active": true, "type": "mobile"},
	}
	c.JSON(200, gin.H{"providers": providers, "total": len(providers)})
}

// GetNetworkTelemetry handles GET /api/network/telemetry
func (h *NetworkOperationsHandler) GetNetworkTelemetry(c *gin.Context) {
	c.JSON(200, gin.H{
		"regions": []gin.H{
			{"region": "Lagos", "nodes": 12, "avgLatencyMs": 18, "packetLoss": 0.2, "jitterMs": 2.1, "status": "healthy"},
			{"region": "Abuja", "nodes": 8, "avgLatencyMs": 24, "packetLoss": 0.5, "jitterMs": 3.4, "status": "healthy"},
			{"region": "Kano", "nodes": 5, "avgLatencyMs": 42, "packetLoss": 1.8, "jitterMs": 6.2, "status": "degraded"},
			{"region": "Port Harcourt", "nodes": 6, "avgLatencyMs": 31, "packetLoss": 0.9, "jitterMs": 4.0, "status": "healthy"},
			{"region": "Ibadan", "nodes": 4, "avgLatencyMs": 55, "packetLoss": 3.1, "jitterMs": 9.5, "status": "critical"},
			{"region": "Enugu", "nodes": 3, "avgLatencyMs": 38, "packetLoss": 1.2, "jitterMs": 5.1, "status": "degraded"},
		},
		"latency": []gin.H{
			{"time": "00:00", "latencyMs": 22}, {"time": "01:00", "latencyMs": 19}, {"time": "02:00", "latencyMs": 21},
			{"time": "03:00", "latencyMs": 18}, {"time": "04:00", "latencyMs": 20}, {"time": "05:00", "latencyMs": 24},
			{"time": "06:00", "latencyMs": 28}, {"time": "07:00", "latencyMs": 32}, {"time": "08:00", "latencyMs": 35},
			{"time": "09:00", "latencyMs": 29}, {"time": "10:00", "latencyMs": 26}, {"time": "11:00", "latencyMs": 23},
			{"time": "12:00", "latencyMs": 27}, {"time": "13:00", "latencyMs": 31}, {"time": "14:00", "latencyMs": 25},
			{"time": "15:00", "latencyMs": 22}, {"time": "16:00", "latencyMs": 24}, {"time": "17:00", "latencyMs": 30},
			{"time": "18:00", "latencyMs": 33}, {"time": "19:00", "latencyMs": 28}, {"time": "20:00", "latencyMs": 25},
			{"time": "21:00", "latencyMs": 22}, {"time": "22:00", "latencyMs": 20}, {"time": "23:00", "latencyMs": 19},
		},
	})
}
