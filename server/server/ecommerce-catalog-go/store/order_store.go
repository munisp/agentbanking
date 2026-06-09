package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/munisp/NGApp/ecommerce-catalog/models"
	_ "github.com/lib/pq"
)

type OrderStore struct {
	db *sql.DB
}

func NewOrderStore(dbURL string) *OrderStore {
	if dbURL == "" {
		return &OrderStore{db: nil}
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		fmt.Printf("[OrderStore] Failed to connect: %v\n", err)
		return &OrderStore{db: nil}
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)
	return &OrderStore{db: db}
}

func (s *OrderStore) Create(ctx context.Context, order *models.Order) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	shippingJSON, _ := json.Marshal(order.ShippingAddr)

	err = tx.QueryRowContext(ctx, `
		INSERT INTO ecommerce_orders (
			order_number, customer_id, merchant_id, agent_id, status,
			sub_total, tax, shipping_fee, discount, total, currency,
			payment_method, payment_ref, shipping_address, notes,
			offline_created, synced_at
		) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
		RETURNING id, created_at, updated_at
	`, order.OrderNumber, order.CustomerID, order.MerchantID,
		nullInt64(order.AgentID), order.Status,
		order.SubTotal, order.Tax, order.ShippingFee, order.Discount,
		order.Total, order.Currency, order.PaymentMethod,
		nullString(order.PaymentRef), string(shippingJSON),
		nullString(order.Notes), order.OfflineCreated, order.SyncedAt,
	).Scan(&order.ID, &order.CreatedAt, &order.UpdatedAt)
	if err != nil {
		return err
	}

	// Insert order items
	for i := range order.Items {
		item := &order.Items[i]
		err = tx.QueryRowContext(ctx, `
			INSERT INTO ecommerce_order_items (order_id, product_id, sku, name, quantity, unit_price, total)
			VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id
		`, order.ID, item.ProductID, item.SKU, item.Name, item.Quantity, item.UnitPrice, item.Total,
		).Scan(&item.ID)
		if err != nil {
			return err
		}
	}

	return tx.Commit()
}

func (s *OrderStore) GetByID(ctx context.Context, id int64) (*models.Order, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not available")
	}

	var order models.Order
	var shippingJSON string
	var agentID sql.NullInt64
	var paymentRef, notes sql.NullString
	var syncedAt, fulfilledAt, cancelledAt sql.NullTime

	err := s.db.QueryRowContext(ctx, `
		SELECT id, order_number, customer_id, merchant_id, agent_id, status,
		       sub_total, tax, shipping_fee, discount, total, currency,
		       payment_method, payment_ref, shipping_address, notes,
		       offline_created, synced_at, created_at, updated_at,
		       fulfilled_at, cancelled_at
		FROM ecommerce_orders WHERE id = $1
	`, id).Scan(
		&order.ID, &order.OrderNumber, &order.CustomerID, &order.MerchantID,
		&agentID, &order.Status, &order.SubTotal, &order.Tax,
		&order.ShippingFee, &order.Discount, &order.Total, &order.Currency,
		&order.PaymentMethod, &paymentRef, &shippingJSON, &notes,
		&order.OfflineCreated, &syncedAt, &order.CreatedAt, &order.UpdatedAt,
		&fulfilledAt, &cancelledAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}

	if agentID.Valid {
		order.AgentID = agentID.Int64
	}
	if paymentRef.Valid {
		order.PaymentRef = paymentRef.String
	}
	if notes.Valid {
		order.Notes = notes.String
	}
	if syncedAt.Valid {
		order.SyncedAt = &syncedAt.Time
	}
	if fulfilledAt.Valid {
		order.FulfilledAt = &fulfilledAt.Time
	}
	if cancelledAt.Valid {
		order.CancelledAt = &cancelledAt.Time
	}
	json.Unmarshal([]byte(shippingJSON), &order.ShippingAddr)

	// Fetch order items
	rows, err := s.db.QueryContext(ctx, `
		SELECT id, order_id, product_id, sku, name, quantity, unit_price, total
		FROM ecommerce_order_items WHERE order_id = $1
	`, id)
	if err != nil {
		return &order, nil
	}
	defer rows.Close()

	for rows.Next() {
		var item models.OrderItem
		rows.Scan(&item.ID, &item.OrderID, &item.ProductID, &item.SKU,
			&item.Name, &item.Quantity, &item.UnitPrice, &item.Total)
		order.Items = append(order.Items, item)
	}

	return &order, nil
}

func (s *OrderStore) List(ctx context.Context, customerID, merchantID int64, status string, limit, offset int) ([]models.Order, int, error) {
	if s.db == nil {
		return []models.Order{}, 0, nil
	}

	where := []string{"1=1"}
	args := []interface{}{}
	argIdx := 1

	if customerID > 0 {
		where = append(where, fmt.Sprintf("customer_id = $%d", argIdx))
		args = append(args, customerID)
		argIdx++
	}
	if merchantID > 0 {
		where = append(where, fmt.Sprintf("merchant_id = $%d", argIdx))
		args = append(args, merchantID)
		argIdx++
	}
	if status != "" {
		where = append(where, fmt.Sprintf("status = $%d", argIdx))
		args = append(args, status)
		argIdx++
	}

	whereClause := ""
	for i, w := range where {
		if i > 0 {
			whereClause += " AND "
		}
		whereClause += w
	}

	var total int
	countQ := fmt.Sprintf("SELECT COUNT(*) FROM ecommerce_orders WHERE %s", whereClause)
	s.db.QueryRowContext(ctx, countQ, args...).Scan(&total)

	query := fmt.Sprintf(`
		SELECT id, order_number, customer_id, merchant_id, status, total, currency,
		       offline_created, created_at
		FROM ecommerce_orders WHERE %s
		ORDER BY created_at DESC LIMIT $%d OFFSET $%d
	`, whereClause, argIdx, argIdx+1)
	args = append(args, limit, offset)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var orders []models.Order
	for rows.Next() {
		var o models.Order
		rows.Scan(&o.ID, &o.OrderNumber, &o.CustomerID, &o.MerchantID,
			&o.Status, &o.Total, &o.Currency, &o.OfflineCreated, &o.CreatedAt)
		orders = append(orders, o)
	}
	return orders, total, nil
}

func (s *OrderStore) UpdateStatus(ctx context.Context, id int64, status models.OrderStatus) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}

	extra := ""
	if status == models.OrderStatusDelivered {
		extra = ", fulfilled_at = NOW()"
	} else if status == models.OrderStatusCancelled {
		extra = ", cancelled_at = NOW()"
	}

	_, err := s.db.ExecContext(ctx, fmt.Sprintf(
		"UPDATE ecommerce_orders SET status=$1, updated_at=NOW()%s WHERE id=$2", extra,
	), status, id)
	return err
}
