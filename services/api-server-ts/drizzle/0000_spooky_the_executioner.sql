CREATE TYPE "public"."agent_tier" AS ENUM('Bronze', 'Silver', 'Gold', 'Platinum');--> statement-breakpoint
CREATE TYPE "public"."audit_status" AS ENUM('success', 'failure', 'warning');--> statement-breakpoint
CREATE TYPE "public"."chat_status" AS ENUM('open', 'assigned', 'resolved', 'escalated');--> statement-breakpoint
CREATE TYPE "public"."fraud_severity" AS ENUM('critical', 'high', 'medium', 'low');--> statement-breakpoint
CREATE TYPE "public"."fraud_status" AS ENUM('open', 'investigating', 'escalated', 'dismissed', 'resolved');--> statement-breakpoint
CREATE TYPE "public"."loyalty_type" AS ENUM('earned', 'redeemed', 'bonus', 'penalty', 'challenge');--> statement-breakpoint
CREATE TYPE "public"."role" AS ENUM('user', 'admin');--> statement-breakpoint
CREATE TYPE "public"."sender_type" AS ENUM('agent', 'support', 'system');--> statement-breakpoint
CREATE TYPE "public"."topup_status" AS ENUM('pending', 'approved', 'rejected');--> statement-breakpoint
CREATE TYPE "public"."tx_channel" AS ENUM('Cash', 'Card', 'USSD', 'QR', 'NFC', 'App');--> statement-breakpoint
CREATE TYPE "public"."tx_status" AS ENUM('success', 'pending', 'failed', 'reversed');--> statement-breakpoint
CREATE TYPE "public"."tx_type" AS ENUM('Cash In', 'Cash Out', 'Transfer', 'Card Payment', 'QR Payment', 'NFC Payment', 'Airtime', 'Bill Payment', 'Reversal', 'Nano Loan', 'Insurance');--> statement-breakpoint
CREATE TABLE "agents" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentCode" varchar(32) NOT NULL,
	"name" varchar(128) NOT NULL,
	"phone" varchar(20) NOT NULL,
	"email" varchar(320),
	"location" varchar(128),
	"terminalModel" varchar(64) DEFAULT 'PAX A920 MAX',
	"terminalSerial" varchar(64),
	"tier" "agent_tier" DEFAULT 'Bronze' NOT NULL,
	"pinHash" varchar(128) NOT NULL,
	"floatBalance" numeric(15, 2) DEFAULT '0.00' NOT NULL,
	"floatLimit" numeric(15, 2) DEFAULT '1000000.00' NOT NULL,
	"commissionBalance" numeric(15, 2) DEFAULT '0.00' NOT NULL,
	"loyaltyPoints" integer DEFAULT 0 NOT NULL,
	"streak" integer DEFAULT 0 NOT NULL,
	"rank" integer DEFAULT 0,
	"isActive" boolean DEFAULT true NOT NULL,
	"lastLoginAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "agents_agentCode_unique" UNIQUE("agentCode")
);
--> statement-breakpoint
CREATE TABLE "audit_log" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"agentId" integer,
	"agentCode" varchar(32),
	"action" varchar(128) NOT NULL,
	"resource" varchar(64),
	"resourceId" varchar(64),
	"ipAddress" varchar(45),
	"userAgent" varchar(256),
	"status" "audit_status" DEFAULT 'success',
	"metadata" json,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "chat_messages" (
	"id" serial PRIMARY KEY NOT NULL,
	"sessionId" integer NOT NULL,
	"senderType" "sender_type" NOT NULL,
	"senderName" varchar(128),
	"content" text NOT NULL,
	"isRead" boolean DEFAULT false,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "chat_sessions" (
	"id" serial PRIMARY KEY NOT NULL,
	"sessionRef" varchar(32) NOT NULL,
	"agentId" integer NOT NULL,
	"category" varchar(64),
	"subject" varchar(256),
	"status" "chat_status" DEFAULT 'open' NOT NULL,
	"supportAgentName" varchar(128),
	"rating" integer,
	"resolvedAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "chat_sessions_sessionRef_unique" UNIQUE("sessionRef")
);
--> statement-breakpoint
CREATE TABLE "float_topup_requests" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer NOT NULL,
	"requestedAmount" numeric(15, 2) NOT NULL,
	"status" "topup_status" DEFAULT 'pending' NOT NULL,
	"approvedBy" varchar(64),
	"notes" text,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "fraud_alerts" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer,
	"transactionId" integer,
	"severity" "fraud_severity" NOT NULL,
	"type" varchar(128) NOT NULL,
	"customerName" varchar(128),
	"amount" numeric(15, 2),
	"reason" text NOT NULL,
	"aiExplanation" json,
	"fraudScore" numeric(5, 2),
	"status" "fraud_status" DEFAULT 'open' NOT NULL,
	"assignedTo" varchar(64),
	"resolvedAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "loyalty_history" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer NOT NULL,
	"transactionId" integer,
	"type" "loyalty_type" NOT NULL,
	"points" integer NOT NULL,
	"description" varchar(256),
	"balanceAfter" integer NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "transactions" (
	"id" serial PRIMARY KEY NOT NULL,
	"ref" varchar(32) NOT NULL,
	"agentId" integer NOT NULL,
	"type" "tx_type" NOT NULL,
	"amount" numeric(15, 2) NOT NULL,
	"fee" numeric(10, 2) DEFAULT '0.00',
	"commission" numeric(10, 2) DEFAULT '0.00',
	"customerName" varchar(128),
	"customerPhone" varchar(20),
	"customerAccount" varchar(20),
	"destinationBank" varchar(64),
	"destinationAccount" varchar(20),
	"channel" "tx_channel" DEFAULT 'Cash',
	"status" "tx_status" DEFAULT 'pending' NOT NULL,
	"failureReason" text,
	"receiptPrinted" boolean DEFAULT false,
	"smsSent" boolean DEFAULT false,
	"fraudScore" numeric(5, 2) DEFAULT '0.00',
	"metadata" json,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "transactions_ref_unique" UNIQUE("ref")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" serial PRIMARY KEY NOT NULL,
	"openId" varchar(64) NOT NULL,
	"name" text,
	"email" varchar(320),
	"loginMethod" varchar(64),
	"role" "role" DEFAULT 'user' NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	"lastSignedIn" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "users_openId_unique" UNIQUE("openId")
);
