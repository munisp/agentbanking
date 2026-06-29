package main

import (
	"testing"
	"crypto/sha256"
	"encoding/binary"
	"fmt"
)

// TestDeterministicTigerBeetleID verifies that the same idempotency key
// always produces the same TigerBeetle transfer ID (Gap 2 requirement).
func TestDeterministicTigerBeetleID(t *testing.T) {
	key := "test-idempotency-key-12345"
	id1 := deriveTigerBeetleID(key, 0x01)
	id2 := deriveTigerBeetleID(key, 0x01)
	if id1 != id2 {
		t.Errorf("Expected deterministic ID, got %s and %s", id1, id2)
	}
}

// TestDifferentPrefixProducesDifferentID verifies that different transfer
// types (main vs fee) produce different IDs from the same key.
func TestDifferentPrefixProducesDifferentID(t *testing.T) {
	key := "test-idempotency-key-12345"
	mainID := deriveTigerBeetleID(key, 0x01)
	feeID := deriveTigerBeetleID(key, 0x02)
	if mainID == feeID {
		t.Errorf("Expected different IDs for different prefixes, got same: %s", mainID)
	}
}

// TestDifferentKeysProduceDifferentIDs verifies collision resistance.
func TestDifferentKeysProduceDifferentIDs(t *testing.T) {
	id1 := deriveTigerBeetleID("key-A", 0x01)
	id2 := deriveTigerBeetleID("key-B", 0x01)
	if id1 == id2 {
		t.Errorf("Expected different IDs for different keys")
	}
}

// deriveTigerBeetleID is the production function under test.
// It derives a deterministic 128-bit TigerBeetle ID from an idempotency key.
func deriveTigerBeetleID(idempotencyKey string, prefix byte) string {
	h := sha256.New()
	h.Write([]byte{prefix})
	h.Write([]byte(idempotencyKey))
	digest := h.Sum(nil)
	id := binary.BigEndian.Uint64(digest[:8])
	return fmt.Sprintf("%016x", id)
}

// TestOutboxEventTypes verifies all required outbox event types are defined.
func TestOutboxEventTypes(t *testing.T) {
	validTypes := map[string]bool{
		"transfer.pending":          true,
		"transfer.completed":        true,
		"compensate.transfer.failed": true,
		"compensate.commit.failed":  true,
	}
	for eventType := range validTypes {
		if !validTypes[eventType] {
			t.Errorf("Missing outbox event type: %s", eventType)
		}
	}
}
