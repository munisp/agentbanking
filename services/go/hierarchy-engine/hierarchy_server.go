package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"github.com/gorilla/mux"
	_ "github.com/lib/pq"
	"github.com/segmentio/kafka-go"
)

type AgentTier string

const (
	TierSuperAgent  AgentTier = "super_agent"
	TierSeniorAgent AgentTier = "senior_agent"
	TierAgent       AgentTier = "agent"
	TierSubAgent    AgentTier = "sub_agent"
	TierTrainee     AgentTier = "trainee"
)

type Agent struct {
	ID            string     `json:"id"`
	AgentID       string     `json:"agent_id"`
	ParentAgentID *string    `json:"parent_agent_id"`
	Tier          AgentTier  `json:"tier"`
	Depth         int        `json:"depth"`
	Path          []string   `json:"path"`
	Status        string     `json:"status"`
	TerritoryID   *string    `json:"territory_id"`
	CreatedAt     time.Time  `json:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at"`
}

type HierarchyStats struct {
	TotalAgents      int            `json:"total_agents"`
	MaxDepth         int            `json:"max_depth"`
	AgentsByTier     map[string]int `json:"agents_by_tier"`
	AgentsByStatus   map[string]int `json:"agents_by_status"`
	OrphanCount      int            `json:"orphan_count"`
	AverageSubtree   float64        `json:"average_subtree_size"`
}

type TierValidation struct {
	ParentTier AgentTier
	AllowedChildren []AgentTier
	MaxChildren int
	MaxDepth int
}

var tierRules = map[AgentTier]TierValidation{
	TierSuperAgent: {
		AllowedChildren: []AgentTier{TierSeniorAgent, TierAgent, TierSubAgent},
		MaxChildren: 50,
		MaxDepth: 1,
	},
	TierSeniorAgent: {
		AllowedChildren: []AgentTier{TierAgent, TierSubAgent},
		MaxChildren: 30,
		MaxDepth: 2,
	},
	TierAgent: {
		AllowedChildren: []AgentTier{TierSubAgent, TierTrainee},
		MaxChildren: 20,
		MaxDepth: 3,
	},
	TierSubAgent: {
		AllowedChildren: []AgentTier{TierTrainee},
		MaxChildren: 10,
		MaxDepth: 4,
	},
	TierTrainee: {
		AllowedChildren: []AgentTier{},
		MaxChildren: 0,
		MaxDepth: 5,
	},
}

type ProductionHierarchyEngine struct {
	db          *sql.DB
	redis       *redis.Client
	kafkaWriter *kafka.Writer
	cacheTTL    time.Duration
	mu          sync.RWMutex
}

type Config struct {
	DatabaseURL     string
	RedisURL        string
	KafkaBootstrap  string
	CacheTTLSeconds int
	ServerPort      int
}

func LoadConfig() *Config {
	cacheTTL, _ := strconv.Atoi(getEnv("CACHE_TTL_SECONDS", "3600"))
	serverPort, _ := strconv.Atoi(getEnv("SERVER_PORT", "8112"))

	return &Config{
		DatabaseURL:     getEnv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/remittance?sslmode=disable"),
		RedisURL:        getEnv("REDIS_URL", "redis://localhost:6379"),
		KafkaBootstrap:  getEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
		CacheTTLSeconds: cacheTTL,
		ServerPort:      serverPort,
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func NewProductionHierarchyEngine(config *Config) (*ProductionHierarchyEngine, error) {
	db, err := sql.Open("postgres", config.DatabaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	opt, err := redis.ParseURL(config.RedisURL)
	if err != nil {
		log.Printf("Warning: Failed to parse Redis URL: %v, caching disabled", err)
	}

	var redisClient *redis.Client
	if opt != nil {
		redisClient = redis.NewClient(opt)
		if _, err := redisClient.Ping(ctx).Result(); err != nil {
			log.Printf("Warning: Failed to connect to Redis: %v, caching disabled", err)
			redisClient = nil
		}
	}

	var kafkaWriter *kafka.Writer
	if config.KafkaBootstrap != "" {
		kafkaWriter = &kafka.Writer{
			Addr:         kafka.TCP(config.KafkaBootstrap),
			Topic:        "hierarchy-events",
			Balancer:     &kafka.LeastBytes{},
			BatchTimeout: 10 * time.Millisecond,
			RequiredAcks: kafka.RequireAll,
		}
	}

	return &ProductionHierarchyEngine{
		db:          db,
		redis:       redisClient,
		kafkaWriter: kafkaWriter,
		cacheTTL:    time.Duration(config.CacheTTLSeconds) * time.Second,
	}, nil
}

func (e *ProductionHierarchyEngine) Close() error {
	if e.kafkaWriter != nil {
		e.kafkaWriter.Close()
	}
	if e.redis != nil {
		e.redis.Close()
	}
	return e.db.Close()
}

func (e *ProductionHierarchyEngine) getCached(ctx context.Context, key string) ([]byte, error) {
	if e.redis == nil {
		return nil, nil
	}
	return e.redis.Get(ctx, key).Bytes()
}

func (e *ProductionHierarchyEngine) setCache(ctx context.Context, key string, value interface{}) error {
	if e.redis == nil {
		return nil
	}
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return e.redis.Set(ctx, key, data, e.cacheTTL).Err()
}

func (e *ProductionHierarchyEngine) invalidateCache(ctx context.Context, patterns ...string) {
	if e.redis == nil {
		return
	}
	for _, pattern := range patterns {
		keys, _ := e.redis.Keys(ctx, pattern).Result()
		if len(keys) > 0 {
			e.redis.Del(ctx, keys...)
		}
	}
}

func (e *ProductionHierarchyEngine) publishEvent(ctx context.Context, eventType string, data interface{}) {
	if e.kafkaWriter == nil {
		return
	}

	event := map[string]interface{}{
		"event_type": eventType,
		"data":       data,
		"timestamp":  time.Now().UTC().Format(time.RFC3339),
	}

	eventData, _ := json.Marshal(event)

	go func() {
		err := e.kafkaWriter.WriteMessages(ctx, kafka.Message{
			Key:   []byte(eventType),
			Value: eventData,
		})
		if err != nil {
			log.Printf("Failed to publish event: %v", err)
		}
	}()
}

func (e *ProductionHierarchyEngine) ValidateTierRules(ctx context.Context, parentID string, childTier AgentTier) error {
	if parentID == "" {
		if childTier != TierSuperAgent {
			return fmt.Errorf("only super_agent can be at root level")
		}
		return nil
	}

	var parentTier string
	err := e.db.QueryRowContext(ctx,
		"SELECT tier FROM agents WHERE agent_id = $1",
		parentID,
	).Scan(&parentTier)

	if err == sql.ErrNoRows {
		return fmt.Errorf("parent agent not found")
	}
	if err != nil {
		return fmt.Errorf("failed to query parent: %w", err)
	}

	rules, ok := tierRules[AgentTier(parentTier)]
	if !ok {
		return fmt.Errorf("unknown parent tier: %s", parentTier)
	}

	allowed := false
	for _, t := range rules.AllowedChildren {
		if t == childTier {
			allowed = true
			break
		}
	}

	if !allowed {
		return fmt.Errorf("tier %s cannot have %s as child", parentTier, childTier)
	}

	var childCount int
	err = e.db.QueryRowContext(ctx,
		"SELECT COUNT(*) FROM agents WHERE parent_agent_id = $1 AND status = 'active'",
		parentID,
	).Scan(&childCount)

	if err != nil {
		return fmt.Errorf("failed to count children: %w", err)
	}

	if childCount >= rules.MaxChildren {
		return fmt.Errorf("parent has reached maximum children limit (%d)", rules.MaxChildren)
	}

	return nil
}

func (e *ProductionHierarchyEngine) GetAgentWithHierarchy(ctx context.Context, agentID string) (*Agent, error) {
	cacheKey := fmt.Sprintf("agent:hierarchy:%s", agentID)
	if cached, err := e.getCached(ctx, cacheKey); err == nil && cached != nil {
		var agent Agent
		if json.Unmarshal(cached, &agent) == nil {
			return &agent, nil
		}
	}

	var agent Agent
	var pathJSON []byte

	err := e.db.QueryRowContext(ctx, `
		SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at
		FROM agents WHERE agent_id = $1
	`, agentID).Scan(
		&agent.ID, &agent.AgentID, &agent.ParentAgentID, &agent.Tier,
		&agent.Depth, &pathJSON, &agent.Status, &agent.TerritoryID,
		&agent.CreatedAt, &agent.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("agent not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query agent: %w", err)
	}

	if pathJSON != nil {
		json.Unmarshal(pathJSON, &agent.Path)
	}

	e.setCache(ctx, cacheKey, agent)

	return &agent, nil
}

func (e *ProductionHierarchyEngine) GetAncestorsWithDetails(ctx context.Context, agentID string) ([]Agent, error) {
	cacheKey := fmt.Sprintf("ancestors:details:%s", agentID)
	if cached, err := e.getCached(ctx, cacheKey); err == nil && cached != nil {
		var ancestors []Agent
		if json.Unmarshal(cached, &ancestors) == nil {
			return ancestors, nil
		}
	}

	rows, err := e.db.QueryContext(ctx, `
		WITH RECURSIVE ancestors AS (
			SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at
			FROM agents WHERE agent_id = $1
			UNION ALL
			SELECT a.id, a.agent_id, a.parent_agent_id, a.tier, a.depth, a.path, a.status, a.territory_id, a.created_at, a.updated_at
			FROM agents a
			INNER JOIN ancestors anc ON a.agent_id = anc.parent_agent_id
		)
		SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at
		FROM ancestors
		WHERE agent_id != $1
		ORDER BY depth ASC
	`, agentID)

	if err != nil {
		return nil, fmt.Errorf("failed to query ancestors: %w", err)
	}
	defer rows.Close()

	var ancestors []Agent
	for rows.Next() {
		var agent Agent
		var pathJSON []byte
		if err := rows.Scan(
			&agent.ID, &agent.AgentID, &agent.ParentAgentID, &agent.Tier,
			&agent.Depth, &pathJSON, &agent.Status, &agent.TerritoryID,
			&agent.CreatedAt, &agent.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan ancestor: %w", err)
		}
		if pathJSON != nil {
			json.Unmarshal(pathJSON, &agent.Path)
		}
		ancestors = append(ancestors, agent)
	}

	e.setCache(ctx, cacheKey, ancestors)

	return ancestors, nil
}

func (e *ProductionHierarchyEngine) GetDescendantsWithDetails(ctx context.Context, agentID string, maxDepth int) ([]Agent, error) {
	cacheKey := fmt.Sprintf("descendants:details:%s:%d", agentID, maxDepth)
	if cached, err := e.getCached(ctx, cacheKey); err == nil && cached != nil {
		var descendants []Agent
		if json.Unmarshal(cached, &descendants) == nil {
			return descendants, nil
		}
	}

	query := `
		WITH RECURSIVE descendants AS (
			SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at, 0 as relative_depth
			FROM agents WHERE agent_id = $1
			UNION ALL
			SELECT a.id, a.agent_id, a.parent_agent_id, a.tier, a.depth, a.path, a.status, a.territory_id, a.created_at, a.updated_at, d.relative_depth + 1
			FROM agents a
			INNER JOIN descendants d ON a.parent_agent_id = d.agent_id
			WHERE d.relative_depth < $2
		)
		SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at
		FROM descendants
		WHERE agent_id != $1
		ORDER BY depth ASC
	`

	rows, err := e.db.QueryContext(ctx, query, agentID, maxDepth)
	if err != nil {
		return nil, fmt.Errorf("failed to query descendants: %w", err)
	}
	defer rows.Close()

	var descendants []Agent
	for rows.Next() {
		var agent Agent
		var pathJSON []byte
		if err := rows.Scan(
			&agent.ID, &agent.AgentID, &agent.ParentAgentID, &agent.Tier,
			&agent.Depth, &pathJSON, &agent.Status, &agent.TerritoryID,
			&agent.CreatedAt, &agent.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan descendant: %w", err)
		}
		if pathJSON != nil {
			json.Unmarshal(pathJSON, &agent.Path)
		}
		descendants = append(descendants, agent)
	}

	e.setCache(ctx, cacheKey, descendants)

	return descendants, nil
}

func (e *ProductionHierarchyEngine) GetHierarchyStats(ctx context.Context) (*HierarchyStats, error) {
	cacheKey := "hierarchy:stats"
	if cached, err := e.getCached(ctx, cacheKey); err == nil && cached != nil {
		var stats HierarchyStats
		if json.Unmarshal(cached, &stats) == nil {
			return &stats, nil
		}
	}

	stats := &HierarchyStats{
		AgentsByTier:   make(map[string]int),
		AgentsByStatus: make(map[string]int),
	}

	err := e.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM agents").Scan(&stats.TotalAgents)
	if err != nil {
		return nil, fmt.Errorf("failed to count agents: %w", err)
	}

	err = e.db.QueryRowContext(ctx, "SELECT COALESCE(MAX(depth), 0) FROM agents").Scan(&stats.MaxDepth)
	if err != nil {
		return nil, fmt.Errorf("failed to get max depth: %w", err)
	}

	rows, err := e.db.QueryContext(ctx, "SELECT tier, COUNT(*) FROM agents GROUP BY tier")
	if err != nil {
		return nil, fmt.Errorf("failed to count by tier: %w", err)
	}
	for rows.Next() {
		var tier string
		var count int
		rows.Scan(&tier, &count)
		stats.AgentsByTier[tier] = count
	}
	rows.Close()

	rows, err = e.db.QueryContext(ctx, "SELECT status, COUNT(*) FROM agents GROUP BY status")
	if err != nil {
		return nil, fmt.Errorf("failed to count by status: %w", err)
	}
	for rows.Next() {
		var status string
		var count int
		rows.Scan(&status, &count)
		stats.AgentsByStatus[status] = count
	}
	rows.Close()

	err = e.db.QueryRowContext(ctx, `
		SELECT COUNT(*) FROM agents a
		LEFT JOIN agents p ON a.parent_agent_id = p.agent_id
		WHERE a.parent_agent_id IS NOT NULL AND p.agent_id IS NULL
	`).Scan(&stats.OrphanCount)
	if err != nil {
		return nil, fmt.Errorf("failed to count orphans: %w", err)
	}

	var totalSubtree, agentsWithChildren int
	rows, err = e.db.QueryContext(ctx, `
		SELECT parent_agent_id, COUNT(*) as child_count
		FROM agents
		WHERE parent_agent_id IS NOT NULL
		GROUP BY parent_agent_id
	`)
	if err == nil {
		for rows.Next() {
			var parentID string
			var count int
			rows.Scan(&parentID, &count)
			totalSubtree += count
			agentsWithChildren++
		}
		rows.Close()
	}

	if agentsWithChildren > 0 {
		stats.AverageSubtree = float64(totalSubtree) / float64(agentsWithChildren)
	}

	e.setCache(ctx, cacheKey, stats)

	return stats, nil
}

func (e *ProductionHierarchyEngine) MoveAgent(ctx context.Context, agentID, newParentID string) error {
	tx, err := e.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	var agentTier string
	err = tx.QueryRowContext(ctx, "SELECT tier FROM agents WHERE agent_id = $1", agentID).Scan(&agentTier)
	if err != nil {
		return fmt.Errorf("agent not found: %w", err)
	}

	if err := e.ValidateTierRules(ctx, newParentID, AgentTier(agentTier)); err != nil {
		return fmt.Errorf("tier validation failed: %w", err)
	}

	descendants, err := e.GetDescendantsWithDetails(ctx, agentID, 10)
	if err != nil {
		return fmt.Errorf("failed to get descendants: %w", err)
	}

	for _, desc := range descendants {
		if desc.AgentID == newParentID {
			return fmt.Errorf("cannot move agent under its own descendant (would create cycle)")
		}
	}

	var newDepth int
	var newPath []string

	if newParentID == "" {
		newDepth = 0
		newPath = []string{agentID}
	} else {
		var parentDepth int
		var parentPathJSON []byte
		err = tx.QueryRowContext(ctx,
			"SELECT depth, path FROM agents WHERE agent_id = $1",
			newParentID,
		).Scan(&parentDepth, &parentPathJSON)
		if err != nil {
			return fmt.Errorf("new parent not found: %w", err)
		}

		newDepth = parentDepth + 1
		if parentPathJSON != nil {
			json.Unmarshal(parentPathJSON, &newPath)
		}
		newPath = append(newPath, agentID)
	}

	newPathJSON, _ := json.Marshal(newPath)

	_, err = tx.ExecContext(ctx, `
		UPDATE agents
		SET parent_agent_id = $1, depth = $2, path = $3, updated_at = NOW()
		WHERE agent_id = $4
	`, newParentID, newDepth, newPathJSON, agentID)

	if err != nil {
		return fmt.Errorf("failed to update agent: %w", err)
	}

	for _, desc := range descendants {
		descNewDepth := newDepth + (desc.Depth - newDepth + 1)
		descNewPath := append(newPath, desc.Path[len(newPath):]...)
		descPathJSON, _ := json.Marshal(descNewPath)

		_, err = tx.ExecContext(ctx, `
			UPDATE agents SET depth = $1, path = $2, updated_at = NOW() WHERE agent_id = $3
		`, descNewDepth, descPathJSON, desc.AgentID)

		if err != nil {
			return fmt.Errorf("failed to update descendant %s: %w", desc.AgentID, err)
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	e.invalidateCache(ctx, "agent:*", "ancestors:*", "descendants:*", "hierarchy:*")

	e.publishEvent(ctx, "agent.moved", map[string]interface{}{
		"agent_id":      agentID,
		"new_parent_id": newParentID,
		"new_depth":     newDepth,
	})

	return nil
}

func (e *ProductionHierarchyEngine) GetTerritoryAgents(ctx context.Context, territoryID string) ([]Agent, error) {
	cacheKey := fmt.Sprintf("territory:agents:%s", territoryID)
	if cached, err := e.getCached(ctx, cacheKey); err == nil && cached != nil {
		var agents []Agent
		if json.Unmarshal(cached, &agents) == nil {
			return agents, nil
		}
	}

	rows, err := e.db.QueryContext(ctx, `
		SELECT id, agent_id, parent_agent_id, tier, depth, path, status, territory_id, created_at, updated_at
		FROM agents
		WHERE territory_id = $1
		ORDER BY depth ASC, tier ASC
	`, territoryID)

	if err != nil {
		return nil, fmt.Errorf("failed to query territory agents: %w", err)
	}
	defer rows.Close()

	var agents []Agent
	for rows.Next() {
		var agent Agent
		var pathJSON []byte
		if err := rows.Scan(
			&agent.ID, &agent.AgentID, &agent.ParentAgentID, &agent.Tier,
			&agent.Depth, &pathJSON, &agent.Status, &agent.TerritoryID,
			&agent.CreatedAt, &agent.UpdatedAt,
		); err != nil {
			return nil, fmt.Errorf("failed to scan agent: %w", err)
		}
		if pathJSON != nil {
			json.Unmarshal(pathJSON, &agent.Path)
		}
		agents = append(agents, agent)
	}

	e.setCache(ctx, cacheKey, agents)

	return agents, nil
}

type HierarchyServer struct {
	engine *ProductionHierarchyEngine
	router *mux.Router
}

func NewHierarchyServer(engine *ProductionHierarchyEngine) *HierarchyServer {
	server := &HierarchyServer{
		engine: engine,
		router: mux.NewRouter(),
	}
	server.setupRoutes()
	return server
}

func (s *HierarchyServer) setupRoutes() {
	s.router.HandleFunc("/health", s.healthHandler).Methods("GET")
	s.router.HandleFunc("/agents/{agent_id}", s.getAgentHandler).Methods("GET")
	s.router.HandleFunc("/agents/{agent_id}/ancestors", s.getAncestorsHandler).Methods("GET")
	s.router.HandleFunc("/agents/{agent_id}/descendants", s.getDescendantsHandler).Methods("GET")
	s.router.HandleFunc("/agents/{agent_id}/move", s.moveAgentHandler).Methods("POST")
	s.router.HandleFunc("/agents/{agent_id}/validate-parent", s.validateParentHandler).Methods("POST")
	s.router.HandleFunc("/hierarchy/stats", s.getStatsHandler).Methods("GET")
	s.router.HandleFunc("/hierarchy/validate", s.validateHierarchyHandler).Methods("GET")
	s.router.HandleFunc("/territories/{territory_id}/agents", s.getTerritoryAgentsHandler).Methods("GET")
}

func (s *HierarchyServer) healthHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	health := map[string]interface{}{
		"status":    "healthy",
		"service":   "Hierarchy Engine (Production)",
		"version":   "2.0.0",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	}

	if err := s.engine.db.PingContext(ctx); err != nil {
		health["status"] = "degraded"
		health["database"] = "unhealthy"
	} else {
		health["database"] = "healthy"
	}

	if s.engine.redis != nil {
		if _, err := s.engine.redis.Ping(ctx).Result(); err != nil {
			health["redis"] = "unhealthy"
		} else {
			health["redis"] = "healthy"
		}
	} else {
		health["redis"] = "disabled"
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(health)
}

func (s *HierarchyServer) getAgentHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	agent, err := s.engine.GetAgentWithHierarchy(ctx, agentID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(agent)
}

func (s *HierarchyServer) getAncestorsHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	ancestors, err := s.engine.GetAncestorsWithDetails(ctx, agentID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent_id":  agentID,
		"ancestors": ancestors,
		"count":     len(ancestors),
	})
}

func (s *HierarchyServer) getDescendantsHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	maxDepth := 10
	if depthStr := r.URL.Query().Get("max_depth"); depthStr != "" {
		if d, err := strconv.Atoi(depthStr); err == nil && d > 0 {
			maxDepth = d
		}
	}

	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	descendants, err := s.engine.GetDescendantsWithDetails(ctx, agentID, maxDepth)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent_id":    agentID,
		"descendants": descendants,
		"count":       len(descendants),
		"max_depth":   maxDepth,
	})
}

func (s *HierarchyServer) moveAgentHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	var request struct {
		NewParentID string `json:"new_parent_id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	if err := s.engine.MoveAgent(ctx, agentID, request.NewParentID); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success":       true,
		"agent_id":      agentID,
		"new_parent_id": request.NewParentID,
	})
}

func (s *HierarchyServer) validateParentHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	var request struct {
		ParentID string    `json:"parent_id"`
		Tier     AgentTier `json:"tier"`
	}

	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	err := s.engine.ValidateTierRules(ctx, request.ParentID, request.Tier)

	response := map[string]interface{}{
		"agent_id":  agentID,
		"parent_id": request.ParentID,
		"tier":      request.Tier,
		"valid":     err == nil,
	}

	if err != nil {
		response["error"] = err.Error()
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *HierarchyServer) getStatsHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	stats, err := s.engine.GetHierarchyStats(ctx)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(stats)
}

func (s *HierarchyServer) validateHierarchyHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 60*time.Second)
	defer cancel()

	he := &HierarchyEngine{db: s.engine.db}
	issues, err := he.ValidateHierarchy(ctx)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	totalIssues := 0
	for _, v := range issues {
		totalIssues += len(v)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"valid":        totalIssues == 0,
		"total_issues": totalIssues,
		"issues":       issues,
	})
}

func (s *HierarchyServer) getTerritoryAgentsHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	territoryID := vars["territory_id"]

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	agents, err := s.engine.GetTerritoryAgents(ctx, territoryID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"territory_id": territoryID,
		"agents":       agents,
		"count":        len(agents),
	})
}

func (s *HierarchyServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.router.ServeHTTP(w, r)
}

func RunServer() {
	config := LoadConfig()

	engine, err := NewProductionHierarchyEngine(config)
	if err != nil {
		log.Fatalf("Failed to create engine: %v", err)
	}
	defer engine.Close()

	server := NewHierarchyServer(engine)

	addr := fmt.Sprintf(":%d", config.ServerPort)
	log.Printf("Starting Hierarchy Engine server on %s", addr)

	if err := http.ListenAndServe(addr, server); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
