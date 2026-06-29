CREATE TABLE "dlq_messages" (
	"id" serial PRIMARY KEY NOT NULL,
	"topic" varchar(128) NOT NULL,
	"partition" integer DEFAULT 0 NOT NULL,
	"offset" varchar(32) DEFAULT '0' NOT NULL,
	"errorMessage" text DEFAULT '' NOT NULL,
	"retryCount" integer DEFAULT 0 NOT NULL,
	"payload" text DEFAULT '{}' NOT NULL,
	"status" varchar(32) DEFAULT 'pending_retry' NOT NULL,
	"resolvedAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "dlq_topic_idx" ON "dlq_messages" USING btree ("topic");--> statement-breakpoint
CREATE INDEX "dlq_status_idx" ON "dlq_messages" USING btree ("status");--> statement-breakpoint
CREATE INDEX "dlq_createdAt_idx" ON "dlq_messages" USING btree ("createdAt");