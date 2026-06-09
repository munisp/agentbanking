CREATE TABLE "commission_audit_trail" (
	"id" serial PRIMARY KEY NOT NULL,
	"entity_type" varchar(32) NOT NULL,
	"entity_id" varchar(32) NOT NULL,
	"action" varchar(32) NOT NULL,
	"previous_value" json,
	"new_value" json,
	"performed_by" varchar(64) NOT NULL,
	"reason" text,
	"ip_address" varchar(45),
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "commission_splits" (
	"id" serial PRIMARY KEY NOT NULL,
	"split_id" varchar(16) NOT NULL,
	"transaction_type" varchar(32) NOT NULL,
	"super_agent_share" numeric(5, 2) NOT NULL,
	"master_agent_share" numeric(5, 2) NOT NULL,
	"agent_share" numeric(5, 2) NOT NULL,
	"sub_agent_share" numeric(5, 2) NOT NULL,
	"platform_share" numeric(5, 2) NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"effective_from" timestamp DEFAULT now() NOT NULL,
	"effective_to" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "commission_splits_split_id_unique" UNIQUE("split_id")
);
--> statement-breakpoint
CREATE TABLE "commission_tiers" (
	"id" serial PRIMARY KEY NOT NULL,
	"tier_id" varchar(16) NOT NULL,
	"name" varchar(128) NOT NULL,
	"transaction_type" varchar(32) NOT NULL,
	"min_volume" numeric(15, 2) DEFAULT '0' NOT NULL,
	"max_volume" numeric(15, 2) DEFAULT '999999999' NOT NULL,
	"rate" numeric(8, 4) NOT NULL,
	"flat_fee" numeric(10, 2) DEFAULT '0' NOT NULL,
	"bonus_rate" numeric(8, 4) DEFAULT '0' NOT NULL,
	"agent_role" varchar(32) DEFAULT 'agent' NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"effective_from" timestamp DEFAULT now() NOT NULL,
	"effective_to" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "commission_tiers_tier_id_unique" UNIQUE("tier_id")
);
--> statement-breakpoint
CREATE TABLE "dispute_evidence" (
	"id" serial PRIMARY KEY NOT NULL,
	"dispute_id" integer NOT NULL,
	"file_name" varchar(256) NOT NULL,
	"file_url" text NOT NULL,
	"file_key" varchar(256) NOT NULL,
	"mime_type" varchar(64),
	"file_size" integer,
	"uploaded_by" varchar(64) NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "cat_entity_idx" ON "commission_audit_trail" USING btree ("entity_type","entity_id");--> statement-breakpoint
CREATE INDEX "cat_action_idx" ON "commission_audit_trail" USING btree ("action");--> statement-breakpoint
CREATE INDEX "cat_created_at_idx" ON "commission_audit_trail" USING btree ("created_at");--> statement-breakpoint
CREATE INDEX "cs_transaction_type_idx" ON "commission_splits" USING btree ("transaction_type");--> statement-breakpoint
CREATE INDEX "cs_is_active_idx" ON "commission_splits" USING btree ("is_active");--> statement-breakpoint
CREATE INDEX "ct_transaction_type_idx" ON "commission_tiers" USING btree ("transaction_type");--> statement-breakpoint
CREATE INDEX "ct_is_active_idx" ON "commission_tiers" USING btree ("is_active");