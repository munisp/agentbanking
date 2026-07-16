CREATE TABLE "agent_bank_accounts" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"bank_name" text NOT NULL,
	"bank_code" text NOT NULL,
	"account_number" text NOT NULL,
	"account_name" text NOT NULL,
	"is_default" boolean DEFAULT false,
	"verified" boolean DEFAULT false,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "agent_performance_scores" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"period" text NOT NULL,
	"tx_volume" numeric(15, 2) DEFAULT '0',
	"tx_count" integer DEFAULT 0,
	"commission_earned" numeric(15, 2) DEFAULT '0',
	"customer_count" integer DEFAULT 0,
	"dispute_rate" numeric(5, 4) DEFAULT '0',
	"uptime_percent" numeric(5, 2) DEFAULT '100',
	"overall_score" numeric(5, 2) DEFAULT '0',
	"rank" integer,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "agent_suspension_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"action" text NOT NULL,
	"reason" text NOT NULL,
	"performed_by" integer NOT NULL,
	"previous_status" text,
	"new_status" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "commission_clawbacks" (
	"id" serial PRIMARY KEY NOT NULL,
	"reversal_request_id" integer NOT NULL,
	"agent_id" integer NOT NULL,
	"original_commission" numeric(15, 2) NOT NULL,
	"clawback_amount" numeric(15, 2) NOT NULL,
	"cascade_level" text NOT NULL,
	"status" text DEFAULT 'pending',
	"applied_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "compliance_checks" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer,
	"transaction_id" integer,
	"check_type" text NOT NULL,
	"rule_code" text NOT NULL,
	"result" text NOT NULL,
	"details" text,
	"flagged_amount" numeric(15, 2),
	"reported_to_regulator" boolean DEFAULT false,
	"reported_at" timestamp,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "float_reconciliations" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"date" timestamp NOT NULL,
	"expected_balance" numeric(15, 2) NOT NULL,
	"actual_balance" numeric(15, 2) NOT NULL,
	"discrepancy" numeric(15, 2) NOT NULL,
	"status" text DEFAULT 'pending',
	"resolved_by" integer,
	"resolved_at" timestamp,
	"notes" text,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "geo_fences" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"region_code" text NOT NULL,
	"center_lat" numeric(10, 7) NOT NULL,
	"center_lng" numeric(10, 7) NOT NULL,
	"radius_km" numeric(8, 2) NOT NULL,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "kyc_documents" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"doc_type" text NOT NULL,
	"doc_number" text,
	"doc_url" text,
	"status" text DEFAULT 'pending',
	"verified_by" integer,
	"verified_at" timestamp,
	"rejection_reason" text,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "pnl_reports" (
	"id" serial PRIMARY KEY NOT NULL,
	"period" text NOT NULL,
	"period_type" text NOT NULL,
	"agent_id" integer,
	"region_code" text,
	"total_revenue" numeric(15, 2) DEFAULT '0',
	"total_commission" numeric(15, 2) DEFAULT '0',
	"total_fees" numeric(15, 2) DEFAULT '0',
	"operating_costs" numeric(15, 2) DEFAULT '0',
	"net_margin" numeric(15, 2) DEFAULT '0',
	"tx_count" integer DEFAULT 0,
	"tx_volume" numeric(15, 2) DEFAULT '0',
	"created_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "transaction_limits" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_tier" text NOT NULL,
	"tx_type" text NOT NULL,
	"daily_limit" numeric(15, 2) NOT NULL,
	"monthly_limit" numeric(15, 2) NOT NULL,
	"per_tx_limit" numeric(15, 2) NOT NULL,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
