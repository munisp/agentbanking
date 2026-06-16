CREATE TABLE "sim_failover_log" (
	"id" serial PRIMARY KEY NOT NULL,
	"terminalId" varchar(32) NOT NULL,
	"agentCode" varchar(32) NOT NULL,
	"fromSlot" integer NOT NULL,
	"toSlot" integer NOT NULL,
	"reason" varchar(32) NOT NULL,
	"latencyMs" integer NOT NULL,
	"lossX10" integer NOT NULL,
	"txRef" varchar(64),
	"switchedAt" timestamp DEFAULT now() NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "sim_failover_log_terminal_switched_idx" ON "sim_failover_log" USING btree ("terminalId","switchedAt");--> statement-breakpoint
CREATE INDEX "sim_failover_log_agent_switched_idx" ON "sim_failover_log" USING btree ("agentCode","switchedAt");