ALTER TABLE "disputes" ADD COLUMN "amount" numeric(15, 2) DEFAULT '0';--> statement-breakpoint
ALTER TABLE "disputes" ADD COLUMN "createdBy" varchar(64);