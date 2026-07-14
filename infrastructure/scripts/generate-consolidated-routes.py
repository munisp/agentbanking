#!/usr/bin/env python3
"""
Regenerates per-service APISIX route files for agent banking.

Each service keeps its OWN route file (matching core banking's convention), but
serviceName now points to the consolidated group and servicePort to the exact
port that service runs on inside the consolidated container.

Run from repo root:
    python3 infrastructure/scripts/generate-consolidated-routes.py
"""

import os, re, glob

ROUTES_DIR = "infrastructure/apisix-resources/routes"
NAMESPACE  = "54agent"
HOST       = "54agent.upi.dev"

# ── Group definitions (must match docker-compose.consolidated.yml order) ──────

GROUPS = [
    dict(name="agent-core",           port_base=9100,
         services=["agent-baas","agent-business-dashboard","agent-embedded-finance","agent_embedded_finance","agent-hierarchy-service","agent-liquidity-network","agent-lms","agent-performance","agent-scorecard","agent_scorecard","agent-service","agent-training","agent-training-academy","agent-wallet-transparency","art-agent-service","commission-calculator","commission-service","commission-settlement","float-management","float-service","float-integration-models","hierarchy-engine","hierarchy-service"]),
    dict(name="agent-pos",            port_base=9125,
         services=["android-native","device-management","firmware-distribution","ios-native","iot-smart-pos","mdm-compliance-engine","mdm-geofence-service","mdm-service","ota-service","pos-fluvio-consumer","pos-geofencing","pos-hardware-management","pos-integration","pos-management","pos-printer","pos-shell-config","pos-terminal-management","power-management","terminal-heartbeat","terminal-ownership","territory-management"]),
    dict(name="ai-ml",                port_base=9148,
         services=["ai-credit-scoring","ai-document-validation","ai-ml-services","ai-orchestration","demand-forecasting-py","gnn-engine","ml-engine","ml-model-registry","ml-pipeline","neural-network-service","python-ml-engine","revenue-forecast-ml"]),
    dict(name="analytics-data",       port_base=9162,
         services=["analytics","analytics-dashboard","analytics-service","analytics-service-ts","business-intelligence","cdp-service","cocoindex-service","connectivity-analytics","customer-analytics","dashboard-service","epr-kgqa-service","opensearch-analytics","opensearch-indexer","projections-targets","reporting-engine","reporting-service","store-analytics-engine","unified-analytics","ussd-analytics"]),
    dict(name="auth-identity",        port_base=9183,
         services=["auth-service","authentication-service","biometric","deepface-service","digital-identity-layer","face-matching","fido2-service","liveness-detection","mfa","mfa-service","pbac-enforcer","pbac-engine","rbac","rbac-service","service-auth","user-management","user-service","verification-service","verification-ui"]),
    dict(name="billing",              port_base=9204,
         services=["billing-aggregator","billing-analytics-pipeline","billing-anomaly-detector","billing-event-processor","billing-provisioning-workflow","billing-reconciliation-engine","billing-sla-monitor","billing-stream-processor","billing-webhook-dispatcher","fee-splitter-realtime","financial-services","invoice-generator","nigeria-vat-service","payroll-disbursement","revenue-reconciler","sla-billing-reporter","tb-commission-sidecar","tb-sidecar"]),
    dict(name="cbn-regulatory",       port_base=9224,
         services=["audit-chain","audit-service","cbn-compliance-comprehensive","cbn-reporting-engine","cbn-tiered-kyc","compliance","compliance-kyc","compliance-reporting","compliance-service","compliance-workflows","gdpr-service","goaml-integration-go"]),
    dict(name="channels-social",      port_base=9238,
         services=["at-sms-sender","at-sms-webhook","discord-service","email-service","google-assistant-service","instagram-service","messenger-service","rcs-service","snapchat-service","telegram-service","tiktok-service","twitter-service","wechat-service","whatsapp-ai-bot","whatsapp-order-service","whatsapp-service"]),
    dict(name="channels-messaging",   port_base=9256,
         services=["communication-gateway","communication-hub","communication-service","communication-shared","messaging-service","multilingual-integration-service","notification-service","omnichannel-middleware","push-notification-service","realtime-notification-service","realtime-translation","sms-gateway","sms-service","sms-transaction-bridge","translation-service","unified-communication-hub","unified-communication-service"]),
    dict(name="channels-ussd-voice",  port_base=9275,
         services=["at-ussd-handler","at-ussd-session","conversational-banking","ussd-gateway","ussd-localization","ussd-menu-builder","ussd-receipt-printer","ussd-service","ussd-session-cache","ussd-session-replayer","ussd-tx-processor","voice-ai-service","voice-assistant-service","voice-command-nlu"]),
    dict(name="connectivity-sim",     port_base=9291,
         services=["airtime-provider-gateway","carrier-billing","carrier-cost-engine","carrier-failover-proxy","carrier-live-api","carrier-performance-reporter","carrier-ranking-engine","carrier-recommendation","carrier-signal-monitor","carrier-sla-monitor","geospatial-service","multi-sim-failover","network-coverage-export","network-diagnostic","network-ml-trainer","network-operations","network-quality-predictor","satellite-connectivity","sim-orchestrator-service","telco-integration"]),
    dict(name="core-accounts",        port_base=9313,
         services=["account-service","beneficiary-service","multi-currency-accounts","multi-currency-engine","multi-currency-wallet","onboarding-service","open-banking","open-banking-api","settings-service","user-onboarding-enhanced"]),
    dict(name="core-ledger",          port_base=9325,
         services=["chart-of-accounts","core-banking","go-ledger-sync","interest-calculation","ledger-bridge","ledger-integrity-validator","offline-ledger","tigerbeetle-core","tigerbeetle-edge","tigerbeetle-integrated","tigerbeetle-sync","tigerbeetle-zig"]),
    dict(name="core-payments",        port_base=9339,
         services=["bill-payment-gateway","biller-integration","cips-integration","cross-border","currency-conversion","education-payments","fps-integration","global-payment-gateway","instant-reversal-engine","mojaloop-connector","mojaloop-connector-pos","nfc-qr-payments","nfc-tap-to-pay","nibss-integration","papss-integration","payment-corridors-service","payment-gateway-service","payment-hub","payment-processing-service","payment-rails-connectors","payment-split-engine","payout-service","qr-code-service","qr-ticket-verification","sepa-instant","swift-integration","upi-connector","upi-integration","wearable-payments","wise-integration"]),
    dict(name="customer-engagement",  port_base=9371,
         services=["coalition-loyalty","customer-service","gamification","knowledge-base","loyalty-service","promotion-service","rewards-service","shareable-links","support-comms-service","support-crm","support-service"]),
    dict(name="data-lakehouse",       port_base=9384,
         services=["backup-manager","backup-service","data-archival","data-warehouse","dual-write-service","etl-pipeline","falkordb-service","lakehouse-integration","lakehouse-mojaloop","lakehouse-service","ollama-service","postgres-production","sync-manager"]),
    dict(name="dispute-settlement",   port_base=9399,
         services=["dispute-resolution","dispute-service","reconciliation-service","recurring-payments","refund-service","settlement-batch-processor","settlement-gateway","settlement-ledger-sync","settlement-service"]),
    dict(name="ecommerce-marketplace",port_base=9410,
         services=["agent-commerce-integration","agent-ecommerce-platform","agent-store-service","amazon-ebay-integration","amazon-service","ebay-service","ecommerce-cart-rust","ecommerce-catalog-go","ecommerce-intelligence-py","ecommerce-service","gaming-integration","gaming-service","jumia-service","konga-service","marketplace-integration","marketplace-integrations-go","store-map-service","storefront-advertising"]),
    dict(name="fraud-risk",           port_base=9430,
         services=["aml-case-manager-go","aml-monitoring","fraud-detection","fraud-engine","fraud-ml-pipeline","fraud-ml-service","risk-assessment","risk-management","rule-engine","sanctions-batch-rescreener","sanctions-etl","transaction-scoring","tx-monitor-alerter","tx-validator"]),
    dict(name="infra-messaging",      port_base=9446,
         services=["dapr-sidecar","fluvio-consumer","fluvio-producer","fluvio-smartmodule","fluvio-streaming","offline-queue","offline-sync","offline-sync-orchestrator","realtime-services","unified-streaming","websocket-service"]),
    dict(name="infra-network",        port_base=9459,
         services=["adaptive-compression","bandwidth-optimizer","circuit-breaker","connection-multiplexer","connection-quality-monitor","connectivity-resilience","edge-computing","edge-deployment","grpc","hybrid-engine","load-balancer","middleware","middleware-integration","optimization","performance-optimization","platform-middleware","redis-cache-layer","resilience-agent","resilience-proxy","rust-middleware-bridge"]),
    dict(name="infra-observability",  port_base=9481,
         services=["chaos-engineering","distributed-tracing","logging-service","metrics-service","monitoring","monitoring-dashboard","telemetry-aggregator","telemetry-api-gateway","telemetry-collector","telemetry-ingestion"]),
    dict(name="kyc-aml",              port_base=9493,
         services=["background-check","bank-verification","case-management","deepfake-detection","docling-service","document-fraud-detection","document-management","document-processing","kyb-analytics","kyb-engine","kyb-risk-engine","kyb-verification","kyc-document-verifier","kyc-enforcement-go","kyc-enhanced","kyc-event-consumer","kyc-kyb-service","kyc-service","kyc-workflow-orchestration","kyc-workflow-orchestrator","multi-ocr-service","ocr-processing","ocr-service","paddle-ocr-service","rust-ocr-bridge","vlm-document-service"]),
    dict(name="lending-credit",       port_base=9521,
         services=["bnpl-engine","carbon-credit-marketplace","credit-scoring","loan-management","loan-service"]),
    dict(name="open-banking-api",     port_base=9528,
         services=["admin-service","admin-services","api-gateway","api-server-ts","apisix-gateway","developer-portal-service","embedded-finance-anaas","gateway-service","management-api","unified-api","white-label-api"]),
    dict(name="platform-tenant",      port_base=9541,
         services=["config-service","enhanced-platform","enterprise-services","super-app-framework","tenant-management"]),
    dict(name="realtime-transactions",port_base=9548,
         services=["card-service","merchant-service","realtime-fee-splitter","realtime-receipt-engine","receipt-engine","transaction-history","transaction-limits","transaction-queue","transaction-services","webhook-delivery","webhook-service"]),
    dict(name="security",             port_base=9561,
         services=["ddos-shield","ransomware-guard","secuirity-services","security-alert","security-monitoring","security-scanner","security-services"]),
    dict(name="specialized-finance",  port_base=9570,
         services=["blockchain","health-insurance-micro","health-service","insurance-service","investment-service","metaverse-service","pension-micro","stablecoin-defi","stablecoin-integration","stablecoin-rails","stablecoin-v2","tokenized-assets","wealth"]),
    dict(name="supply-chain-govt",    port_base=9585,
         services=["agritech-payments","government-integration","i18n-currency","inventory-management","inventory-service","supply-chain","supply-chain-go"]),
    dict(name="third-party-integrations", port_base=9594,
         services=["additional-services","erpnext-integration","remitly-integration","zapier-integration","zapier-service"]),
    dict(name="workflow-orchestration", port_base=9601,
         services=["compensating-actions","integration-layer","integration-service","integrations","orchestrator-service","scheduler-service","temporal","workflow-integration","workflow-orchestration","workflow-orchestrator","workflow-orchestrator-enhanced","workflow-service"]),
]

# Build flat svc → (group_name, port) map
SVC_MAP = {}
for g in GROUPS:
    for i, svc in enumerate(g['services']):
        SVC_MAP[svc] = (g['name'], g['port_base'] + i)


def svc_to_path(svc_name):
    """
    Derive URL path from service name following core banking convention:
    - Replace underscores with hyphens
    - Strip language suffixes: -py, -go, -rs, -ts
    - Strip -service suffix (only when it won't collide with another service name)
    """
    name = svc_name.replace("_", "-")

    # Strip language suffixes
    for suffix in ("-py", "-go", "-rs", "-ts"):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break

    # Strip -service only when safe (no bare name conflicts with another service)
    if name.endswith("-service"):
        bare = name[:-len("-service")]
        # Only strip if the bare name isn't also a service in SVC_MAP
        if bare not in SVC_MAP and bare.replace("-", "_") not in SVC_MAP:
            name = bare

    return name


def extract_existing_path(route_file):
    """Pull the first path value from an existing route YAML (no full parse needed)."""
    try:
        with open(route_file) as f:
            for line in f:
                m = re.match(r"\s+- (/.+)", line)
                if m:
                    path = m.group(1).rstrip()
                    # strip trailing /* for the prefix
                    return path.rstrip("/*").rstrip("/") or "/"
    except FileNotFoundError:
        pass
    return None


def gen_route(svc_name, group_name, port, path_prefix):
    safe_svc = svc_name.replace("_", "-")
    return f"""# {safe_svc}
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: 54agent-{safe_svc}-route
  namespace: {NAMESPACE}
spec:
  ingressClassName: apisix
  http:
    - name: rule-1
      priority: 10
      match:
        hosts:
          - {HOST}
        paths:
          - /{path_prefix}/*
      backends:
        - serviceName: {group_name}
          servicePort: {port}
      plugins:
        - name: proxy-rewrite
          enable: true
          config:
            regex_uri:
              - "^/{path_prefix}/(.*)"
              - "/$1"
        - name: cors
          enable: true
          config:
            allow_origins: "*"
            allow_methods: "*"
            allow_headers: "*"
            expose_headers: "*"
"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root  = os.path.dirname(os.path.dirname(script_dir))
    routes_dir = os.path.join(repo_root, ROUTES_DIR)

    # ── 1. Delete ALL existing routes (old per-service + 32 consolidated group files) ──
    existing = glob.glob(os.path.join(routes_dir, "*.yaml"))
    for f in existing:
        os.remove(f)
    print(f"Deleted {len(existing)} old route files.\n")

    # ── 2. Generate one route file per service ─────────────────────────────────────────
    written = 0
    for svc, (group_name, port) in sorted(SVC_MAP.items()):
        safe_svc = svc.replace("_", "-")
        out_file = os.path.join(routes_dir, f"{safe_svc}.yaml")

        # Derive path: use computed convention (same as core banking)
        path_prefix = svc_to_path(svc)

        content = gen_route(svc, group_name, port, path_prefix)
        with open(out_file, "w") as f:
            f.write(content)
        written += 1
        print(f"  {safe_svc}.yaml  →  {group_name}:{port}  /{path_prefix}/*")

    total_svcs = sum(len(g['services']) for g in GROUPS)
    print(f"\nDone. Wrote {written}/{total_svcs} route files.")


if __name__ == "__main__":
    main()
