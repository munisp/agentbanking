#!/bin/bash
# Builds and pushes agentbanking service images to the DO registry.
#
# Two build modes, auto-selected per target:
#   - Consolidated groups (multiple services in one image via Dockerfile.consolidated)
#   - Standalone charts (a single service built from its own services/<name>/Dockerfile)
#
# Usage:
#   ./docker/build-and-push.sh                      # build + push everything (top → bottom)
#   ./docker/build-and-push.sh <name>               # build + push one group or standalone service
#   BUILD_ONLY=1 ./docker/build-and-push.sh         # build without pushing
#   REVERSE=1 ./docker/build-and-push.sh            # build + push everything (bottom → top)
#   REVERSE=1 BUILD_ONLY=1 ./docker/build-and-push.sh
#
set -e

export DOCKER_BUILDKIT=1

REGISTRY="registry.digitalocean.com/talentgraph-auth"
TAG="${TAG:-0.0.1}"
DOCKERFILE="docker/Dockerfile.consolidated"
CONTEXT="."
BUILD_ONLY="${BUILD_ONLY:-0}"
REVERSE="${REVERSE:-0}"
TARGET="${1:-}"

cd "$(dirname "$0")/.."

# ── Consolidated groups: name|services|port_base ─────────────────────────────
# Generated from infrastructure/charts/*/values.yaml (SERVICE_GROUP/SERVICES/PORT_BASE)
GROUPS_DATA="
agent-core|agent-baas,agent-business-dashboard,agent-embedded-finance,agent_embedded_finance,agent-hierarchy-service,agent-liquidity-network,agent-lms,agent-performance,agent-scorecard,agent_scorecard,agent-service,agent-training,agent-training-academy,agent-wallet-transparency,art-agent-service,commission-calculator,commission-service,commission-settlement,float-management,float-service,float-integration-models,hierarchy-engine,hierarchy-service|9100
agent-pos|android-native,device-management,firmware-distribution,ios-native,iot-smart-pos,mdm-compliance-engine,mdm-geofence-service,mdm-service,ota-service,pos-fluvio-consumer,pos-geofencing,pos-hardware-management,pos-integration,pos-management,pos-printer,pos-shell-config,pos-terminal-management,power-management,terminal-heartbeat,terminal-ownership,territory-management|9125
ai-ml|ai-credit-scoring,ai-document-validation,ai-ml-services,ai-orchestration,demand-forecasting-py,gnn-engine,ml-engine,ml-model-registry,ml-pipeline,neural-network-service,python-ml-engine,revenue-forecast-ml|9148
analytics-data|analytics,analytics-dashboard,analytics-service,analytics-service-ts,business-intelligence,cdp-service,cocoindex-service,connectivity-analytics,customer-analytics,dashboard-service,epr-kgqa-service,opensearch-analytics,opensearch-indexer,projections-targets,reporting-engine,reporting-service,store-analytics-engine,unified-analytics,ussd-analytics|9162
billing|billing-aggregator,billing-analytics-pipeline,billing-anomaly-detector,billing-event-processor,billing-provisioning-workflow,billing-reconciliation-engine,billing-sla-monitor,billing-stream-processor,billing-webhook-dispatcher,fee-splitter-realtime,financial-services,invoice-generator,nigeria-vat-service,payroll-disbursement,revenue-reconciler,sla-billing-reporter,tb-commission-sidecar,tb-sidecar|9204
cbn-regulatory|audit-chain,audit-service,cbn-compliance-comprehensive,cbn-reporting-engine,cbn-tiered-kyc,compliance,compliance-kyc,compliance-reporting,compliance-service,compliance-workflows,gdpr-service,goaml-integration-go|9224
channels-messaging|communication-gateway,communication-hub,communication-service,communication-shared,messaging-service,multilingual-integration-service,notification-service,omnichannel-middleware,push-notification-service,realtime-notification-service,realtime-translation,sms-gateway,sms-service,sms-transaction-bridge,translation-service,unified-communication-hub,unified-communication-service|9256
channels-social|at-sms-sender,at-sms-webhook,discord-service,email-service,google-assistant-service,instagram-service,messenger-service,rcs-service,snapchat-service,telegram-service,tiktok-service,twitter-service,wechat-service,whatsapp-ai-bot,whatsapp-order-service,whatsapp-service|9238
channels-ussd-voice|at-ussd-handler,at-ussd-session,conversational-banking,ussd-gateway,ussd-localization,ussd-menu-builder,ussd-receipt-printer,ussd-service,ussd-session-cache,ussd-session-replayer,ussd-tx-processor,voice-ai-service,voice-assistant-service,voice-command-nlu|9275
connectivity-sim|airtime-provider-gateway,carrier-billing,carrier-cost-engine,carrier-failover-proxy,carrier-live-api,carrier-performance-reporter,carrier-ranking-engine,carrier-recommendation,carrier-signal-monitor,carrier-sla-monitor,geospatial-service,multi-sim-failover,network-coverage-export,network-diagnostic,network-ml-trainer,network-operations,network-quality-predictor,satellite-connectivity,telco-integration|9291
core-accounts|account-service,beneficiary-service,multi-currency-accounts,multi-currency-engine,multi-currency-wallet,onboarding-service,open-banking,open-banking-api,settings-service,user-onboarding-enhanced|9313
core-ledger|chart-of-accounts,core-banking,go-ledger-sync,interest-calculation,ledger-bridge,ledger-integrity-validator,offline-ledger,tigerbeetle-core,tigerbeetle-edge,tigerbeetle-integrated,tigerbeetle-sync,tigerbeetle-zig|9325
core-payments|bill-payment-gateway,biller-integration,cips-integration,cross-border,currency-conversion,education-payments,fps-integration,global-payment-gateway,instant-reversal-engine,mojaloop-connector,mojaloop-connector-pos,nfc-qr-payments,nfc-tap-to-pay,nibss-integration,papss-integration,payment-corridors-service,payment-gateway-service,payment-hub,payment-processing-service,payment-rails-connectors,payment-split-engine,payout-service,qr-code-service,qr-ticket-verification,sepa-instant,swift-integration,upi-connector,upi-integration,wearable-payments,wise-integration|9339
customer-engagement|coalition-loyalty,customer-service,gamification,knowledge-base,loyalty-service,promotion-service,rewards-service,shareable-links,support-comms-service,support-crm,support-service|9371
data-lakehouse|backup-manager,backup-service,data-archival,data-warehouse,dual-write-service,etl-pipeline,falkordb-service,lakehouse-integration,lakehouse-mojaloop,lakehouse-service,ollama-service,postgres-production,sync-manager|9384
dispute-settlement|dispute-resolution,dispute-service,reconciliation-service,recurring-payments,refund-service,settlement-batch-processor,settlement-gateway,settlement-ledger-sync,settlement-service|9399
ecommerce-marketplace|agent-commerce-integration,agent-ecommerce-platform,agent-store-service,amazon-ebay-integration,amazon-service,ebay-service,ecommerce-cart-rust,ecommerce-catalog-go,ecommerce-intelligence-py,ecommerce-service,gaming-integration,gaming-service,jumia-service,konga-service,marketplace-integration,marketplace-integrations-go,store-map-service,storefront-advertising|9410
fraud-risk|aml-case-manager-go,aml-monitoring,fraud-detection,fraud-ml-pipeline,fraud-ml-service,risk-assessment,risk-management,rule-engine,sanctions-batch-rescreener,sanctions-etl,transaction-scoring,tx-monitor-alerter,tx-validator|9430
infra-messaging|dapr-sidecar,fluvio-consumer,fluvio-producer,fluvio-smartmodule,fluvio-streaming,offline-sync,offline-sync-orchestrator,realtime-services,unified-streaming,websocket-service|9446
infra-network|adaptive-compression,bandwidth-optimizer,circuit-breaker,connection-multiplexer,connection-quality-monitor,connectivity-resilience,edge-computing,edge-deployment,grpc,hybrid-engine,load-balancer,middleware,middleware-integration,optimization,performance-optimization,platform-middleware,redis-cache-layer,resilience-agent,resilience-proxy,rust-middleware-bridge|9459
infra-observability|chaos-engineering,distributed-tracing,logging-service,metrics-service,monitoring,monitoring-dashboard,telemetry-aggregator,telemetry-api-gateway,telemetry-collector,telemetry-ingestion|9481
kyc-aml|background-check,bank-verification,case-management,deepfake-detection,docling-service,document-fraud-detection,document-management,document-processing,kyb-analytics,kyb-engine,kyb-risk-engine,kyb-verification,kyc-document-verifier,kyc-enforcement-go,kyc-enhanced,kyc-event-consumer,kyc-kyb-service,kyc-service,kyc-workflow-orchestration,kyc-workflow-orchestrator,multi-ocr-service,ocr-processing,ocr-service,paddle-ocr-service,rust-ocr-bridge,vlm-document-service|9493
lending-credit|bnpl-engine,carbon-credit-marketplace,credit-scoring,loan-management,loan-service|9521
open-banking-api|admin-service,admin-services,api-gateway,api-server-ts,apisix-gateway,developer-portal-service,embedded-finance-anaas,gateway-service,management-api,unified-api,white-label-api|9528
platform-tenant|config-service,enhanced-platform,enterprise-services,super-app-framework,tenant-management|9541
realtime-transactions|card-service,merchant-service,realtime-fee-splitter,realtime-receipt-engine,receipt-engine,transaction-history,transaction-limits,transaction-queue,transaction-services,webhook-delivery,webhook-service|9548
security|ddos-shield,ransomware-guard,secuirity-services,security-alert,security-monitoring,security-scanner,security-services|9561
specialized-finance|blockchain,health-insurance-micro,health-service,insurance-service,investment-service,metaverse-service,pension-micro,stablecoin-defi,stablecoin-integration,stablecoin-rails,stablecoin-v2,tokenized-assets,wealth|9570
supply-chain-govt|agritech-payments,government-integration,i18n-currency,inventory-management,inventory-service,supply-chain,supply-chain-go|9585
third-party-integrations|additional-services,erpnext-integration,remitly-integration,zapier-integration,zapier-service|9594
transaction-ledger|transaction-ledger|9337
workflow-orchestration|compensating-actions,integration-layer,integration-service,integrations,orchestrator-service,scheduler-service,temporal,workflow-integration,workflow-orchestration,workflow-orchestrator,workflow-orchestrator-enhanced,workflow-service|9601
"

# ── Standalone charts: built from their own services/<name>/Dockerfile ──────
# (these have no SERVICES field in their Helm values — one service, one image)
STANDALONE_LIST="auth-service authentication-service biometric chart-of-accounts deepface-service digital-identity-layer face-matching fido2-service fraud-engine liveness-detection mfa-service mfa notification-service offline-queue pbac-enforcer pbac-engine rbac-service rbac service-auth sim-orchestrator-service user-management user-service verification-service verification-ui"

is_standalone() {
    local name="$1"
    for s in $STANDALONE_LIST; do
        [ "$s" = "$name" ] && return 0
    done
    return 1
}

# ── Build one consolidated group ─────────────────────────────────────────────
build_group() {
    local group="$1"
    local services="$2"
    local port_base="$3"
    local image="${REGISTRY}/54agent-${group}:${TAG}"
    local svc_count
    svc_count=$(echo "$services" | tr ',' '\n' | wc -l | xargs)

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Building : $group (group)"
    echo "  Image    : $image"
    echo "  Services : $svc_count"
    echo "  Port base: $port_base"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local output_flag="--load"
    if [ "$BUILD_ONLY" = "0" ]; then
        # Force gzip compression — DO registry rejects zstd (BuildKit default)
        output_flag="--output type=image,name=${image},push=true,compression=gzip,force-compression=true"
    fi

    if ! docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --file "$DOCKERFILE" \
        --build-arg "SERVICES=$services" \
        --build-arg "PORT_BASE=$port_base" \
        --tag "$image" \
        $output_flag \
        "$CONTEXT"; then
        echo "[failed] $group ✗"
        return 1
    fi

    echo "[done] $group ✓"
}

# ── Build one standalone service (its own Dockerfile) ───────────────────────
build_standalone() {
    local name="$1"
    local dockerfile="services/$name/Dockerfile"
    local image="${REGISTRY}/54agent-${name}:${TAG}"

    if [ ! -f "$dockerfile" ]; then
        echo "[failed] $name — no Dockerfile at $dockerfile ✗"
        return 1
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Building : $name (standalone)"
    echo "  Image    : $image"
    echo "  Dockerfile: $dockerfile"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    local output_flag="--load"
    if [ "$BUILD_ONLY" = "0" ]; then
        output_flag="--output type=image,name=${image},push=true,compression=gzip,force-compression=true"
    fi

    if ! docker buildx build \
        --platform linux/amd64 \
        --provenance=false \
        --file "$dockerfile" \
        --tag "$image" \
        $output_flag \
        "services/$name"; then
        echo "[failed] $name ✗"
        return 1
    fi

    echo "[done] $name ✓"
}

# ── Main ──────────────────────────────────────────────────────────────────────
FAILED=""

if [ -n "$TARGET" ] && is_standalone "$TARGET"; then
    build_standalone "$TARGET" || FAILED="$FAILED $TARGET"
else
    while IFS='|' read -r group services port; do
        [ -z "$group" ] && continue
        if [ -n "$TARGET" ] && [ "$group" != "$TARGET" ]; then
            continue
        fi
        build_group "$group" "$services" "$port" || FAILED="$FAILED $group"
    done <<< "$([ "$REVERSE" = "1" ] && echo "$GROUPS_DATA" | tac || echo "$GROUPS_DATA")"

    if [ -z "$TARGET" ]; then
        for name in $STANDALONE_LIST; do
            build_standalone "$name" || FAILED="$FAILED $name"
        done
    elif [ -z "$(echo "$GROUPS_DATA" | grep "^${TARGET}|")" ] && ! is_standalone "$TARGET"; then
        echo "ERROR: unknown target '$TARGET'"
        exit 1
    fi
fi

echo ""
echo "════════════════════════════════════════"
if [ -z "$FAILED" ]; then
    echo "  All targets built successfully ✓"
else
    echo "  Failed:$FAILED"
    exit 1
fi
echo "════════════════════════════════════════"
