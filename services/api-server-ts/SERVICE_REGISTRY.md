# API Server TS — Service Registry

Migrated from NGApp TypeScript monolith. Production-hardened Express + tRPC server.

## Entry Point
`server/_core/index.ts`

## Architecture
- **Runtime**: Node.js 22 + TypeScript
- **API Layer**: tRPC v11 (type-safe end-to-end)
- **Auth**: Keycloak OIDC + FIDO2/WebAuthn
- **Database**: PostgreSQL via Drizzle ORM
- **Cache**: Redis
- **Events**: Kafka + Fluvio
- **Workflows**: Temporal
- **Ledger**: TigerBeetle
- **Secrets**: HashiCorp Vault
- **Observability**: OpenTelemetry + Prometheus

## Router Modules (477 tRPC routers)

### Core Banking
- transactions.ts — Cash in, cash out, transfer, reversal, history
- agent.ts — Agent profile, performance, onboarding
- agentBanking.ts — Agency banking operations
- settlement.ts — Batch settlement processing
- tigerBeetle.ts — Double-entry ledger operations
- float*.ts — Float management, forecasting, insurance

### Compliance & KYC
- kyc.ts, agentKyc.ts, agentKycDocVault.ts — KYC workflows
- amlScreening.ts — AML transaction monitoring
- complianceReporting.ts — CBN/regulatory reporting
- gdpr.ts — GDPR compliance

### Agent Management
- agentManagement.ts, agentOnboarding*.ts — Agent lifecycle
- agentHierarchy*.ts, agentTerritory*.ts — Hierarchy & territory
- agentPerformance*.ts, agentScorecard.ts — Scorecards
- agentCommissionCalc.ts, commissionEngine.ts — Commission calculation

### Payments & Channels
- fxRates.ts, multiCurrency.ts — FX and multi-currency
- ussd*.ts — USSD gateway & analytics
- whatsappChannel.ts — WhatsApp payments
- nfcTapToPay.ts, wearablePayments.ts — Tap-to-pay
- stablecoinRails.ts — Stablecoin support
- crossBorderRemittanceHub.ts — International transfers

### Fraud & Security
- fraud.ts, fraudMlScoringEngine.ts — ML fraud scoring
- fraudRealtimeViz.ts — Real-time fraud visualization
- ransomwareAlerts.ts — Security monitoring
- biometricAuth.ts, biometricAuthGateway.ts — Biometric auth

### Notifications
- emailNotifications.ts, smsNotifications.ts
- pushNotifications.ts, webhookNotifications.ts
- notificationInbox.ts, multiChannelNotificationHub.ts

### Analytics & Reporting
- analytics.ts, analyticsDashboard.ts
- lakehouse.ts, advancedBiReporting.ts
- scheduledReports.ts, reportBuilderTemplates.ts

### Infrastructure
- mdm.ts — Mobile Device Management
- simOrchestrator.ts — SIM failover
- mqttBridge.ts — IoT/POS MQTT
- kafkaConsumer.ts — Event stream
- temporalWorkflows.ts — Workflow orchestration
- vaultSecrets.ts — Secret management

## Database Schema
`drizzle/` — 87 migration files, complete schema

## Key Dependencies
See package.json for full dependency list.
