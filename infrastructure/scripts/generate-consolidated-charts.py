#!/usr/bin/env python3
"""
Generates 32 consolidated Helm charts and APISIX routes for agent banking.
Run from the repo root:  python3 infrastructure/scripts/generate-consolidated-charts.py
"""

import os, re

REGISTRY      = "registry.digitalocean.com/talentgraph-auth"
NAMESPACE     = "54agent"
HOST          = "54agent.upi.dev"
CHARTS_DIR    = "infrastructure/charts"
ROUTES_DIR    = "infrastructure/apisix-resources/routes"

COMMON_SECRETS = {
    "DATABASE_URL":              "postgresql://doadmin:AVNS_MSy6CW3EGXnA8wJgkLv@db-postgresql-nyc1-18193-do-user-10555812-0.e.db.ondigitalocean.com:25060/link_core_banking",
    "DATABASE_URI":              "postgresql://doadmin:AVNS_MSy6CW3EGXnA8wJgkLv@db-postgresql-nyc1-18193-do-user-10555812-0.e.db.ondigitalocean.com:25060/link_core_banking",
    "DATABASE_POOL_SIZE":        "3",
    "DATABASE_MAX_OVERFLOW":     "2",
    "DATABASE_POOL_TIMEOUT":     "30",
    "DATABASE_POOL_RECYCLE":     "1800",
    "DB_HOST":                   "db-postgresql-nyc1-18193-do-user-10555812-0.e.db.ondigitalocean.com",
    "DB_PORT":                   "25060",
    "DB_NAME":                   "link_core_banking",
    "DB_USER":                   "doadmin",
    "DB_PASSWORD":               "AVNS_MSy6CW3EGXnA8wJgkLv",
    "REDIS_URL":                 "redis-master.redis.svc.cluster.local:6379",
    "REDIS_ADDRESS":             "redis-master.redis.svc.cluster.local:6379",
    "REDIS_HOST":                "redis-master.redis.svc.cluster.local",
    "REDIS_PORT":                "6379",
    "REDIS_PASSWORD":            "3phHSv7qbAuZLb2pi9FWED2X",
    "KAFKA_BROKERS":             "mojaloop-kafka-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092",
    "KAFKA_BOOTSTRAP_SERVERS":   "mojaloop-kafka-cluster-kafka-bootstrap.kafka.svc:9092",
    "KAFKA_SECURITY_PROTOCOL":   "PLAINTEXT",
    "KAFKA_SASL_MECHANISM":      "",
    "KAFKA_SASL_USERNAME":       "",
    "KAFKA_SASL_PASSWORD":       "",
    "FLUVIO_ENDPOINT":           "fluvio:9003",
    "FLUVIO_ADDR":               "fluvio:9003",
    "DAPR_URL":                  "http://localhost:3500",
    "DAPR_HTTP_PORT":            "3500",
    "DAPR_PUBSUB":               "pubsub",
    "DAPR_PUBSUB_NAME":          "pubsub",
    "DAPR_PLACEMENT_ADDRESS":    "dapr-placement:50005",
    "KEYCLOAK_URL":              "https://keycloak.servers.upi.dev",
    "KEYCLOAK_BASE_URL":         "https://keycloak.servers.upi.dev",
    "KEYCLOAK_ADMIN_USERNAME":   "admin",
    "KEYCLOAK_ADMIN_PASSWORD":   "0lQ09=4+Wcpi)DW",
    "DEFAULT_KEYCLOAK_REALM":    "54link",
    "ALLOWED_ORIGINS":           "*",
    "PERMIFY_URL":               "http://permify.permify.svc.cluster.local:3476",
    "PERMIFY_HOST":              "permify.54agent.svc.cluster.local",
    "PERMIFY_PORT":              "3476",
    "TIGERBEETLE_ADDRESS":       "10.233.107.191:3000,10.233.108.26:3000,10.233.108.25:3000",
    "TIGERBEETLE_ADDRESSES":     "10.233.107.191:3000,10.233.108.26:3000,10.233.108.25:3000",
    "TIGERBEETLE_CLUSTER_ID":    "af786bfebbbab6fcb3acd4184e6fe4f4",
    "TB_ADDRESS":                "10.233.107.191:3000,10.233.108.26:3000,10.233.108.25:3000",
    "TB_CLUSTER_ID":             "233240165285264747596733200182526600436",
    "TEMPORAL_ADDRESS":          "temporal-frontend.temporal.svc:7233",
    "TEMPORAL_NAMESPACE":        "54agent-dev",
    "APISIX_ADMIN_URL":          "http://apisix-admin.apisix.svc.cluster.local:9180",
    "OPENSEARCH_URL":            "http://opensearch:9200",
    "AGENT_NAMESPACE":           "54agent",
    "CORE_BANKING_URL":          "https://api.54link.ng",
    "TRPC_API_URL":              "https://api.54link.ng/api/trpc",
    "LOG_PATH":                  "./logs",
    "LOG_LEVEL":                 "info",
    "LOG_SILENT":                "false",
}

# Each group: name, port_base, primary_lang, description, memory_limit (Mi), services list
GROUPS = [
    dict(name="agent-core",           port_base=9100, lang="python", mem=1472,
         desc="Agent core — float, commission, hierarchy, performance, training, BaaS",
         services=["agent-baas","agent-business-dashboard","agent-embedded-finance","agent_embedded_finance","agent-hierarchy-service","agent-liquidity-network","agent-lms","agent-performance","agent-scorecard","agent_scorecard","agent-service","agent-training","agent-training-academy","agent-wallet-transparency","art-agent-service","commission-calculator","commission-service","commission-settlement","float-management","float-service","float-integration-models","hierarchy-engine","hierarchy-service"]),
    dict(name="agent-pos",            port_base=9125, lang="python", mem=1344,
         desc="POS/hardware — MDM, device management, terminals, geofencing, OTA",
         services=["android-native","device-management","firmware-distribution","ios-native","iot-smart-pos","mdm-compliance-engine","mdm-geofence-service","mdm-service","ota-service","pos-fluvio-consumer","pos-geofencing","pos-hardware-management","pos-integration","pos-management","pos-printer","pos-shell-config","pos-terminal-management","power-management","terminal-heartbeat","terminal-ownership","territory-management"]),
    dict(name="ai-ml",                port_base=9148, lang="python", mem=768,
         desc="AI/ML — models, inference, forecasting, GNN, revenue, credit scoring",
         services=["ai-credit-scoring","ai-document-validation","ai-ml-services","ai-orchestration","demand-forecasting-py","gnn-engine","ml-engine","ml-model-registry","ml-pipeline","neural-network-service","python-ml-engine","revenue-forecast-ml"]),
    dict(name="analytics-data",       port_base=9162, lang="python", mem=1216,
         desc="Analytics & data — dashboards, reporting, OpenSearch, CDP, KGQA",
         services=["analytics","analytics-dashboard","analytics-service","analytics-service-ts","business-intelligence","cdp-service","cocoindex-service","connectivity-analytics","customer-analytics","dashboard-service","epr-kgqa-service","opensearch-analytics","opensearch-indexer","projections-targets","reporting-engine","reporting-service","store-analytics-engine","unified-analytics","ussd-analytics"]),
    dict(name="auth-identity",        port_base=9183, lang="go",     mem=1216,
         desc="Identity & auth — Keycloak, MFA, biometric, PBAC, RBAC, face match, liveness",
         services=["auth-service","authentication-service","biometric","deepface-service","digital-identity-layer","face-matching","fido2-service","liveness-detection","mfa","mfa-service","pbac-enforcer","pbac-engine","rbac","rbac-service","service-auth","user-management","user-service","verification-service","verification-ui"]),
    dict(name="billing",              port_base=9204, lang="python", mem=1152,
         desc="Billing — invoicing, commissions, tax, SLA, revenue reconciliation",
         services=["billing-aggregator","billing-analytics-pipeline","billing-anomaly-detector","billing-event-processor","billing-provisioning-workflow","billing-reconciliation-engine","billing-sla-monitor","billing-stream-processor","billing-webhook-dispatcher","fee-splitter-realtime","financial-services","invoice-generator","nigeria-vat-service","payroll-disbursement","revenue-reconciler","sla-billing-reporter","tb-commission-sidecar","tb-sidecar"]),
    dict(name="cbn-regulatory",       port_base=9224, lang="python", mem=768,
         desc="CBN/regulatory — compliance, audit, GDPR, AML reporting, returns",
         services=["audit-chain","audit-service","cbn-compliance-comprehensive","cbn-reporting-engine","cbn-tiered-kyc","compliance","compliance-kyc","compliance-reporting","compliance-service","compliance-workflows","gdpr-service","goaml-integration-go"]),
    dict(name="channels-social",      port_base=9238, lang="python", mem=1024,
         desc="Social channels — WhatsApp, Telegram, social media bots",
         services=["at-sms-sender","at-sms-webhook","discord-service","email-service","google-assistant-service","instagram-service","messenger-service","rcs-service","snapchat-service","telegram-service","tiktok-service","twitter-service","wechat-service","whatsapp-ai-bot","whatsapp-order-service","whatsapp-service"]),
    dict(name="channels-messaging",   port_base=9256, lang="go",     mem=1088,
         desc="Messaging — SMS, push, notifications, translation, omnichannel",
         services=["communication-gateway","communication-hub","communication-service","communication-shared","messaging-service","multilingual-integration-service","notification-service","omnichannel-middleware","push-notification-service","realtime-notification-service","realtime-translation","sms-gateway","sms-service","sms-transaction-bridge","translation-service","unified-communication-hub","unified-communication-service"]),
    dict(name="channels-ussd-voice",  port_base=9275, lang="python", mem=896,
         desc="USSD/voice — IVR, voice AI, USSD sessions, conversational banking",
         services=["at-ussd-handler","at-ussd-session","conversational-banking","ussd-gateway","ussd-localization","ussd-menu-builder","ussd-receipt-printer","ussd-service","ussd-session-cache","ussd-session-replayer","ussd-tx-processor","voice-ai-service","voice-assistant-service","voice-command-nlu"]),
    dict(name="connectivity-sim",     port_base=9291, lang="python", mem=1280,
         desc="SIM/connectivity — carrier management, network ops, satellite, multi-SIM failover",
         services=["airtime-provider-gateway","carrier-billing","carrier-cost-engine","carrier-failover-proxy","carrier-live-api","carrier-performance-reporter","carrier-ranking-engine","carrier-recommendation","carrier-signal-monitor","carrier-sla-monitor","geospatial-service","multi-sim-failover","network-coverage-export","network-diagnostic","network-ml-trainer","network-operations","network-quality-predictor","satellite-connectivity","sim-orchestrator-service","telco-integration"]),
    dict(name="core-accounts",        port_base=9313, lang="go",     mem=640,
         desc="Account management — accounts, multi-currency, onboarding, open banking",
         services=["account-service","beneficiary-service","multi-currency-accounts","multi-currency-engine","multi-currency-wallet","onboarding-service","open-banking","open-banking-api","settings-service","user-onboarding-enhanced"]),
    dict(name="core-ledger",          port_base=9325, lang="rust",   mem=640,
         desc="Ledger — TigerBeetle, chart of accounts, offline ledger, interest",
         services=["chart-of-accounts","core-banking","go-ledger-sync","interest-calculation","ledger-bridge","ledger-integrity-validator","offline-ledger","tigerbeetle-core","tigerbeetle-edge","tigerbeetle-integrated","tigerbeetle-sync","tigerbeetle-zig"]),
    dict(name="core-payments",        port_base=9339, lang="go",     mem=1920,
         desc="Payments — NIBSS, cross-border, NFC, QR, Mojaloop, PAPSS, SWIFT, UPI",
         services=["bill-payment-gateway","biller-integration","cips-integration","cross-border","currency-conversion","education-payments","fps-integration","global-payment-gateway","instant-reversal-engine","mojaloop-connector","mojaloop-connector-pos","nfc-qr-payments","nfc-tap-to-pay","nibss-integration","papss-integration","payment-corridors-service","payment-gateway-service","payment-hub","payment-processing-service","payment-rails-connectors","payment-split-engine","payout-service","qr-code-service","qr-ticket-verification","sepa-instant","swift-integration","upi-connector","upi-integration","wearable-payments","wise-integration"]),
    dict(name="customer-engagement",  port_base=9371, lang="go",     mem=704,
         desc="Customer engagement — CRM, loyalty, gamification, support, rewards",
         services=["coalition-loyalty","customer-service","gamification","knowledge-base","loyalty-service","promotion-service","rewards-service","shareable-links","support-comms-service","support-crm","support-service"]),
    dict(name="data-lakehouse",       port_base=9384, lang="python", mem=832,
         desc="Data & lakehouse — ETL, lakehouse, FalkorDB, Ollama, backups, sync",
         services=["backup-manager","backup-service","data-archival","data-warehouse","dual-write-service","etl-pipeline","falkordb-service","lakehouse-integration","lakehouse-mojaloop","lakehouse-service","ollama-service","postgres-production","sync-manager"]),
    dict(name="dispute-settlement",   port_base=9399, lang="rust",   mem=576,
         desc="Dispute & settlement — reconciliation, reversals, refunds, settlement",
         services=["dispute-resolution","dispute-service","reconciliation-service","recurring-payments","refund-service","settlement-batch-processor","settlement-gateway","settlement-ledger-sync","settlement-service"]),
    dict(name="ecommerce-marketplace",port_base=9410, lang="go",     mem=1152,
         desc="E-commerce & marketplace — Amazon, eBay, Jumia, Konga, storefronts",
         services=["agent-commerce-integration","agent-ecommerce-platform","agent-store-service","amazon-ebay-integration","amazon-service","ebay-service","ecommerce-cart-rust","ecommerce-catalog-go","ecommerce-intelligence-py","ecommerce-service","gaming-integration","gaming-service","jumia-service","konga-service","marketplace-integration","marketplace-integrations-go","store-map-service","storefront-advertising"]),
    dict(name="fraud-risk",           port_base=9430, lang="python", mem=896,
         desc="Fraud & risk — detection, AML, sanctions, scoring, rules engine",
         services=["aml-case-manager-go","aml-monitoring","fraud-detection","fraud-engine","fraud-ml-pipeline","fraud-ml-service","risk-assessment","risk-management","rule-engine","sanctions-batch-rescreener","sanctions-etl","transaction-scoring","tx-monitor-alerter","tx-validator"]),
    dict(name="infra-messaging",      port_base=9446, lang="rust",   mem=704,
         desc="Messaging infra — Fluvio, Dapr, WebSocket, offline sync, event streaming",
         services=["dapr-sidecar","fluvio-consumer","fluvio-producer","fluvio-smartmodule","fluvio-streaming","offline-queue","offline-sync","offline-sync-orchestrator","realtime-services","unified-streaming","websocket-service"]),
    dict(name="infra-network",        port_base=9459, lang="rust",   mem=1280,
         desc="Network infra — circuit breaker, load balancer, gRPC, compression, resilience",
         services=["adaptive-compression","bandwidth-optimizer","circuit-breaker","connection-multiplexer","connection-quality-monitor","connectivity-resilience","edge-computing","edge-deployment","grpc","hybrid-engine","load-balancer","middleware","middleware-integration","optimization","performance-optimization","platform-middleware","redis-cache-layer","resilience-agent","resilience-proxy","rust-middleware-bridge"]),
    dict(name="infra-observability",  port_base=9481, lang="python", mem=640,
         desc="Observability — monitoring, telemetry, tracing, chaos engineering",
         services=["chaos-engineering","distributed-tracing","logging-service","metrics-service","monitoring","monitoring-dashboard","telemetry-aggregator","telemetry-api-gateway","telemetry-collector","telemetry-ingestion"]),
    dict(name="kyc-aml",              port_base=9493, lang="python", mem=1664,
         desc="KYC/AML — document verification, biometric OCR, KYB, sanctions screening",
         services=["background-check","bank-verification","case-management","deepfake-detection","docling-service","document-fraud-detection","document-management","document-processing","kyb-analytics","kyb-engine","kyb-risk-engine","kyb-verification","kyc-document-verifier","kyc-enforcement-go","kyc-enhanced","kyc-event-consumer","kyc-kyb-service","kyc-service","kyc-workflow-orchestration","kyc-workflow-orchestrator","multi-ocr-service","ocr-processing","ocr-service","paddle-ocr-service","rust-ocr-bridge","vlm-document-service"]),
    dict(name="lending-credit",       port_base=9521, lang="python", mem=320,
         desc="Lending & credit — loans, BNPL, credit scoring, carbon credit marketplace",
         services=["bnpl-engine","carbon-credit-marketplace","credit-scoring","loan-management","loan-service"]),
    dict(name="open-banking-api",     port_base=9528, lang="go",     mem=704,
         desc="API platform — gateway, APISIX, developer portal, open banking, white-label",
         services=["admin-service","admin-services","api-gateway","api-server-ts","apisix-gateway","developer-portal-service","embedded-finance-anaas","gateway-service","management-api","unified-api","white-label-api"]),
    dict(name="platform-tenant",      port_base=9541, lang="go",     mem=320,
         desc="Platform & tenant — config, tenant management, enterprise, super-app",
         services=["config-service","enhanced-platform","enterprise-services","super-app-framework","tenant-management"]),
    dict(name="realtime-transactions",port_base=9548, lang="rust",   mem=704,
         desc="Real-time transactions — cards, receipts, webhooks, transaction history",
         services=["card-service","merchant-service","realtime-fee-splitter","realtime-receipt-engine","receipt-engine","transaction-history","transaction-limits","transaction-queue","transaction-services","webhook-delivery","webhook-service"]),
    dict(name="security",             port_base=9561, lang="rust",   mem=448,
         desc="Security — DDoS, ransomware, security scanning, audit",
         services=["ddos-shield","ransomware-guard","secuirity-services","security-alert","security-monitoring","security-scanner","security-services"]),
    dict(name="specialized-finance",  port_base=9570, lang="python", mem=832,
         desc="Specialized finance — insurance, blockchain, stablecoins, wealth, metaverse",
         services=["blockchain","health-insurance-micro","health-service","insurance-service","investment-service","metaverse-service","pension-micro","stablecoin-defi","stablecoin-integration","stablecoin-rails","stablecoin-v2","tokenized-assets","wealth"]),
    dict(name="supply-chain-govt",    port_base=9585, lang="go",     mem=448,
         desc="Supply chain & government — agritech, inventory, government integration",
         services=["agritech-payments","government-integration","i18n-currency","inventory-management","inventory-service","supply-chain","supply-chain-go"]),
    dict(name="third-party-integrations", port_base=9594, lang="python", mem=320,
         desc="Third-party integrations — ERPNext, Remitly, Zapier, additional connectors",
         services=["additional-services","erpnext-integration","remitly-integration","zapier-integration","zapier-service"]),
    dict(name="workflow-orchestration", port_base=9601, lang="go",   mem=768,
         desc="Workflow & orchestration — Temporal, sagas, schedulers, integration layer",
         services=["compensating-actions","integration-layer","integration-service","integrations","orchestrator-service","scheduler-service","temporal","workflow-integration","workflow-orchestration","workflow-orchestrator","workflow-orchestrator-enhanced","workflow-service"]),
]


def svc_to_path(svc_name):
    """Convert service name to URL path prefix (underscores → hyphens)."""
    return svc_name.replace("_", "-")


def helm_name(group_name):
    """Helm template function prefix — matches chart name."""
    return group_name


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {path}")


# ─────────────────────────────────────────────────────────────────────────────
# Helm chart generation
# ─────────────────────────────────────────────────────────────────────────────

def gen_chart_yaml(g):
    return f"""apiVersion: v2
name: {g['name']}
description: 54agent {g['name'].replace('-', ' ').title()} Consolidated Helm Chart
type: application
version: 0.0.1
appVersion: "1.0.0"
"""


def gen_values_yaml(g):
    ports = [g['port_base'] + i for i in range(len(g['services']))]
    ports_yaml = "\n".join(f"    - port: {p}" for p in ports)
    svc_list = ",".join(g['services'])

    secrets_yaml = "\n".join(
        f'  {k}: "{v}"' for k, v in COMMON_SECRETS.items()
    )
    # Group-specific extras
    extras = (
        f'  APP_HOST: "0.0.0.0"\n'
        f'  APP_PORT: "{g["port_base"]}"\n'
        f'  PORT_BASE: "{g["port_base"]}"\n'
        f'  SERVICE_GROUP: {g["name"]}\n'
        f'  SERVICES: "{svc_list}"\n'
    )

    mem_req = max(128, g['mem'] // 4)

    return f"""replicaCount: 1
image:
  repository: {REGISTRY}/54agent-{g['name']}
  pullPolicy: IfNotPresent
  tag: "0.0.1"
nameOverride: ""
fullnameOverride: ""
serviceAccount:
  create: false
  name: {NAMESPACE}
podAnnotations: {{}}
podLabels: {{}}
podSecurityContext: {{}}
securityContext: {{}}
service:
  type: ClusterIP
  ports:
{ports_yaml}
resources:
  requests:
    cpu: 200m
    memory: {mem_req}Mi
  limits:
    ephemeral-storage: 4Gi
    cpu: 1000m
    memory: {g['mem']}Mi
autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 5
  targetCPUUtilizationPercentage: 80
volumes: []
volumeMounts: []
nodeSelector: {{}}
tolerations: []
affinity: {{}}
dapr:
  appId: {g['name']}
  appPort: {g['port_base']}
  enableMetrics: true
  enabled: true
  metricsPort: 9099
  sidecarListenAddresses: "0.0.0.0"
  cpu-request: 100m
  cpu-limit: 300m
  memory-request: 250Mi
  memory-limit: 1000Mi
secrets:
{secrets_yaml}
{extras}"""


def gen_helpers_tpl(g):
    n = g['name']
    return f"""{{{{- define "{n}.name" -}}}}
{{{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{- define "{n}.fullname" -}}}}
{{{{- if .Values.fullnameOverride }}}}
{{{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- $name := default .Chart.Name .Values.nameOverride }}}}
{{{{- if contains $name .Release.Name }}}}
{{{{- .Release.Name | trunc 63 | trimSuffix "-" }}}}
{{{{- else }}}}
{{{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}
{{{{- end }}}}
{{{{- end }}}}

{{{{- define "{n}.chart" -}}}}
{{{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}}}
{{{{- end }}}}

{{{{- define "{n}.labels" -}}}}
helm.sh/chart: {{{{ include "{n}.chart" . }}}}
{{{{ include "{n}.selectorLabels" . }}}}
{{{{- if .Chart.AppVersion }}}}
app.kubernetes.io/version: {{{{ .Chart.AppVersion | quote }}}}
{{{{- end }}}}
app.kubernetes.io/managed-by: {{{{ .Release.Service }}}}
{{{{- end }}}}

{{{{- define "{n}.selectorLabels" -}}}}
app.kubernetes.io/name: {{{{ include "{n}.name" . }}}}
app.kubernetes.io/instance: {{{{ .Release.Name }}}}
{{{{- end }}}}

{{{{- define "{n}.serviceAccountName" -}}}}
{{{{- if .Values.serviceAccount.create }}}}
{{{{- default (include "{n}.fullname" .) .Values.serviceAccount.name }}}}
{{{{- else }}}}
{{{{- default "default" .Values.serviceAccount.name }}}}
{{{{- end }}}}
{{{{- end }}}}
"""


def gen_deployment_yaml(g):
    n = g['name']
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{ include "{n}.fullname" . }}}}
  labels:
    {{{{- include "{n}.labels" . | nindent 4 }}}}
spec:
  {{{{- if not .Values.autoscaling.enabled }}}}
  replicas: {{{{ .Values.replicaCount }}}}
  {{{{- end }}}}
  selector:
    matchLabels:
      {{{{- include "{n}.selectorLabels" . | nindent 6 }}}}
  template:
    metadata:
      annotations:
        dapr.io/app-id: "{{{{ .Values.dapr.appId }}}}"
        dapr.io/app-port: "{{{{ .Values.dapr.appPort }}}}"
        dapr.io/enable-metrics: "{{{{ .Values.dapr.enableMetrics }}}}"
        dapr.io/enabled: "{{{{ .Values.dapr.enabled }}}}"
        dapr.io/metrics-port: "{{{{ .Values.dapr.metricsPort }}}}"
        dapr.io/sidecar-listen-addresses: "{{{{ .Values.dapr.sidecarListenAddresses }}}}"
        dapr.io/log-level: "debug"
        dapr.io/sidecar-cpu-request:    '{{{{ index .Values.dapr "cpu-request" }}}}'
        dapr.io/sidecar-cpu-limit:      '{{{{ index .Values.dapr "cpu-limit" }}}}'
        dapr.io/sidecar-memory-request: '{{{{ index .Values.dapr "memory-request" }}}}'
        dapr.io/sidecar-memory-limit:   '{{{{ index .Values.dapr "memory-limit" }}}}'
      labels:
        {{{{- include "{n}.labels" . | nindent 8 }}}}
        {{{{- with .Values.podLabels }}}}
        {{{{- toYaml . | nindent 8 }}}}
        {{{{- end }}}}
    spec:
      {{{{- with .Values.imagePullSecrets }}}}
      imagePullSecrets:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      serviceAccountName: {{{{ include "{n}.serviceAccountName" . }}}}
      {{{{- with .Values.podSecurityContext }}}}
      securityContext:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      containers:
        - name: {{{{ .Chart.Name }}}}
          {{{{- with .Values.securityContext }}}}
          securityContext:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          image: "{{{{ .Values.image.repository }}}}:{{{{ .Values.image.tag | default .Chart.AppVersion }}}}"
          imagePullPolicy: {{{{ .Values.image.pullPolicy }}}}
          ports:
            {{{{- range .Values.service.ports }}}}
            - name: port-{{{{ .port }}}}
              containerPort: {{{{ .port }}}}
              protocol: TCP
            {{{{- end }}}}
          envFrom:
            - secretRef:
                name: {{{{ include "{n}.fullname" . }}}}-secrets
          {{{{- with .Values.resources }}}}
          resources:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
          {{{{- with .Values.volumeMounts }}}}
          volumeMounts:
            {{{{- toYaml . | nindent 12 }}}}
          {{{{- end }}}}
      {{{{- with .Values.volumes }}}}
      volumes:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.nodeSelector }}}}
      nodeSelector:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.affinity }}}}
      affinity:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
      {{{{- with .Values.tolerations }}}}
      tolerations:
        {{{{- toYaml . | nindent 8 }}}}
      {{{{- end }}}}
"""


def gen_service_yaml(g):
    n = g['name']
    return f"""apiVersion: v1
kind: Service
metadata:
  name: {{{{ include "{n}.fullname" . }}}}
  labels:
    {{{{- include "{n}.labels" . | nindent 4 }}}}
spec:
  type: {{{{ .Values.service.type }}}}
  ports:
    {{{{- range .Values.service.ports }}}}
    - port: {{{{ .port }}}}
      targetPort: {{{{ .port }}}}
      protocol: TCP
      name: port-{{{{ .port }}}}
    {{{{- end }}}}
  selector:
    {{{{- include "{n}.selectorLabels" . | nindent 4 }}}}
"""


def gen_secret_yaml(g):
    n = g['name']
    return f"""apiVersion: v1
kind: Secret
metadata:
  name: {{{{ include "{n}.fullname" . }}}}-secrets
type: Opaque
stringData:
{{{{- range $key, $value := .Values.secrets }}}}
  {{{{ $key }}}}: {{{{ $value | quote }}}}
{{{{- end }}}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# APISIX route generation
# ─────────────────────────────────────────────────────────────────────────────

def gen_apisix_route(g):
    n = g['name']
    route_name = f"54agent-{n}-route"
    svc_count = len(g['services'])

    rules = []
    for i, svc in enumerate(g['services']):
        port = g['port_base'] + i
        path_prefix = svc_to_path(svc)
        rules.append(f"""    - name: rule-{i+1}
      priority: 10
      match:
        hosts:
          - {HOST}
        paths:
          - /{path_prefix}/*
      backends:
        - serviceName: {n}
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
            expose_headers: "*"\n""")

    rules_yaml = "\n".join(rules)

    return f"""# {n} — {svc_count} services | ports {g['port_base']}-{g['port_base']+svc_count-1}
# {g['desc']}
apiVersion: apisix.apache.org/v2
kind: ApisixRoute
metadata:
  name: {route_name}
  namespace: {NAMESPACE}
spec:
  ingressClassName: apisix
  http:
{rules_yaml}"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # Resolve paths relative to repo root (two levels up from this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(os.path.dirname(script_dir))
    charts_root = os.path.join(repo_root, CHARTS_DIR)
    routes_root = os.path.join(repo_root, ROUTES_DIR)

    total_svcs = sum(len(g['services']) for g in GROUPS)
    print(f"Generating {len(GROUPS)} consolidated charts + routes ({total_svcs} services total)\n")

    for g in GROUPS:
        n = g['name']
        print(f"[{n}]  {len(g['services'])} services  ports {g['port_base']}-{g['port_base']+len(g['services'])-1}")

        chart_dir = os.path.join(charts_root, n)
        tmpl_dir  = os.path.join(chart_dir, "templates")

        write(os.path.join(chart_dir, "Chart.yaml"),              gen_chart_yaml(g))
        write(os.path.join(chart_dir, "values.yaml"),             gen_values_yaml(g))
        write(os.path.join(tmpl_dir,  "_helpers.tpl"),            gen_helpers_tpl(g))
        write(os.path.join(tmpl_dir,  "deployment.yaml"),         gen_deployment_yaml(g))
        write(os.path.join(tmpl_dir,  "service.yaml"),            gen_service_yaml(g))
        write(os.path.join(tmpl_dir,  "secret.yaml"),             gen_secret_yaml(g))
        write(os.path.join(routes_root, f"{n}.yaml"),             gen_apisix_route(g))

    print(f"\nDone. Created {len(GROUPS)*7} files ({len(GROUPS)} charts × 6 files + {len(GROUPS)} APISIX routes).")


if __name__ == "__main__":
    main()
