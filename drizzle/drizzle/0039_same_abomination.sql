CREATE TYPE "public"."billing_audit_action" AS ENUM('config_created', 'config_updated', 'config_deleted', 'split_recorded', 'reconciliation_run', 'discrepancy_resolved', 'tenant_billing_provisioned', 'billing_model_changed', 'permission_granted', 'permission_revoked', 'export_generated');--> statement-breakpoint
CREATE TYPE "public"."billing_permission" AS ENUM('view_ledger', 'record_split', 'run_reconciliation', 'manage_billing_config', 'view_dashboard', 'export_data', 'resolve_discrepancy', 'manage_tenant_billing');--> statement-breakpoint
CREATE TYPE "public"."billing_role" AS ENUM('platform_admin', 'billing_admin', 'billing_analyst', 'billing_viewer');--> statement-breakpoint
CREATE TABLE "billing_audit_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"tenant_id" integer NOT NULL,
	"user_id" integer NOT NULL,
	"user_name" varchar(128),
	"action" "billing_audit_action" NOT NULL,
	"resource_type" varchar(64) NOT NULL,
	"resource_id" varchar(128),
	"before_state" json,
	"after_state" json,
	"metadata" json,
	"ip_address" varchar(45),
	"user_agent" varchar(512),
	"session_id" varchar(128),
	"kafka_offset" varchar(64),
	"notification_sent" boolean DEFAULT false,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "billing_provisioning_history" (
	"id" serial PRIMARY KEY NOT NULL,
	"tenant_id" integer NOT NULL,
	"step" varchar(64) NOT NULL,
	"status" varchar(20) DEFAULT 'pending' NOT NULL,
	"details" json,
	"temporal_workflow_id" varchar(128),
	"started_at" timestamp DEFAULT now() NOT NULL,
	"completed_at" timestamp,
	"error" text
);
--> statement-breakpoint
CREATE TABLE "billing_role_assignments" (
	"id" serial PRIMARY KEY NOT NULL,
	"user_id" integer NOT NULL,
	"tenant_id" integer NOT NULL,
	"billing_role" "billing_role" NOT NULL,
	"permissions" json,
	"granted_by" integer NOT NULL,
	"granted_at" timestamp DEFAULT now() NOT NULL,
	"expires_at" timestamp,
	"is_active" boolean DEFAULT true NOT NULL
);
--> statement-breakpoint
CREATE TABLE "tenant_billing_config" (
	"id" serial PRIMARY KEY NOT NULL,
	"tenant_id" integer NOT NULL,
	"billing_model" "billing_model_type" DEFAULT 'revenue_share' NOT NULL,
	"revenue_share_config" json,
	"subscription_config" json,
	"hybrid_config" json,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"effective_date" timestamp DEFAULT now() NOT NULL,
	"contract_end_date" timestamp,
	"auto_renew" boolean DEFAULT true NOT NULL,
	"provisioned_at" timestamp DEFAULT now() NOT NULL,
	"provisioned_by" integer,
	"tigerbeetle_account_id" varchar(64),
	"kafka_topic_prefix" varchar(64),
	"status" varchar(20) DEFAULT 'active' NOT NULL,
	"last_modified_at" timestamp DEFAULT now() NOT NULL,
	"last_modified_by" integer,
	CONSTRAINT "tenant_billing_config_tenant_id_unique" UNIQUE("tenant_id")
);
--> statement-breakpoint
CREATE INDEX "bal_tenant_idx" ON "billing_audit_log" USING btree ("tenant_id");--> statement-breakpoint
CREATE INDEX "bal_user_idx" ON "billing_audit_log" USING btree ("user_id");--> statement-breakpoint
CREATE INDEX "bal_action_idx" ON "billing_audit_log" USING btree ("action");--> statement-breakpoint
CREATE INDEX "bal_resource_idx" ON "billing_audit_log" USING btree ("resource_type","resource_id");--> statement-breakpoint
CREATE INDEX "bal_created_at_idx" ON "billing_audit_log" USING btree ("created_at");--> statement-breakpoint
CREATE INDEX "bph_tenant_idx" ON "billing_provisioning_history" USING btree ("tenant_id");--> statement-breakpoint
CREATE INDEX "bph_step_idx" ON "billing_provisioning_history" USING btree ("step");--> statement-breakpoint
CREATE INDEX "bph_status_idx" ON "billing_provisioning_history" USING btree ("status");--> statement-breakpoint
CREATE INDEX "bra_user_tenant_idx" ON "billing_role_assignments" USING btree ("user_id","tenant_id");--> statement-breakpoint
CREATE INDEX "bra_tenant_idx" ON "billing_role_assignments" USING btree ("tenant_id");--> statement-breakpoint
CREATE INDEX "bra_role_idx" ON "billing_role_assignments" USING btree ("billing_role");--> statement-breakpoint
CREATE UNIQUE INDEX "tbc_tenant_idx" ON "tenant_billing_config" USING btree ("tenant_id");--> statement-breakpoint
CREATE INDEX "tbc_billing_model_idx" ON "tenant_billing_config" USING btree ("billing_model");--> statement-breakpoint
CREATE INDEX "tbc_status_idx" ON "tenant_billing_config" USING btree ("status");