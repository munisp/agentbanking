package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
	"golang.org/x/time/rate"
)

// HierarchyNode represents a node in the agent hierarchy
type HierarchyNode struct {
	ID       string  `json:"id"`
	AgentID  string  `json:"agent_id"`
	ParentID *string `json:"parent_id"`
	Depth    int     `json:"depth"`
	Path     []string `json:"path"`
}

// HierarchyEngine provides high-performance hierarchy operations
type HierarchyEngine struct {
	db *sql.DB
}

// NewHierarchyEngine creates a new hierarchy engine
func NewHierarchyEngine(dbURL string) (*HierarchyEngine, error) {
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	// Set connection pool settings
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &HierarchyEngine{db: db}, nil
}

// Close closes the database connection
func (he *HierarchyEngine) Close() error {
	return he.db.Close()
}

// GetAncestors returns all ancestors of a node (bottom-up)
func (he *HierarchyEngine) GetAncestors(ctx context.Context, nodeID string) ([]string, error) {
	ancestors := make([]string, 0)
	currentID := nodeID

	// Traverse up the hierarchy
	for {
		var parentID *string
		err := he.db.QueryRowContext(ctx,
			"SELECT parent_id FROM hierarchy_nodes WHERE id = $1",
			currentID,
		).Scan(&parentID)

		if err == sql.ErrNoRows {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("failed to query parent: %w", err)
		}

		if parentID == nil {
			break
		}

		ancestors = append(ancestors, *parentID)
		currentID = *parentID
	}

	return ancestors, nil
}

// GetDescendants returns all descendants of a node (top-down)
func (he *HierarchyEngine) GetDescendants(ctx context.Context, nodeID string) ([]string, error) {
	descendants := make([]string, 0)
	queue := []string{nodeID}
	visited := make(map[string]bool)

	// Breadth-first traversal
	for len(queue) > 0 {
		currentID := queue[0]
		queue = queue[1:]

		if visited[currentID] {
			continue
		}
		visited[currentID] = true

		// Get children
		rows, err := he.db.QueryContext(ctx,
			"SELECT id FROM hierarchy_nodes WHERE parent_id = $1",
			currentID,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to query children: %w", err)
		}

		for rows.Next() {
			var childID string
			if err := rows.Scan(&childID); err != nil {
				rows.Close()
				return nil, fmt.Errorf("failed to scan child: %w", err)
			}
			descendants = append(descendants, childID)
			queue = append(queue, childID)
		}
		rows.Close()

		if err := rows.Err(); err != nil {
			return nil, fmt.Errorf("row iteration error: %w", err)
		}
	}

	return descendants, nil
}

// DetectCycle checks if adding a parent would create a cycle
func (he *HierarchyEngine) DetectCycle(ctx context.Context, nodeID, parentID string) (bool, error) {
	// If parentID is in the descendants of nodeID, it would create a cycle
	descendants, err := he.GetDescendants(ctx, nodeID)
	if err != nil {
		return false, err
	}

	for _, desc := range descendants {
		if desc == parentID {
			return true, nil
		}
	}

	return false, nil
}

// GetPath returns the path from root to node
func (he *HierarchyEngine) GetPath(ctx context.Context, nodeID string) ([]string, error) {
	var pathJSON []byte
	err := he.db.QueryRowContext(ctx,
		"SELECT path FROM hierarchy_nodes WHERE id = $1",
		nodeID,
	).Scan(&pathJSON)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("node not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to query path: %w", err)
	}

	var path []string
	if err := json.Unmarshal(pathJSON, &path); err != nil {
		return nil, fmt.Errorf("failed to unmarshal path: %w", err)
	}

	return path, nil
}

// GetSubtreeSize returns the number of descendants
func (he *HierarchyEngine) GetSubtreeSize(ctx context.Context, nodeID string) (int, error) {
	descendants, err := he.GetDescendants(ctx, nodeID)
	if err != nil {
		return 0, err
	}
	return len(descendants), nil
}

// GetDepth returns the depth of a node
func (he *HierarchyEngine) GetDepth(ctx context.Context, nodeID string) (int, error) {
	var depth int
	err := he.db.QueryRowContext(ctx,
		"SELECT depth FROM hierarchy_nodes WHERE id = $1",
		nodeID,
	).Scan(&depth)

	if err == sql.ErrNoRows {
		return 0, fmt.Errorf("node not found")
	}
	if err != nil {
		return 0, fmt.Errorf("failed to query depth: %w", err)
	}

	return depth, nil
}

// FindCommonAncestor finds the lowest common ancestor of two nodes
func (he *HierarchyEngine) FindCommonAncestor(ctx context.Context, nodeID1, nodeID2 string) (string, error) {
	// Get ancestors of both nodes
	ancestors1, err := he.GetAncestors(ctx, nodeID1)
	if err != nil {
		return "", err
	}

	ancestors2, err := he.GetAncestors(ctx, nodeID2)
	if err != nil {
		return "", err
	}

	// Create a set of ancestors1
	ancestorSet := make(map[string]bool)
	for _, ancestor := range ancestors1 {
		ancestorSet[ancestor] = true
	}

	// Find first common ancestor in ancestors2
	for _, ancestor := range ancestors2 {
		if ancestorSet[ancestor] {
			return ancestor, nil
		}
	}

	return "", fmt.Errorf("no common ancestor found")
}

// ValidateHierarchy checks for integrity issues
func (he *HierarchyEngine) ValidateHierarchy(ctx context.Context) (map[string][]string, error) {
	issues := map[string][]string{
		"orphan_nodes":          make([]string, 0),
		"circular_dependencies": make([]string, 0),
		"invalid_depths":        make([]string, 0),
	}

	// Check for orphan nodes
	rows, err := he.db.QueryContext(ctx, `
		SELECT hn.id
		FROM hierarchy_nodes hn
		LEFT JOIN hierarchy_nodes parent ON hn.parent_id = parent.id
		WHERE hn.parent_id IS NOT NULL AND parent.id IS NULL
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to check orphans: %w", err)
	}

	for rows.Next() {
		var nodeID string
		if err := rows.Scan(&nodeID); err != nil {
			rows.Close()
			return nil, err
		}
		issues["orphan_nodes"] = append(issues["orphan_nodes"], nodeID)
	}
	rows.Close()

	// Check for invalid depths
	rows, err = he.db.QueryContext(ctx, `
		SELECT hn.id
		FROM hierarchy_nodes hn
		JOIN hierarchy_nodes parent ON hn.parent_id = parent.id
		WHERE hn.depth != parent.depth + 1
	`)
	if err != nil {
		return nil, fmt.Errorf("failed to check depths: %w", err)
	}

	for rows.Next() {
		var nodeID string
		if err := rows.Scan(&nodeID); err != nil {
			rows.Close()
			return nil, err
		}
		issues["invalid_depths"] = append(issues["invalid_depths"], nodeID)
	}
	rows.Close()

	return issues, nil
}

// GetMaxDepth returns the maximum depth in the hierarchy
func (he *HierarchyEngine) GetMaxDepth(ctx context.Context) (int, error) {
	var maxDepth int
	err := he.db.QueryRowContext(ctx,
		"SELECT COALESCE(MAX(depth), 0) FROM hierarchy_nodes",
	).Scan(&maxDepth)

	if err != nil {
		return 0, fmt.Errorf("failed to query max depth: %w", err)
	}

	return maxDepth, nil
}


func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok","service":"hierarchy-engine"}`))
}

func main() {

	// ── OpenTelemetry ────────────────────────────────────────────────────────────
	svcName := os.Getenv("SERVICE_NAME")
	if svcName == "" {
		svcName = "hierarchy-engine"
	}
	svcVersion := os.Getenv("SERVICE_VERSION")
	if svcVersion == "" {
		svcVersion = "1.0.0"
	}
	shutdownTracer := initTracer(svcName, svcVersion)
	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = shutdownTracer(ctx)
	}()
	if len(os.Args) < 2 {
		fmt.Println("Usage: hierarchy-engine <command> [args...]")
		fmt.Println("Commands:")
		fmt.Println("  ancestors <node_id>")
		fmt.Println("  descendants <node_id>")
		fmt.Println("  detect-cycle <node_id> <parent_id>")
		fmt.Println("  path <node_id>")
		fmt.Println("  subtree-size <node_id>")
		fmt.Println("  depth <node_id>")
		fmt.Println("  common-ancestor <node_id1> <node_id2>")
		fmt.Println("  validate")
		fmt.Println("  max-depth")
		os.Exit(1)
	}

	// Get database URL from environment
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgresql://banking_user:banking_pass@localhost:5432/remittance?sslmode=disable"
	}

	// Create engine
	engine, err := NewHierarchyEngine(dbURL)
	if err != nil {
		log.Fatalf("Failed to create engine: %v", err)
	}
	defer engine.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	command := os.Args[1]

	switch command {
	case "ancestors":
		if len(os.Args) < 3 {
			log.Fatal("Usage: ancestors <node_id>")
		}
		nodeID := os.Args[2]
		ancestors, err := engine.GetAncestors(ctx, nodeID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(ancestors)
		fmt.Println(string(output))

	case "descendants":
		if len(os.Args) < 3 {
			log.Fatal("Usage: descendants <node_id>")
		}
		nodeID := os.Args[2]
		descendants, err := engine.GetDescendants(ctx, nodeID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(descendants)
		fmt.Println(string(output))

	case "detect-cycle":
		if len(os.Args) < 4 {
			log.Fatal("Usage: detect-cycle <node_id> <parent_id>")
		}
		nodeID := os.Args[2]
		parentID := os.Args[3]
		hasCycle, err := engine.DetectCycle(ctx, nodeID, parentID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(map[string]bool{"has_cycle": hasCycle})
		fmt.Println(string(output))

	case "path":
		if len(os.Args) < 3 {
			log.Fatal("Usage: path <node_id>")
		}
		nodeID := os.Args[2]
		path, err := engine.GetPath(ctx, nodeID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(path)
		fmt.Println(string(output))

	case "subtree-size":
		if len(os.Args) < 3 {
			log.Fatal("Usage: subtree-size <node_id>")
		}
		nodeID := os.Args[2]
		size, err := engine.GetSubtreeSize(ctx, nodeID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(map[string]int{"size": size})
		fmt.Println(string(output))

	case "depth":
		if len(os.Args) < 3 {
			log.Fatal("Usage: depth <node_id>")
		}
		nodeID := os.Args[2]
		depth, err := engine.GetDepth(ctx, nodeID)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(map[string]int{"depth": depth})
		fmt.Println(string(output))

	case "common-ancestor":
		if len(os.Args) < 4 {
			log.Fatal("Usage: common-ancestor <node_id1> <node_id2>")
		}
		nodeID1 := os.Args[2]
		nodeID2 := os.Args[3]
		ancestor, err := engine.FindCommonAncestor(ctx, nodeID1, nodeID2)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(map[string]string{"common_ancestor": ancestor})
		fmt.Println(string(output))

	case "validate":
		issues, err := engine.ValidateHierarchy(ctx)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(issues)
		fmt.Println(string(output))

	case "max-depth":
		maxDepth, err := engine.GetMaxDepth(ctx)
		if err != nil {
			log.Fatalf("Error: %v", err)
		}
		output, _ := json.Marshal(map[string]int{"max_depth": maxDepth})
		fmt.Println(string(output))

	default:
		log.Fatalf("Unknown command: %s", command)
	}
}

// initTracer initialises the OTLP trace exporter.
// Returns a shutdown function; safe to call even if OTEL is not configured.
func initTracer(serviceName, serviceVersion string) func(context.Context) error {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		return func(context.Context) error { return nil }
	}
	ctx := context.Background()
	exp, err := otlptracehttp.New(ctx, otlptracehttp.WithEndpoint(endpoint))
	if err != nil {
		slog.Warn("OTel exporter init failed", "err", err)
		return func(context.Context) error { return nil }
	}
	res := resource.NewWithAttributes(
		"https://opentelemetry.io/schemas/1.24.0",
		semconv.ServiceName(serviceName),
		semconv.ServiceVersion(serviceVersion),
		attribute.String("deployment.environment", os.Getenv("ENVIRONMENT")),
	)
	tp := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exp),
		sdktrace.WithResource(res),
	)
	otel.SetTracerProvider(tp)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
	return tp.Shutdown
}

// otelMiddleware wraps an http.Handler with OTel tracing.
func otelMiddleware(serviceName string, next http.Handler) http.Handler {
	tracer := otel.Tracer(serviceName)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ctx, span := tracer.Start(r.Context(), r.Method+" "+r.URL.Path)
		defer span.End()
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// rateLimitMiddleware applies a token-bucket rate limiter.
func rateLimitMiddleware(rps float64, burst int, next http.Handler) http.Handler {
	limiter := rate.NewLimiter(rate.Limit(rps), burst)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !limiter.Allow() {
			http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// gracefulShutdown waits for SIGTERM/SIGINT then drains the server.
func gracefulShutdown(serviceName string, srv *http.Server, cleanup func(context.Context) error) {
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
	sig := <-quit
	slog.Info("Shutdown signal received", "service", serviceName, "signal", sig)
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("Server shutdown error", "err", err)
	}
	if cleanup != nil {
		if err := cleanup(ctx); err != nil {
			slog.Error("Cleanup error", "err", err)
		}
	}
	slog.Info("Server stopped gracefully", "service", serviceName)
}

