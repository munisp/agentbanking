package store

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/munisp/NGApp/ecommerce-catalog/models"
	_ "github.com/lib/pq"
)

type InventoryStore struct {
	db *sql.DB
}

func NewInventoryStore(dbURL string) *InventoryStore {
	if dbURL == "" {
		return &InventoryStore{db: nil}
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		fmt.Printf("[InventoryStore] Failed to connect: %v\n", err)
		return &InventoryStore{db: nil}
	}
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(3)
	db.SetConnMaxLifetime(5 * time.Minute)
	return &InventoryStore{db: db}
}

func (s *InventoryStore) GetBySKU(ctx context.Context, sku string) (*models.InventoryRecord, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not available")
	}

	var inv models.InventoryRecord
	err := s.db.QueryRowContext(ctx, `
		SELECT id, sku, product_id, quantity, reserved, (quantity - reserved) as available,
		       reorder_point, warehouse_id, last_restocked, updated_at
		FROM ecommerce_inventory WHERE sku = $1
	`, sku).Scan(
		&inv.ID, &inv.SKU, &inv.ProductID, &inv.Quantity, &inv.Reserved,
		&inv.Available, &inv.ReorderPoint, &inv.WarehouseID,
		&inv.LastRestocked, &inv.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &inv, nil
}

// Reserve holds inventory for a pending order (fail-closed: returns error if insufficient stock)
func (s *InventoryStore) Reserve(ctx context.Context, sku string, quantity int, orderID int64) error {
	if s.db == nil {
		return fmt.Errorf("database not available — cannot reserve inventory")
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	// Lock the row for update
	var available int
	err = tx.QueryRowContext(ctx, `
		SELECT (quantity - reserved) FROM ecommerce_inventory WHERE sku = $1 FOR UPDATE
	`, sku).Scan(&available)
	if err != nil {
		return fmt.Errorf("inventory lookup failed for SKU %s: %w", sku, err)
	}

	if available < quantity {
		return fmt.Errorf("insufficient stock for SKU %s: requested %d, available %d", sku, quantity, available)
	}

	// Reserve
	_, err = tx.ExecContext(ctx, `
		UPDATE ecommerce_inventory SET reserved = reserved + $1, updated_at = NOW() WHERE sku = $2
	`, quantity, sku)
	if err != nil {
		return err
	}

	// Record reservation
	_, err = tx.ExecContext(ctx, `
		INSERT INTO ecommerce_inventory_reservations (sku, order_id, quantity, expires_at)
		VALUES ($1, $2, $3, NOW() + INTERVAL '30 minutes')
	`, sku, orderID, quantity)
	if err != nil {
		return err
	}

	return tx.Commit()
}

// Release returns reserved inventory back to available (e.g. on order cancellation)
func (s *InventoryStore) Release(ctx context.Context, sku string, quantity int, orderID int64) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	_, err = tx.ExecContext(ctx, `
		UPDATE ecommerce_inventory SET reserved = GREATEST(reserved - $1, 0), updated_at = NOW() WHERE sku = $2
	`, quantity, sku)
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(ctx, `
		DELETE FROM ecommerce_inventory_reservations WHERE sku = $1 AND order_id = $2
	`, sku, orderID)
	if err != nil {
		return err
	}

	return tx.Commit()
}

// Deduct permanently removes stock after order fulfillment
func (s *InventoryStore) Deduct(ctx context.Context, sku string, quantity int, orderID int64) error {
	if s.db == nil {
		return fmt.Errorf("database not available — cannot deduct inventory (fail-closed)")
	}

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	_, err = tx.ExecContext(ctx, `
		UPDATE ecommerce_inventory
		SET quantity = quantity - $1, reserved = GREATEST(reserved - $1, 0), updated_at = NOW()
		WHERE sku = $2
	`, quantity, sku)
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(ctx, `
		DELETE FROM ecommerce_inventory_reservations WHERE sku = $1 AND order_id = $2
	`, sku, orderID)
	if err != nil {
		return err
	}

	return tx.Commit()
}

// LowStock returns items below their reorder point
func (s *InventoryStore) LowStock(ctx context.Context, limit int) ([]models.InventoryRecord, error) {
	if s.db == nil {
		return []models.InventoryRecord{}, nil
	}

	rows, err := s.db.QueryContext(ctx, `
		SELECT id, sku, product_id, quantity, reserved, (quantity - reserved) as available,
		       reorder_point, warehouse_id, last_restocked, updated_at
		FROM ecommerce_inventory
		WHERE (quantity - reserved) <= reorder_point
		ORDER BY (quantity - reserved) ASC
		LIMIT $1
	`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []models.InventoryRecord
	for rows.Next() {
		var inv models.InventoryRecord
		rows.Scan(&inv.ID, &inv.SKU, &inv.ProductID, &inv.Quantity, &inv.Reserved,
			&inv.Available, &inv.ReorderPoint, &inv.WarehouseID, &inv.LastRestocked, &inv.UpdatedAt)
		items = append(items, inv)
	}
	return items, nil
}
