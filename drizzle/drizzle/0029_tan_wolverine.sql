CREATE TABLE "refunds" (
	"id" serial PRIMARY KEY NOT NULL,
	"ref" varchar(32) NOT NULL,
	"disputeId" integer,
	"transactionId" integer,
	"transactionRef" varchar(32),
	"agentId" integer NOT NULL,
	"customerId" integer,
	"customerName" varchar(128),
	"customerPhone" varchar(20),
	"originalAmount" integer NOT NULL,
	"refundAmount" integer NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"reason" varchar(256) NOT NULL,
	"category" varchar(64) DEFAULT 'general' NOT NULL,
	"status" varchar(32) DEFAULT 'pending' NOT NULL,
	"method" varchar(32) DEFAULT 'original_method' NOT NULL,
	"approvedBy" varchar(128),
	"approvedAt" timestamp,
	"processedAt" timestamp,
	"rejectedBy" varchar(128),
	"rejectedAt" timestamp,
	"rejectionReason" text,
	"notes" text,
	"metadata" text,
	"tenantId" integer,
	"deletedAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "refunds_ref_unique" UNIQUE("ref")
);
--> statement-breakpoint
CREATE INDEX "refund_agentId_idx" ON "refunds" USING btree ("agentId");--> statement-breakpoint
CREATE INDEX "refund_status_idx" ON "refunds" USING btree ("status");--> statement-breakpoint
CREATE INDEX "refund_disputeId_idx" ON "refunds" USING btree ("disputeId");--> statement-breakpoint
CREATE INDEX "refund_transactionRef_idx" ON "refunds" USING btree ("transactionRef");