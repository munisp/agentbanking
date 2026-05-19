#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Kafka Topic Provisioning Script — 54Link Agency Banking Platform
#
# Creates all required Kafka topics with appropriate partitions and replication.
# Run once after Kafka starts: ./infra/kafka/create-topics.sh
#
# Prerequisites:
#   - kafka-topics.sh available (Kafka bin directory in PATH)
#   - Kafka broker reachable at KAFKA_BROKERS
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

KAFKA_BROKERS="${KAFKA_BROKERS:-localhost:9092}"
REPLICATION_FACTOR="${KAFKA_REPLICATION_FACTOR:-1}"  # 3 in production cluster

echo "[Kafka] Connecting to brokers: ${KAFKA_BROKERS}"

# Helper function to create topic if it doesn't exist
create_topic() {
  local TOPIC=$1
  local PARTITIONS=$2
  local RETENTION_MS=$3
  local CLEANUP_POLICY="${4:-delete}"

  kafka-topics.sh \
    --bootstrap-server "${KAFKA_BROKERS}" \
    --create \
    --if-not-exists \
    --topic "${TOPIC}" \
    --partitions "${PARTITIONS}" \
    --replication-factor "${REPLICATION_FACTOR}" \
    --config retention.ms="${RETENTION_MS}" \
    --config cleanup.policy="${CLEANUP_POLICY}" \
    --config min.insync.replicas=1 \
    && echo "[Kafka] ✓ Topic: ${TOPIC} (${PARTITIONS} partitions, retention: ${RETENTION_MS}ms)"
}

# ── Core transaction topics ───────────────────────────────────────────────────
# 7 days retention for transaction events
create_topic "54link.transactions.created"     12  604800000
create_topic "54link.transactions.completed"   12  604800000
create_topic "54link.transactions.failed"      12  604800000
create_topic "54link.transactions.reversed"    6   604800000

# ── Float management topics ───────────────────────────────────────────────────
create_topic "54link.float.topup.requested"    6   604800000
create_topic "54link.float.topup.approved"     6   604800000
create_topic "54link.float.topup.rejected"     6   604800000
create_topic "54link.float.balance.updated"    6   86400000   # 1 day

# ── Fraud detection topics ────────────────────────────────────────────────────
create_topic "54link.fraud.events"             12  2592000000  # 30 days
create_topic "54link.fraud.alerts"             6   2592000000
create_topic "54link.fraud.decisions"          6   2592000000

# ── SIM orchestrator topics ───────────────────────────────────────────────────
create_topic "54link.sim.probe.readings"       6   86400000   # 1 day
create_topic "54link.sim.failover.events"      6   604800000
create_topic "54link.sim.carrier.status"       3   86400000

# ── Settlement topics ─────────────────────────────────────────────────────────
create_topic "54link.settlement.daily"         3   2592000000  # 30 days
create_topic "54link.settlement.completed"     3   2592000000
create_topic "54link.settlement.failed"        3   2592000000

# ── Agent lifecycle topics ────────────────────────────────────────────────────
create_topic "54link.agent.registered"         3   -1          # infinite
create_topic "54link.agent.suspended"          3   -1
create_topic "54link.agent.kyc.completed"      3   -1

# ── Audit log topics (compacted — infinite retention) ─────────────────────────
create_topic "54link.audit.log"                6   -1  compact

# ── Push notification topics ──────────────────────────────────────────────────
create_topic "54link.push.notifications"       6   3600000    # 1 hour

# ── Dead letter queues ────────────────────────────────────────────────────────
create_topic "54link.dlq.transactions"         3   604800000
create_topic "54link.dlq.settlements"          3   604800000
create_topic "54link.dlq.notifications"        3   604800000

echo ""
echo "[Kafka] ✅ All topics provisioned"
kafka-topics.sh --bootstrap-server "${KAFKA_BROKERS}" --list | grep "54link\." | wc -l | xargs -I{} echo "[Kafka] Total 54link topics: {}"
