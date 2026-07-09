ALTER TABLE "devices" ADD COLUMN IF NOT EXISTS "enrollmentToken" varchar(64);--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN IF NOT EXISTS "enrollmentExpiresAt" timestamp;--> statement-breakpoint
ALTER TABLE "disputes" ADD COLUMN IF NOT EXISTS "slaDeadlineAt" timestamp;
