CREATE TYPE "public"."fraud_rule_category" AS ENUM('velocity', 'geofence', 'device_fingerprint', 'amount_anomaly', 'time_of_day', 'blacklist', 'custom');--> statement-breakpoint
CREATE TABLE "fraud_rules" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(128) NOT NULL,
	"category" "fraud_rule_category" NOT NULL,
	"description" text,
	"threshold" numeric(5, 4) DEFAULT '0.7000' NOT NULL,
	"windowSeconds" integer DEFAULT 3600,
	"maxCount" integer DEFAULT 5,
	"enabled" boolean DEFAULT true NOT NULL,
	"hitCount" integer DEFAULT 0 NOT NULL,
	"lastHitAt" timestamp,
	"createdBy" varchar(64),
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "fraud_rules_category_enabled_idx" ON "fraud_rules" USING btree ("category","enabled");