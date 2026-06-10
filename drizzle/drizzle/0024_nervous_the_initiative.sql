CREATE TABLE "device_compliance_policies" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(128) NOT NULL,
	"description" text,
	"tenantId" integer,
	"rules" json NOT NULL,
	"severity" varchar(16) DEFAULT 'medium' NOT NULL,
	"enabled" boolean DEFAULT true NOT NULL,
	"enforcementAction" varchar(32) DEFAULT 'notify',
	"createdBy" varchar(64),
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "device_compliance_violations" (
	"id" serial PRIMARY KEY NOT NULL,
	"deviceId" integer NOT NULL,
	"policyId" integer NOT NULL,
	"serialNumber" varchar(64) NOT NULL,
	"agentCode" varchar(32),
	"violationType" varchar(64) NOT NULL,
	"severity" varchar(16) NOT NULL,
	"details" json,
	"status" varchar(32) DEFAULT 'open' NOT NULL,
	"enforcementAction" varchar(32),
	"resolvedAt" timestamp,
	"resolvedBy" varchar(64),
	"detectedAt" timestamp DEFAULT now() NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "mdm_geofence_violations" (
	"id" serial PRIMARY KEY NOT NULL,
	"deviceId" integer NOT NULL,
	"serialNumber" varchar(64) NOT NULL,
	"agentCode" varchar(32),
	"zoneId" integer,
	"zoneName" varchar(128),
	"violationType" varchar(32) NOT NULL,
	"latE6" integer,
	"lonE6" integer,
	"distanceMeters" integer,
	"status" varchar(32) DEFAULT 'open' NOT NULL,
	"notifiedAt" timestamp,
	"resolvedAt" timestamp,
	"detectedAt" timestamp DEFAULT now() NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "batteryLevel" integer;--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "batteryCharging" boolean DEFAULT false;--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "wifiSsid" varchar(64);--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "wifiRssi" integer;--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "wifiIpAddress" varchar(45);--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "networkType" varchar(16);--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "screenshotUrl" text;--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "lastScreenshotAt" timestamp;--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "complianceStatus" varchar(32) DEFAULT 'unknown';--> statement-breakpoint
ALTER TABLE "devices" ADD COLUMN "lastComplianceCheckAt" timestamp;--> statement-breakpoint
CREATE INDEX "dcp_tenantId_idx" ON "device_compliance_policies" USING btree ("tenantId");--> statement-breakpoint
CREATE INDEX "dcp_enabled_idx" ON "device_compliance_policies" USING btree ("enabled");--> statement-breakpoint
CREATE INDEX "dcv_deviceId_idx" ON "device_compliance_violations" USING btree ("deviceId");--> statement-breakpoint
CREATE INDEX "dcv_policyId_idx" ON "device_compliance_violations" USING btree ("policyId");--> statement-breakpoint
CREATE INDEX "dcv_status_idx" ON "device_compliance_violations" USING btree ("status");--> statement-breakpoint
CREATE INDEX "dcv_detectedAt_idx" ON "device_compliance_violations" USING btree ("detectedAt");--> statement-breakpoint
CREATE INDEX "mgv_deviceId_idx" ON "mdm_geofence_violations" USING btree ("deviceId");--> statement-breakpoint
CREATE INDEX "mgv_detectedAt_idx" ON "mdm_geofence_violations" USING btree ("detectedAt");--> statement-breakpoint
CREATE INDEX "mgv_status_idx" ON "mdm_geofence_violations" USING btree ("status");