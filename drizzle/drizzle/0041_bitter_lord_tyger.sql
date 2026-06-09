CREATE TABLE "biometric_audit_events" (
	"id" serial PRIMARY KEY NOT NULL,
	"sessionId" varchar(128) NOT NULL,
	"userId" integer,
	"eventType" varchar(64) NOT NULL,
	"outcome" varchar(32) NOT NULL,
	"confidenceScore" numeric(5, 4),
	"spoofType" varchar(64),
	"spoofScore" numeric(5, 4),
	"livenessMethod" varchar(32),
	"matchScore" numeric(5, 4),
	"processingTimeMs" integer,
	"deviceInfo" json,
	"ipAddress" varchar(64),
	"geoLocation" json,
	"errorDetails" text,
	"tenantId" integer,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "face_enrollments" (
	"id" serial PRIMARY KEY NOT NULL,
	"userId" integer NOT NULL,
	"enrollmentType" varchar(32) DEFAULT 'kyc' NOT NULL,
	"embeddingVector" text NOT NULL,
	"embeddingVersion" varchar(32) DEFAULT 'arcface_w600k_r50' NOT NULL,
	"qualityScore" numeric(5, 4),
	"livenessScore" numeric(5, 4),
	"antiSpoofScore" numeric(5, 4),
	"sourceImageHash" varchar(128),
	"deviceFingerprint" varchar(256),
	"ipAddress" varchar(64),
	"isActive" boolean DEFAULT true NOT NULL,
	"revokedAt" timestamp,
	"revokedReason" text,
	"expiresAt" timestamp,
	"tenantId" integer,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE INDEX "bae_sessionId_idx" ON "biometric_audit_events" USING btree ("sessionId");--> statement-breakpoint
CREATE INDEX "bae_userId_idx" ON "biometric_audit_events" USING btree ("userId");--> statement-breakpoint
CREATE INDEX "bae_eventType_idx" ON "biometric_audit_events" USING btree ("eventType");--> statement-breakpoint
CREATE INDEX "bae_outcome_idx" ON "biometric_audit_events" USING btree ("outcome");--> statement-breakpoint
CREATE INDEX "bae_tenantId_idx" ON "biometric_audit_events" USING btree ("tenantId");--> statement-breakpoint
CREATE INDEX "bae_createdAt_idx" ON "biometric_audit_events" USING btree ("createdAt");--> statement-breakpoint
CREATE INDEX "fe_userId_idx" ON "face_enrollments" USING btree ("userId");--> statement-breakpoint
CREATE INDEX "fe_tenantId_idx" ON "face_enrollments" USING btree ("tenantId");--> statement-breakpoint
CREATE INDEX "fe_active_idx" ON "face_enrollments" USING btree ("userId","isActive");