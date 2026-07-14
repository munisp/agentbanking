CREATE TABLE "customer_journey_events" (
	"id" serial PRIMARY KEY NOT NULL,
	"customer_id" text NOT NULL,
	"event_type" text NOT NULL,
	"event_source" text NOT NULL,
	"event_data" text,
	"session_id" text,
	"device_type" text,
	"channel" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "data_export_jobs" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"export_type" text NOT NULL,
	"format" text DEFAULT 'csv' NOT NULL,
	"filters" text,
	"status" text DEFAULT 'pending' NOT NULL,
	"file_url" text,
	"file_size" integer,
	"record_count" integer,
	"requested_by" text NOT NULL,
	"started_at" timestamp,
	"completed_at" timestamp,
	"expires_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "gl_accounts" (
	"id" serial PRIMARY KEY NOT NULL,
	"account_code" text NOT NULL,
	"account_name" text NOT NULL,
	"account_type" text NOT NULL,
	"parent_account_id" integer,
	"currency" text DEFAULT 'NGN' NOT NULL,
	"balance" integer DEFAULT 0 NOT NULL,
	"is_active" boolean DEFAULT true,
	"description" text,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp,
	CONSTRAINT "gl_accounts_account_code_unique" UNIQUE("account_code")
);
--> statement-breakpoint
CREATE TABLE "gl_journal_entries" (
	"id" serial PRIMARY KEY NOT NULL,
	"entry_number" text NOT NULL,
	"description" text NOT NULL,
	"debit_account_id" integer NOT NULL,
	"credit_account_id" integer NOT NULL,
	"amount" integer NOT NULL,
	"currency" text DEFAULT 'NGN' NOT NULL,
	"reference_type" text,
	"reference_id" text,
	"posted_by" text,
	"reversed_entry_id" integer,
	"status" text DEFAULT 'posted' NOT NULL,
	"posted_at" timestamp DEFAULT now(),
	"created_at" timestamp DEFAULT now(),
	CONSTRAINT "gl_journal_entries_entry_number_unique" UNIQUE("entry_number")
);
--> statement-breakpoint
CREATE TABLE "notification_channels" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"channel_type" text NOT NULL,
	"config" text,
	"is_active" boolean DEFAULT true,
	"priority" integer DEFAULT 0,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp
);
--> statement-breakpoint
CREATE TABLE "notification_logs" (
	"id" serial PRIMARY KEY NOT NULL,
	"channel_id" integer,
	"recipient_id" text NOT NULL,
	"recipient_type" text NOT NULL,
	"subject" text,
	"body" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"sent_at" timestamp,
	"delivered_at" timestamp,
	"failure_reason" text,
	"retry_count" integer DEFAULT 0,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "platform_health_checks" (
	"id" serial PRIMARY KEY NOT NULL,
	"service_name" text NOT NULL,
	"check_type" text NOT NULL,
	"status" text DEFAULT 'healthy' NOT NULL,
	"response_time" integer,
	"status_code" integer,
	"message" text,
	"metadata" text,
	"checked_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "platform_incidents" (
	"id" serial PRIMARY KEY NOT NULL,
	"title" text NOT NULL,
	"description" text,
	"severity" text DEFAULT 'medium' NOT NULL,
	"status" text DEFAULT 'open' NOT NULL,
	"affected_services" text,
	"root_cause" text,
	"resolution" text,
	"reported_by" text,
	"assigned_to" text,
	"started_at" timestamp DEFAULT now(),
	"resolved_at" timestamp,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp
);
--> statement-breakpoint
CREATE TABLE "realtime_tx_alerts" (
	"id" serial PRIMARY KEY NOT NULL,
	"transaction_id" text NOT NULL,
	"alert_type" text NOT NULL,
	"severity" text DEFAULT 'medium' NOT NULL,
	"message" text NOT NULL,
	"metadata" text,
	"acknowledged" boolean DEFAULT false,
	"acknowledged_by" text,
	"acknowledged_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "sla_breaches" (
	"id" serial PRIMARY KEY NOT NULL,
	"sla_definition_id" integer NOT NULL,
	"breach_type" text NOT NULL,
	"actual_value" integer NOT NULL,
	"target_value" integer NOT NULL,
	"duration" integer,
	"impact_level" text DEFAULT 'medium' NOT NULL,
	"resolved_at" timestamp,
	"resolution" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "sla_definitions" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"service_type" text NOT NULL,
	"metric_type" text NOT NULL,
	"target_value" integer NOT NULL,
	"warning_threshold" integer,
	"critical_threshold" integer,
	"measurement_window" text DEFAULT '1h' NOT NULL,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp
);
