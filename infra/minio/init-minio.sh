#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# MinIO Lakehouse Initialisation Script — 54Link Agency Banking Platform
#
# Creates all required buckets and sets lifecycle policies.
# Run once after MinIO starts: ./infra/minio/init-minio.sh
#
# Prerequisites:
#   - mc (MinIO Client) installed: https://min.io/docs/minio/linux/reference/minio-mc.html
#   - MinIO running at MINIO_ENDPOINT (default: http://localhost:9000)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MINIO_ENDPOINT="${MINIO_ENDPOINT:-http://localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
ALIAS="54link"

echo "[MinIO] Configuring mc alias → ${MINIO_ENDPOINT}"
mc alias set "${ALIAS}" "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}" --api S3v4

# ── Create buckets ────────────────────────────────────────────────────────────
BUCKETS=(
  "54link-transactions"      # Raw transaction records (Parquet)
  "54link-settlements"       # Daily settlement reports (CSV + Parquet)
  "54link-fraud-events"      # Fraud detection events (JSON)
  "54link-kyc-documents"     # KYC/KYB document uploads (encrypted)
  "54link-receipts"          # Generated PDF receipts
  "54link-audit-logs"        # Immutable audit trail (WORM)
  "54link-analytics"         # Aggregated analytics datasets
  "54link-backups"           # Database and config backups
  "54link-ota-packages"      # OTA firmware update packages
  "54link-agent-media"       # Agent profile photos and documents
)

for BUCKET in "${BUCKETS[@]}"; do
  if mc ls "${ALIAS}/${BUCKET}" &>/dev/null; then
    echo "[MinIO] Bucket already exists: ${BUCKET}"
  else
    mc mb "${ALIAS}/${BUCKET}"
    echo "[MinIO] Created bucket: ${BUCKET}"
  fi
done

# ── Set versioning on critical buckets ────────────────────────────────────────
VERSIONED_BUCKETS=(
  "54link-transactions"
  "54link-settlements"
  "54link-audit-logs"
  "54link-kyc-documents"
)

for BUCKET in "${VERSIONED_BUCKETS[@]}"; do
  mc version enable "${ALIAS}/${BUCKET}"
  echo "[MinIO] Versioning enabled: ${BUCKET}"
done

# ── Set object lock (WORM) on audit logs ─────────────────────────────────────
# Note: Object lock must be enabled at bucket creation time.
# Re-create with lock if needed:
# mc mb --with-lock "${ALIAS}/54link-audit-logs"

# ── Set lifecycle policies ────────────────────────────────────────────────────
# Transactions: archive after 90 days, delete after 7 years (CBN compliance)
cat > /tmp/transactions-lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "ID": "archive-old-transactions",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "Transition": {
        "Days": 90,
        "StorageClass": "GLACIER"
      },
      "Expiration": {
        "Days": 2555
      }
    }
  ]
}
EOF
mc ilm import "${ALIAS}/54link-transactions" < /tmp/transactions-lifecycle.json
echo "[MinIO] Lifecycle policy set: 54link-transactions"

# Receipts: delete after 2 years
cat > /tmp/receipts-lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "ID": "expire-old-receipts",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "Expiration": {
        "Days": 730
      }
    }
  ]
}
EOF
mc ilm import "${ALIAS}/54link-receipts" < /tmp/receipts-lifecycle.json
echo "[MinIO] Lifecycle policy set: 54link-receipts"

# Backups: delete after 90 days
cat > /tmp/backups-lifecycle.json << 'EOF'
{
  "Rules": [
    {
      "ID": "expire-old-backups",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
EOF
mc ilm import "${ALIAS}/54link-backups" < /tmp/backups-lifecycle.json
echo "[MinIO] Lifecycle policy set: 54link-backups"

# ── Set bucket policies ───────────────────────────────────────────────────────
# KYC documents: private (no public access)
mc anonymous set none "${ALIAS}/54link-kyc-documents"
mc anonymous set none "${ALIAS}/54link-audit-logs"
mc anonymous set none "${ALIAS}/54link-backups"
echo "[MinIO] Private access enforced on sensitive buckets"

# ── Create service account for application ────────────────────────────────────
mc admin user add "${ALIAS}" "54link-app" "54link-app-secret-change-in-prod"
mc admin policy attach "${ALIAS}" readwrite --user "54link-app"
echo "[MinIO] Service account created: 54link-app"

echo ""
echo "[MinIO] ✅ Lakehouse initialisation complete"
echo "  Buckets: ${#BUCKETS[@]} created"
echo "  Versioning: ${#VERSIONED_BUCKETS[@]} buckets"
echo "  Lifecycle policies: transactions (7yr), receipts (2yr), backups (90d)"

# ── Apply lifecycle policies from JSON files ──────────────────────────────────
# Screenshots: expire after 90 days, transition to GLACIER after 30 days
if [[ -f "/init/lifecycle/54link-screenshots-lifecycle.json" ]]; then
  mc mb "${ALIAS}/54link-screenshots" 2>/dev/null || true
  mc ilm import "${ALIAS}/54link-screenshots" < /init/lifecycle/54link-screenshots-lifecycle.json
  echo "[MinIO] Lifecycle policy set: 54link-screenshots"
fi

# Firmware: expire old non-current versions after 1 year
if [[ -f "/init/lifecycle/54link-firmware-lifecycle.json" ]]; then
  mc mb "${ALIAS}/54link-firmware" 2>/dev/null || true
  mc ilm import "${ALIAS}/54link-firmware" < /init/lifecycle/54link-firmware-lifecycle.json
  echo "[MinIO] Lifecycle policy set: 54link-firmware"
fi

# Lakehouse: tiered storage (hot→warm→cold→delete)
if [[ -f "/init/lifecycle/54link-lakehouse-lifecycle.json" ]]; then
  mc mb "${ALIAS}/54link-lakehouse" 2>/dev/null || true
  mc ilm import "${ALIAS}/54link-lakehouse" < /init/lifecycle/54link-lakehouse-lifecycle.json
  echo "[MinIO] Lifecycle policy set: 54link-lakehouse"
fi

echo "[MinIO] ✅ All lifecycle policies applied"
