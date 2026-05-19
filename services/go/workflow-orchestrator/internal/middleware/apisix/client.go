package apisix

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"workflow-orchestrator/pkg/logger"
)

// Client represents an APISIX client for API gateway management
type Client struct {
	httpClient *http.Client
	config     *Config
}

// Config holds APISIX configuration
type Config struct {
	AdminURL   string
	GatewayURL string
	APIKey     string
}

// Route represents an APISIX route
type Route struct {
	ID          string                 `json:"id,omitempty"`
	URI         string                 `json:"uri"`
	Name        string                 `json:"name"`
	Methods     []string               `json:"methods"`
	Upstream    *Upstream              `json:"upstream"`
	Plugins     map[string]interface{} `json:"plugins,omitempty"`
	Status      int                    `json:"status,omitempty"`
}

// Upstream represents an APISIX upstream
type Upstream struct {
	Type  string `json:"type"`
	Nodes []Node `json:"nodes"`
}

// Node represents an upstream node
type Node struct {
	Host   string `json:"host"`
	Port   int    `json:"port"`
	Weight int    `json:"weight"`
}

// NewClient creates a new APISIX client
func NewClient(config *Config) (*Client, error) {
	return &Client{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		config: config,
	}, nil
}

// CreateRoute creates a new route in APISIX
func (c *Client) CreateRoute(ctx context.Context, route *Route) error {
	logger.Logger.Info("Creating APISIX route",
		logger.String("route_id", route.ID),
		logger.String("uri", route.URI),
	)

	// Marshal route to JSON
	data, err := json.Marshal(route)
	if err != nil {
		return fmt.Errorf("failed to marshal route: %w", err)
	}

	// Create HTTP request
	url := fmt.Sprintf("%s/apisix/admin/routes/%s", c.config.AdminURL, route.ID)
	req, err := http.NewRequestWithContext(ctx, "PUT", url, bytes.NewBuffer(data))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-KEY", c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to create APISIX route", logger.Error(err))
		return fmt.Errorf("failed to create route: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("APISIX returned error: %d - %s", resp.StatusCode, string(body))
	}

	logger.Logger.Info("APISIX route created successfully")
	return nil
}

// GetRoute retrieves a route from APISIX
func (c *Client) GetRoute(ctx context.Context, routeID string) (*Route, error) {
	logger.Logger.Info("Getting APISIX route",
		logger.String("route_id", routeID),
	)

	// Create HTTP request
	url := fmt.Sprintf("%s/apisix/admin/routes/%s", c.config.AdminURL, routeID)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-API-KEY", c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to get APISIX route", logger.Error(err))
		return nil, fmt.Errorf("failed to get route: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("APISIX returned error: %d - %s", resp.StatusCode, string(body))
	}

	// Parse response
	var result struct {
		Node struct {
			Value Route `json:"value"`
		} `json:"node"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &result.Node.Value, nil
}

// DeleteRoute deletes a route from APISIX
func (c *Client) DeleteRoute(ctx context.Context, routeID string) error {
	logger.Logger.Info("Deleting APISIX route",
		logger.String("route_id", routeID),
	)

	// Create HTTP request
	url := fmt.Sprintf("%s/apisix/admin/routes/%s", c.config.AdminURL, routeID)
	req, err := http.NewRequestWithContext(ctx, "DELETE", url, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-API-KEY", c.config.APIKey)

	// Send request
	resp, err := c.httpClient.Do(req)
	if err != nil {
		logger.Logger.Error("Failed to delete APISIX route", logger.Error(err))
		return fmt.Errorf("failed to delete route: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("APISIX returned error: %d - %s", resp.StatusCode, string(body))
	}

	logger.Logger.Info("APISIX route deleted successfully")
	return nil
}

// EnableRateLimiting enables rate limiting on a route
func (c *Client) EnableRateLimiting(ctx context.Context, routeID string, count, timeWindow int) error {
	logger.Logger.Info("Enabling rate limiting on APISIX route",
		logger.String("route_id", routeID),
		logger.Int("count", count),
		logger.Int("time_window", timeWindow),
	)

	// Get existing route
	route, err := c.GetRoute(ctx, routeID)
	if err != nil {
		return fmt.Errorf("failed to get route: %w", err)
	}

	// Add rate limiting plugin
	if route.Plugins == nil {
		route.Plugins = make(map[string]interface{})
	}
	route.Plugins["limit-count"] = map[string]interface{}{
		"count":         count,
		"time_window":   timeWindow,
		"rejected_code": 429,
	}

	// Update route
	return c.CreateRoute(ctx, route)
}

// EnableAuthentication enables JWT authentication on a route
func (c *Client) EnableAuthentication(ctx context.Context, routeID, keycloakURL, realm string) error {
	logger.Logger.Info("Enabling authentication on APISIX route",
		logger.String("route_id", routeID),
	)

	// Get existing route
	route, err := c.GetRoute(ctx, routeID)
	if err != nil {
		return fmt.Errorf("failed to get route: %w", err)
	}

	// Add JWT authentication plugin
	if route.Plugins == nil {
		route.Plugins = make(map[string]interface{})
	}
	route.Plugins["openid-connect"] = map[string]interface{}{
		"client_id":     "workflow-orchestrator",
		"client_secret": "secret",
		"discovery":     fmt.Sprintf("%s/realms/%s/.well-known/openid-configuration", keycloakURL, realm),
		"scope":         "openid profile email",
		"bearer_only":   true,
		"realm":         realm,
	}

	// Update route
	return c.CreateRoute(ctx, route)
}

// ConfigureWorkflowOrchestratorRoute configures the main orchestrator route
func (c *Client) ConfigureWorkflowOrchestratorRoute(ctx context.Context, orchestratorHost string, orchestratorPort int) error {
	logger.Logger.Info("Configuring workflow orchestrator route in APISIX")

	route := &Route{
		ID:      "workflow-orchestrator",
		URI:     "/api/workflows/*",
		Name:    "Workflow Orchestrator API",
		Methods: []string{"GET", "POST", "PUT", "DELETE"},
		Upstream: &Upstream{
			Type: "roundrobin",
			Nodes: []Node{
				{
					Host:   orchestratorHost,
					Port:   orchestratorPort,
					Weight: 1,
				},
			},
		},
		Status: 1,
	}

	return c.CreateRoute(ctx, route)
}

// Close closes the APISIX client
func (c *Client) Close() error {
	c.httpClient.CloseIdleConnections()
	return nil
}

