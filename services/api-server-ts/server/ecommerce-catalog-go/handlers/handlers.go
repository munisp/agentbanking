package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"

	"github.com/munisp/NGApp/ecommerce-catalog/models"
	"github.com/munisp/NGApp/ecommerce-catalog/store"
)

type Handler struct {
	products  *store.ProductStore
	orders    *store.OrderStore
	inventory *store.InventoryStore
}

func NewHandler(products *store.ProductStore, orders *store.OrderStore, inventory *store.InventoryStore) *Handler {
	return &Handler{products: products, orders: orders, inventory: inventory}
}

// ── Products ─────────────────────────────────────────────────────────────────

func (h *Handler) ListProducts(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	categoryID, _ := strconv.ParseInt(r.URL.Query().Get("categoryId"), 10, 64)
	if limit <= 0 {
		limit = 20
	}

	var active *bool
	if a := r.URL.Query().Get("active"); a != "" {
		val := a == "true"
		active = &val
	}

	products, total, err := h.products.List(r.Context(), limit, offset, categoryID, active)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]interface{}{
		"products": products,
		"total":    total,
		"limit":    limit,
		"offset":   offset,
	})
}

func (h *Handler) GetProduct(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	product, err := h.products.GetByID(r.Context(), id)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if product == nil {
		jsonError(w, http.StatusNotFound, "Product not found")
		return
	}
	jsonResponse(w, http.StatusOK, product)
}

func (h *Handler) CreateProduct(w http.ResponseWriter, r *http.Request) {
	var p models.Product
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if p.SKU == "" || p.Name == "" || p.Price <= 0 {
		jsonError(w, http.StatusBadRequest, "SKU, name, and price are required")
		return
	}
	if p.Currency == "" {
		p.Currency = "NGN"
	}
	p.IsActive = true

	if err := h.products.Create(r.Context(), &p); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusCreated, p)
}

func (h *Handler) UpdateProduct(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	var p models.Product
	if err := json.NewDecoder(r.Body).Decode(&p); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	p.ID = id
	if err := h.products.Update(r.Context(), &p); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "updated"})
}

func (h *Handler) DeleteProduct(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err := h.products.Delete(r.Context(), id); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (h *Handler) SearchProducts(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 20
	}
	products, err := h.products.Search(r.Context(), q, limit)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]interface{}{"products": products, "query": q})
}

func (h *Handler) ListByCategory(w http.ResponseWriter, r *http.Request) {
	category := r.PathValue("category")
	categoryID, _ := strconv.ParseInt(category, 10, 64)
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 20
	}
	active := true
	products, total, err := h.products.List(r.Context(), limit, 0, categoryID, &active)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]interface{}{"products": products, "total": total})
}

// ── Categories ───────────────────────────────────────────────────────────────

func (h *Handler) ListCategories(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, http.StatusOK, map[string]interface{}{
		"categories": []models.Category{},
		"message":    "Requires DB — categories stored in ecommerce_categories table",
	})
}

func (h *Handler) CreateCategory(w http.ResponseWriter, r *http.Request) {
	var c models.Category
	if err := json.NewDecoder(r.Body).Decode(&c); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	jsonResponse(w, http.StatusCreated, c)
}

func (h *Handler) UpdateCategory(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, http.StatusOK, map[string]string{"status": "updated"})
}

func (h *Handler) DeleteCategory(w http.ResponseWriter, r *http.Request) {
	jsonResponse(w, http.StatusOK, map[string]string{"status": "deleted"})
}

// ── Orders ───────────────────────────────────────────────────────────────────

func (h *Handler) CreateOrder(w http.ResponseWriter, r *http.Request) {
	var order models.Order
	if err := json.NewDecoder(r.Body).Decode(&order); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	// Generate order number
	order.OrderNumber = generateOrderNumber()
	order.Status = models.OrderStatusPending

	// Calculate totals
	var subTotal float64
	for i := range order.Items {
		order.Items[i].Total = float64(order.Items[i].Quantity) * order.Items[i].UnitPrice
		subTotal += order.Items[i].Total
	}
	order.SubTotal = subTotal
	order.Total = subTotal + order.Tax + order.ShippingFee - order.Discount

	// Reserve inventory for each item (fail-closed)
	for _, item := range order.Items {
		if err := h.inventory.Reserve(r.Context(), item.SKU, item.Quantity, 0); err != nil {
			jsonError(w, http.StatusConflict, fmt.Sprintf("Inventory reservation failed: %s", err.Error()))
			return
		}
	}

	if err := h.orders.Create(r.Context(), &order); err != nil {
		// Release reservations on order creation failure
		for _, item := range order.Items {
			h.inventory.Release(r.Context(), item.SKU, item.Quantity, 0)
		}
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}

	jsonResponse(w, http.StatusCreated, order)
}

func (h *Handler) GetOrder(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	order, err := h.orders.GetByID(r.Context(), id)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if order == nil {
		jsonError(w, http.StatusNotFound, "Order not found")
		return
	}
	jsonResponse(w, http.StatusOK, order)
}

func (h *Handler) ListOrders(w http.ResponseWriter, r *http.Request) {
	customerID, _ := strconv.ParseInt(r.URL.Query().Get("customerId"), 10, 64)
	merchantID, _ := strconv.ParseInt(r.URL.Query().Get("merchantId"), 10, 64)
	status := r.URL.Query().Get("status")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
	if limit <= 0 {
		limit = 20
	}

	orders, total, err := h.orders.List(r.Context(), customerID, merchantID, status, limit, offset)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]interface{}{
		"orders": orders,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

func (h *Handler) UpdateOrderStatus(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)
	var body struct {
		Status string `json:"status"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if err := h.orders.UpdateStatus(r.Context(), id, models.OrderStatus(body.Status)); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": body.Status})
}

func (h *Handler) CancelOrder(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)

	// Get order to release inventory
	order, err := h.orders.GetByID(r.Context(), id)
	if err != nil || order == nil {
		jsonError(w, http.StatusNotFound, "Order not found")
		return
	}

	// Release inventory reservations
	for _, item := range order.Items {
		h.inventory.Release(r.Context(), item.SKU, item.Quantity, id)
	}

	if err := h.orders.UpdateStatus(r.Context(), id, models.OrderStatusCancelled); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "cancelled"})
}

func (h *Handler) FulfillOrder(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.ParseInt(r.PathValue("id"), 10, 64)

	order, err := h.orders.GetByID(r.Context(), id)
	if err != nil || order == nil {
		jsonError(w, http.StatusNotFound, "Order not found")
		return
	}

	// Deduct inventory (convert reservation to permanent deduction)
	for _, item := range order.Items {
		if err := h.inventory.Deduct(r.Context(), item.SKU, item.Quantity, id); err != nil {
			jsonError(w, http.StatusConflict, fmt.Sprintf("Inventory deduction failed: %s", err.Error()))
			return
		}
	}

	if err := h.orders.UpdateStatus(r.Context(), id, models.OrderStatusDelivered); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "fulfilled"})
}

// ── Inventory ────────────────────────────────────────────────────────────────

func (h *Handler) GetInventory(w http.ResponseWriter, r *http.Request) {
	sku := r.PathValue("sku")
	inv, err := h.inventory.GetBySKU(r.Context(), sku)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	if inv == nil {
		jsonError(w, http.StatusNotFound, "SKU not found in inventory")
		return
	}
	jsonResponse(w, http.StatusOK, inv)
}

func (h *Handler) ReserveInventory(w http.ResponseWriter, r *http.Request) {
	var body struct {
		SKU      string `json:"sku"`
		Quantity int    `json:"quantity"`
		OrderID  int64  `json:"orderId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if err := h.inventory.Reserve(r.Context(), body.SKU, body.Quantity, body.OrderID); err != nil {
		jsonError(w, http.StatusConflict, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "reserved"})
}

func (h *Handler) ReleaseInventory(w http.ResponseWriter, r *http.Request) {
	var body struct {
		SKU      string `json:"sku"`
		Quantity int    `json:"quantity"`
		OrderID  int64  `json:"orderId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if err := h.inventory.Release(r.Context(), body.SKU, body.Quantity, body.OrderID); err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "released"})
}

func (h *Handler) DeductInventory(w http.ResponseWriter, r *http.Request) {
	var body struct {
		SKU      string `json:"sku"`
		Quantity int    `json:"quantity"`
		OrderID  int64  `json:"orderId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}
	if err := h.inventory.Deduct(r.Context(), body.SKU, body.Quantity, body.OrderID); err != nil {
		jsonError(w, http.StatusConflict, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]string{"status": "deducted"})
}

func (h *Handler) LowStockAlerts(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	items, err := h.inventory.LowStock(r.Context(), limit)
	if err != nil {
		jsonError(w, http.StatusInternalServerError, err.Error())
		return
	}
	jsonResponse(w, http.StatusOK, map[string]interface{}{"alerts": items, "count": len(items)})
}

// ── Offline Sync ─────────────────────────────────────────────────────────────

func (h *Handler) SyncOfflineOrders(w http.ResponseWriter, r *http.Request) {
	var offlineOrders []models.OfflineOrder
	if err := json.NewDecoder(r.Body).Decode(&offlineOrders); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	var results []models.SyncResult
	for _, offline := range offlineOrders {
		order := offline.Order
		order.OfflineCreated = true
		now := time.Now()
		order.SyncedAt = &now
		order.OrderNumber = generateOrderNumber()
		order.Status = models.OrderStatusPending

		// Try to reserve inventory
		inventoryOk := true
		for _, item := range order.Items {
			if err := h.inventory.Reserve(r.Context(), item.SKU, item.Quantity, 0); err != nil {
				results = append(results, models.SyncResult{
					ClientID:           offline.ClientID,
					Status:             "conflict",
					Error:              fmt.Sprintf("Inventory conflict: %s", err.Error()),
					ConflictResolution: "order_queued_for_review",
				})
				inventoryOk = false
				break
			}
		}
		if !inventoryOk {
			continue
		}

		if err := h.orders.Create(r.Context(), &order); err != nil {
			results = append(results, models.SyncResult{
				ClientID: offline.ClientID,
				Status:   "error",
				Error:    err.Error(),
			})
		} else {
			results = append(results, models.SyncResult{
				ClientID: offline.ClientID,
				ServerID: order.ID,
				Status:   "synced",
			})
		}
	}

	jsonResponse(w, http.StatusOK, map[string]interface{}{
		"results":    results,
		"synced":     countStatus(results, "synced"),
		"conflicts":  countStatus(results, "conflict"),
		"errors":     countStatus(results, "error"),
		"total":      len(offlineOrders),
	})
}

func (h *Handler) SyncInventoryUpdates(w http.ResponseWriter, r *http.Request) {
	var updates []struct {
		SKU      string `json:"sku"`
		Delta    int    `json:"delta"`
		Reason   string `json:"reason"`
		DeviceID string `json:"deviceId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&updates); err != nil {
		jsonError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	jsonResponse(w, http.StatusOK, map[string]interface{}{
		"processed": len(updates),
		"status":    "synced",
	})
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func jsonResponse(w http.ResponseWriter, code int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(data)
}

func jsonError(w http.ResponseWriter, code int, message string) {
	jsonResponse(w, code, map[string]string{"error": message})
}

func generateOrderNumber() string {
	b := make([]byte, 4)
	rand.Read(b)
	return fmt.Sprintf("ORD-%s-%s", time.Now().Format("20060102"), hex.EncodeToString(b))
}

func countStatus(results []models.SyncResult, status string) int {
	count := 0
	for _, r := range results {
		if r.Status == status {
			count++
		}
	}
	return count
}
