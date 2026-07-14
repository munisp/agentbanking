ALTER TABLE "webhook_deliveries" ADD COLUMN "subscription_id" integer;--> statement-breakpoint
ALTER TABLE "webhook_deliveries" ADD COLUMN "response_code" integer;--> statement-breakpoint
ALTER TABLE "webhook_deliveries" ADD COLUMN "response_time" integer;--> statement-breakpoint
ALTER TABLE "webhook_deliveries" ADD COLUMN "retry_count" integer DEFAULT 0 NOT NULL;--> statement-breakpoint
ALTER TABLE "webhook_deliveries" ADD COLUMN "updated_at" timestamp;