CREATE TYPE "public"."loan_status" AS ENUM('pending', 'approved', 'disbursed', 'repaying', 'completed', 'defaulted', 'rejected');--> statement-breakpoint
CREATE TABLE "agent_achievements" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"achievement_type" text NOT NULL,
	"title" text NOT NULL,
	"description" text,
	"badge_icon" text,
	"points" integer DEFAULT 0,
	"level" integer DEFAULT 1,
	"unlocked_at" timestamp DEFAULT now(),
	"metadata" text
);
--> statement-breakpoint
CREATE TABLE "agent_badges" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"icon" text NOT NULL,
	"category" text NOT NULL,
	"requirement" text NOT NULL,
	"points_value" integer DEFAULT 0,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "agent_loans" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"loan_type" text NOT NULL,
	"principal_amount" numeric(15, 2) NOT NULL,
	"interest_rate" numeric(5, 2) NOT NULL,
	"tenor_days" integer NOT NULL,
	"total_repayable" numeric(15, 2) NOT NULL,
	"amount_repaid" numeric(15, 2) DEFAULT '0',
	"status" "loan_status" DEFAULT 'pending' NOT NULL,
	"disbursed_at" timestamp,
	"due_date" timestamp,
	"approved_by" integer,
	"credit_score" integer,
	"collateral_type" text,
	"collateral_value" numeric(15, 2),
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "analytics_dashboards" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"owner_id" integer NOT NULL,
	"is_public" boolean DEFAULT false,
	"layout" text,
	"filters" text,
	"refresh_interval" integer DEFAULT 300,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "backup_snapshots" (
	"id" serial PRIMARY KEY NOT NULL,
	"snapshot_type" text NOT NULL,
	"status" text DEFAULT 'in_progress' NOT NULL,
	"size_bytes" integer,
	"storage_url" text,
	"tables_included" integer,
	"rows_backed_up" integer,
	"duration_ms" integer,
	"rto_minutes" integer,
	"rpo_minutes" integer,
	"triggered_by" text NOT NULL,
	"completed_at" timestamp,
	"expires_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "bi_report_definitions" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"report_type" text NOT NULL,
	"data_source" text NOT NULL,
	"query" text,
	"schedule" text,
	"recipients" text,
	"last_run_at" timestamp,
	"is_active" boolean DEFAULT true,
	"created_by" integer,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "compliance_filings" (
	"id" serial PRIMARY KEY NOT NULL,
	"filing_type" text NOT NULL,
	"reference_number" text NOT NULL,
	"status" text DEFAULT 'draft' NOT NULL,
	"reporting_period" text,
	"submitted_to" text,
	"submitted_at" timestamp,
	"acknowledged_at" timestamp,
	"total_transactions" integer DEFAULT 0,
	"total_amount" numeric(15, 2),
	"flagged_count" integer DEFAULT 0,
	"filing_data" text,
	"prepared_by" integer,
	"reviewed_by" integer,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "customer_journey_steps" (
	"id" serial PRIMARY KEY NOT NULL,
	"customer_id" integer NOT NULL,
	"step_type" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"completed_at" timestamp,
	"metadata" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "data_consent_records" (
	"id" serial PRIMARY KEY NOT NULL,
	"entity_type" text NOT NULL,
	"entity_id" integer NOT NULL,
	"consent_type" text NOT NULL,
	"granted" boolean NOT NULL,
	"granted_at" timestamp,
	"revoked_at" timestamp,
	"ip_address" text,
	"user_agent" text,
	"version" integer DEFAULT 1,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "encrypted_fields" (
	"id" serial PRIMARY KEY NOT NULL,
	"table_name" text NOT NULL,
	"field_name" text NOT NULL,
	"encryption_key_id" text NOT NULL,
	"algorithm" text DEFAULT 'AES-256-GCM' NOT NULL,
	"last_rotated_at" timestamp,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "fee_audit_trail" (
	"id" serial PRIMARY KEY NOT NULL,
	"transaction_id" integer,
	"fee_rule_id" integer,
	"tx_amount" numeric(15, 2) NOT NULL,
	"calculated_fee" numeric(15, 2) NOT NULL,
	"applied_fee" numeric(15, 2) NOT NULL,
	"waiver_applied" boolean DEFAULT false,
	"waiver_reason" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "fee_rules" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"tx_type" text NOT NULL,
	"agent_tier" text,
	"min_amount" numeric(15, 2) DEFAULT '0',
	"max_amount" numeric(15, 2),
	"fee_type" text NOT NULL,
	"fee_value" numeric(10, 4) NOT NULL,
	"min_fee" numeric(15, 2),
	"max_fee" numeric(15, 2),
	"is_promotional" boolean DEFAULT false,
	"promo_start_date" timestamp,
	"promo_end_date" timestamp,
	"is_active" boolean DEFAULT true,
	"priority" integer DEFAULT 0,
	"created_by" integer,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "fraud_ml_scores" (
	"id" serial PRIMARY KEY NOT NULL,
	"transaction_id" integer,
	"agent_id" integer,
	"risk_score" numeric(5, 2) NOT NULL,
	"model_version" text NOT NULL,
	"features" text,
	"prediction" text NOT NULL,
	"confidence" numeric(5, 4),
	"false_positive" boolean DEFAULT false,
	"reviewed_by" integer,
	"reviewed_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "gl_entries" (
	"id" serial PRIMARY KEY NOT NULL,
	"account_code" text NOT NULL,
	"account_name" text NOT NULL,
	"entry_type" text NOT NULL,
	"amount" numeric(15, 2) NOT NULL,
	"currency" text DEFAULT 'NGN' NOT NULL,
	"reference" text NOT NULL,
	"description" text,
	"period_date" timestamp NOT NULL,
	"posted_by" integer,
	"is_reversed" boolean DEFAULT false,
	"reversal_ref" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "merchant_kyc_docs" (
	"id" serial PRIMARY KEY NOT NULL,
	"merchant_id" integer NOT NULL,
	"doc_type" text NOT NULL,
	"doc_url" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"verified_by" integer,
	"verified_at" timestamp,
	"rejection_reason" text,
	"expires_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "merchant_payouts" (
	"id" serial PRIMARY KEY NOT NULL,
	"merchant_id" integer NOT NULL,
	"amount" numeric(15, 2) NOT NULL,
	"currency" text DEFAULT 'NGN' NOT NULL,
	"bank_code" text NOT NULL,
	"account_number" text NOT NULL,
	"account_name" text NOT NULL,
	"reference" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"processed_at" timestamp,
	"failure_reason" text,
	"period_start" timestamp NOT NULL,
	"period_end" timestamp NOT NULL,
	"tx_count" integer DEFAULT 0,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "notification_dispatch_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"recipient_id" integer,
	"recipient_type" text NOT NULL,
	"channel" text NOT NULL,
	"template_id" text,
	"subject" text,
	"body" text NOT NULL,
	"status" text DEFAULT 'queued' NOT NULL,
	"external_id" text,
	"retry_count" integer DEFAULT 0,
	"max_retries" integer DEFAULT 3,
	"next_retry_at" timestamp,
	"delivered_at" timestamp,
	"failure_reason" text,
	"metadata" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "observability_alerts" (
	"id" serial PRIMARY KEY NOT NULL,
	"alert_name" text NOT NULL,
	"service" text NOT NULL,
	"severity" text NOT NULL,
	"metric" text NOT NULL,
	"threshold" numeric(10, 2) NOT NULL,
	"current_value" numeric(10, 2),
	"status" text DEFAULT 'firing' NOT NULL,
	"acknowledged_by" integer,
	"acknowledged_at" timestamp,
	"resolved_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "rate_limit_rules" (
	"id" serial PRIMARY KEY NOT NULL,
	"endpoint" text NOT NULL,
	"method" text DEFAULT '*' NOT NULL,
	"max_requests" integer NOT NULL,
	"window_seconds" integer NOT NULL,
	"burst_limit" integer,
	"scope" text DEFAULT 'global' NOT NULL,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "reconciliation_batches" (
	"id" serial PRIMARY KEY NOT NULL,
	"batch_reference" text NOT NULL,
	"source_type" text NOT NULL,
	"file_name" text,
	"file_url" text,
	"total_records" integer DEFAULT 0,
	"matched_count" integer DEFAULT 0,
	"unmatched_count" integer DEFAULT 0,
	"discrepancy_count" integer DEFAULT 0,
	"total_amount" numeric(15, 2),
	"status" text DEFAULT 'pending' NOT NULL,
	"processed_by" integer,
	"processed_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "reconciliation_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"batch_id" integer NOT NULL,
	"external_ref" text NOT NULL,
	"internal_ref" text,
	"external_amount" numeric(15, 2) NOT NULL,
	"internal_amount" numeric(15, 2),
	"discrepancy" numeric(15, 2),
	"match_status" text NOT NULL,
	"resolution" text,
	"resolved_by" integer,
	"resolved_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "tenant_feature_toggles" (
	"id" serial PRIMARY KEY NOT NULL,
	"tenant_id" integer NOT NULL,
	"feature_key" text NOT NULL,
	"enabled" boolean DEFAULT false,
	"config" text,
	"enabled_by" integer,
	"enabled_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "training_courses" (
	"id" serial PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"description" text,
	"category" text NOT NULL,
	"content_type" text NOT NULL,
	"content_url" text,
	"duration_minutes" integer,
	"passing_score" integer DEFAULT 70,
	"is_mandatory" boolean DEFAULT false,
	"is_active" boolean DEFAULT true,
	"version" integer DEFAULT 1,
	"created_by" integer,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "training_enrollments" (
	"id" serial PRIMARY KEY NOT NULL,
	"course_id" integer NOT NULL,
	"agent_id" integer NOT NULL,
	"status" text DEFAULT 'enrolled' NOT NULL,
	"progress" integer DEFAULT 0,
	"score" integer,
	"started_at" timestamp,
	"completed_at" timestamp,
	"certificate_url" text,
	"expires_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "tx_monitoring_alerts" (
	"id" serial PRIMARY KEY NOT NULL,
	"transaction_id" integer,
	"alert_type" text NOT NULL,
	"severity" text NOT NULL,
	"description" text NOT NULL,
	"risk_score" numeric(5, 2),
	"agent_id" integer,
	"resolved" boolean DEFAULT false,
	"resolved_by" integer,
	"resolved_at" timestamp,
	"metadata" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "workflow_definitions" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"description" text,
	"category" text NOT NULL,
	"steps" text NOT NULL,
	"sla_hours" integer,
	"escalation_rules" text,
	"is_active" boolean DEFAULT true,
	"version" integer DEFAULT 1,
	"created_by" integer,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "workflow_instances" (
	"id" serial PRIMARY KEY NOT NULL,
	"definition_id" integer NOT NULL,
	"entity_type" text NOT NULL,
	"entity_id" integer NOT NULL,
	"current_step" integer DEFAULT 0,
	"status" text DEFAULT 'active' NOT NULL,
	"assigned_to" integer,
	"started_at" timestamp DEFAULT now(),
	"completed_at" timestamp,
	"sla_deadline" timestamp,
	"step_history" text,
	"created_at" timestamp DEFAULT now()
);
