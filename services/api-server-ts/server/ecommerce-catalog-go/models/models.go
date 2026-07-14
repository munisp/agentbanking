package models

import "time"

// Product represents a sellable item in the catalog
type Product struct {
	ID          int64     `json:"id"`
	SKU         string    `json:"sku"`
	Name        string    `json:"name"`
	Description string    `json:"description"`
	CategoryID  int64     `json:"categoryId"`
	Price       float64   `json:"price"`
	Currency    string    `json:"currency"`
	ImageURL    string    `json:"imageUrl,omitempty"`
	IsActive    bool      `json:"isActive"`
	MerchantID  int64     `json:"merchantId"`
	AgentID     int64     `json:"agentId,omitempty"`
	Weight      float64   `json:"weight,omitempty"`
	Dimensions  string    `json:"dimensions,omitempty"`
	Tags        []string  `json:"tags,omitempty"`
	Attributes  map[string]string `json:"attributes,omitempty"`
	CreatedAt   time.Time `json:"createdAt"`
	UpdatedAt   time.Time `json:"updatedAt"`
}

// Category organizes products
type Category struct {
	ID          int64     `json:"id"`
	Name        string    `json:"name"`
	Slug        string    `json:"slug"`
	Description string    `json:"description,omitempty"`
	ParentID    *int64    `json:"parentId,omitempty"`
	ImageURL    string    `json:"imageUrl,omitempty"`
	SortOrder   int       `json:"sortOrder"`
	IsActive    bool      `json:"isActive"`
	CreatedAt   time.Time `json:"createdAt"`
}

// Order represents a customer purchase
type Order struct {
	ID             int64       `json:"id"`
	OrderNumber    string      `json:"orderNumber"`
	CustomerID     int64       `json:"customerId"`
	MerchantID     int64       `json:"merchantId"`
	AgentID        int64       `json:"agentId,omitempty"`
	Status         OrderStatus `json:"status"`
	Items          []OrderItem `json:"items"`
	SubTotal       float64     `json:"subTotal"`
	Tax            float64     `json:"tax"`
	ShippingFee    float64     `json:"shippingFee"`
	Discount       float64     `json:"discount"`
	Total          float64     `json:"total"`
	Currency       string      `json:"currency"`
	PaymentMethod  string      `json:"paymentMethod"`
	PaymentRef     string      `json:"paymentRef,omitempty"`
	ShippingAddr   Address     `json:"shippingAddress"`
	Notes          string      `json:"notes,omitempty"`
	OfflineCreated bool        `json:"offlineCreated"`
	SyncedAt       *time.Time  `json:"syncedAt,omitempty"`
	CreatedAt      time.Time   `json:"createdAt"`
	UpdatedAt      time.Time   `json:"updatedAt"`
	FulfilledAt    *time.Time  `json:"fulfilledAt,omitempty"`
	CancelledAt    *time.Time  `json:"cancelledAt,omitempty"`
}

// OrderItem is a line item within an order
type OrderItem struct {
	ID        int64   `json:"id"`
	OrderID   int64   `json:"orderId"`
	ProductID int64   `json:"productId"`
	SKU       string  `json:"sku"`
	Name      string  `json:"name"`
	Quantity  int     `json:"quantity"`
	UnitPrice float64 `json:"unitPrice"`
	Total     float64 `json:"total"`
}

// Address for shipping
type Address struct {
	Street  string `json:"street"`
	City    string `json:"city"`
	State   string `json:"state"`
	Country string `json:"country"`
	ZipCode string `json:"zipCode"`
	Phone   string `json:"phone"`
}

// OrderStatus tracks order lifecycle
type OrderStatus string

const (
	OrderStatusPending    OrderStatus = "pending"
	OrderStatusConfirmed  OrderStatus = "confirmed"
	OrderStatusProcessing OrderStatus = "processing"
	OrderStatusShipped    OrderStatus = "shipped"
	OrderStatusDelivered  OrderStatus = "delivered"
	OrderStatusCancelled  OrderStatus = "cancelled"
	OrderStatusRefunded   OrderStatus = "refunded"
)

// InventoryRecord tracks stock levels
type InventoryRecord struct {
	ID           int64     `json:"id"`
	SKU          string    `json:"sku"`
	ProductID    int64     `json:"productId"`
	Quantity     int       `json:"quantity"`
	Reserved     int       `json:"reserved"`
	Available    int       `json:"available"`
	ReorderPoint int       `json:"reorderPoint"`
	WarehouseID  string    `json:"warehouseId"`
	LastRestocked time.Time `json:"lastRestocked"`
	UpdatedAt    time.Time `json:"updatedAt"`
}

// InventoryReservation holds stock for pending orders
type InventoryReservation struct {
	ID        int64     `json:"id"`
	SKU       string    `json:"sku"`
	OrderID   int64     `json:"orderId"`
	Quantity  int       `json:"quantity"`
	ExpiresAt time.Time `json:"expiresAt"`
	CreatedAt time.Time `json:"createdAt"`
}

// OfflineOrder represents an order created while offline
type OfflineOrder struct {
	ClientID    string    `json:"clientId"`
	Order       Order     `json:"order"`
	CreatedAt   time.Time `json:"createdAt"`
	Checksum    string    `json:"checksum"`
	DeviceID    string    `json:"deviceId"`
	AgentID     int64     `json:"agentId"`
}

// SyncResult reports the outcome of an offline sync
type SyncResult struct {
	ClientID   string `json:"clientId"`
	ServerID   int64  `json:"serverId,omitempty"`
	Status     string `json:"status"`
	Error      string `json:"error,omitempty"`
	ConflictResolution string `json:"conflictResolution,omitempty"`
}
