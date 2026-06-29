CREATE TABLE "agent_push_subscriptions" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentCode" varchar(32) NOT NULL,
	"endpoint" text NOT NULL,
	"p256dhKey" text NOT NULL,
	"authKey" text NOT NULL,
	"userAgent" text,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "agent_push_subscriptions_endpoint_unique" UNIQUE("endpoint")
);
--> statement-breakpoint
CREATE INDEX "agent_push_subscriptions_agent_code_idx" ON "agent_push_subscriptions" USING btree ("agentCode");