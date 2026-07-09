CREATE TABLE "commission_cascade_history" (
	"id" serial PRIMARY KEY NOT NULL,
	"transactionId" integer NOT NULL,
	"transactionRef" varchar(64) NOT NULL,
	"transactionType" varchar(32) NOT NULL,
	"transactionAmount" numeric(15, 2) NOT NULL,
	"totalCommission" numeric(15, 2) NOT NULL,
	"originAgentId" integer NOT NULL,
	"originAgentCode" varchar(32) NOT NULL,
	"recipientAgentId" integer NOT NULL,
	"recipientAgentCode" varchar(32) NOT NULL,
	"recipientHierarchyRole" varchar(32) NOT NULL,
	"recipientHierarchyLevel" integer NOT NULL,
	"splitPercentage" numeric(5, 2) NOT NULL,
	"commissionAmount" numeric(15, 2) NOT NULL,
	"status" varchar(16) DEFAULT 'credited' NOT NULL,
	"creditedAt" timestamp DEFAULT now(),
	"tenantId" integer,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "parentAgentId" integer;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "hierarchyRole" varchar(32) DEFAULT 'agent';--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "hierarchyLevel" integer DEFAULT 3;--> statement-breakpoint
ALTER TABLE "agents" ADD COLUMN "commissionSplitOverride" numeric(5, 2);--> statement-breakpoint
CREATE INDEX "cch_transactionRef_idx" ON "commission_cascade_history" USING btree ("transactionRef");--> statement-breakpoint
CREATE INDEX "cch_originAgentId_idx" ON "commission_cascade_history" USING btree ("originAgentId");--> statement-breakpoint
CREATE INDEX "cch_recipientAgentId_idx" ON "commission_cascade_history" USING btree ("recipientAgentId");--> statement-breakpoint
CREATE INDEX "cch_createdAt_idx" ON "commission_cascade_history" USING btree ("createdAt");--> statement-breakpoint
CREATE INDEX "agents_parentAgentId_idx" ON "agents" USING btree ("parentAgentId");--> statement-breakpoint
CREATE INDEX "agents_hierarchyRole_idx" ON "agents" USING btree ("hierarchyRole");