CREATE TYPE "public"."command_status" AS ENUM('pending', 'acknowledged', 'completed', 'failed', 'expired');--> statement-breakpoint
CREATE TYPE "public"."device_command" AS ENUM('UPDATE', 'RECONFIG', 'RESTART', 'WIPE', 'PING');--> statement-breakpoint
CREATE TYPE "public"."device_status" AS ENUM('online', 'offline', 'updating', 'error');--> statement-breakpoint
CREATE TYPE "public"."dispute_author_role" AS ENUM('agent', 'admin', 'supervisor', 'system');--> statement-breakpoint
CREATE TYPE "public"."dispute_status" AS ENUM('raised', 'reviewing', 'resolved', 'rejected');--> statement-breakpoint
ALTER TYPE "public"."role" ADD VALUE 'supervisor';--> statement-breakpoint
CREATE TABLE "device_commands" (
	"id" serial PRIMARY KEY NOT NULL,
	"deviceId" integer NOT NULL,
	"command" "device_command" NOT NULL,
	"payload" json,
	"status" "command_status" DEFAULT 'pending' NOT NULL,
	"issuedBy" varchar(64),
	"issuedAt" timestamp DEFAULT now() NOT NULL,
	"acknowledgedAt" timestamp,
	"completedAt" timestamp,
	"errorMessage" text
);
--> statement-breakpoint
CREATE TABLE "devices" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer NOT NULL,
	"serialNumber" varchar(64) NOT NULL,
	"model" varchar(64) DEFAULT 'PAX A920 MAX' NOT NULL,
	"osVersion" varchar(32),
	"appVersion" varchar(32),
	"firmwareVersion" varchar(32),
	"ipAddress" varchar(45),
	"location" varchar(128),
	"status" "device_status" DEFAULT 'offline' NOT NULL,
	"configJson" json,
	"lastSeenAt" timestamp,
	"enrolledAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "devices_serialNumber_unique" UNIQUE("serialNumber")
);
--> statement-breakpoint
CREATE TABLE "dispute_messages" (
	"id" serial PRIMARY KEY NOT NULL,
	"disputeId" integer NOT NULL,
	"authorId" integer,
	"authorName" varchar(128) NOT NULL,
	"authorRole" "dispute_author_role" NOT NULL,
	"message" text NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "disputes" (
	"id" serial PRIMARY KEY NOT NULL,
	"ref" varchar(32) NOT NULL,
	"transactionId" integer NOT NULL,
	"transactionRef" varchar(32) NOT NULL,
	"agentId" integer NOT NULL,
	"reason" varchar(256) NOT NULL,
	"evidence" text,
	"status" "dispute_status" DEFAULT 'raised' NOT NULL,
	"resolution" text,
	"resolvedBy" varchar(64),
	"resolvedAt" timestamp,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "disputes_ref_unique" UNIQUE("ref")
);
--> statement-breakpoint
CREATE TABLE "supervisor_agents" (
	"id" serial PRIMARY KEY NOT NULL,
	"supervisorUserId" integer NOT NULL,
	"agentId" integer NOT NULL,
	"assignedAt" timestamp DEFAULT now() NOT NULL
);
