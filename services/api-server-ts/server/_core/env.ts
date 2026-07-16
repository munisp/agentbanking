/**
 * env.ts — Centralised environment variable registry
 * Every env var consumed by the server MUST be declared here.
 * All values have safe defaults so the server starts without any .env file.
 * Production deployments override these via the platform Secrets panel.
 *
 * Default URLs follow the 54agent Docker Compose service name convention:
 *   http://<service>:<port>  — internal Docker network (production default)
 *   https://<service>.54agent.io  — public-facing microservices
 *   https://api.54agent.io        — APISix gateway
 *   https://auth.54agent.io       — Keycloak OIDC
 *   mqtt://broker.54agent.io:1883 — MQTT broker (TLS: 8883)
 */
export const ENV = {
  // ── Manus Platform ──────────────────────────────────────────────────────────
  appId: process.env.VITE_APP_ID ?? "",
  cookieSecret: process.env.JWT_SECRET ?? "",
  databaseUrl: process.env.DATABASE_URL ?? "",
  postgresUrl: process.env.POSTGRES_URL ?? "",
  isProduction: process.env.NODE_ENV === "production",
  port: parseInt(process.env.PORT ?? "3000", 10),
  apiVersion: process.env.API_VERSION ?? "1.0.0",

  // ── Notification (self-hosted SMTP + webhook) ─────────────────────────────
  // Set SMTP_HOST + NOTIFY_EMAIL for email delivery.
  // Set NOTIFY_WEBHOOK_URL for Slack/Discord/custom webhook delivery.
  smtpHost: process.env.SMTP_HOST ?? "",
  smtpPort: process.env.SMTP_PORT ?? "587",
  smtpUser: process.env.SMTP_USER ?? "",
  smtpPass: process.env.SMTP_PASS ?? "",
  smtpSecure: process.env.SMTP_SECURE ?? "false",
  notifyEmail: process.env.NOTIFY_EMAIL ?? "",
  notifyWebhookUrl: process.env.NOTIFY_WEBHOOK_URL ?? "",

  // ── S3/MinIO file storage ─────────────────────────────────────────────────
  s3Endpoint: process.env.S3_ENDPOINT ?? "http://minio:9000",
  s3Bucket: process.env.S3_BUCKET ?? "54link-storage",
  s3AccessKey: process.env.S3_ACCESS_KEY ?? "",
  s3SecretKey: process.env.S3_SECRET_KEY ?? "",
  s3PublicUrl: process.env.S3_PUBLIC_URL ?? "",

  // ── Geocoding ─────────────────────────────────────────────────────────────
  // Default: OpenStreetMap Nominatim (free, no key required).
  // Set GEOCODING_PROVIDER=google and GEOCODING_API_KEY for paid providers.
  geocodingProvider: process.env.GEOCODING_PROVIDER ?? "nominatim",
  geocodingApiKey: process.env.GEOCODING_API_KEY ?? "",

  // ── AI / LLM (OpenAI-compatible) ──────────────────────────────────────────
  // Used by imageGeneration.ts, voiceTranscription.ts, and llm.ts.
  openaiApiKey: process.env.OPENAI_API_KEY ?? "",
  openaiApiBase: process.env.OPENAI_API_BASE ?? "https://api.openai.com/v1",
  imageGenModel: process.env.IMAGE_GEN_MODEL ?? "dall-e-3",

  // ── Redis ───────────────────────────────────────────────────────────────────
  redisUrl: process.env.REDIS_URL ?? "redis://redis:6379",

  // ── Kafka ───────────────────────────────────────────────────────────────────
  kafkaBrokers: process.env.KAFKA_BROKERS ?? "kafka:9092",
  kafkaClientId: process.env.KAFKA_CLIENT_ID ?? "pos-shell",
  kafkaEnabled: process.env.KAFKA_ENABLED ?? "false",
  kafkaSsl: process.env.KAFKA_SSL ?? "false",
  kafkaSaslUsername: process.env.KAFKA_SASL_USERNAME ?? "",
  kafkaSaslPassword: process.env.KAFKA_SASL_PASSWORD ?? "",

  // ── TigerBeetle sidecar ─────────────────────────────────────────────────────
  tbSidecarUrl: process.env.TB_SIDECAR_URL ?? "http://tigerbeetle-sidecar:8080",

  // ── Platform APISix gateway ─────────────────────────────────────────────────
  platformBaseUrl: process.env.PLATFORM_BASE_URL ?? "http://apisix:9080",
  platformApiKey: process.env.PLATFORM_API_KEY ?? "54agent-platform-dev-api-key",
  platformServiceToken:
    process.env.PLATFORM_SERVICE_TOKEN ?? "54agent-service-token-dev",

  // ── Keycloak OIDC ───────────────────────────────────────────────────────────
  keycloakUrl: process.env.KEYCLOAK_URL ?? "http://keycloak:8080",
  keycloakRealm: process.env.KEYCLOAK_REALM ?? "54agent",
  keycloakClientId: process.env.KEYCLOAK_CLIENT_ID ?? "pos-shell",
  keycloakClientSecret:
    process.env.KEYCLOAK_CLIENT_SECRET ?? "54agent-keycloak-dev-secret",

  // ── Temporal workflow engine ─────────────────────────────────────────────────
  temporalAddress: process.env.TEMPORAL_ADDRESS ?? "temporal:7233",
  temporalNamespace: process.env.TEMPORAL_NAMESPACE ?? "54agent-production",
  temporalTaskQueue: process.env.TEMPORAL_TASK_QUEUE ?? "settlement-queue",

  // ── HashiCorp Vault ──────────────────────────────────────────────────────────
  vaultAddr: process.env.VAULT_ADDR ?? "http://vault:8200",
  vaultRoleId: process.env.VAULT_ROLE_ID ?? "",
  vaultSecretId: process.env.VAULT_SECRET_ID ?? "",
  vaultSecretPath:
    process.env.VAULT_SECRET_PATH ?? "secret/data/pos-shell-demo",

  // ── Permify authorization service ───────────────────────────────────────────
  permifyUrl: process.env.PERMIFY_URL ?? "http://permify:3476",
  permifyTenantId: process.env.PERMIFY_TENANT_ID ?? "t1",

  // ── MinIO / Lakehouse ────────────────────────────────────────────────────────
  minioEndpoint: process.env.MINIO_ENDPOINT ?? "http://minio:9000",
  minioAccessKey: process.env.MINIO_ACCESS_KEY ?? "54agent_admin",
  minioSecretKey: process.env.MINIO_SECRET_KEY ?? "54agent_minio_dev_secret",
  minioBucket: process.env.MINIO_BUCKET ?? "54agent-screenshots",

  // ── APISix gateway admin API ────────────────────────────────────────────────
  apisixAdminUrl: process.env.APISIX_ADMIN_URL ?? "http://apisix:9180",
  apisixAdminKey: process.env.APISIX_ADMIN_KEY ?? "54agent-apisix-dev-admin-key",

  // ── MDM microservices ────────────────────────────────────────────────────────
  mdmComplianceEngineUrl:
    process.env.MDM_COMPLIANCE_ENGINE_URL ??
    "http://mdm-compliance-engine:8091",
  mdmGeofenceServiceUrl:
    process.env.MDM_GEOFENCE_SERVICE_URL ?? "http://mdm-geofence-service:8092",

  // ── Resilience / offline sub-services ──────────────────────────────────────
  resilienceAgentUrl:
    process.env.RESILIENCE_AGENT_URL ?? "https://resilience.54agent.io",
  offlineQueueUrl: process.env.OFFLINE_QUEUE_URL ?? "https://queue.54agent.io",
  analyticsServiceUrl:
    process.env.ANALYTICS_SERVICE_URL ?? "https://analytics.54agent.io",

  // ── POS Printer sidecar (Rust ESC/POS service) ──────────────────────────────
  posPrinterUrl: process.env.POS_PRINTER_URL ?? "http://pos-printer:8085",

  // ── mTLS ────────────────────────────────────────────────────────────────────
  mtlsEnabled: (process.env.MTLS_ENABLED ?? "false") === "true",
  mtlsCertDir: process.env.MTLS_CERT_DIR ?? "/etc/54agent/certs",

  // ── OpenTelemetry ───────────────────────────────────────────────────────────
  otelEndpoint:
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://otel-collector:4318",
  otelServiceName: process.env.OTEL_SERVICE_NAME ?? "pos-shell",
  otelServiceVersion: process.env.OTEL_SERVICE_VERSION ?? "1.0.0",

  // ── Termii SMS / OTP ────────────────────────────────────────────────────────
  // Override TERMII_API_KEY in production Secrets panel.
  termiiApiKey: process.env.TERMII_API_KEY ?? "TLtest_54agent_dev_key",

  // ── Web Push (VAPID) ────────────────────────────────────────────────────────
  // These are dev/demo VAPID keys — override via VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY in production.
  vapidPublicKey:
    process.env.VAPID_PUBLIC_KEY ??
    "BE4Tbbh5r0IGPRlQ_0ePL0AEJfiWJynWxxM0UDmffgbenp87U4upzpn0aNysgCVQdT8IUfNSG3Dx6_k2Wn6lRgA",
  vapidPrivateKey:
    process.env.VAPID_PRIVATE_KEY ??
    "vBqalBipE6mu4a592N8c1wucdpun-RaKemy8gZDa99M",
  vapidSubject: process.env.VAPID_SUBJECT ?? "mailto:admin@54agent.io",

  // ── Platform microservice URLs (override per deployment) ───────────────────
  PLATFORM_KYC_URL: process.env.PLATFORM_KYC_URL ?? "http://kyc-service:8070",
  PLATFORM_VIDEO_KYC_URL:
    process.env.PLATFORM_VIDEO_KYC_URL ?? "http://video-kyc-service:8071",
  PLATFORM_FRAUD_URL:
    process.env.PLATFORM_FRAUD_URL ?? "http://fraud-engine:8072",
  PLATFORM_SETTLEMENT_URL:
    process.env.PLATFORM_SETTLEMENT_URL ?? "http://settlement-service:8073",
  PLATFORM_GEOFENCING_URL:
    process.env.PLATFORM_GEOFENCING_URL ?? "http://mdm-geofence-service:8092",
  PLATFORM_LOYALTY_URL:
    process.env.PLATFORM_LOYALTY_URL ?? "http://loyalty-service:8074",
  PLATFORM_FLOAT_URL:
    process.env.PLATFORM_FLOAT_URL ?? "http://float-manager:8075",
  PLATFORM_DISPUTE_URL:
    process.env.PLATFORM_DISPUTE_URL ?? "http://dispute-service:8076",
  PLATFORM_ANALYTICS_URL:
    process.env.PLATFORM_ANALYTICS_URL ?? "http://analytics-service:8077",
  PLATFORM_NOTIFICATION_URL:
    process.env.PLATFORM_NOTIFICATION_URL ?? "http://notification-service:8078",

  // ── Fluvio streaming cluster ─────────────────────────────────────────────────
  fluvioEndpoint: process.env.FLUVIO_ENDPOINT ?? "http://fluvio:9003",
  fluvioApiKey: process.env.FLUVIO_API_KEY ?? "54agent-fluvio-dev-key",

  // ── MQTT broker (InfinyOn MQTT Source Connector) ─────────────────────────────
  mqttBrokerUrl: process.env.MQTT_BROKER_URL ?? "mqtt://mosquitto:1883",
  mqttClientId: process.env.MQTT_CLIENT_ID ?? "54agent-fluvio-bridge",
  mqttUsername: process.env.MQTT_USERNAME ?? "54agent_mqtt",
  mqttPassword: process.env.MQTT_PASSWORD ?? "54agent_mqtt_dev_pass",

  // ── S3 presigned URL signing ─────────────────────────────────────────────────
  s3Region: process.env.S3_REGION ?? "us-east-1",
  s3PresignExpiry: parseInt(
    process.env.S3_PRESIGN_EXPIRY_SECONDS ?? "3600",
    10
  ),

  // ── Internal security ────────────────────────────────────────────────────────
  // CRON_SECRET: shared secret for internal cron/scheduler → API calls.
  // INTERNAL_API_KEY: service-to-service auth header (X-Internal-Key).
  // Both are validated at startup by envValidation.ts — no hardcoded fallbacks.
  cronSecret: process.env.CRON_SECRET ?? "",
  internalApiKey: process.env.INTERNAL_API_KEY ?? "",
};
