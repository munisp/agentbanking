CREATE TYPE "public"."email_provider" AS ENUM('sendgrid', 'ses', 'smtp', 'console');--> statement-breakpoint
CREATE TYPE "public"."rate_alert_direction" AS ENUM('above', 'below');--> statement-breakpoint
CREATE TYPE "public"."rate_alert_status" AS ENUM('active', 'paused', 'triggered', 'expired');--> statement-breakpoint
CREATE TABLE "email_delivery_log" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"email_queue_id" integer,
	"provider" "email_provider" NOT NULL,
	"provider_message_id" varchar(128),
	"to_address" varchar(320) NOT NULL,
	"subject" varchar(256) NOT NULL,
	"status" varchar(32) DEFAULT 'sent' NOT NULL,
	"opened_at" timestamp,
	"clicked_at" timestamp,
	"bounced_at" timestamp,
	"error_message" text,
	"metadata" json DEFAULT '{}'::json,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "rate_alerts" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"base_currency" varchar(3) NOT NULL,
	"target_currency" varchar(3) NOT NULL,
	"target_rate" numeric(18, 8) NOT NULL,
	"direction" "rate_alert_direction" NOT NULL,
	"status" "rate_alert_status" DEFAULT 'active' NOT NULL,
	"current_rate" numeric(18, 8),
	"triggered_at" timestamp,
	"notified_via" json DEFAULT '[]'::json,
	"expires_at" timestamp,
	"note" varchar(256),
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "email_delivery_provider_idx" ON "email_delivery_log" USING btree ("provider","created_at");--> statement-breakpoint
CREATE INDEX "email_delivery_queue_id_idx" ON "email_delivery_log" USING btree ("email_queue_id");--> statement-breakpoint
CREATE INDEX "rate_alert_agent_status_idx" ON "rate_alerts" USING btree ("agent_id","status");--> statement-breakpoint
CREATE INDEX "rate_alert_pair_idx" ON "rate_alerts" USING btree ("base_currency","target_currency");