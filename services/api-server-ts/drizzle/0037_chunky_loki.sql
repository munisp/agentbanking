CREATE TYPE "public"."load_test_run_status" AS ENUM('running', 'completed', 'failed', 'cancelled');--> statement-breakpoint
CREATE TABLE "load_test_runs" (
	"id" serial PRIMARY KEY NOT NULL,
	"run_id" varchar(64) NOT NULL,
	"status" "load_test_run_status" DEFAULT 'running' NOT NULL,
	"started_at" timestamp DEFAULT now() NOT NULL,
	"completed_at" timestamp,
	"triggered_by" varchar(128),
	"target_rps" integer DEFAULT 100 NOT NULL,
	"duration_seconds" integer DEFAULT 60 NOT NULL,
	"concurrency" integer DEFAULT 10 NOT NULL,
	"zipf_skew" numeric(4, 2) DEFAULT '1.07',
	"merchant_count" integer DEFAULT 1000,
	"results" json,
	"error_message" text,
	CONSTRAINT "load_test_runs_run_id_unique" UNIQUE("run_id")
);
--> statement-breakpoint
CREATE INDEX "ltr_status_idx" ON "load_test_runs" USING btree ("status");--> statement-breakpoint
CREATE INDEX "ltr_started_at_idx" ON "load_test_runs" USING btree ("started_at");