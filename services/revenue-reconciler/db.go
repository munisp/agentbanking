package main

import (
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
)

// db is the shared PostgreSQL handle used by the reconciliation engine.
var db *sql.DB

// initDB opens and verifies the PostgreSQL connection. The reconciler has no
// meaningful work without both data sources, so callers must fail startup on
// error.
func initDB(dsn string) error {
	if dsn == "" {
		return fmt.Errorf("POSTGRES_URL not set")
	}
	conn, err := sql.Open("postgres", dsn)
	if err != nil {
		return fmt.Errorf("postgres open: %w", err)
	}
	if err := conn.Ping(); err != nil {
		conn.Close()
		return fmt.Errorf("postgres unreachable: %w", err)
	}
	db = conn
	return nil
}
