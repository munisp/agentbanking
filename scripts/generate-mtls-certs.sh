#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# 54Link mTLS Certificate Generation Script
# Generates a CA + per-service client/server certs for mutual TLS
# Usage: ./scripts/generate-mtls-certs.sh [--output-dir ./certs]
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${1:-$SCRIPT_DIR/../certs/mtls}"
DAYS=825  # Max validity for mTLS certs per Apple/browser guidelines
COUNTRY="NG"
ORG="54Link Agency Banking"
CA_CN="54Link Internal CA"

# Services that need mTLS certs
SERVICES=(
  "pos-shell"
  "api-gateway"
  "auth-service"
  "fraud-engine"
  "settlement-service"
  "kyc-service"
  "hierarchy-engine"
  "mdm-compliance-engine"
  "mdm-geofence-service"
  "cbn-reporting-engine"
  "ota-service"
  "notification-service"
  "analytics-service"
  "workflow-orchestrator"
  "credit-scoring"
  "rbac-service"
  "mfa-service"
  "sim-orchestrator"
  "resilience-agent"
  "tigerbeetle-sidecar"
)

mkdir -p "$OUTPUT_DIR/ca"
mkdir -p "$OUTPUT_DIR/services"

echo "=== Generating 54Link mTLS Certificates ==="
echo "Output: $OUTPUT_DIR"
echo ""

# ── Step 1: Generate CA ───────────────────────────────────────────────────────
echo "[1/3] Generating Root CA..."
openssl genrsa -out "$OUTPUT_DIR/ca/ca.key" 4096

openssl req -new -x509 \
  -key "$OUTPUT_DIR/ca/ca.key" \
  -out "$OUTPUT_DIR/ca/ca.crt" \
  -days $DAYS \
  -subj "/C=$COUNTRY/O=$ORG/CN=$CA_CN" \
  -extensions v3_ca \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"

echo "  ✓ CA certificate: $OUTPUT_DIR/ca/ca.crt"

# ── Step 2: Generate per-service certs ───────────────────────────────────────
echo ""
echo "[2/3] Generating service certificates..."

for SERVICE in "${SERVICES[@]}"; do
  SVC_DIR="$OUTPUT_DIR/services/$SERVICE"
  mkdir -p "$SVC_DIR"

  # Generate service private key
  openssl genrsa -out "$SVC_DIR/tls.key" 2048

  # Generate CSR
  openssl req -new \
    -key "$SVC_DIR/tls.key" \
    -out "$SVC_DIR/tls.csr" \
    -subj "/C=$COUNTRY/O=$ORG/CN=$SERVICE.54link.internal"

  # Create SAN extension file
  cat > "$SVC_DIR/san.ext" << EOF
[SAN]
subjectAltName=DNS:$SERVICE,DNS:$SERVICE.54link.internal,DNS:$SERVICE.default.svc.cluster.local,DNS:localhost,IP:127.0.0.1
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth,clientAuth
basicConstraints=CA:FALSE
EOF

  # Sign with CA
  openssl x509 -req \
    -in "$SVC_DIR/tls.csr" \
    -CA "$OUTPUT_DIR/ca/ca.crt" \
    -CAkey "$OUTPUT_DIR/ca/ca.key" \
    -CAcreateserial \
    -out "$SVC_DIR/tls.crt" \
    -days $DAYS \
    -extfile "$SVC_DIR/san.ext" \
    -extensions SAN \
    -sha256 2>/dev/null

  # Create bundle (cert + CA chain)
  cat "$SVC_DIR/tls.crt" "$OUTPUT_DIR/ca/ca.crt" > "$SVC_DIR/tls-bundle.crt"

  # Cleanup CSR and ext file
  rm -f "$SVC_DIR/tls.csr" "$SVC_DIR/san.ext"

  echo "  ✓ $SERVICE"
done

# ── Step 3: Generate docker-compose secrets snippet ──────────────────────────
echo ""
echo "[3/3] Generating docker-compose secrets reference..."

SECRETS_FILE="$OUTPUT_DIR/docker-compose-secrets.yml"
cat > "$SECRETS_FILE" << 'YAML_EOF'
# Add this to your docker-compose.production.yml secrets section:
secrets:
  ca_cert:
    file: ./certs/mtls/ca/ca.crt
YAML_EOF

for SERVICE in "${SERVICES[@]}"; do
  cat >> "$SECRETS_FILE" << YAML_EOF
  ${SERVICE//-/_}_tls_cert:
    file: ./certs/mtls/services/$SERVICE/tls.crt
  ${SERVICE//-/_}_tls_key:
    file: ./certs/mtls/services/$SERVICE/tls.key
YAML_EOF
done

echo "  ✓ Secrets reference: $SECRETS_FILE"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "=== mTLS Certificate Generation Complete ==="
echo "  CA cert:      $OUTPUT_DIR/ca/ca.crt"
echo "  CA key:       $OUTPUT_DIR/ca/ca.key  (KEEP SECRET)"
echo "  Services:     ${#SERVICES[@]} certs generated"
echo "  Valid for:    $DAYS days"
echo ""
echo "⚠  IMPORTANT: Add certs/ to .gitignore — never commit private keys!"
echo "   Add this line to .gitignore: certs/mtls/**/*.key"
echo ""
echo "Next steps:"
echo "  1. Mount certs as Docker secrets in docker-compose.production.yml"
echo "  2. Configure each service to load certs from /run/secrets/"
echo "  3. Set MTLS_ENABLED=true in .env.production"
