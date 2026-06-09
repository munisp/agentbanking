CREATE TYPE "public"."connectivity_quality" AS ENUM('Excellent', 'Good', 'Poor', 'Offline');--> statement-breakpoint
CREATE TABLE "connectivity_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentCode" varchar(32) NOT NULL,
	"quality" "connectivity_quality" NOT NULL,
	"latencyMs" integer,
	"recordedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "connectivity_log_agent_recorded_idx" ON "connectivity_log" USING btree ("agentCode","recordedAt");