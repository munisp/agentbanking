// TB Commission Sidecar — Go HTTP server providing double-entry ledger
// for commission credits, settlement transfers, and refund reversals.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/54link/tb-commission-sidecar/internal/api"
	"github.com/54link/tb-commission-sidecar/internal/ledger"
)

func main() {
	port := os.Getenv("TB_COMMISSION_PORT")
	if port == "" {
		port = "8040"
	}
	dbPath := os.Getenv("TB_COMMISSION_DB_PATH")
	if dbPath == "" {
		dbPath = "/var/lib/54link/tb-commission.db"
	}

	os.MkdirAll("/var/lib/54link", 0755)

	log.Printf("[TB-Commission-Sidecar] Starting on :%s (db=%s)", port, dbPath)

	l, err := ledger.New(dbPath)
	if err != nil {
		log.Fatalf("Failed to initialize ledger: %v", err)
	}
	defer l.Close()

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      api.New(l),
		ReadTimeout:  5 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	go func() {
		log.Printf("[TB-Commission-Sidecar] Listening on :%s", port)
		if err := srv.ListenAndServe(); err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("[TB-Commission-Sidecar] Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
	log.Println("[TB-Commission-Sidecar] Stopped")
}
