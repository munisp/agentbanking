// 54Link Agent Store Service — Go Microservice
// Port: 8220
// Purpose: Agent-level store registration, discovery, delivery zones, fulfillment
// Integrations: Kafka (Dapr), Redis, Keycloak JWT, Temporal, Permify, APISIX,
//               TigerBeetle (payment holds), Fluvio (event streaming)

package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
)

// ── Configuration ──────────────────────────────────────────────────────────────

type Config struct {
	Port            string
	PostgresURL     string
	RedisURL        string
	KafkaBrokers    string
	TemporalHost    string
	KeycloakURL     string
	PermifyHost     string
	TigerBeetleAddr string
	DaprHTTPPort    string
	FluvioEndpoint  string
	ApisixAdminURL  string
	Environment     string
}

func loadConfig() Config {
	return Config{
		Port:            envOr("PORT", "8220"),
		PostgresURL:     envOr("DATABASE_URL", "postgresql://ngapp:password@localhost:5432/ngapp"),
		RedisURL:        envOr("REDIS_URL", "redis://localhost:6379/10"),
		KafkaBrokers:    envOr("KAFKA_BROKERS", "localhost:9092"),
		TemporalHost:    envOr("TEMPORAL_HOST", "localhost:7233"),
		KeycloakURL:     envOr("KEYCLOAK_URL", "http://localhost:8080"),
		PermifyHost:     envOr("PERMIFY_HOST", "localhost:3476"),
		TigerBeetleAddr: envOr("TIGERBEETLE_ADDR", "localhost:3000"),
		DaprHTTPPort:    envOr("DAPR_HTTP_PORT", "3500"),
		FluvioEndpoint:  envOr("FLUVIO_ENDPOINT", "localhost:9003"),
		ApisixAdminURL:  envOr("APISIX_ADMIN_URL", "http://localhost:9180"),
		Environment:     envOr("ENVIRONMENT", "development"),
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// ── Models ─────────────────────────────────────────────────────────────────────

type AgentStore struct {
	ID                   int64              `json:"id"`
	AgentID              int64              `json:"agentId"`
	AgentCode            string             `json:"agentCode"`
	Slug                 string             `json:"slug"`
	StoreName            string             `json:"storeName"`
	Description          string             `json:"description,omitempty"`
	LogoURL              string             `json:"logoUrl,omitempty"`
	BannerURL            string             `json:"bannerUrl,omitempty"`
	ThemeColor           string             `json:"themeColor"`
	AboutHTML            string             `json:"aboutHtml,omitempty"`
	Phone                string             `json:"phone,omitempty"`
	Email                string             `json:"email,omitempty"`
	Address              string             `json:"address,omitempty"`
	City                 string             `json:"city,omitempty"`
	State                string             `json:"state,omitempty"`
	LGA                  string             `json:"lga,omitempty"`
	Latitude             float64            `json:"latitude,omitempty"`
	Longitude            float64            `json:"longitude,omitempty"`
	BusinessHours        map[string]DayHour `json:"businessHours,omitempty"`
	Categories           []string           `json:"categories"`
	Tags                 []string           `json:"tags"`
	DeliveryEnabled      bool               `json:"deliveryEnabled"`
	PickupEnabled        bool               `json:"pickupEnabled"`
	MinOrderAmount       float64            `json:"minOrderAmount"`
	PlatformCommissionPct float64           `json:"platformCommissionPct"`
	Status               string             `json:"status"`
	IsVerified           bool               `json:"isVerified"`
	TotalSales           int                `json:"totalSales"`
	TotalRevenue         float64            `json:"totalRevenue"`
	AverageRating        float64            `json:"averageRating"`
	ReviewCount          int                `json:"reviewCount"`
	CreatedAt            time.Time          `json:"createdAt"`
	UpdatedAt            time.Time          `json:"updatedAt"`
}

type DayHour struct {
	Open  string `json:"open"`
	Close string `json:"close"`
}

type DeliveryZone struct {
	ID               int64    `json:"id"`
	StoreID          int64    `json:"storeId"`
	ZoneName         string   `json:"zoneName"`
	Description      string   `json:"description,omitempty"`
	DeliveryFee      float64  `json:"deliveryFee"`
	EstimatedMinutes int      `json:"estimatedMinutes"`
	MaxDistanceKm    float64  `json:"maxDistanceKm,omitempty"`
	Areas            []string `json:"areas"`
	IsActive         bool     `json:"isActive"`
}

type DeliveryTracking struct {
	ID                int64     `json:"id"`
	OrderID           int64     `json:"orderId"`
	StoreID           int64     `json:"storeId"`
	DeliveryZoneID    int64     `json:"deliveryZoneId,omitempty"`
	Status            string    `json:"status"`
	RiderName         string    `json:"riderName,omitempty"`
	RiderPhone        string    `json:"riderPhone,omitempty"`
	TrackingCode      string    `json:"trackingCode"`
	EstimatedDelivery time.Time `json:"estimatedDelivery,omitempty"`
	ActualDelivery    time.Time `json:"actualDelivery,omitempty"`
	DeliveryNotes     string    `json:"deliveryNotes,omitempty"`
	Latitude          float64   `json:"latitude,omitempty"`
	Longitude         float64   `json:"longitude,omitempty"`
}

type FulfillmentOrder struct {
	OrderID     int64   `json:"orderId"`
	StoreID     int64   `json:"storeId"`
	AgentID     int64   `json:"agentId"`
	Status      string  `json:"status"`
	Items       []OrderItem `json:"items"`
	Total       float64 `json:"total"`
	CustomerName string `json:"customerName"`
	ShippingAddr string `json:"shippingAddress"`
}

type OrderItem struct {
	ProductID int64   `json:"productId"`
	SKU       string  `json:"sku"`
	Name      string  `json:"name"`
	Quantity  int     `json:"quantity"`
	Price     float64 `json:"price"`
}

// ── Request/Response Types ─────────────────────────────────────────────────────

type RegisterStoreRequest struct {
	AgentID         int64              `json:"agentId"`
	AgentCode       string             `json:"agentCode"`
	StoreName       string             `json:"storeName"`
	Description     string             `json:"description,omitempty"`
	Phone           string             `json:"phone,omitempty"`
	Email           string             `json:"email,omitempty"`
	Address         string             `json:"address,omitempty"`
	City            string             `json:"city,omitempty"`
	State           string             `json:"state,omitempty"`
	LGA             string             `json:"lga,omitempty"`
	Latitude        float64            `json:"latitude,omitempty"`
	Longitude       float64            `json:"longitude,omitempty"`
	Categories      []string           `json:"categories"`
	DeliveryEnabled bool               `json:"deliveryEnabled"`
	PickupEnabled   bool               `json:"pickupEnabled"`
	BusinessHours   map[string]DayHour `json:"businessHours,omitempty"`
}

type DiscoverStoresRequest struct {
	Limit    int    `json:"limit"`
	Offset   int    `json:"offset"`
	Search   string `json:"search,omitempty"`
	City     string `json:"city,omitempty"`
	State    string `json:"state,omitempty"`
	Category string `json:"category,omitempty"`
	SortBy   string `json:"sortBy"`
}

type StoreListResponse struct {
	Stores []AgentStore `json:"stores"`
	Total  int          `json:"total"`
}

type NearbyRequest struct {
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	RadiusKm  float64 `json:"radiusKm"`
	Limit     int     `json:"limit"`
}

type FulfillmentStatusUpdate struct {
	OrderID  int64  `json:"orderId"`
	Status   string `json:"status"`
	RiderName string `json:"riderName,omitempty"`
	RiderPhone string `json:"riderPhone,omitempty"`
	Notes    string `json:"notes,omitempty"`
}

// ── In-Memory Store (production: PostgreSQL) ───────────────────────────────────

type StoreRegistry struct {
	mu             sync.RWMutex
	stores         map[int64]*AgentStore
	slugIndex      map[string]int64
	agentIndex     map[int64]int64 // agentID -> storeID
	codeIndex      map[string]int64
	deliveryZones  map[int64][]DeliveryZone
	tracking       map[int64]*DeliveryTracking // orderID -> tracking
	fulfillment    map[int64]*FulfillmentOrder
	nextStoreID    int64
	nextZoneID     int64
	nextTrackingID int64
}

func NewStoreRegistry() *StoreRegistry {
	return &StoreRegistry{
		stores:         make(map[int64]*AgentStore),
		slugIndex:      make(map[string]int64),
		agentIndex:     make(map[int64]int64),
		codeIndex:      make(map[string]int64),
		deliveryZones:  make(map[int64][]DeliveryZone),
		tracking:       make(map[int64]*DeliveryTracking),
		fulfillment:    make(map[int64]*FulfillmentOrder),
		nextStoreID:    1,
		nextZoneID:     1,
		nextTrackingID: 1,
	}
}

// ── Middleware Clients ──────────────────────────────────────────────────────────

type MiddlewareClients struct {
	config       Config
	httpClient   *http.Client
	registry     *StoreRegistry
}

func NewMiddlewareClients(cfg Config) *MiddlewareClients {
	return &MiddlewareClients{
		config:     cfg,
		httpClient: &http.Client{Timeout: 10 * time.Second},
		registry:   NewStoreRegistry(),
	}
}

// Dapr Pub/Sub
func (mc *MiddlewareClients) publishEvent(topic string, data interface{}) error {
	body, _ := json.Marshal(data)
	url := fmt.Sprintf("http://localhost:%s/v1.0/publish/kafka-pubsub/%s", mc.config.DaprHTTPPort, topic)
	resp, err := mc.httpClient.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		log.Printf("[Dapr] publish %s failed: %v", topic, err)
		return err
	}
	defer resp.Body.Close()
	return nil
}

// Keycloak JWT validation
func (mc *MiddlewareClients) validateJWT(token string) (map[string]interface{}, error) {
	url := fmt.Sprintf("%s/realms/54link/protocol/openid-connect/userinfo", mc.config.KeycloakURL)
	req, _ := http.NewRequest("GET", url, nil)
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := mc.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("keycloak unreachable: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("invalid token: status %d", resp.StatusCode)
	}
	var claims map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&claims)
	return claims, nil
}

// Redis cache
func (mc *MiddlewareClients) cacheSet(key string, value interface{}, ttlSec int) {
	body, _ := json.Marshal(map[string]interface{}{
		"key":   key,
		"value": value,
	})
	url := fmt.Sprintf("http://localhost:%s/v1.0/state/redis-store", mc.config.DaprHTTPPort)
	mc.httpClient.Post(url, "application/json", bytes.NewReader(body))
}

// Permify: grant store-owner permission
func (mc *MiddlewareClients) grantStoreOwner(agentID, storeID int64) {
	body, _ := json.Marshal(map[string]interface{}{
		"metadata":  map[string]string{"schema_version": ""},
		"tuples":    []map[string]interface{}{
			{
				"entity":   map[string]string{"type": "store", "id": fmt.Sprintf("%d", storeID)},
				"relation": "owner",
				"subject":  map[string]interface{}{"type": "user", "id": fmt.Sprintf("%d", agentID)},
			},
		},
	})
	url := fmt.Sprintf("http://%s/v1/tenants/t1/relationships/write", mc.config.PermifyHost)
	mc.httpClient.Post(url, "application/json", bytes.NewReader(body))
}

// Fluvio streaming
func (mc *MiddlewareClients) streamToFluvio(topic string, data interface{}) {
	body, _ := json.Marshal(data)
	url := fmt.Sprintf("http://%s/produce/%s", mc.config.FluvioEndpoint, topic)
	mc.httpClient.Post(url, "application/json", bytes.NewReader(body))
}

// Temporal: start fulfillment workflow
func (mc *MiddlewareClients) startFulfillmentWorkflow(orderID int64, storeID int64) {
	body, _ := json.Marshal(map[string]interface{}{
		"workflow":  "AgentStoreFulfillment",
		"taskQueue": "agent-store-fulfillment",
		"input":     map[string]int64{"orderId": orderID, "storeId": storeID},
	})
	url := fmt.Sprintf("http://%s/api/v1/namespaces/default/workflows", mc.config.TemporalHost)
	mc.httpClient.Post(url, "application/json", bytes.NewReader(body))
}

// ── Slug Generation ────────────────────────────────────────────────────────────

func slugify(s string) string {
	s = strings.ToLower(s)
	var result []byte
	for _, c := range s {
		if (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') {
			result = append(result, byte(c))
		} else if c == ' ' || c == '-' {
			if len(result) > 0 && result[len(result)-1] != '-' {
				result = append(result, '-')
			}
		}
	}
	return strings.Trim(string(result), "-")
}

func (r *StoreRegistry) uniqueSlug(base string) string {
	slug := slugify(base)
	r.mu.RLock()
	defer r.mu.RUnlock()
	if _, exists := r.slugIndex[slug]; !exists {
		return slug
	}
	for i := 1; i < 100; i++ {
		candidate := fmt.Sprintf("%s-%d", slug, i)
		if _, exists := r.slugIndex[candidate]; !exists {
			return candidate
		}
	}
	h := sha256.Sum256([]byte(fmt.Sprintf("%s-%d", base, time.Now().UnixNano())))
	return slug + "-" + hex.EncodeToString(h[:4])
}

// ── Haversine Distance ─────────────────────────────────────────────────────────

func haversineKm(lat1, lon1, lat2, lon2 float64) float64 {
	const R = 6371.0
	dLat := (lat2 - lat1) * math.Pi / 180
	dLon := (lon2 - lon1) * math.Pi / 180
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*math.Pi/180)*math.Cos(lat2*math.Pi/180)*
			math.Sin(dLon/2)*math.Sin(dLon/2)
	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
	return R * c
}

// ── Handlers ───────────────────────────────────────────────────────────────────

// POST /api/v1/stores/register
func (mc *MiddlewareClients) handleRegisterStore(w http.ResponseWriter, r *http.Request) {
	var req RegisterStoreRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid request body"}`, http.StatusBadRequest)
		return
	}
	if req.StoreName == "" || req.AgentCode == "" {
		http.Error(w, `{"error":"storeName and agentCode required"}`, http.StatusBadRequest)
		return
	}

	reg := mc.registry
	reg.mu.Lock()

	// Check if agent already has a store
	if _, exists := reg.agentIndex[req.AgentID]; exists {
		reg.mu.Unlock()
		http.Error(w, `{"error":"agent already has a store"}`, http.StatusConflict)
		return
	}

	slug := slugify(req.StoreName)
	if _, exists := reg.slugIndex[slug]; exists {
		for i := 1; i < 100; i++ {
			candidate := fmt.Sprintf("%s-%d", slug, i)
			if _, exists := reg.slugIndex[candidate]; !exists {
				slug = candidate
				break
			}
		}
	}

	store := &AgentStore{
		ID:                    reg.nextStoreID,
		AgentID:               req.AgentID,
		AgentCode:             req.AgentCode,
		Slug:                  slug,
		StoreName:             req.StoreName,
		Description:           req.Description,
		Phone:                 req.Phone,
		Email:                 req.Email,
		Address:               req.Address,
		City:                  req.City,
		State:                 req.State,
		LGA:                   req.LGA,
		Latitude:              req.Latitude,
		Longitude:             req.Longitude,
		BusinessHours:         req.BusinessHours,
		Categories:            req.Categories,
		Tags:                  []string{},
		DeliveryEnabled:       req.DeliveryEnabled,
		PickupEnabled:         req.PickupEnabled,
		MinOrderAmount:        0,
		PlatformCommissionPct: 5.00,
		Status:                "active",
		ThemeColor:            "#3b82f6",
		CreatedAt:             time.Now(),
		UpdatedAt:             time.Now(),
	}
	if store.Categories == nil {
		store.Categories = []string{}
	}

	reg.stores[store.ID] = store
	reg.slugIndex[store.Slug] = store.ID
	reg.agentIndex[store.AgentID] = store.ID
	reg.codeIndex[store.AgentCode] = store.ID
	reg.nextStoreID++
	reg.mu.Unlock()

	// Async middleware integrations
	go func() {
		mc.grantStoreOwner(store.AgentID, store.ID)
		mc.publishEvent("agent-store.registered", map[string]interface{}{
			"storeId":   store.ID,
			"agentId":   store.AgentID,
			"agentCode": store.AgentCode,
			"storeName": store.StoreName,
			"city":      store.City,
			"state":     store.State,
		})
		mc.streamToFluvio("agent-store-events", map[string]interface{}{
			"event":   "store.registered",
			"storeId": store.ID,
			"ts":      time.Now().Unix(),
		})
		mc.cacheSet(fmt.Sprintf("store:slug:%s", store.Slug), store, 3600)
		mc.cacheSet(fmt.Sprintf("store:agent:%d", store.AgentID), store, 3600)
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(store)
}

// GET /api/v1/stores/discover
func (mc *MiddlewareClients) handleDiscoverStores(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	search := r.URL.Query().Get("search")
	city := r.URL.Query().Get("city")
	state := r.URL.Query().Get("state")
	category := r.URL.Query().Get("category")
	sortBy := r.URL.Query().Get("sortBy")

	if limit <= 0 || limit > 100 {
		limit = 20
	}

	reg := mc.registry
	reg.mu.RLock()
	defer reg.mu.RUnlock()

	var filtered []*AgentStore
	for _, s := range reg.stores {
		if s.Status != "active" {
			continue
		}
		if search != "" {
			low := strings.ToLower(search)
			if !strings.Contains(strings.ToLower(s.StoreName), low) &&
				!strings.Contains(strings.ToLower(s.Description), low) {
				continue
			}
		}
		if city != "" && !strings.EqualFold(s.City, city) {
			continue
		}
		if state != "" && !strings.EqualFold(s.State, state) {
			continue
		}
		if category != "" {
			found := false
			for _, c := range s.Categories {
				if strings.EqualFold(c, category) {
					found = true
					break
				}
			}
			if !found {
				continue
			}
		}
		filtered = append(filtered, s)
	}

	// Sort
	switch sortBy {
	case "rating":
		sortStores(filtered, func(a, b *AgentStore) bool { return a.AverageRating > b.AverageRating })
	case "newest":
		sortStores(filtered, func(a, b *AgentStore) bool { return a.CreatedAt.After(b.CreatedAt) })
	case "name":
		sortStores(filtered, func(a, b *AgentStore) bool { return a.StoreName < b.StoreName })
	default: // popular
		sortStores(filtered, func(a, b *AgentStore) bool { return a.TotalSales > b.TotalSales })
	}

	total := len(filtered)
	if offset >= total {
		filtered = nil
	} else {
		end := offset + limit
		if end > total {
			end = total
		}
		filtered = filtered[offset:end]
	}

	result := make([]AgentStore, len(filtered))
	for i, s := range filtered {
		result[i] = *s
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(StoreListResponse{Stores: result, Total: total})
}

// Bubble sort (small dataset, no stdlib sort dependency on struct)
func sortStores(stores []*AgentStore, less func(a, b *AgentStore) bool) {
	for i := 0; i < len(stores); i++ {
		for j := i + 1; j < len(stores); j++ {
			if less(stores[j], stores[i]) {
				stores[i], stores[j] = stores[j], stores[i]
			}
		}
	}
}

// GET /api/v1/stores/{slug}
func (mc *MiddlewareClients) handleGetStoreBySlug(w http.ResponseWriter, r *http.Request) {
	slug := mux.Vars(r)["slug"]
	reg := mc.registry
	reg.mu.RLock()
	defer reg.mu.RUnlock()

	storeID, ok := reg.slugIndex[slug]
	if !ok {
		http.Error(w, `{"error":"store not found"}`, http.StatusNotFound)
		return
	}
	store := reg.stores[storeID]
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(store)
}

// GET /api/v1/stores/agent/{agentCode}
func (mc *MiddlewareClients) handleGetStoreByAgent(w http.ResponseWriter, r *http.Request) {
	code := mux.Vars(r)["agentCode"]
	reg := mc.registry
	reg.mu.RLock()
	defer reg.mu.RUnlock()

	storeID, ok := reg.codeIndex[code]
	if !ok {
		http.Error(w, `{"error":"store not found"}`, http.StatusNotFound)
		return
	}
	store := reg.stores[storeID]
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(store)
}

// POST /api/v1/stores/{storeId}/update
func (mc *MiddlewareClients) handleUpdateStore(w http.ResponseWriter, r *http.Request) {
	storeID, _ := strconv.ParseInt(mux.Vars(r)["storeId"], 10, 64)

	var updates map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		http.Error(w, `{"error":"invalid body"}`, http.StatusBadRequest)
		return
	}

	reg := mc.registry
	reg.mu.Lock()
	defer reg.mu.Unlock()

	store, ok := reg.stores[storeID]
	if !ok {
		http.Error(w, `{"error":"store not found"}`, http.StatusNotFound)
		return
	}

	if v, ok := updates["storeName"].(string); ok { store.StoreName = v }
	if v, ok := updates["description"].(string); ok { store.Description = v }
	if v, ok := updates["logoUrl"].(string); ok { store.LogoURL = v }
	if v, ok := updates["bannerUrl"].(string); ok { store.BannerURL = v }
	if v, ok := updates["themeColor"].(string); ok { store.ThemeColor = v }
	if v, ok := updates["aboutHtml"].(string); ok { store.AboutHTML = v }
	if v, ok := updates["phone"].(string); ok { store.Phone = v }
	if v, ok := updates["email"].(string); ok { store.Email = v }
	if v, ok := updates["address"].(string); ok { store.Address = v }
	if v, ok := updates["city"].(string); ok { store.City = v }
	if v, ok := updates["state"].(string); ok { store.State = v }
	if v, ok := updates["lga"].(string); ok { store.LGA = v }
	if v, ok := updates["deliveryEnabled"].(bool); ok { store.DeliveryEnabled = v }
	if v, ok := updates["pickupEnabled"].(bool); ok { store.PickupEnabled = v }
	store.UpdatedAt = time.Now()

	go mc.publishEvent("agent-store.updated", map[string]interface{}{
		"storeId": store.ID, "agentId": store.AgentID,
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(store)
}

// GET /api/v1/stores/nearby
func (mc *MiddlewareClients) handleNearbyStores(w http.ResponseWriter, r *http.Request) {
	lat, _ := strconv.ParseFloat(r.URL.Query().Get("lat"), 64)
	lon, _ := strconv.ParseFloat(r.URL.Query().Get("lon"), 64)
	radius, _ := strconv.ParseFloat(r.URL.Query().Get("radius"), 64)
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if radius <= 0 { radius = 10.0 }
	if limit <= 0 { limit = 20 }

	reg := mc.registry
	reg.mu.RLock()
	defer reg.mu.RUnlock()

	type storeWithDist struct {
		Store    AgentStore `json:"store"`
		Distance float64    `json:"distanceKm"`
	}
	var results []storeWithDist
	for _, s := range reg.stores {
		if s.Status != "active" || s.Latitude == 0 || s.Longitude == 0 { continue }
		d := haversineKm(lat, lon, s.Latitude, s.Longitude)
		if d <= radius {
			results = append(results, storeWithDist{Store: *s, Distance: math.Round(d*100)/100})
		}
	}
	// Sort by distance
	for i := 0; i < len(results); i++ {
		for j := i + 1; j < len(results); j++ {
			if results[j].Distance < results[i].Distance {
				results[i], results[j] = results[j], results[i]
			}
		}
	}
	if len(results) > limit { results = results[:limit] }

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"stores": results, "total": len(results)})
}

// ── Delivery Zone Handlers ─────────────────────────────────────────────────────

// POST /api/v1/stores/{storeId}/delivery-zones
func (mc *MiddlewareClients) handleCreateDeliveryZone(w http.ResponseWriter, r *http.Request) {
	storeID, _ := strconv.ParseInt(mux.Vars(r)["storeId"], 10, 64)
	var zone DeliveryZone
	if err := json.NewDecoder(r.Body).Decode(&zone); err != nil {
		http.Error(w, `{"error":"invalid body"}`, http.StatusBadRequest)
		return
	}

	reg := mc.registry
	reg.mu.Lock()
	zone.ID = reg.nextZoneID
	zone.StoreID = storeID
	zone.IsActive = true
	if zone.Areas == nil { zone.Areas = []string{} }
	reg.deliveryZones[storeID] = append(reg.deliveryZones[storeID], zone)
	reg.nextZoneID++
	reg.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(zone)
}

// GET /api/v1/stores/{storeId}/delivery-zones
func (mc *MiddlewareClients) handleListDeliveryZones(w http.ResponseWriter, r *http.Request) {
	storeID, _ := strconv.ParseInt(mux.Vars(r)["storeId"], 10, 64)

	reg := mc.registry
	reg.mu.RLock()
	zones := reg.deliveryZones[storeID]
	reg.mu.RUnlock()

	if zones == nil { zones = []DeliveryZone{} }
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{"zones": zones})
}

// ── Fulfillment Handlers ───────────────────────────────────────────────────────

// POST /api/v1/fulfillment/assign-rider
func (mc *MiddlewareClients) handleAssignRider(w http.ResponseWriter, r *http.Request) {
	var req struct {
		OrderID    int64  `json:"orderId"`
		StoreID    int64  `json:"storeId"`
		RiderName  string `json:"riderName"`
		RiderPhone string `json:"riderPhone"`
		ZoneID     int64  `json:"zoneId"`
		EstMinutes int    `json:"estimatedMinutes"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid body"}`, http.StatusBadRequest)
		return
	}

	reg := mc.registry
	reg.mu.Lock()
	trackCode := fmt.Sprintf("DT-%s-%04d", strings.ToUpper(strconv.FormatInt(time.Now().Unix(), 36)), reg.nextTrackingID)
	tracking := &DeliveryTracking{
		ID:                reg.nextTrackingID,
		OrderID:           req.OrderID,
		StoreID:           req.StoreID,
		DeliveryZoneID:    req.ZoneID,
		Status:            "assigned",
		RiderName:         req.RiderName,
		RiderPhone:        req.RiderPhone,
		TrackingCode:      trackCode,
		EstimatedDelivery: time.Now().Add(time.Duration(req.EstMinutes) * time.Minute),
	}
	reg.tracking[req.OrderID] = tracking
	reg.nextTrackingID++
	reg.mu.Unlock()

	go func() {
		mc.publishEvent("delivery.rider.assigned", map[string]interface{}{
			"orderId": req.OrderID, "storeId": req.StoreID,
			"riderName": req.RiderName, "trackingCode": trackCode,
		})
		mc.startFulfillmentWorkflow(req.OrderID, req.StoreID)
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(tracking)
}

// POST /api/v1/fulfillment/update-status
func (mc *MiddlewareClients) handleUpdateFulfillmentStatus(w http.ResponseWriter, r *http.Request) {
	var req FulfillmentStatusUpdate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, `{"error":"invalid body"}`, http.StatusBadRequest)
		return
	}

	validStatuses := map[string]bool{
		"pending": true, "assigned": true, "picked_up": true,
		"in_transit": true, "delivered": true, "failed": true, "returned": true,
	}
	if !validStatuses[req.Status] {
		http.Error(w, `{"error":"invalid status"}`, http.StatusBadRequest)
		return
	}

	reg := mc.registry
	reg.mu.Lock()
	tracking, ok := reg.tracking[req.OrderID]
	if !ok {
		reg.mu.Unlock()
		http.Error(w, `{"error":"tracking not found"}`, http.StatusNotFound)
		return
	}
	tracking.Status = req.Status
	if req.Status == "delivered" { tracking.ActualDelivery = time.Now() }
	if req.Notes != "" { tracking.DeliveryNotes = req.Notes }
	reg.mu.Unlock()

	go mc.publishEvent("delivery.status.updated", map[string]interface{}{
		"orderId": req.OrderID, "status": req.Status, "trackingCode": tracking.TrackingCode,
	})

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tracking)
}

// GET /api/v1/fulfillment/track/{trackingCode}
func (mc *MiddlewareClients) handleTrackDelivery(w http.ResponseWriter, r *http.Request) {
	code := mux.Vars(r)["trackingCode"]

	reg := mc.registry
	reg.mu.RLock()
	defer reg.mu.RUnlock()

	for _, t := range reg.tracking {
		if t.TrackingCode == code {
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(t)
			return
		}
	}
	http.Error(w, `{"error":"tracking not found"}`, http.StatusNotFound)
}

// ── Health Check ───────────────────────────────────────────────────────────────

func handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "agent-store-service",
		"version": "1.0.0",
		"time":    time.Now().UTC().Format(time.RFC3339),
	})
}

// ── Register APISIX Routes ─────────────────────────────────────────────────────

func (mc *MiddlewareClients) registerAPIRoutes() {
	routes := []struct{ URI, Upstream string }{
		{"/api/agent-store/*", fmt.Sprintf("http://localhost:%s", mc.config.Port)},
	}
	for _, route := range routes {
		body, _ := json.Marshal(map[string]interface{}{
			"uri":      route.URI,
			"upstream": map[string]interface{}{"type": "roundrobin", "nodes": map[string]int{route.Upstream: 1}},
		})
		req, _ := http.NewRequest("PUT", mc.config.ApisixAdminURL+"/apisix/admin/routes/agent-store", bytes.NewReader(body))
		req.Header.Set("X-API-KEY", "edd1c9f034335f136f87ad84b625c8f1")
		req.Header.Set("Content-Type", "application/json")
		mc.httpClient.Do(req)
	}
}

// ── Main ───────────────────────────────────────────────────────────────────────

func main() {
	cfg := loadConfig()
	mc := NewMiddlewareClients(cfg)
	r := mux.NewRouter()

	// Health
	r.HandleFunc("/health", handleHealth).Methods("GET")

	// Store CRUD
	r.HandleFunc("/api/v1/stores/register", mc.handleRegisterStore).Methods("POST")
	r.HandleFunc("/api/v1/stores/discover", mc.handleDiscoverStores).Methods("GET")
	r.HandleFunc("/api/v1/stores/nearby", mc.handleNearbyStores).Methods("GET")
	r.HandleFunc("/api/v1/stores/{slug}", mc.handleGetStoreBySlug).Methods("GET")
	r.HandleFunc("/api/v1/stores/agent/{agentCode}", mc.handleGetStoreByAgent).Methods("GET")
	r.HandleFunc("/api/v1/stores/{storeId}/update", mc.handleUpdateStore).Methods("POST")

	// Delivery Zones
	r.HandleFunc("/api/v1/stores/{storeId}/delivery-zones", mc.handleCreateDeliveryZone).Methods("POST")
	r.HandleFunc("/api/v1/stores/{storeId}/delivery-zones", mc.handleListDeliveryZones).Methods("GET")

	// Fulfillment
	r.HandleFunc("/api/v1/fulfillment/assign-rider", mc.handleAssignRider).Methods("POST")
	r.HandleFunc("/api/v1/fulfillment/update-status", mc.handleUpdateFulfillmentStatus).Methods("POST")
	r.HandleFunc("/api/v1/fulfillment/track/{trackingCode}", mc.handleTrackDelivery).Methods("GET")

	go mc.registerAPIRoutes()

	log.Printf("Agent Store Service starting on :%s", cfg.Port)
	log.Fatal(http.ListenAndServe(":"+cfg.Port, r))
}

// Suppress unused import warnings
var _ = io.EOF
var _ = context.Background
