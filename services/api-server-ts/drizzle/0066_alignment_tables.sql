-- Round-9 Wave B1b: schema/migration alignment (0066_alignment_tables).
--
-- TWO GROUPS of missing tables are created here, all idempotent via
-- CREATE TABLE IF NOT EXISTS so re-application and coexistence with
-- db-push-managed environments are both safe:
--
--   GROUP A (21 tables): "phantom" tables that existing routers query ONLY
--   via raw SQL (sql`...` templates), e.g. agritechPayments -> "agri_farms".
--   They 500 on a migrations-built DB because no migration 0000-0065 creates
--   them. Column shapes are derived from the actual SQL usage: every router
--   uses the same generic-record pattern (id, data jsonb, status text,
--   tenant_id text, agent_id integer, metadata jsonb, created_at,
--   updated_at). All domain attributes live inside the `data`/`metadata`
--   jsonb documents (e.g. data->>'crop_sales'), so jsonb is the exact
--   compatible type. Ambiguities resolved to the narrowest compatible type:
--     - agent_id: integer (healthInsuranceMicro inserts ctx.user.id, and
--       users.id is serial; compared via String(row.agent_id)).
--     - tenant_id: text (routers insert the literal 'default').
--     - id: serial (routers bind numeric ids and RETURNING id).
--     - kyc_review / kyc_submission: no raw SQL references found in
--       customerOnboardingPipeline.ts (they appear only as pipeline STAGE
--       name strings); created with the same generic-record shape as the
--       other 19 for forward compatibility.
--
--   GROUP B (20 tables): tables defined in drizzle/schema.ts (managed via
--   drizzle-kit push) that have no CREATE TABLE in any migration 0000-0065.
--   DDL is generated from the pgTable definitions with exact column names,
--   types, defaults and nullability, so migrations-built DBs match the
--   db-push-managed schema. NOTE: schema.ts models 6 of these columns as
--   pgEnum (ecommerce_product_status, ecommerce_order_status,
--   ecommerce_interaction_type, agent_store_status, payment_split_status,
--   delivery_status) but those enum TYPEs are also absent from 0000-0065;
--   the columns are emitted as varchar with an inline CHECK constraint over
--   the exact pgEnum label sets (functionally compatible with drizzle's
--   string reads/writes) instead of CREATE TYPE statements.
--
-- No CONCURRENTLY anywhere: drizzle-kit runs migrations inside a
-- transaction, where CREATE INDEX CONCURRENTLY is illegal in Postgres.

-- ══ GROUP A: phantom tables queried via raw SQL ══════════════════════════

CREATE TABLE IF NOT EXISTS "agri_farms" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "anaas_tenants" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "bnpl_applications" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "carbon_projects" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "credit_scores" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "did_identities" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "edu_schools" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "health_policies" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "iot_devices" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "kyc_review" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "kyc_submission" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "loyalty_members" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "mini_apps" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "nfc_terminals" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "open_banking_partners" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "payroll_employers" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "pension_accounts" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "satellite_links" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "stable_wallets" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "tokenized_assets" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "wearable_devices" (
	"id" serial PRIMARY KEY NOT NULL,
	"data" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'active',
	"tenant_id" text DEFAULT 'default',
	"agent_id" integer,
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint

-- ══ GROUP B: schema.ts (db-push-managed) tables missing from migrations ══

CREATE TABLE IF NOT EXISTS "receipt_templates" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(128) NOT NULL,
	"channel" varchar(32) DEFAULT 'print' NOT NULL,
	"bodyTemplate" text NOT NULL,
	"headerTemplate" text,
	"footerTemplate" text,
	"isDefault" boolean DEFAULT false NOT NULL,
	"createdAt" timestamp DEFAULT now() NOT NULL,
	"updatedAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "guide_feedback" (
	"id" serial PRIMARY KEY NOT NULL,
	"guideId" varchar(128) NOT NULL,
	"subsection" varchar(128),
	"userId" integer,
	"rating" integer NOT NULL,
	"comment" text,
	"createdAt" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_categories" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" varchar(128) NOT NULL,
	"slug" varchar(128) NOT NULL,
	"description" text,
	"parent_id" integer,
	"image_url" varchar(512),
	"sort_order" integer DEFAULT 0 NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "ecommerce_categories_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_products" (
	"id" serial PRIMARY KEY NOT NULL,
	"sku" varchar(64) NOT NULL,
	"name" varchar(256) NOT NULL,
	"description" text,
	"category_id" integer NOT NULL,
	"price" numeric(12, 2) NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"image_url" varchar(512),
	"is_active" boolean DEFAULT true NOT NULL,
	-- pgEnum "ecommerce_product_status" (type not present in 0000-0065); varchar+CHECK
	"status" varchar(32) DEFAULT 'active' NOT NULL CHECK ("status" IN ('active', 'draft', 'archived', 'out_of_stock')),
	"merchant_id" integer NOT NULL,
	"agent_id" integer,
	"weight" numeric(8, 2),
	"dimensions" varchar(64),
	"tags" jsonb DEFAULT '[]'::jsonb,
	"attributes" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "ecommerce_products_sku_unique" UNIQUE("sku")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_inventory" (
	"id" serial PRIMARY KEY NOT NULL,
	"sku" varchar(64) NOT NULL,
	"product_id" integer NOT NULL,
	"quantity" integer DEFAULT 0 NOT NULL,
	"reserved" integer DEFAULT 0 NOT NULL,
	"reorder_point" integer DEFAULT 10 NOT NULL,
	"warehouse_id" varchar(64) DEFAULT 'default' NOT NULL,
	"last_restocked" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "ecommerce_inventory_sku_unique" UNIQUE("sku")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_inventory_reservations" (
	"id" serial PRIMARY KEY NOT NULL,
	"sku" varchar(64) NOT NULL,
	"order_id" integer NOT NULL,
	"quantity" integer NOT NULL,
	"expires_at" timestamp NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_orders" (
	"id" serial PRIMARY KEY NOT NULL,
	"order_number" varchar(32) NOT NULL,
	"customer_id" integer NOT NULL,
	"merchant_id" integer NOT NULL,
	"agent_id" integer,
	-- pgEnum "ecommerce_order_status" (type not present in 0000-0065); varchar+CHECK
	"status" varchar(32) DEFAULT 'pending' NOT NULL CHECK ("status" IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
	"sub_total" numeric(12, 2) NOT NULL,
	"tax" numeric(12, 2) DEFAULT '0' NOT NULL,
	"shipping_fee" numeric(12, 2) DEFAULT '0' NOT NULL,
	"discount" numeric(12, 2) DEFAULT '0' NOT NULL,
	"total" numeric(12, 2) NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"payment_method" varchar(32) NOT NULL,
	"payment_ref" varchar(128),
	"shipping_address" jsonb,
	"notes" text,
	"offline_created" boolean DEFAULT false NOT NULL,
	"synced_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	"fulfilled_at" timestamp,
	"cancelled_at" timestamp,
	CONSTRAINT "ecommerce_orders_order_number_unique" UNIQUE("order_number")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_order_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"order_id" integer NOT NULL,
	"product_id" integer NOT NULL,
	"sku" varchar(64) NOT NULL,
	"name" varchar(256) NOT NULL,
	"quantity" integer NOT NULL,
	"unit_price" numeric(12, 2) NOT NULL,
	"total" numeric(12, 2) NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_carts" (
	"id" serial PRIMARY KEY NOT NULL,
	"customer_id" integer NOT NULL,
	"coupon_code" varchar(32),
	"discount_amount" numeric(12, 2) DEFAULT '0' NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	"offline_created" boolean DEFAULT false NOT NULL,
	"device_id" varchar(128),
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	"expires_at" timestamp
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_cart_items" (
	"id" serial PRIMARY KEY NOT NULL,
	"cart_id" integer NOT NULL,
	"product_id" integer NOT NULL,
	"sku" varchar(64) NOT NULL,
	"name" varchar(256) NOT NULL,
	"quantity" integer NOT NULL,
	"unit_price" numeric(12, 2) NOT NULL,
	"merchant_id" integer NOT NULL,
	"added_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "ecommerce_interactions" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"customer_id" integer NOT NULL,
	"product_id" integer NOT NULL,
	-- pgEnum "ecommerce_interaction_type" (type not present in 0000-0065); varchar+CHECK
	"interaction_type" varchar(32) NOT NULL CHECK ("interaction_type" IN ('view', 'add_to_cart', 'purchase', 'review', 'wishlist')),
	"metadata" jsonb DEFAULT '{}'::jsonb,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "agent_stores" (
	"id" serial PRIMARY KEY NOT NULL,
	"agent_id" integer NOT NULL,
	"agent_code" varchar(32) NOT NULL,
	"slug" varchar(128) NOT NULL,
	"store_name" varchar(256) NOT NULL,
	"description" text,
	"logo_url" varchar(512),
	"banner_url" varchar(512),
	"theme_color" varchar(7) DEFAULT '#3b82f6',
	"about_html" text,
	"phone" varchar(20),
	"email" varchar(256),
	"address" text,
	"city" varchar(128),
	"state" varchar(64),
	"lga" varchar(128),
	"latitude" numeric(10, 7),
	"longitude" numeric(10, 7),
	"business_hours" jsonb,
	"categories" jsonb DEFAULT '[]'::jsonb,
	"tags" jsonb DEFAULT '[]'::jsonb,
	"delivery_enabled" boolean DEFAULT true NOT NULL,
	"pickup_enabled" boolean DEFAULT true NOT NULL,
	"min_order_amount" numeric(12, 2) DEFAULT '0',
	"platform_commission_pct" numeric(5, 2) DEFAULT '5.00' NOT NULL,
	-- pgEnum "agent_store_status" (type not present in 0000-0065); varchar+CHECK
	"status" varchar(32) DEFAULT 'pending' NOT NULL CHECK ("status" IN ('pending', 'active', 'suspended', 'closed')),
	"is_verified" boolean DEFAULT false NOT NULL,
	"total_sales" integer DEFAULT 0 NOT NULL,
	"total_revenue" numeric(14, 2) DEFAULT '0' NOT NULL,
	"average_rating" numeric(3, 2) DEFAULT '0',
	"review_count" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "agent_stores_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "delivery_zones" (
	"id" serial PRIMARY KEY NOT NULL,
	"store_id" integer NOT NULL,
	"zone_name" varchar(128) NOT NULL,
	"description" text,
	"delivery_fee" numeric(12, 2) NOT NULL,
	"estimated_minutes" integer DEFAULT 60,
	"max_distance_km" numeric(8, 2),
	"areas" jsonb DEFAULT '[]'::jsonb,
	"is_active" boolean DEFAULT true NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "product_reviews" (
	"id" serial PRIMARY KEY NOT NULL,
	"product_id" integer NOT NULL,
	"store_id" integer NOT NULL,
	"customer_id" integer NOT NULL,
	"customer_name" varchar(128),
	"rating" integer NOT NULL,
	"title" varchar(256),
	"body" text,
	"is_verified_purchase" boolean DEFAULT false NOT NULL,
	"helpful_count" integer DEFAULT 0 NOT NULL,
	"images" jsonb DEFAULT '[]'::jsonb,
	"seller_reply" text,
	"seller_replied_at" timestamp,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "store_reviews" (
	"id" serial PRIMARY KEY NOT NULL,
	"store_id" integer NOT NULL,
	"customer_id" integer NOT NULL,
	"customer_name" varchar(128),
	"rating" integer NOT NULL,
	"body" text,
	"order_id" integer,
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "payment_splits" (
	"id" serial PRIMARY KEY NOT NULL,
	"order_id" integer NOT NULL,
	"order_number" varchar(32) NOT NULL,
	"store_id" integer NOT NULL,
	"agent_id" integer NOT NULL,
	"order_total" numeric(12, 2) NOT NULL,
	"platform_fee" numeric(12, 2) NOT NULL,
	"platform_fee_pct" numeric(5, 2) NOT NULL,
	"agent_payout" numeric(12, 2) NOT NULL,
	"tax_amount" numeric(12, 2) DEFAULT '0' NOT NULL,
	"currency" varchar(3) DEFAULT 'NGN' NOT NULL,
	-- pgEnum "payment_split_status" (type not present in 0000-0065); varchar+CHECK
	"status" varchar(32) DEFAULT 'pending' NOT NULL CHECK ("status" IN ('pending', 'processed', 'settled', 'failed')),
	"settled_at" timestamp,
	"payment_ref" varchar(128),
	"created_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "delivery_tracking" (
	"id" serial PRIMARY KEY NOT NULL,
	"order_id" integer NOT NULL,
	"store_id" integer NOT NULL,
	"delivery_zone_id" integer,
	-- pgEnum "delivery_status" (type not present in 0000-0065); varchar+CHECK
	"status" varchar(32) DEFAULT 'pending' NOT NULL CHECK ("status" IN ('pending', 'assigned', 'picked_up', 'in_transit', 'delivered', 'failed', 'returned')),
	"rider_name" varchar(128),
	"rider_phone" varchar(20),
	"tracking_code" varchar(64),
	"estimated_delivery" timestamp,
	"actual_delivery" timestamp,
	"delivery_notes" text,
	"delivery_proof_url" varchar(512),
	"latitude" numeric(10, 7),
	"longitude" numeric(10, 7),
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL,
	CONSTRAINT "delivery_tracking_tracking_code_unique" UNIQUE("tracking_code")
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "aml_screenings" (
	"id" serial PRIMARY KEY NOT NULL,
	"entity_name" varchar(200) NOT NULL,
	"entity_type" varchar(20) NOT NULL,
	"country" varchar(2),
	"national_id" varchar(50),
	"risk_score" integer DEFAULT 0 NOT NULL,
	"status" varchar(20) DEFAULT 'clear' NOT NULL,
	"sanctions_match" boolean DEFAULT false NOT NULL,
	"pep_match" boolean DEFAULT false NOT NULL,
	"adverse_media_match" boolean DEFAULT false NOT NULL,
	"high_risk_country" boolean DEFAULT false NOT NULL,
	"screened_at" timestamp DEFAULT now() NOT NULL,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"updated_at" timestamp DEFAULT now() NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "aml_watchlist_entries" (
	"id" serial PRIMARY KEY NOT NULL,
	"entity_name" varchar(200) NOT NULL,
	"aliases" text,
	"list_type" varchar(30) NOT NULL,
	"source_list" varchar(100),
	"country" varchar(2),
	"date_added" timestamp DEFAULT now() NOT NULL,
	"active" boolean DEFAULT true NOT NULL
);
--> statement-breakpoint

CREATE TABLE IF NOT EXISTS "idempotency_keys" (
	"id" serial PRIMARY KEY NOT NULL,
	"idempotency_key" varchar(128) NOT NULL,
	"response_data" text,
	"created_at" timestamp DEFAULT now() NOT NULL,
	"expires_at" timestamp NOT NULL,
	CONSTRAINT "idempotency_keys_idempotency_key_unique" UNIQUE("idempotency_key")
);
