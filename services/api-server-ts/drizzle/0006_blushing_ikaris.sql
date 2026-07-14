ALTER TYPE "public"."tx_status" ADD VALUE 'pending_reversal_approval';--> statement-breakpoint
CREATE TABLE "platform_settings" (
	"id" serial PRIMARY KEY NOT NULL,
	"key" varchar(128) NOT NULL,
	"value" text NOT NULL,
	"description" text,
	"updatedBy" varchar(64),
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "platform_settings_key_unique" UNIQUE("key")
);
--> statement-breakpoint
CREATE TABLE "velocity_limits" (
	"id" serial PRIMARY KEY NOT NULL,
	"tier" "agent_tier" NOT NULL,
	"maxTxPerHour" integer DEFAULT 20 NOT NULL,
	"maxSingleTxAmount" numeric(15, 2) DEFAULT '50000.00' NOT NULL,
	"maxDailyVolume" numeric(15, 2) DEFAULT '500000.00' NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "velocity_limits_tier_unique" UNIQUE("tier")
);
--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "floatLocked" boolean DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "velocityBreached" boolean DEFAULT false;--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "velocityReason" text;--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "approvalRequired" boolean DEFAULT false;--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "approvedBy" varchar(64);--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "approvedAt" timestamp;--> statement-breakpoint
ALTER TABLE "transactions" ADD COLUMN "deviceToken" varchar(64);