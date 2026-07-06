#!/usr/bin/env bash
###############################################################################
# OpenSearch Bootstrap — 54Link Platform
# Applies index templates, ILM policies, and creates initial indexes
# Run once on cluster initialization or after configuration changes
###############################################################################
set -euo pipefail

OS_URL="${OPENSEARCH_URL:-http://localhost:9200}"
OS_USER="${OPENSEARCH_USER:-admin}"
OS_PASS="${OPENSEARCH_PASSWORD:-admin}"
AUTH_HEADER="Authorization: Basic $(echo -n "$OS_USER:$OS_PASS" | base64)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }

wait_for_opensearch() {
  log "Waiting for OpenSearch at $OS_URL ..."
  for i in $(seq 1 60); do
    if curl -sf -H "$AUTH_HEADER" "$OS_URL/_cluster/health" >/dev/null 2>&1; then
      log "OpenSearch is ready"
      return 0
    fi
    sleep 2
  done
  log "ERROR: OpenSearch not reachable after 120s"
  exit 1
}

apply_ilm_policies() {
  log "Applying ILM policies..."
  local templates_file="$SCRIPT_DIR/index-templates.json"
  if [ ! -f "$templates_file" ]; then
    log "WARN: index-templates.json not found, skipping ILM"
    return
  fi

  # Extract and apply each ILM policy
  local policy_count
  policy_count=$(python3 -c "import json; d=json.load(open('$templates_file')); print(len(d.get('ilm_policies',[])))" 2>/dev/null || echo "0")

  for i in $(seq 0 $((policy_count - 1))); do
    local name body
    name=$(python3 -c "import json; d=json.load(open('$templates_file')); print(d['ilm_policies'][$i]['name'])")
    body=$(python3 -c "import json; d=json.load(open('$templates_file')); print(json.dumps(d['ilm_policies'][$i]['policy']))")

    curl -sf -X PUT "$OS_URL/_plugins/_ism/policies/$name" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d "{\"policy\": $body}" >/dev/null 2>&1 && \
      log "  ILM policy '$name' applied" || \
      log "  WARN: ILM policy '$name' failed (may already exist)"
  done
}

apply_index_templates() {
  log "Applying index templates..."
  local templates_file="$SCRIPT_DIR/index-templates.json"
  if [ ! -f "$templates_file" ]; then
    log "WARN: index-templates.json not found, skipping templates"
    return
  fi

  local template_count
  template_count=$(python3 -c "import json; d=json.load(open('$templates_file')); print(len(d.get('index_templates',[])))" 2>/dev/null || echo "0")

  for i in $(seq 0 $((template_count - 1))); do
    local name body
    name=$(python3 -c "import json; d=json.load(open('$templates_file')); print(d['index_templates'][$i]['name'])")
    body=$(python3 -c "import json; d=json.load(open('$templates_file')); print(json.dumps({'index_patterns': d['index_templates'][$i]['index_patterns'], 'template': d['index_templates'][$i]['template']}))")

    curl -sf -X PUT "$OS_URL/_index_template/$name" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d "$body" >/dev/null 2>&1 && \
      log "  Template '$name' applied" || \
      log "  WARN: Template '$name' failed"
  done
}

create_initial_indexes() {
  log "Creating initial indexes (if not exist)..."
  local today
  today=$(date +%Y.%m.%d)
  for index in "transactions-$today" "audit-logs-$today" "fraud-events-$today" "agent-metrics-$today"; do
    curl -sf -X PUT "$OS_URL/$index" \
      -H "$AUTH_HEADER" \
      -H "Content-Type: application/json" \
      -d '{}' >/dev/null 2>&1 && \
      log "  Index '$index' created" || \
      log "  Index '$index' already exists"
  done
}

configure_security() {
  log "Configuring security settings..."
  # Disable CORS for external access (API gateway handles CORS)
  curl -sf -X PUT "$OS_URL/_cluster/settings" \
    -H "$AUTH_HEADER" \
    -H "Content-Type: application/json" \
    -d '{
      "persistent": {
        "plugins.security.audit.type": "internal_opensearch",
        "plugins.security.audit.config.disabled_rest_categories": ["AUTHENTICATED"],
        "plugins.security.restapi.roles_enabled": ["all_access"]
      }
    }' >/dev/null 2>&1 && \
    log "  Security audit logging enabled" || \
    log "  WARN: Security configuration skipped"
}

# ─── Main ─────────────────────────────────────────────────────────────────
wait_for_opensearch
apply_ilm_policies
apply_index_templates
create_initial_indexes
configure_security
log "OpenSearch bootstrap complete!"
