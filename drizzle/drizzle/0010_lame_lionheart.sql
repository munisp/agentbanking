CREATE TABLE "agent_geofence_zones" (
	"id" serial PRIMARY KEY NOT NULL,
	"agentId" integer NOT NULL,
	"zoneId" integer NOT NULL,
	"assignedBy" varchar(64),
	"assignedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "compliance_reports" (
	"id" serial PRIMARY KEY NOT NULL,
	"periodStart" timestamp NOT NULL,
	"periodEnd" timestamp NOT NULL,
	"totalAlerts" integer DEFAULT 0 NOT NULL,
	"highAlerts" integer DEFAULT 0 NOT NULL,
	"mediumAlerts" integer DEFAULT 0 NOT NULL,
	"lowAlerts" integer DEFAULT 0 NOT NULL,
	"escalatedAlerts" integer DEFAULT 0 NOT NULL,
	"resolvedAlerts" integer DEFAULT 0 NOT NULL,
	"topOffendersJson" json,
	"pdfUrl" text,
	"pdfKey" varchar(256),
	"generatedBy" varchar(64) DEFAULT 'system' NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "device_locations" (
	"id" serial PRIMARY KEY NOT NULL,
	"deviceId" integer NOT NULL,
	"agentId" integer NOT NULL,
	"latitude" numeric(10, 7) NOT NULL,
	"longitude" numeric(10, 7) NOT NULL,
	"accuracy" numeric(8, 2),
	"withinZone" boolean DEFAULT true NOT NULL,
	"reportedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "geofence_zones" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(128) NOT NULL,
	"description" text,
	"latitude" numeric(10, 7) NOT NULL,
	"longitude" numeric(10, 7) NOT NULL,
	"radiusMetres" integer DEFAULT 500 NOT NULL,
	"isActive" boolean DEFAULT true NOT NULL,
	"createdBy" varchar(64),
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
