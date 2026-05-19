CREATE TYPE "public"."erp_type" AS ENUM('odoo', 'sap', 'netsuite', 'quickbooks', 'sage', 'dynamics365', 'custom');--> statement-breakpoint
CREATE TABLE "erp_config" (
	"id" serial PRIMARY KEY NOT NULL,
	"erpType" "erp_type" DEFAULT 'odoo' NOT NULL,
	"name" varchar(128) DEFAULT 'Default ERP' NOT NULL,
	"baseUrl" text DEFAULT '' NOT NULL,
	"apiKey" text DEFAULT '',
	"username" varchar(128) DEFAULT '',
	"database" varchar(128) DEFAULT '',
	"fieldMappings" json DEFAULT '{}'::json,
	"syncEnabled" boolean DEFAULT false NOT NULL,
	"syncIntervalMinutes" integer DEFAULT 60 NOT NULL,
	"syncTransactions" boolean DEFAULT true NOT NULL,
	"syncAgents" boolean DEFAULT false NOT NULL,
	"syncInventory" boolean DEFAULT false NOT NULL,
	"lastSyncAt" timestamp,
	"lastSyncStatus" varchar(32) DEFAULT 'never',
	"lastSyncError" text,
	"lastSyncCount" integer DEFAULT 0,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
