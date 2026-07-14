package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/munisp/NGApp/ecommerce-catalog/models"
	_ "github.com/lib/pq"
)

type ProductStore struct {
	db *sql.DB
}

func NewProductStore(dbURL string) *ProductStore {
	if dbURL == "" {
		return &ProductStore{db: nil}
	}
	db, err := sql.Open("postgres", dbURL)
	if err != nil {
		fmt.Printf("[ProductStore] Failed to connect: %v\n", err)
		return &ProductStore{db: nil}
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)
	return &ProductStore{db: db}
}

func (s *ProductStore) List(ctx context.Context, limit, offset int, categoryID int64, active *bool) ([]models.Product, int, error) {
	if s.db == nil {
		return []models.Product{}, 0, nil
	}

	where := []string{"1=1"}
	args := []interface{}{}
	argIdx := 1

	if categoryID > 0 {
		where = append(where, fmt.Sprintf("category_id = $%d", argIdx))
		args = append(args, categoryID)
		argIdx++
	}
	if active != nil {
		where = append(where, fmt.Sprintf("is_active = $%d", argIdx))
		args = append(args, *active)
		argIdx++
	}

	whereClause := strings.Join(where, " AND ")

	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM ecommerce_products WHERE %s", whereClause)
	var total int
	if err := s.db.QueryRowContext(ctx, countQuery, args...).Scan(&total); err != nil {
		return nil, 0, err
	}

	query := fmt.Sprintf(`
		SELECT id, sku, name, description, category_id, price, currency, 
		       image_url, is_active, merchant_id, agent_id, weight, dimensions,
		       tags, attributes, created_at, updated_at
		FROM ecommerce_products
		WHERE %s
		ORDER BY created_at DESC
		LIMIT $%d OFFSET $%d
	`, whereClause, argIdx, argIdx+1)
	args = append(args, limit, offset)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, err
	}
	defer rows.Close()

	var products []models.Product
	for rows.Next() {
		var p models.Product
		var tags, attrs sql.NullString
		var imageURL, dimensions sql.NullString
		var agentID sql.NullInt64

		err := rows.Scan(
			&p.ID, &p.SKU, &p.Name, &p.Description, &p.CategoryID,
			&p.Price, &p.Currency, &imageURL, &p.IsActive, &p.MerchantID,
			&agentID, &p.Weight, &dimensions, &tags, &attrs,
			&p.CreatedAt, &p.UpdatedAt,
		)
		if err != nil {
			return nil, 0, err
		}
		if imageURL.Valid {
			p.ImageURL = imageURL.String
		}
		if dimensions.Valid {
			p.Dimensions = dimensions.String
		}
		if agentID.Valid {
			p.AgentID = agentID.Int64
		}
		if tags.Valid {
			json.Unmarshal([]byte(tags.String), &p.Tags)
		}
		if attrs.Valid {
			json.Unmarshal([]byte(attrs.String), &p.Attributes)
		}
		products = append(products, p)
	}
	return products, total, nil
}

func (s *ProductStore) GetByID(ctx context.Context, id int64) (*models.Product, error) {
	if s.db == nil {
		return nil, fmt.Errorf("database not available")
	}

	var p models.Product
	var tags, attrs sql.NullString
	var imageURL, dimensions sql.NullString
	var agentID sql.NullInt64

	err := s.db.QueryRowContext(ctx, `
		SELECT id, sku, name, description, category_id, price, currency,
		       image_url, is_active, merchant_id, agent_id, weight, dimensions,
		       tags, attributes, created_at, updated_at
		FROM ecommerce_products WHERE id = $1
	`, id).Scan(
		&p.ID, &p.SKU, &p.Name, &p.Description, &p.CategoryID,
		&p.Price, &p.Currency, &imageURL, &p.IsActive, &p.MerchantID,
		&agentID, &p.Weight, &dimensions, &tags, &attrs,
		&p.CreatedAt, &p.UpdatedAt,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if imageURL.Valid {
		p.ImageURL = imageURL.String
	}
	if dimensions.Valid {
		p.Dimensions = dimensions.String
	}
	if agentID.Valid {
		p.AgentID = agentID.Int64
	}
	if tags.Valid {
		json.Unmarshal([]byte(tags.String), &p.Tags)
	}
	if attrs.Valid {
		json.Unmarshal([]byte(attrs.String), &p.Attributes)
	}
	return &p, nil
}

func (s *ProductStore) Create(ctx context.Context, p *models.Product) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}

	tagsJSON, _ := json.Marshal(p.Tags)
	attrsJSON, _ := json.Marshal(p.Attributes)

	return s.db.QueryRowContext(ctx, `
		INSERT INTO ecommerce_products (sku, name, description, category_id, price, currency,
		  image_url, is_active, merchant_id, agent_id, weight, dimensions, tags, attributes)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
		RETURNING id, created_at, updated_at
	`, p.SKU, p.Name, p.Description, p.CategoryID, p.Price, p.Currency,
		nullString(p.ImageURL), p.IsActive, p.MerchantID, nullInt64(p.AgentID),
		p.Weight, nullString(p.Dimensions), string(tagsJSON), string(attrsJSON),
	).Scan(&p.ID, &p.CreatedAt, &p.UpdatedAt)
}

func (s *ProductStore) Update(ctx context.Context, p *models.Product) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}

	tagsJSON, _ := json.Marshal(p.Tags)
	attrsJSON, _ := json.Marshal(p.Attributes)

	_, err := s.db.ExecContext(ctx, `
		UPDATE ecommerce_products SET
		  name=$1, description=$2, category_id=$3, price=$4, currency=$5,
		  image_url=$6, is_active=$7, weight=$8, dimensions=$9, tags=$10,
		  attributes=$11, updated_at=NOW()
		WHERE id=$12
	`, p.Name, p.Description, p.CategoryID, p.Price, p.Currency,
		nullString(p.ImageURL), p.IsActive, p.Weight, nullString(p.Dimensions),
		string(tagsJSON), string(attrsJSON), p.ID,
	)
	return err
}

func (s *ProductStore) Delete(ctx context.Context, id int64) error {
	if s.db == nil {
		return fmt.Errorf("database not available")
	}
	_, err := s.db.ExecContext(ctx, "DELETE FROM ecommerce_products WHERE id=$1", id)
	return err
}

func (s *ProductStore) Search(ctx context.Context, query string, limit int) ([]models.Product, error) {
	if s.db == nil {
		return []models.Product{}, nil
	}

	rows, err := s.db.QueryContext(ctx, `
		SELECT id, sku, name, description, category_id, price, currency,
		       image_url, is_active, merchant_id, agent_id, weight, dimensions,
		       tags, attributes, created_at, updated_at
		FROM ecommerce_products
		WHERE name ILIKE $1 OR description ILIKE $1 OR sku ILIKE $1
		ORDER BY created_at DESC LIMIT $2
	`, "%"+query+"%", limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var products []models.Product
	for rows.Next() {
		var p models.Product
		var tags, attrs, imageURL, dimensions sql.NullString
		var agentID sql.NullInt64
		rows.Scan(&p.ID, &p.SKU, &p.Name, &p.Description, &p.CategoryID,
			&p.Price, &p.Currency, &imageURL, &p.IsActive, &p.MerchantID,
			&agentID, &p.Weight, &dimensions, &tags, &attrs, &p.CreatedAt, &p.UpdatedAt)
		if imageURL.Valid {
			p.ImageURL = imageURL.String
		}
		if agentID.Valid {
			p.AgentID = agentID.Int64
		}
		if tags.Valid {
			json.Unmarshal([]byte(tags.String), &p.Tags)
		}
		if attrs.Valid {
			json.Unmarshal([]byte(attrs.String), &p.Attributes)
		}
		products = append(products, p)
	}
	return products, nil
}

func nullString(s string) sql.NullString {
	if s == "" {
		return sql.NullString{}
	}
	return sql.NullString{String: s, Valid: true}
}

func nullInt64(i int64) sql.NullInt64 {
	if i == 0 {
		return sql.NullInt64{}
	}
	return sql.NullInt64{Int64: i, Valid: true}
}
