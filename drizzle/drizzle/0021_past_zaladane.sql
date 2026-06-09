CREATE TABLE "system_config" (
	"id" serial PRIMARY KEY NOT NULL,
	"key" varchar(128) NOT NULL,
	"value" text NOT NULL,
	"description" text,
	"updatedBy" varchar(64),
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "system_config_key_unique" UNIQUE("key")
);
--> statement-breakpoint
CREATE UNIQUE INDEX "system_config_key_idx" ON "system_config" USING btree ("key");