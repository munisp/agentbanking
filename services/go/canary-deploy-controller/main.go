package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	_ "github.com/lib/pq"
)

type CanaryStage struct {
	Percent    int           `json:"percent"`
	Duration   time.Duration `json:"duration"`
	MetricCheck string       `json:"metric_check"`
}

var DefaultStages = []CanaryStage{
	{Percent: 1, Duration: 5 * time.Minute, MetricCheck: "error_rate < 0.01"},
	{Percent: 5, Duration: 10 * time.Minute, MetricCheck: "error_rate < 0.01 && p99_latency < 500"},
	{Percent: 25, Duration: 15 * time.Minute, MetricCheck: "error_rate < 0.02 && p99_latency < 800"},
	{Percent: 50, Duration: 20 * time.Minute, MetricCheck: "error_rate < 0.03"},
	{Percent: 100, Duration: 0, MetricCheck: ""},
}

type CanaryDeployment struct {
	ID            string    `json:"id"`
	ServiceName   string    `json:"service_name"`
	NewVersion    string    `json:"new_version"`
	OldVersion    string    `json:"old_version"`
	CurrentStage  int       `json:"current_stage"`
	TrafficPercent int      `json:"traffic_percent"`
	Status        string    `json:"status"`
	ErrorRate     float64   `json:"error_rate"`
	P99Latency    float64   `json:"p99_latency"`
	StartedAt     time.Time `json:"started_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type Controller struct {
	db          *sql.DB
	mu          sync.RWMutex
	deployments map[string]*CanaryDeployment
}

func NewController(db *sql.DB) *Controller {
	return &Controller{
		db:          db,
		deployments: make(map[string]*CanaryDeployment),
	}
}

func (c *Controller) StartCanary(serviceName, newVersion, oldVersion string) (*CanaryDeployment, error) {
	deployment := &CanaryDeployment{
		ID:             fmt.Sprintf("canary-%d", time.Now().UnixMilli()),
		ServiceName:    serviceName,
		NewVersion:     newVersion,
		OldVersion:     oldVersion,
		CurrentStage:   0,
		TrafficPercent: DefaultStages[0].Percent,
		Status:         "in_progress",
		StartedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	query := `INSERT INTO canary_deployments (id, service_name, new_version, old_version, current_stage, traffic_percent, status, started_at)
	           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`
	_, err := c.db.Exec(query, deployment.ID, deployment.ServiceName, deployment.NewVersion, deployment.OldVersion, deployment.CurrentStage, deployment.TrafficPercent, deployment.Status, deployment.StartedAt)
	if err != nil {
		return nil, fmt.Errorf("failed to create canary: %w", err)
	}

	c.mu.Lock()
	c.deployments[deployment.ID] = deployment
	c.mu.Unlock()

	log.Printf("Canary started: %s (%s → %s) at %d%%", serviceName, oldVersion, newVersion, deployment.TrafficPercent)
	return deployment, nil
}

func (c *Controller) AdvanceStage(deploymentID string) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	dep, ok := c.deployments[deploymentID]
	if !ok {
		return fmt.Errorf("deployment %s not found", deploymentID)
	}

	if dep.ErrorRate > 0.05 || dep.P99Latency > 1000 {
		dep.Status = "rolled_back"
		dep.TrafficPercent = 0
		log.Printf("ROLLBACK: %s — error_rate=%.3f p99=%.0fms", dep.ServiceName, dep.ErrorRate, dep.P99Latency)
		c.db.Exec(`UPDATE canary_deployments SET status = 'rolled_back', traffic_percent = 0 WHERE id = $1`, dep.ID)
		return fmt.Errorf("metrics exceeded threshold, rolled back")
	}

	if dep.CurrentStage >= len(DefaultStages)-1 {
		dep.Status = "completed"
		dep.TrafficPercent = 100
		log.Printf("Canary COMPLETE: %s now at 100%%", dep.ServiceName)
		c.db.Exec(`UPDATE canary_deployments SET status = 'completed', traffic_percent = 100 WHERE id = $1`, dep.ID)
		return nil
	}

	dep.CurrentStage++
	dep.TrafficPercent = DefaultStages[dep.CurrentStage].Percent
	dep.UpdatedAt = time.Now()
	log.Printf("Canary advanced: %s stage %d → %d%%", dep.ServiceName, dep.CurrentStage, dep.TrafficPercent)
	c.db.Exec(`UPDATE canary_deployments SET current_stage = $1, traffic_percent = $2, updated_at = $3 WHERE id = $4`,
		dep.CurrentStage, dep.TrafficPercent, dep.UpdatedAt, dep.ID)
	return nil
}

func (c *Controller) UpdateMetrics(deploymentID string, errorRate, p99Latency float64) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if dep, ok := c.deployments[deploymentID]; ok {
		dep.ErrorRate = errorRate
		dep.P99Latency = p99Latency
	}
}

func (c *Controller) GetDeployments() []*CanaryDeployment {
	c.mu.RLock()
	defer c.mu.RUnlock()
	result := make([]*CanaryDeployment, 0, len(c.deployments))
	for _, d := range c.deployments {
		result = append(result, d)
	}
	return result
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8401"
	}
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://localhost:5432/agentbanking?sslmode=disable"
	}

	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		log.Fatalf("DB connection failed: %v", err)
	}
	defer db.Close()
	db.SetMaxOpenConns(10)

	_ = math.Abs(0) // ensure math import is used

	ctrl := NewController(db)
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		if err := db.Ping(); err != nil {
			http.Error(w, "unhealthy", http.StatusServiceUnavailable)
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "healthy", "service": "canary-deploy-controller"})
	})

	mux.HandleFunc("/api/v1/canary/start", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		var req struct {
			ServiceName string `json:"service_name"`
			NewVersion  string `json:"new_version"`
			OldVersion  string `json:"old_version"`
		}
		json.NewDecoder(r.Body).Decode(&req)
		dep, err := ctrl.StartCanary(req.ServiceName, req.NewVersion, req.OldVersion)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		json.NewEncoder(w).Encode(dep)
	})

	mux.HandleFunc("/api/v1/canary/list", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(ctrl.GetDeployments())
	})

	mux.HandleFunc("/api/v1/canary/advance", func(w http.ResponseWriter, r *http.Request) {
		id := r.URL.Query().Get("id")
		if err := ctrl.AdvanceStage(id); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		json.NewEncoder(w).Encode(map[string]string{"status": "advanced"})
	})

	server := &http.Server{Addr: ":" + port, Handler: mux}
	go func() {
		log.Printf("Canary Deploy Controller on :%s", port)
		server.ListenAndServe()
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh
	log.Println("Shutting down canary controller...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	server.Shutdown(ctx)
}
