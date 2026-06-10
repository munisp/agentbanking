ALTER TABLE "float_topup_requests" ADD COLUMN "supervisorApprovalRequired" boolean DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE "float_topup_requests" ADD COLUMN "supervisorApprovedBy" varchar(64);--> statement-breakpoint
ALTER TABLE "float_topup_requests" ADD COLUMN "supervisorApprovedAt" timestamp;