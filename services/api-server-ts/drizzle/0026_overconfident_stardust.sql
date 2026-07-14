CREATE TYPE "public"."commission_payout_status" AS ENUM('pending', 'approved', 'processing', 'completed', 'failed', 'rejected');--> statement-breakpoint
CREATE TYPE "public"."onboarding_step" AS ENUM('profile', 'kyc', 'float', 'terminal', 'training', 'activated');--> statement-breakpoint
CREATE TYPE "public"."reconciliation_status" AS ENUM('pending', 'matched', 'discrepancy', 'resolved');--> statement-breakpoint
CREATE TYPE "public"."referral_status" AS ENUM('pending', 'activated', 'rewarded', 'expired');--> statement-breakpoint
CREATE TYPE "public"."webhook_delivery_status" AS ENUM('pending', 'delivered', 'failed', 'retrying');--> statement-breakpoint
CREATE TABLE "agent_onboarding_progress" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"agent_code" varchar(32) NOT NULL,
	"current_step" "onboarding_step" DEFAULT 'profile' NOT NULL,
	"profile_complete" boolean DEFAULT false NOT NULL,
	"kyc_complete" boolean DEFAULT false NOT NULL,
	"float_funded" boolean DEFAULT false NOT NULL,
	"terminal_assigned" boolean DEFAULT false NOT NULL,
	"training_complete" boolean DEFAULT false NOT NULL,
	"activated_at" timestamp,
	"notes" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "agent_onboarding_progress_agent_id_unique" UNIQUE("agent_id")
);
--> statement-breakpoint
CREATE TABLE "commission_payouts" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"agent_code" varchar(32) NOT NULL,
	"amount" numeric(18, 2) NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"status" "commission_payout_status" DEFAULT 'pending' NOT NULL,
	"requested_by" integer,
	"approved_by" integer,
	"rejected_by" integer,
	"rejection_reason" text,
	"bank_code" varchar(10),
	"account_number" varchar(20),
	"account_name" varchar(100),
	"nuban_ref" varchar(64),
	"processed_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "referrals" (
	"id" serial PRIMARY KEY NOT NULL,
	"referrer_agent_id" integer NOT NULL,
	"referrer_code" varchar(32) NOT NULL,
	"referral_code" varchar(16) NOT NULL,
	"referee_agent_id" integer,
	"referee_code" varchar(32),
	"status" "referral_status" DEFAULT 'pending' NOT NULL,
	"bonus_points" integer DEFAULT 0 NOT NULL,
	"bonus_cash" numeric(10, 2) DEFAULT '0' NOT NULL,
	"activated_at" timestamp,
	"rewarded_at" timestamp,
	"expires_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "referrals_referral_code_unique" UNIQUE("referral_code")
);
--> statement-breakpoint
CREATE TABLE "settlement_reconciliation" (
	"id" serial PRIMARY KEY NOT NULL,
	"settlement_date" varchar(10) NOT NULL,
	"agent_id" integer,
	"agent_code" varchar(32),
	"expected_amount" numeric(18, 2) NOT NULL,
	"actual_amount" numeric(18, 2) NOT NULL,
	"discrepancy" numeric(18, 2) DEFAULT '0' NOT NULL,
	"status" "reconciliation_status" DEFAULT 'pending' NOT NULL,
	"resolved_by" integer,
	"resolution_note" text,
	"resolved_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "webhook_deliveries" (
	"id" serial PRIMARY KEY NOT NULL,
	"endpoint_id" integer NOT NULL,
	"event_type" varchar(64) NOT NULL,
	"payload" json NOT NULL,
	"status" "webhook_delivery_status" DEFAULT 'pending' NOT NULL,
	"status_code" integer,
	"response_body" text,
	"attempt_count" integer DEFAULT 0 NOT NULL,
	"max_attempts" integer DEFAULT 3 NOT NULL,
	"next_retry_at" timestamp,
	"delivered_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "webhook_endpoints" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(100) NOT NULL,
	"url" text NOT NULL,
	"secret" varchar(64) NOT NULL,
	"events" text[] DEFAULT '{}' NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"tenant_id" integer,
	"created_by" integer,
	"failure_count" integer DEFAULT 0 NOT NULL,
	"last_delivery_at" timestamp,
	"last_status_code" integer,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "agent_onboarding_progress" ADD CONSTRAINT "agent_onboarding_progress_agent_id_agents_id_fk" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "commission_payouts" ADD CONSTRAINT "commission_payouts_agent_id_agents_id_fk" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "referrals" ADD CONSTRAINT "referrals_referrer_agent_id_agents_id_fk" FOREIGN KEY ("referrer_agent_id") REFERENCES "public"."agents"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "referrals" ADD CONSTRAINT "referrals_referee_agent_id_agents_id_fk" FOREIGN KEY ("referee_agent_id") REFERENCES "public"."agents"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "settlement_reconciliation" ADD CONSTRAINT "settlement_reconciliation_agent_id_agents_id_fk" FOREIGN KEY ("agent_id") REFERENCES "public"."agents"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "webhook_deliveries" ADD CONSTRAINT "webhook_deliveries_endpoint_id_webhook_endpoints_id_fk" FOREIGN KEY ("endpoint_id") REFERENCES "public"."webhook_endpoints"("id") ON DELETE no action ON UPDATE no action;