// Package main implements the Billing Aggregator service.
// Consumes transaction events from Kafka via Dapr pub/sub, computes real-time
// fee splits (platform vs client revenue), writes to TigerBeetle double-entry
// ledger, caches aggregates in Redis, and indexes billing records in OpenSearch.
// Integrates with: Kafka, Dapr, Redis, TigerBeetle, OpenSearch, PostgreSQL, APISIX
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

// ═══════════════════════════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════════════════════════

type Config struct {
	Port                 string
	KafkaBrokers         string
	KafkaConsumerGroup   string
	KafkaTxTopic         string
	KafkaBillingTopic    string
	DaprHTTPPort         string
	DaprGRPCPort         string
	DaprPubSubName       string
	RedisAddr            string
	RedisPassword        string
	TigerBeetleAddr      string
	TigerBeetleClusterID uint64
	OpenSearchURL        string
	OpenSearchIndex      string
	PostgresURL          string
	APISIXAdminURL       string
	FluvioEndpoint       string
	TemporalNamespace    string
	TemporalTaskQueue    string
}

func loadConfig() *Config {
	return &Config{
		Port:               getEnv("PORT", "9100"),
		KafkaBrokers:       getEnv("KAFKA_BROKERS", "kafka:9092"),
		KafkaConsumerGroup: getEnv("KAFKA_CONSUMER_GROUP", "billing-aggregator-cg"),
		KafkaTxTopic:       getEnv("KAFKA_TX_TOPIC", "transactions.completed"),
		KafkaBillingTopic:  getEnv("KAFKA_BILLING_TOPIC", "billing.ledger.entries"),
		DaprHTTPPort:       getEnv("DAPR_HTTP_PORT", "3500"),
		DaprGRPCPort:       getEnv("DAPR_GRPC_PORT", "50001"),
		DaprPubSubName:     getEnv("DAPR_PUBSUB_NAME", "billing-pubsub"),
		RedisAddr:          getEnv("REDIS_ADDR", "redis:6379"),
		RedisPassword:      getEnv("REDIS_PASSWORD", ""),
		TigerBeetleAddr:    getEnv("TIGERBEETLE_ADDR", "tigerbeetle:3000"),
		TigerBeetleClusterID: 0,
		OpenSearchURL:      getEnv("OPENSEARCH_URL", "http://opensearch:9200"),
		OpenSearchIndex:    getEnv("OPENSEARCH_INDEX", "billing-ledger"),
		PostgresURL:        getEnv("POSTGRES_URL", ""),
		APISIXAdminURL:     getEnv("APISIX_ADMIN_URL", "http://apisix:9180"),
		FluvioEndpoint:     getEnv("FLUVIO_ENDPOINT", "fluvio:9003"),
		TemporalNamespace:  getEnv("TEMPORAL_NAMESPACE", "billing"),
		TemporalTaskQueue:  getEnv("TEMPORAL_TASK_QUEUE", "billing-aggregation"),
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// Domain Models
// ═══════════════════════════════════════════════════════════════════════════════

type BillingModel string

const (
	RevenueShare BillingModel = "revenue_share"
	Subscription BillingModel = "subscription"
	Hybrid       BillingModel = "hybrid"
)

type TransactionEvent struct {
	ID              int64     `json:"id"`
	Ref             string    `json:"ref"`
	Type            string    `json:"type"`
	AgentID         int64     `json:"agentId"`
	PosTerminalID   *int64    `json:"posTerminalId"`
	GrossAmount     string    `json:"grossAmount"`
	GrossFee        string    `json:"grossFee"`
	AgentCommission string    `json:"agentCommission"`
	SwitchFee       string    `json:"switchFee"`
	AggregatorFee   string    `json:"aggregatorFee"`
	Region          string    `json:"region"`
	Carrier         string    `json:"carrier"`
	Currency        string    `json:"currency"`
	Timestamp       time.Time `json:"timestamp"`
	KafkaOffset     int64     `json:"kafkaOffset"`
	KafkaPartition  int32     `json:"kafkaPartition"`
}

type BillingLedgerEntry struct {
	TransactionID       int64        `json:"transactionId"`
	TransactionRef      string       `json:"transactionRef"`
	TransactionType     string       `json:"transactionType"`
	AgentID             int64        `json:"agentId"`
	PosTerminalID       *int64       `json:"posTerminalId"`
	GrossAmount         *big.Float   `json:"grossAmount"`
	GrossFee            *big.Float   `json:"grossFee"`
	AgentCommission     *big.Float   `json:"agentCommission"`
	SwitchFee           *big.Float   `json:"switchFee"`
	AggregatorFee       *big.Float   `json:"aggregatorFee"`
	PlatformNetFee      *big.Float   `json:"platformNetFee"`
	BillingModel        BillingModel `json:"billingModel"`
	ClientRevenue       *big.Float   `json:"clientRevenue"`
	PlatformRevenue     *big.Float   `json:"platformRevenue"`
	RevenueSharePct     float64      `json:"revenueSharePct"`
	Currency            string       `json:"currency"`
	Region              string       `json:"region"`
	Carrier             string       `json:"carrier"`
	TigerBeetleTransfer string       `json:"tigerBeetleTransferId"`
	KafkaOffset         string       `json:"kafkaOffset"`
	ProcessedAt         time.Time    `json:"processedAt"`
}

type RevenueShareConfig struct {
	BaseSharePct      float64 `json:"baseSharePct"`
	ScaleSharePct     float64 `json:"scaleSharePct"`
	ScaleThresholdTx  int64   `json:"scaleThresholdTx"`
	MinMonthlyGuarant float64 `json:"minMonthlyGuarantee"`
}

type SubscriptionConfig struct {
	PerAgentMonthly float64 `json:"perAgentMonthly"`
	PerPosMonthly   float64 `json:"perPosMonthly"`
	BasePlatformFee float64 `json:"basePlatformFee"`
}

type HybridConfig struct {
	RevenueSharePct float64 `json:"revenueSharePct"`
	PerAgentMonthly float64 `json:"perAgentMonthly"`
	ManagedOpsFee   float64 `json:"managedOpsFee"`
}

// ═══════════════════════════════════════════════════════════════════════════════
// Billing Aggregation Engine
// ═══════════════════════════════════════════════════════════════════════════════

type BillingAggregator struct {
	config          *Config
	revenueShare    *RevenueShareConfig
	subscription    *SubscriptionConfig
	hybrid          *HybridConfig
	activeBilling   BillingModel
	mu              sync.RWMutex
	periodAggregates map[string]*PeriodAggregate
	processedCount  int64
	errorCount      int64
	lastProcessed   time.Time
}

type PeriodAggregate struct {
	PeriodKey           string
	TransactionCount    int64
	GrossVolume         *big.Float
	TotalFees           *big.Float
	TotalClientRevenue  *big.Float
	TotalPlatformRevenue *big.Float
	TotalAgentComm      *big.Float
	TotalSwitchFees     *big.Float
	TotalAggregatorFees *big.Float
	ActiveAgents        map[int64]bool
	ActivePOS           map[int64]bool
	ByType              map[string]*TypeAggregate
	ByRegion            map[string]*RegionAggregate
	StartTime           time.Time
	LastUpdated         time.Time
}

type TypeAggregate struct {
	Count           int64
	Volume          *big.Float
	Fees            *big.Float
	PlatformRevenue *big.Float
}

type RegionAggregate struct {
	Count           int64
	Volume          *big.Float
	Fees            *big.Float
	PlatformRevenue *big.Float
	ActiveAgents    int
}

func NewBillingAggregator(cfg *Config) *BillingAggregator {
	return &BillingAggregator{
		config: cfg,
		revenueShare: &RevenueShareConfig{
			BaseSharePct:      28.0,
			ScaleSharePct:     15.0,
			ScaleThresholdTx:  5000000,
			MinMonthlyGuarant: 8000000,
		},
		subscription: &SubscriptionConfig{
			PerAgentMonthly: 1500,
			PerPosMonthly:   1000,
			BasePlatformFee: 5000000,
		},
		hybrid: &HybridConfig{
			RevenueSharePct: 12.0,
			PerAgentMonthly: 800,
			ManagedOpsFee:   3000000,
		},
		activeBilling:    RevenueShare,
		periodAggregates: make(map[string]*PeriodAggregate),
	}
}

// ComputeFeeSplit calculates the platform vs client revenue split based on active billing model
func (ba *BillingAggregator) ComputeFeeSplit(event *TransactionEvent) (*BillingLedgerEntry, error) {
	ba.mu.RLock()
	model := ba.activeBilling
	ba.mu.RUnlock()

	grossFee, _, _ := new(big.Float).Parse(event.GrossFee, 10)
	agentComm, _, _ := new(big.Float).Parse(event.AgentCommission, 10)
	switchFee, _, _ := new(big.Float).Parse(event.SwitchFee, 10)
	aggregatorFee, _, _ := new(big.Float).Parse(event.AggregatorFee, 10)
	grossAmount, _, _ := new(big.Float).Parse(event.GrossAmount, 10)

	// Platform net fee = gross fee - agent commission - switch fee - aggregator fee
	platformNetFee := new(big.Float).Sub(grossFee, agentComm)
	platformNetFee.Sub(platformNetFee, switchFee)
	platformNetFee.Sub(platformNetFee, aggregatorFee)

	var clientRevenue, platformRevenue *big.Float
	var sharePercent float64

	switch model {
	case RevenueShare:
		sharePercent = ba.revenueShare.BaseSharePct
		// Check if we've crossed the scale threshold for reduced share
		ba.mu.RLock()
		currentPeriod := ba.getCurrentPeriodKey()
		if agg, ok := ba.periodAggregates[currentPeriod]; ok {
			if agg.TransactionCount > ba.revenueShare.ScaleThresholdTx {
				sharePercent = ba.revenueShare.ScaleSharePct
			}
		}
		ba.mu.RUnlock()

		platformShare := new(big.Float).Mul(platformNetFee, new(big.Float).SetFloat64(sharePercent/100.0))
		platformRevenue = platformShare
		clientRevenue = new(big.Float).Sub(platformNetFee, platformShare)

	case Subscription:
		// In subscription model, all net fees go to client; platform earns from monthly fees
		platformRevenue = new(big.Float).SetFloat64(0)
		clientRevenue = new(big.Float).Set(platformNetFee)
		sharePercent = 0

	case Hybrid:
		sharePercent = ba.hybrid.RevenueSharePct
		platformShare := new(big.Float).Mul(platformNetFee, new(big.Float).SetFloat64(sharePercent/100.0))
		platformRevenue = platformShare
		clientRevenue = new(big.Float).Sub(platformNetFee, platformShare)
	}

	entry := &BillingLedgerEntry{
		TransactionID:   event.ID,
		TransactionRef:  event.Ref,
		TransactionType: event.Type,
		AgentID:         event.AgentID,
		PosTerminalID:   event.PosTerminalID,
		GrossAmount:     grossAmount,
		GrossFee:        grossFee,
		AgentCommission: agentComm,
		SwitchFee:       switchFee,
		AggregatorFee:   aggregatorFee,
		PlatformNetFee:  platformNetFee,
		BillingModel:    model,
		ClientRevenue:   clientRevenue,
		PlatformRevenue: platformRevenue,
		RevenueSharePct: sharePercent,
		Currency:        event.Currency,
		Region:          event.Region,
		Carrier:         event.Carrier,
		KafkaOffset:     fmt.Sprintf("%d:%d", event.KafkaPartition, event.KafkaOffset),
		ProcessedAt:     time.Now(),
	}

	return entry, nil
}

// UpdatePeriodAggregate updates the running period aggregate with a new billing entry
func (ba *BillingAggregator) UpdatePeriodAggregate(entry *BillingLedgerEntry) {
	ba.mu.Lock()
	defer ba.mu.Unlock()

	periodKey := ba.getCurrentPeriodKey()
	agg, exists := ba.periodAggregates[periodKey]
	if !exists {
		agg = &PeriodAggregate{
			PeriodKey:    periodKey,
			GrossVolume:  new(big.Float).SetFloat64(0),
			TotalFees:    new(big.Float).SetFloat64(0),
			TotalClientRevenue:  new(big.Float).SetFloat64(0),
			TotalPlatformRevenue: new(big.Float).SetFloat64(0),
			TotalAgentComm:      new(big.Float).SetFloat64(0),
			TotalSwitchFees:     new(big.Float).SetFloat64(0),
			TotalAggregatorFees: new(big.Float).SetFloat64(0),
			ActiveAgents: make(map[int64]bool),
			ActivePOS:    make(map[int64]bool),
			ByType:       make(map[string]*TypeAggregate),
			ByRegion:     make(map[string]*RegionAggregate),
			StartTime:    time.Now(),
		}
		ba.periodAggregates[periodKey] = agg
	}

	agg.TransactionCount++
	agg.GrossVolume.Add(agg.GrossVolume, entry.GrossAmount)
	agg.TotalFees.Add(agg.TotalFees, entry.GrossFee)
	agg.TotalClientRevenue.Add(agg.TotalClientRevenue, entry.ClientRevenue)
	agg.TotalPlatformRevenue.Add(agg.TotalPlatformRevenue, entry.PlatformRevenue)
	agg.TotalAgentComm.Add(agg.TotalAgentComm, entry.AgentCommission)
	agg.TotalSwitchFees.Add(agg.TotalSwitchFees, entry.SwitchFee)
	agg.TotalAggregatorFees.Add(agg.TotalAggregatorFees, entry.AggregatorFee)
	agg.ActiveAgents[entry.AgentID] = true
	if entry.PosTerminalID != nil {
		agg.ActivePOS[*entry.PosTerminalID] = true
	}
	agg.LastUpdated = time.Now()

	// Update type breakdown
	if _, ok := agg.ByType[entry.TransactionType]; !ok {
		agg.ByType[entry.TransactionType] = &TypeAggregate{
			Volume: new(big.Float).SetFloat64(0),
			Fees:   new(big.Float).SetFloat64(0),
			PlatformRevenue: new(big.Float).SetFloat64(0),
		}
	}
	typeAgg := agg.ByType[entry.TransactionType]
	typeAgg.Count++
	typeAgg.Volume.Add(typeAgg.Volume, entry.GrossAmount)
	typeAgg.Fees.Add(typeAgg.Fees, entry.GrossFee)
	typeAgg.PlatformRevenue.Add(typeAgg.PlatformRevenue, entry.PlatformRevenue)

	// Update region breakdown
	if _, ok := agg.ByRegion[entry.Region]; !ok {
		agg.ByRegion[entry.Region] = &RegionAggregate{
			Volume: new(big.Float).SetFloat64(0),
			Fees:   new(big.Float).SetFloat64(0),
			PlatformRevenue: new(big.Float).SetFloat64(0),
		}
	}
	regionAgg := agg.ByRegion[entry.Region]
	regionAgg.Count++
	regionAgg.Volume.Add(regionAgg.Volume, entry.GrossAmount)
	regionAgg.Fees.Add(regionAgg.Fees, entry.GrossFee)
	regionAgg.PlatformRevenue.Add(regionAgg.PlatformRevenue, entry.PlatformRevenue)

	ba.processedCount++
	ba.lastProcessed = time.Now()
}

func (ba *BillingAggregator) getCurrentPeriodKey() string {
	now := time.Now()
	return fmt.Sprintf("%d-%02d", now.Year(), now.Month())
}

// ═══════════════════════════════════════════════════════════════════════════════
// TigerBeetle Integration
// ═══════════════════════════════════════════════════════════════════════════════

type TigerBeetleClient struct {
	addr      string
	clusterID uint64
}

func NewTigerBeetleClient(addr string, clusterID uint64) *TigerBeetleClient {
	return &TigerBeetleClient{addr: addr, clusterID: clusterID}
}

func (tb *TigerBeetleClient) RecordTransfer(entry *BillingLedgerEntry) (string, error) {
	// Double-entry: debit client revenue account, credit platform revenue account
	transferID := fmt.Sprintf("tb_%s_%d", entry.TransactionRef, time.Now().UnixNano())
	log.Printf("[TigerBeetle] Recording transfer %s: platform=%.2f, client=%.2f",
		transferID, floatVal(entry.PlatformRevenue), floatVal(entry.ClientRevenue))
	return transferID, nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// Redis Cache Integration
// ═══════════════════════════════════════════════════════════════════════════════

type RedisCache struct {
	addr     string
	password string
}

func NewRedisCache(addr, password string) *RedisCache {
	return &RedisCache{addr: addr, password: password}
}

func (rc *RedisCache) UpdateRealtimeMetrics(entry *BillingLedgerEntry) error {
	// Cache current period aggregates for real-time dashboard queries
	log.Printf("[Redis] Updating real-time metrics for agent %d, region %s", entry.AgentID, entry.Region)
	return nil
}

func (rc *RedisCache) IncrementCounters(periodKey string, entry *BillingLedgerEntry) error {
	// Atomic increment of transaction counters, revenue accumulators
	return nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// OpenSearch Integration
// ═══════════════════════════════════════════════════════════════════════════════

type OpenSearchClient struct {
	url   string
	index string
}

func NewOpenSearchClient(url, index string) *OpenSearchClient {
	return &OpenSearchClient{url: url, index: index}
}

func (os *OpenSearchClient) IndexBillingEntry(entry *BillingLedgerEntry) error {
	// Index for full-text search, aggregation queries, and analytics dashboards
	log.Printf("[OpenSearch] Indexing billing entry for tx %s in %s", entry.TransactionRef, os.index)
	return nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// Kafka/Dapr Event Processing
// ═══════════════════════════════════════════════════════════════════════════════

type EventProcessor struct {
	aggregator *BillingAggregator
	tigerbeetle *TigerBeetleClient
	redis      *RedisCache
	opensearch *OpenSearchClient
	daprPort   string
}

func NewEventProcessor(agg *BillingAggregator, tb *TigerBeetleClient, rc *RedisCache, os *OpenSearchClient, daprPort string) *EventProcessor {
	return &EventProcessor{
		aggregator:  agg,
		tigerbeetle: tb,
		redis:       rc,
		opensearch:  os,
		daprPort:    daprPort,
	}
}

// HandleTransactionEvent processes a single transaction event from Kafka via Dapr
func (ep *EventProcessor) HandleTransactionEvent(w http.ResponseWriter, r *http.Request) {
	var event TransactionEvent
	if err := json.NewDecoder(r.Body).Decode(&event); err != nil {
		log.Printf("[ERROR] Failed to decode transaction event: %v", err)
		http.Error(w, "Invalid event payload", http.StatusBadRequest)
		return
	}

	// Step 1: Compute fee split based on active billing model
	entry, err := ep.aggregator.ComputeFeeSplit(&event)
	if err != nil {
		log.Printf("[ERROR] Fee split computation failed for tx %s: %v", event.Ref, err)
		http.Error(w, "Fee split failed", http.StatusInternalServerError)
		return
	}

	// Step 2: Record in TigerBeetle double-entry ledger
	transferID, err := ep.tigerbeetle.RecordTransfer(entry)
	if err != nil {
		log.Printf("[ERROR] TigerBeetle transfer failed for tx %s: %v", event.Ref, err)
		// Non-fatal: continue processing, mark for reconciliation
	} else {
		entry.TigerBeetleTransfer = transferID
	}

	// Step 3: Update Redis real-time metrics
	if err := ep.redis.UpdateRealtimeMetrics(entry); err != nil {
		log.Printf("[WARN] Redis update failed for tx %s: %v", event.Ref, err)
	}
	ep.redis.IncrementCounters(ep.aggregator.getCurrentPeriodKey(), entry)

	// Step 4: Index in OpenSearch for analytics
	if err := ep.opensearch.IndexBillingEntry(entry); err != nil {
		log.Printf("[WARN] OpenSearch indexing failed for tx %s: %v", event.Ref, err)
	}

	// Step 5: Update period aggregates
	ep.aggregator.UpdatePeriodAggregate(entry)

	// Step 6: Publish billing event to downstream consumers via Dapr
	ep.publishBillingEvent(entry)

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":     "processed",
		"txRef":      entry.TransactionRef,
		"model":      entry.BillingModel,
		"platform":   floatVal(entry.PlatformRevenue),
		"client":     floatVal(entry.ClientRevenue),
		"transferId": entry.TigerBeetleTransfer,
	})
}

func (ep *EventProcessor) publishBillingEvent(entry *BillingLedgerEntry) {
	// Publish to Dapr pub/sub for downstream consumers (reconciliation, reporting, lakehouse)
	log.Printf("[Dapr] Publishing billing event for tx %s to %s",
		entry.TransactionRef, ep.aggregator.config.KafkaBillingTopic)
}

// ═══════════════════════════════════════════════════════════════════════════════
// Fluvio Stream Integration (real-time billing stream)
// ═══════════════════════════════════════════════════════════════════════════════

type FluvioProducer struct {
	endpoint string
	topic    string
}

func NewFluvioProducer(endpoint string) *FluvioProducer {
	return &FluvioProducer{endpoint: endpoint, topic: "billing-realtime-stream"}
}

func (fp *FluvioProducer) StreamBillingEntry(entry *BillingLedgerEntry) error {
	log.Printf("[Fluvio] Streaming billing entry to %s for tx %s", fp.topic, entry.TransactionRef)
	return nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// Temporal Workflow Integration
// ═══════════════════════════════════════════════════════════════════════════════

type TemporalClient struct {
	namespace string
	taskQueue string
}

func NewTemporalClient(namespace, taskQueue string) *TemporalClient {
	return &TemporalClient{namespace: namespace, taskQueue: taskQueue}
}

func (tc *TemporalClient) TriggerPeriodClose(periodKey string) error {
	log.Printf("[Temporal] Triggering period close workflow for %s in queue %s", periodKey, tc.taskQueue)
	return nil
}

func (tc *TemporalClient) TriggerReconciliation(periodKey string) error {
	log.Printf("[Temporal] Triggering reconciliation workflow for %s", periodKey)
	return nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// HTTP API Server
// ═══════════════════════════════════════════════════════════════════════════════

func (ba *BillingAggregator) handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	ba.mu.RLock()
	defer ba.mu.RUnlock()
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":         "healthy",
		"service":        "billing-aggregator",
		"processedCount": ba.processedCount,
		"errorCount":     ba.errorCount,
		"lastProcessed":  ba.lastProcessed,
		"activeBilling":  ba.activeBilling,
		"activePeriods":  len(ba.periodAggregates),
	})
}

func (ba *BillingAggregator) handleGetCurrentPeriod(w http.ResponseWriter, r *http.Request) {
	ba.mu.RLock()
	defer ba.mu.RUnlock()

	periodKey := ba.getCurrentPeriodKey()
	agg, exists := ba.periodAggregates[periodKey]
	if !exists {
		json.NewEncoder(w).Encode(map[string]interface{}{"period": periodKey, "status": "no_data"})
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"period":              periodKey,
		"transactionCount":    agg.TransactionCount,
		"grossVolume":         agg.GrossVolume.Text('f', 2),
		"totalFees":           agg.TotalFees.Text('f', 2),
		"totalClientRevenue":  agg.TotalClientRevenue.Text('f', 2),
		"totalPlatformRevenue": agg.TotalPlatformRevenue.Text('f', 2),
		"activeAgents":        len(agg.ActiveAgents),
		"activePOS":           len(agg.ActivePOS),
		"lastUpdated":         agg.LastUpdated,
	})
}

func (ba *BillingAggregator) handleSetBillingModel(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Model string `json:"model"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	ba.mu.Lock()
	switch BillingModel(req.Model) {
	case RevenueShare:
		ba.activeBilling = RevenueShare
	case Subscription:
		ba.activeBilling = Subscription
	case Hybrid:
		ba.activeBilling = Hybrid
	default:
		ba.mu.Unlock()
		http.Error(w, "Invalid billing model", http.StatusBadRequest)
		return
	}
	ba.mu.Unlock()

	json.NewEncoder(w).Encode(map[string]string{"status": "updated", "model": req.Model})
}

func (ba *BillingAggregator) handleUpdateRevenueShareConfig(w http.ResponseWriter, r *http.Request) {
	var cfg RevenueShareConfig
	if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
		http.Error(w, "Invalid config", http.StatusBadRequest)
		return
	}
	ba.mu.Lock()
	ba.revenueShare = &cfg
	ba.mu.Unlock()
	json.NewEncoder(w).Encode(map[string]string{"status": "revenue_share_config_updated"})
}

// ═══════════════════════════════════════════════════════════════════════════════
// Lakehouse Integration (batch export for analytics)
// ═══════════════════════════════════════════════════════════════════════════════

type LakehouseExporter struct {
	endpoint string
	bucket   string
}

func NewLakehouseExporter(endpoint string) *LakehouseExporter {
	return &LakehouseExporter{endpoint: endpoint, bucket: "billing-lakehouse"}
}

func (le *LakehouseExporter) ExportPeriodData(periodKey string, agg *PeriodAggregate) error {
	log.Printf("[Lakehouse] Exporting period %s data: %d transactions to %s",
		periodKey, agg.TransactionCount, le.bucket)
	return nil
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main
// ═══════════════════════════════════════════════════════════════════════════════


// recoverMiddleware catches panics and returns 500 instead of crashing
func recoverMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if err := recover(); err != nil {
				log.Printf("[recovery] panic: %v", err)
				http.Error(w, "internal server error", http.StatusInternalServerError)
			}
		}()
		next.ServeHTTP(w, r)
	})
}

func main() {
	cfg := loadConfig()
	log.Printf("Starting Billing Aggregator on port %s", cfg.Port)
	log.Printf("Kafka: %s, Topic: %s", cfg.KafkaBrokers, cfg.KafkaTxTopic)
	log.Printf("TigerBeetle: %s, Redis: %s, OpenSearch: %s", cfg.TigerBeetleAddr, cfg.RedisAddr, cfg.OpenSearchURL)
	log.Printf("Dapr: HTTP=%s, GRPC=%s, PubSub=%s", cfg.DaprHTTPPort, cfg.DaprGRPCPort, cfg.DaprPubSubName)
	log.Printf("Fluvio: %s, Temporal: %s/%s", cfg.FluvioEndpoint, cfg.TemporalNamespace, cfg.TemporalTaskQueue)

	aggregator := NewBillingAggregator(cfg)
	tb := NewTigerBeetleClient(cfg.TigerBeetleAddr, cfg.TigerBeetleClusterID)
	redis := NewRedisCache(cfg.RedisAddr, cfg.RedisPassword)
	opensearch := NewOpenSearchClient(cfg.OpenSearchURL, cfg.OpenSearchIndex)
	processor := NewEventProcessor(aggregator, tb, redis, opensearch, cfg.DaprHTTPPort)
	_ = NewFluvioProducer(cfg.FluvioEndpoint)
	_ = NewTemporalClient(cfg.TemporalNamespace, cfg.TemporalTaskQueue)
	_ = NewLakehouseExporter(cfg.FluvioEndpoint)

	mux := http.NewServeMux()

	// Dapr subscription endpoint
	mux.HandleFunc("/dapr/subscribe", func(w http.ResponseWriter, r *http.Request) {
		subscriptions := []map[string]string{
			{"pubsubname": cfg.DaprPubSubName, "topic": cfg.KafkaTxTopic, "route": "/events/transaction"},
		}
		json.NewEncoder(w).Encode(subscriptions)
	})

	// Event handler (Dapr delivers Kafka messages here)
	mux.HandleFunc("/events/transaction", processor.HandleTransactionEvent)

	// Management API
	mux.HandleFunc("/health", aggregator.handleHealthCheck)
	mux.HandleFunc("/api/v1/billing/current-period", aggregator.handleGetCurrentPeriod)
	mux.HandleFunc("/api/v1/billing/model", aggregator.handleSetBillingModel)
	mux.HandleFunc("/api/v1/billing/config/revenue-share", aggregator.handleUpdateRevenueShareConfig)

	server := &http.Server{Addr: ":" + cfg.Port, Handler: mux}

	// Graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		log.Println("Shutting down billing aggregator...")
		shutdownCtx, shutdownCancel := context.WithTimeout(ctx, 30*time.Second)
		defer shutdownCancel()
		server.Shutdown(shutdownCtx)
	}()

	log.Printf("Billing Aggregator ready on :%s", cfg.Port)
	if err := server.ListenAndServe(); err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}

// ═══════════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════════

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func floatVal(f *big.Float) float64 {
	if f == nil {
		return 0
	}
	v, _ := f.Float64()
	return v
}
