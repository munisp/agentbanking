ALTER TABLE "agents" ADD COLUMN "terminalEnabled" boolean DEFAULT true NOT NULL;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "terminalDisabledReason" text;--> statement-breakpoint
ALTER TABLE "fraud_alerts" ADD COLUMN "snoozedUntil" timestamp;--> statement-breakpoint
ALTER TABLE "fraud_alerts" ADD COLUMN "escalatedAt" timestamp;--> statement-breakpoint
ALTER TABLE "fraud_alerts" ADD COLUMN "escalatedTo" varchar(64);