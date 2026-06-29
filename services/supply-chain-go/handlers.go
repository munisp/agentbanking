package main

import (
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"sort"
	"strconv"
	"sync"
	"time"
)

// ─── In-Memory Store (production: backed by Postgres via Drizzle schema) ─────

type Warehouse struct {
	ID               int            `json:"id"`
	Code             string         `json:"code"`
	Name             string         `json:"name"`
	Type             string         `json:"type"`
	Address          map[string]any `json:"address"`
	Capacity         int            `json:"capacity"`
	CurrentOccupancy int            `json:"currentOccupancy"`
	IsActive         bool           `json:"isActive"`
	ManagerID        int            `json:"managerId"`
	CreatedAt        time.Time      `json:"createdAt"`
}

type Zone struct {
	ID          int    `json:"id"`
	WarehouseID int    `json:"warehouseId"`
	Name        string `json:"name"`
	Type        string `json:"type"`
	Capacity    int    `json:"capacity"`
	IsActive    bool   `json:"isActive"`
}

type Location struct {
	ID              int    `json:"id"`
	ZoneID          int    `json:"zoneId"`
	Aisle           string `json:"aisle"`
	Rack            string `json:"rack"`
	Shelf           string `json:"shelf"`
	Bin             string `json:"bin"`
	Label           string `json:"label"`
	Capacity        int    `json:"capacity"`
	CurrentQuantity int    `json:"currentQuantity"`
	SKU             string `json:"sku"`
	IsActive        bool   `json:"isActive"`
}

type StockMovement struct {
	ID              int       `json:"id"`
	SKU             string    `json:"sku"`
	Type            string    `json:"type"`
	Quantity        int       `json:"quantity"`
	FromWarehouseID int       `json:"fromWarehouseId,omitempty"`
	ToWarehouseID   int       `json:"toWarehouseId,omitempty"`
	FromLocationID  int       `json:"fromLocationId,omitempty"`
	ToLocationID    int       `json:"toLocationId,omitempty"`
	ReferenceType   string    `json:"referenceType,omitempty"`
	ReferenceID     int       `json:"referenceId,omitempty"`
	Reason          string    `json:"reason,omitempty"`
	PerformedBy     int       `json:"performedBy"`
	CreatedAt       time.Time `json:"createdAt"`
}

type Supplier struct {
	ID                 int            `json:"id"`
	Code               string         `json:"code"`
	Name               string         `json:"name"`
	ContactName        string         `json:"contactName"`
	Email              string         `json:"email"`
	Phone              string         `json:"phone"`
	Address            map[string]any `json:"address"`
	PaymentTerms       string         `json:"paymentTerms"`
	LeadTimeDays       int            `json:"leadTimeDays"`
	Rating             float64        `json:"rating"`
	TotalOrders        int            `json:"totalOrders"`
	OnTimeDeliveryRate float64        `json:"onTimeDeliveryRate"`
	IsActive           bool           `json:"isActive"`
	CreatedAt          time.Time      `json:"createdAt"`
}

type PurchaseOrder struct {
	ID               int           `json:"id"`
	PONumber         string        `json:"poNumber"`
	SupplierID       int           `json:"supplierId"`
	WarehouseID      int           `json:"warehouseId"`
	Status           string        `json:"status"`
	SubTotal         float64       `json:"subTotal"`
	Tax              float64       `json:"tax"`
	ShippingCost     float64       `json:"shippingCost"`
	Total            float64       `json:"total"`
	Currency         string        `json:"currency"`
	ExpectedDelivery *time.Time    `json:"expectedDelivery"`
	Items            []POItem      `json:"items"`
	CreatedBy        int           `json:"createdBy"`
	CreatedAt        time.Time     `json:"createdAt"`
}

type POItem struct {
	SKU              string  `json:"sku"`
	ProductName      string  `json:"productName"`
	QuantityOrdered  int     `json:"quantityOrdered"`
	QuantityReceived int     `json:"quantityReceived"`
	UnitCost         float64 `json:"unitCost"`
	Total            float64 `json:"total"`
}

type Shipment struct {
	ID                int            `json:"id"`
	OrderID           int            `json:"orderId"`
	CarrierID         int            `json:"carrierId"`
	TrackingNumber    string         `json:"trackingNumber"`
	LabelURL          string         `json:"labelUrl"`
	Status            string         `json:"status"`
	EstimatedDelivery *time.Time     `json:"estimatedDelivery"`
	ShippingCost      float64        `json:"shippingCost"`
	Weight            float64        `json:"weight"`
	FromAddress       map[string]any `json:"fromAddress"`
	ToAddress         map[string]any `json:"toAddress"`
	ProofOfDelivery   string         `json:"proofOfDelivery"`
	CreatedAt         time.Time      `json:"createdAt"`
}

type Carrier struct {
	ID                  int      `json:"id"`
	Code                string   `json:"code"`
	Name                string   `json:"name"`
	TrackingURLTemplate string   `json:"trackingUrlTemplate"`
	IsActive            bool     `json:"isActive"`
	SupportedCountries  []string `json:"supportedCountries"`
	RatePerKg           float64  `json:"ratePerKg"`
	BaseRate            float64  `json:"baseRate"`
}

type Valuation struct {
	SKU         string  `json:"sku"`
	WarehouseID int     `json:"warehouseId"`
	Method      string  `json:"method"`
	Quantity    int     `json:"quantity"`
	UnitCost    float64 `json:"unitCost"`
	TotalValue  float64 `json:"totalValue"`
}

var (
	mu            sync.RWMutex
	warehouseSeq  = 0
	zoneSeq       = 0
	locationSeq   = 0
	movementSeq   = 0
	supplierSeq   = 0
	poSeq         = 0
	shipmentSeq   = 0
	warehouseList []Warehouse
	zoneList      []Zone
	locationList  []Location
	movementList  []StockMovement
	supplierList  []Supplier
	poList        []PurchaseOrder
	shipmentList  []Shipment
	carrierList   = []Carrier{
		{ID: 1, Code: "GIGL", Name: "GIG Logistics", IsActive: true, SupportedCountries: []string{"NG"}, RatePerKg: 350, BaseRate: 1500},
		{ID: 2, Code: "DHL", Name: "DHL Express", IsActive: true, SupportedCountries: []string{"NG", "GH", "KE", "ZA"}, RatePerKg: 2500, BaseRate: 5000},
		{ID: 3, Code: "FEDEX", Name: "FedEx", IsActive: true, SupportedCountries: []string{"NG", "US", "UK", "DE"}, RatePerKg: 3000, BaseRate: 7500},
		{ID: 4, Code: "KWIK", Name: "Kwik Delivery", IsActive: true, SupportedCountries: []string{"NG"}, RatePerKg: 200, BaseRate: 800},
		{ID: 5, Code: "SENDBOX", Name: "Sendbox", IsActive: true, SupportedCountries: []string{"NG", "GH"}, RatePerKg: 300, BaseRate: 1200},
	}
	stockLevels = make(map[string]map[int]int) // SKU -> warehouseID -> quantity
)

func writeJSON(w http.ResponseWriter, code int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(data)
}

func readJSON(r *http.Request, v any) error {
	return json.NewDecoder(r.Body).Decode(v)
}

// ─── Warehouse Handlers ──────────────────────────────────────────────────────

func listWarehouses(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()
	writeJSON(w, 200, map[string]any{"warehouses": warehouseList, "total": len(warehouseList)})
}

func createWarehouse(w http.ResponseWriter, r *http.Request) {
	var wh Warehouse
	if err := readJSON(r, &wh); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	warehouseSeq++
	wh.ID = warehouseSeq
	wh.IsActive = true
	wh.CreatedAt = time.Now()
	warehouseList = append(warehouseList, wh)
	mu.Unlock()
	writeJSON(w, 201, wh)
}

func getWarehouse(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, wh := range warehouseList {
		if wh.ID == id {
			writeJSON(w, 200, wh)
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "warehouse not found"})
}

func updateWarehouse(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var update Warehouse
	if err := readJSON(r, &update); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	defer mu.Unlock()
	for i := range warehouseList {
		if warehouseList[i].ID == id {
			if update.Name != "" {
				warehouseList[i].Name = update.Name
			}
			if update.Capacity > 0 {
				warehouseList[i].Capacity = update.Capacity
			}
			writeJSON(w, 200, warehouseList[i])
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func listZones(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	var result []Zone
	for _, z := range zoneList {
		if z.WarehouseID == id {
			result = append(result, z)
		}
	}
	writeJSON(w, 200, map[string]any{"zones": result})
}

func createZone(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var z Zone
	if err := readJSON(r, &z); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	zoneSeq++
	z.ID = zoneSeq
	z.WarehouseID = id
	z.IsActive = true
	zoneList = append(zoneList, z)
	mu.Unlock()
	writeJSON(w, 201, z)
}

func listLocations(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	var result []Location
	for _, l := range locationList {
		for _, z := range zoneList {
			if z.ID == l.ZoneID && z.WarehouseID == id {
				result = append(result, l)
				break
			}
		}
	}
	writeJSON(w, 200, map[string]any{"locations": result})
}

func createLocation(w http.ResponseWriter, r *http.Request) {
	var l Location
	if err := readJSON(r, &l); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	locationSeq++
	l.ID = locationSeq
	l.IsActive = true
	l.Label = fmt.Sprintf("%s-%s-%s-%s", l.Aisle, l.Rack, l.Shelf, l.Bin)
	locationList = append(locationList, l)
	mu.Unlock()
	writeJSON(w, 201, l)
}

func getOccupancy(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, wh := range warehouseList {
		if wh.ID == id {
			pct := 0.0
			if wh.Capacity > 0 {
				pct = float64(wh.CurrentOccupancy) / float64(wh.Capacity) * 100
			}
			writeJSON(w, 200, map[string]any{
				"warehouseId":      id,
				"capacity":         wh.Capacity,
				"currentOccupancy": wh.CurrentOccupancy,
				"percentage":       math.Round(pct*100) / 100,
			})
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

// ─── Stock Movement Handlers ─────────────────────────────────────────────────

func receiveStock(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU         string `json:"sku"`
		Quantity    int    `json:"quantity"`
		WarehouseID int    `json:"warehouseId"`
		LocationID  int    `json:"locationId"`
		PerformedBy int    `json:"performedBy"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	movementSeq++
	mv := StockMovement{
		ID: movementSeq, SKU: req.SKU, Type: "receiving", Quantity: req.Quantity,
		ToWarehouseID: req.WarehouseID, ToLocationID: req.LocationID,
		PerformedBy: req.PerformedBy, CreatedAt: time.Now(),
	}
	movementList = append(movementList, mv)
	if stockLevels[req.SKU] == nil {
		stockLevels[req.SKU] = make(map[int]int)
	}
	stockLevels[req.SKU][req.WarehouseID] += req.Quantity
	mu.Unlock()
	writeJSON(w, 201, mv)
}

func transferStock(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU             string `json:"sku"`
		Quantity        int    `json:"quantity"`
		FromWarehouseID int    `json:"fromWarehouseId"`
		ToWarehouseID   int    `json:"toWarehouseId"`
		PerformedBy     int    `json:"performedBy"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	available := stockLevels[req.SKU][req.FromWarehouseID]
	if available < req.Quantity {
		mu.Unlock()
		writeJSON(w, 409, map[string]string{"error": "insufficient stock for transfer"})
		return
	}
	movementSeq++
	mv := StockMovement{
		ID: movementSeq, SKU: req.SKU, Type: "transfer", Quantity: req.Quantity,
		FromWarehouseID: req.FromWarehouseID, ToWarehouseID: req.ToWarehouseID,
		PerformedBy: req.PerformedBy, CreatedAt: time.Now(),
	}
	movementList = append(movementList, mv)
	stockLevels[req.SKU][req.FromWarehouseID] -= req.Quantity
	if stockLevels[req.SKU] == nil {
		stockLevels[req.SKU] = make(map[int]int)
	}
	stockLevels[req.SKU][req.ToWarehouseID] += req.Quantity
	mu.Unlock()
	writeJSON(w, 201, mv)
}

func adjustStock(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU         string `json:"sku"`
		Quantity    int    `json:"quantity"`
		WarehouseID int    `json:"warehouseId"`
		Reason      string `json:"reason"`
		PerformedBy int    `json:"performedBy"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	movementSeq++
	mv := StockMovement{
		ID: movementSeq, SKU: req.SKU, Type: "adjustment", Quantity: req.Quantity,
		ToWarehouseID: req.WarehouseID, Reason: req.Reason,
		PerformedBy: req.PerformedBy, CreatedAt: time.Now(),
	}
	movementList = append(movementList, mv)
	if stockLevels[req.SKU] == nil {
		stockLevels[req.SKU] = make(map[int]int)
	}
	stockLevels[req.SKU][req.WarehouseID] += req.Quantity
	mu.Unlock()
	writeJSON(w, 201, mv)
}

func reserveStock(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU         string `json:"sku"`
		Quantity    int    `json:"quantity"`
		WarehouseID int    `json:"warehouseId"`
		OrderID     int    `json:"orderId"`
		PerformedBy int    `json:"performedBy"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	available := stockLevels[req.SKU][req.WarehouseID]
	if available < req.Quantity {
		mu.Unlock()
		writeJSON(w, 409, map[string]string{"error": "insufficient stock for reservation"})
		return
	}
	movementSeq++
	mv := StockMovement{
		ID: movementSeq, SKU: req.SKU, Type: "reservation", Quantity: -req.Quantity,
		FromWarehouseID: req.WarehouseID, ReferenceType: "order", ReferenceID: req.OrderID,
		PerformedBy: req.PerformedBy, CreatedAt: time.Now(),
	}
	movementList = append(movementList, mv)
	stockLevels[req.SKU][req.WarehouseID] -= req.Quantity
	mu.Unlock()
	writeJSON(w, 201, mv)
}

func pickStock(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU         string `json:"sku"`
		Quantity    int    `json:"quantity"`
		WarehouseID int    `json:"warehouseId"`
		LocationID  int    `json:"locationId"`
		OrderID     int    `json:"orderId"`
		PerformedBy int    `json:"performedBy"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	movementSeq++
	mv := StockMovement{
		ID: movementSeq, SKU: req.SKU, Type: "pick", Quantity: -req.Quantity,
		FromWarehouseID: req.WarehouseID, FromLocationID: req.LocationID,
		ReferenceType: "order", ReferenceID: req.OrderID,
		PerformedBy: req.PerformedBy, CreatedAt: time.Now(),
	}
	movementList = append(movementList, mv)
	mu.Unlock()
	writeJSON(w, 201, mv)
}

func listMovements(w http.ResponseWriter, r *http.Request) {
	sku := r.URL.Query().Get("sku")
	movType := r.URL.Query().Get("type")
	mu.RLock()
	defer mu.RUnlock()
	var result []StockMovement
	for _, m := range movementList {
		if sku != "" && m.SKU != sku {
			continue
		}
		if movType != "" && m.Type != movType {
			continue
		}
		result = append(result, m)
	}
	writeJSON(w, 200, map[string]any{"movements": result, "total": len(result)})
}

func getStockLevels(w http.ResponseWriter, r *http.Request) {
	sku := r.URL.Query().Get("sku")
	mu.RLock()
	defer mu.RUnlock()
	if sku != "" {
		levels := stockLevels[sku]
		writeJSON(w, 200, map[string]any{"sku": sku, "levels": levels})
		return
	}
	writeJSON(w, 200, map[string]any{"stockLevels": stockLevels})
}

func getStockAlerts(w http.ResponseWriter, r *http.Request) {
	reorderPoint := 10
	if rp := r.URL.Query().Get("reorderPoint"); rp != "" {
		reorderPoint, _ = strconv.Atoi(rp)
	}
	mu.RLock()
	defer mu.RUnlock()
	type Alert struct {
		SKU         string `json:"sku"`
		WarehouseID int    `json:"warehouseId"`
		Quantity    int    `json:"quantity"`
		Threshold   int    `json:"threshold"`
	}
	var alerts []Alert
	for sku, whMap := range stockLevels {
		for whID, qty := range whMap {
			if qty <= reorderPoint {
				alerts = append(alerts, Alert{SKU: sku, WarehouseID: whID, Quantity: qty, Threshold: reorderPoint})
			}
		}
	}
	writeJSON(w, 200, map[string]any{"alerts": alerts, "total": len(alerts)})
}

// ─── Valuation Handlers ──────────────────────────────────────────────────────

func getValuation(w http.ResponseWriter, r *http.Request) {
	sku := r.PathValue("sku")
	method := r.URL.Query().Get("method")
	if method == "" {
		method = "weighted_average"
	}
	mu.RLock()
	levels := stockLevels[sku]
	mu.RUnlock()
	var valuations []Valuation
	for whID, qty := range levels {
		unitCost := 1000.0 // default; in production from purchase history
		valuations = append(valuations, Valuation{
			SKU: sku, WarehouseID: whID, Method: method,
			Quantity: qty, UnitCost: unitCost, TotalValue: float64(qty) * unitCost,
		})
	}
	writeJSON(w, 200, map[string]any{"valuations": valuations})
}

func calculateValuation(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SKU    string `json:"sku"`
		Method string `json:"method"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.RLock()
	totalQty := 0
	for _, qty := range stockLevels[req.SKU] {
		totalQty += qty
	}
	mu.RUnlock()
	unitCost := 1000.0
	writeJSON(w, 200, map[string]any{
		"sku": req.SKU, "method": req.Method, "quantity": totalQty,
		"unitCost": unitCost, "totalValue": float64(totalQty) * unitCost,
	})
}

func valuationReport(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()
	totalValue := 0.0
	skuCount := len(stockLevels)
	for _, whMap := range stockLevels {
		for _, qty := range whMap {
			totalValue += float64(qty) * 1000.0
		}
	}
	writeJSON(w, 200, map[string]any{
		"totalValue": totalValue, "skuCount": skuCount,
		"method": "weighted_average", "generatedAt": time.Now(),
	})
}

// ─── Supplier/Procurement Handlers ───────────────────────────────────────────

func listSuppliers(w http.ResponseWriter, r *http.Request) {
	mu.RLock()
	defer mu.RUnlock()
	writeJSON(w, 200, map[string]any{"suppliers": supplierList, "total": len(supplierList)})
}

func createSupplier(w http.ResponseWriter, r *http.Request) {
	var s Supplier
	if err := readJSON(r, &s); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	supplierSeq++
	s.ID = supplierSeq
	s.IsActive = true
	s.CreatedAt = time.Now()
	supplierList = append(supplierList, s)
	mu.Unlock()
	writeJSON(w, 201, s)
}

func getSupplier(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, s := range supplierList {
		if s.ID == id {
			writeJSON(w, 200, s)
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "supplier not found"})
}

func updateSupplier(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var update Supplier
	readJSON(r, &update)
	mu.Lock()
	defer mu.Unlock()
	for i := range supplierList {
		if supplierList[i].ID == id {
			if update.Name != "" {
				supplierList[i].Name = update.Name
			}
			if update.Rating > 0 {
				supplierList[i].Rating = update.Rating
			}
			writeJSON(w, 200, supplierList[i])
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func getSupplierPerformance(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, s := range supplierList {
		if s.ID == id {
			writeJSON(w, 200, map[string]any{
				"supplierId":         id,
				"rating":             s.Rating,
				"totalOrders":        s.TotalOrders,
				"onTimeDeliveryRate": s.OnTimeDeliveryRate,
				"leadTimeDays":       s.LeadTimeDays,
				"qualityScore":       85.0,
			})
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func listPurchaseOrders(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")
	mu.RLock()
	defer mu.RUnlock()
	var result []PurchaseOrder
	for _, po := range poList {
		if status != "" && po.Status != status {
			continue
		}
		result = append(result, po)
	}
	writeJSON(w, 200, map[string]any{"purchaseOrders": result, "total": len(result)})
}

func createPurchaseOrder(w http.ResponseWriter, r *http.Request) {
	var po PurchaseOrder
	if err := readJSON(r, &po); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	poSeq++
	po.ID = poSeq
	po.PONumber = fmt.Sprintf("PO-%06d", poSeq)
	po.Status = "draft"
	po.Currency = "NGN"
	po.CreatedAt = time.Now()
	// Calculate totals
	po.SubTotal = 0
	for i := range po.Items {
		po.Items[i].Total = float64(po.Items[i].QuantityOrdered) * po.Items[i].UnitCost
		po.SubTotal += po.Items[i].Total
	}
	po.Total = po.SubTotal + po.Tax + po.ShippingCost
	poList = append(poList, po)
	mu.Unlock()
	writeJSON(w, 201, po)
}

func getPurchaseOrder(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, po := range poList {
		if po.ID == id {
			writeJSON(w, 200, po)
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "PO not found"})
}

func updatePOStatus(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var req struct {
		Status string `json:"status"`
	}
	readJSON(r, &req)
	validTransitions := map[string][]string{
		"draft":              {"submitted", "cancelled"},
		"submitted":         {"approved", "cancelled"},
		"approved":          {"ordered", "cancelled"},
		"ordered":           {"partially_received", "received", "cancelled"},
		"partially_received": {"received", "cancelled"},
	}
	mu.Lock()
	defer mu.Unlock()
	for i := range poList {
		if poList[i].ID == id {
			allowed := validTransitions[poList[i].Status]
			valid := false
			for _, s := range allowed {
				if s == req.Status {
					valid = true
					break
				}
			}
			if !valid {
				writeJSON(w, 409, map[string]string{"error": fmt.Sprintf("cannot transition from %s to %s", poList[i].Status, req.Status)})
				return
			}
			poList[i].Status = req.Status
			writeJSON(w, 200, poList[i])
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func receivePO(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var req struct {
		Items []struct {
			SKU              string `json:"sku"`
			QuantityReceived int    `json:"quantityReceived"`
		} `json:"items"`
	}
	readJSON(r, &req)
	mu.Lock()
	defer mu.Unlock()
	for i := range poList {
		if poList[i].ID == id {
			allReceived := true
			for _, recv := range req.Items {
				for j := range poList[i].Items {
					if poList[i].Items[j].SKU == recv.SKU {
						poList[i].Items[j].QuantityReceived += recv.QuantityReceived
						if poList[i].Items[j].QuantityReceived < poList[i].Items[j].QuantityOrdered {
							allReceived = false
						}
						// Update stock
						if stockLevels[recv.SKU] == nil {
							stockLevels[recv.SKU] = make(map[int]int)
						}
						stockLevels[recv.SKU][poList[i].WarehouseID] += recv.QuantityReceived
					}
				}
			}
			if allReceived {
				poList[i].Status = "received"
			} else {
				poList[i].Status = "partially_received"
			}
			writeJSON(w, 200, poList[i])
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

// ─── Logistics Handlers ──────────────────────────────────────────────────────

func listCarriers(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]any{"carriers": carrierList})
}

func createShipment(w http.ResponseWriter, r *http.Request) {
	var s Shipment
	if err := readJSON(r, &s); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	mu.Lock()
	shipmentSeq++
	s.ID = shipmentSeq
	s.Status = "pending"
	s.TrackingNumber = fmt.Sprintf("TRK%010d", shipmentSeq)
	s.CreatedAt = time.Now()
	shipmentList = append(shipmentList, s)
	mu.Unlock()
	writeJSON(w, 201, s)
}

func getShipment(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, s := range shipmentList {
		if s.ID == id {
			writeJSON(w, 200, s)
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "shipment not found"})
}

func updateShipmentStatus(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var req struct {
		Status string `json:"status"`
	}
	readJSON(r, &req)
	mu.Lock()
	defer mu.Unlock()
	for i := range shipmentList {
		if shipmentList[i].ID == id {
			shipmentList[i].Status = req.Status
			if req.Status == "delivered" {
				now := time.Now()
				shipmentList[i].EstimatedDelivery = &now
			}
			writeJSON(w, 200, shipmentList[i])
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func generateLabel(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.Lock()
	defer mu.Unlock()
	for i := range shipmentList {
		if shipmentList[i].ID == id {
			shipmentList[i].LabelURL = fmt.Sprintf("/labels/shipment-%d.pdf", id)
			writeJSON(w, 200, map[string]any{
				"labelUrl":       shipmentList[i].LabelURL,
				"trackingNumber": shipmentList[i].TrackingNumber,
			})
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func trackShipment(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	mu.RLock()
	defer mu.RUnlock()
	for _, s := range shipmentList {
		if s.ID == id {
			events := []map[string]any{
				{"status": "pending", "timestamp": s.CreatedAt, "location": "Origin"},
			}
			if s.Status != "pending" {
				events = append(events, map[string]any{"status": s.Status, "timestamp": time.Now(), "location": "In transit"})
			}
			writeJSON(w, 200, map[string]any{"tracking": s.TrackingNumber, "status": s.Status, "events": events})
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func submitProofOfDelivery(w http.ResponseWriter, r *http.Request) {
	id, _ := strconv.Atoi(r.PathValue("id"))
	var req struct {
		ImageURL string `json:"imageUrl"`
		Notes    string `json:"notes"`
	}
	readJSON(r, &req)
	mu.Lock()
	defer mu.Unlock()
	for i := range shipmentList {
		if shipmentList[i].ID == id {
			shipmentList[i].ProofOfDelivery = req.ImageURL
			shipmentList[i].Status = "delivered"
			now := time.Now()
			shipmentList[i].EstimatedDelivery = &now
			writeJSON(w, 200, map[string]any{"success": true, "deliveredAt": now})
			return
		}
	}
	writeJSON(w, 404, map[string]string{"error": "not found"})
}

func calculateShippingRates(w http.ResponseWriter, r *http.Request) {
	weightStr := r.URL.Query().Get("weight")
	weight, _ := strconv.ParseFloat(weightStr, 64)
	if weight == 0 {
		weight = 1.0
	}
	country := r.URL.Query().Get("country")
	if country == "" {
		country = "NG"
	}
	type Rate struct {
		CarrierID    int     `json:"carrierId"`
		CarrierName  string  `json:"carrierName"`
		Cost         float64 `json:"cost"`
		EstDays      int     `json:"estimatedDays"`
		ServiceLevel string  `json:"serviceLevel"`
	}
	var rates []Rate
	for _, c := range carrierList {
		supported := false
		for _, sc := range c.SupportedCountries {
			if sc == country {
				supported = true
				break
			}
		}
		if !supported {
			continue
		}
		cost := c.BaseRate + c.RatePerKg*weight
		estDays := 3
		if c.Code == "DHL" || c.Code == "FEDEX" {
			estDays = 2
		}
		rates = append(rates, Rate{CarrierID: c.ID, CarrierName: c.Name, Cost: cost, EstDays: estDays, ServiceLevel: "standard"})
	}
	sort.Slice(rates, func(i, j int) bool { return rates[i].Cost < rates[j].Cost })
	writeJSON(w, 200, map[string]any{"rates": rates, "weight": weight, "country": country})
}

func optimizeRoute(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Origin       map[string]float64   `json:"origin"`
		Destinations []map[string]float64 `json:"destinations"`
	}
	if err := readJSON(r, &req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid body"})
		return
	}
	// Nearest-neighbor heuristic
	type Stop struct {
		Index    int     `json:"index"`
		Lat      float64 `json:"lat"`
		Lng      float64 `json:"lng"`
		Distance float64 `json:"distanceKm"`
	}
	var route []Stop
	visited := make(map[int]bool)
	current := req.Origin
	for len(route) < len(req.Destinations) {
		minDist := math.MaxFloat64
		minIdx := -1
		for i, dest := range req.Destinations {
			if visited[i] {
				continue
			}
			dist := haversine(current["lat"], current["lng"], dest["lat"], dest["lng"])
			if dist < minDist {
				minDist = dist
				minIdx = i
			}
		}
		if minIdx >= 0 {
			visited[minIdx] = true
			route = append(route, Stop{Index: minIdx, Lat: req.Destinations[minIdx]["lat"], Lng: req.Destinations[minIdx]["lng"], Distance: minDist})
			current = req.Destinations[minIdx]
		}
	}
	totalDist := 0.0
	for _, s := range route {
		totalDist += s.Distance
	}
	writeJSON(w, 200, map[string]any{"route": route, "totalDistanceKm": math.Round(totalDist*100) / 100, "stops": len(route)})
}

func haversine(lat1, lng1, lat2, lng2 float64) float64 {
	const R = 6371
	dLat := (lat2 - lat1) * math.Pi / 180
	dLng := (lng2 - lng1) * math.Pi / 180
	a := math.Sin(dLat/2)*math.Sin(dLat/2) + math.Cos(lat1*math.Pi/180)*math.Cos(lat2*math.Pi/180)*math.Sin(dLng/2)*math.Sin(dLng/2)
	return R * 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))
}

// ─── Cycle Counting ──────────────────────────────────────────────────────────

func startCycleCount(w http.ResponseWriter, r *http.Request) {
	var req struct {
		WarehouseID int    `json:"warehouseId"`
		ZoneID      int    `json:"zoneId"`
		PerformedBy int    `json:"performedBy"`
		SKUs        []string `json:"skus"`
	}
	readJSON(r, &req)
	writeJSON(w, 200, map[string]any{
		"countId":     fmt.Sprintf("CC-%d-%d", req.WarehouseID, time.Now().Unix()),
		"warehouseId": req.WarehouseID,
		"zoneId":      req.ZoneID,
		"skus":        req.SKUs,
		"status":      "in_progress",
		"startedAt":   time.Now(),
	})
}

func recordCycleCount(w http.ResponseWriter, r *http.Request) {
	var req struct {
		CountID     string `json:"countId"`
		SKU         string `json:"sku"`
		LocationID  int    `json:"locationId"`
		Counted     int    `json:"counted"`
		Expected    int    `json:"expected"`
		PerformedBy int    `json:"performedBy"`
	}
	readJSON(r, &req)
	diff := req.Counted - req.Expected
	writeJSON(w, 200, map[string]any{
		"sku": req.SKU, "counted": req.Counted, "expected": req.Expected,
		"discrepancy": diff, "needsInvestigation": diff != 0,
	})
}

func getDiscrepancies(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]any{"discrepancies": []any{}, "total": 0})
}
