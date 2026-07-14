CREATE TABLE "analytics_metrics" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"metricName" varchar(128) NOT NULL,
	"value" numeric(20, 4) NOT NULL,
	"bucketMinute" timestamp NOT NULL,
	"tags" json DEFAULT '{}'::json,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "erp_sync_log" ADD COLUMN "retryCount" integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE "erp_sync_log" ADD COLUMN "maxRetries" integer DEFAULT 5 NOT NULL;--> statement-breakpoint
ALTER TABLE "erp_sync_log" ADD COLUMN "nextRetryAt" timestamp;