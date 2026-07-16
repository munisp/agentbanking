import {
  bigserial,
  boolean,
  index,
  integer,
  json,
  numeric,
  pgEnum,
  pgTable,
  serial,
  text,
  timestamp,
  uniqueIndex,
  varchar,
} from "drizzle-orm/pg-core";

// ─── Multi-Store / Storefront ────────────────────────────────────────────────
export const stores = pgTable(
  "ecom_stores",
  {
    id: serial("id").primaryKey(),
    merchantId: integer("merchant_id").notNull(),
    name: varchar("name", { length: 256 }).notNull(),
    slug: varchar("slug", { length: 128 }).notNull().unique(),
    description: text("description"),
    logo: varchar("logo", { length: 512 }),
    banner: varchar("banner", { length: 512 }),
    primaryColor: varchar("primary_color", { length: 7 }).default("#1a73e8"),
    secondaryColor: varchar("secondary_color", { length: 7 }).default(
      "#f5f5f5"
    ),
    templateId: varchar("template_id", { length: 64 }),
    domain: varchar("domain", { length: 256 }),
    currency: varchar("currency", { length: 3 }).default("NGN").notNull(),
    isActive: boolean("is_active").default(true).notNull(),
    settings: json("settings").$type<Record<string, unknown>>().default({}),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  t => ({
    slugIdx: uniqueIndex("ecom_store_slug_idx").on(t.slug),
    merchantIdx: index("ecom_store_merchant_idx").on(t.merchantId),
  })
);

// ─── Product Variants ────────────────────────────────────────────────────────
export const productVariants = pgTable(
  "ecom_product_variants",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull(),
    sku: varchar("sku", { length: 64 }).notNull().unique(),
    name: varchar("name", { length: 256 }).notNull(),
    attributes: json("attributes").$type<Record<string, string>>().default({}),
    price: numeric("price", { precision: 12, scale: 2 }).notNull(),
    compareAtPrice: numeric("compare_at_price", { precision: 12, scale: 2 }),
    weight: numeric("weight", { precision: 8, scale: 2 }),
    barcode: varchar("barcode", { length: 64 }),
    imageUrl: varchar("image_url", { length: 512 }),
    isActive: boolean("is_active").default(true).notNull(),
    sortOrder: integer("sort_order").default(0),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    productIdx: index("ecom_variant_product_idx").on(t.productId),
    skuIdx: uniqueIndex("ecom_variant_sku_idx").on(t.sku),
    barcodeIdx: index("ecom_variant_barcode_idx").on(t.barcode),
  })
);

// ─── Product Reviews ─────────────────────────────────────────────────────────
export const productReviews = pgTable(
  "ecom_product_reviews",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull(),
    customerId: integer("customer_id").notNull(),
    orderId: integer("order_id"),
    rating: integer("rating").notNull(),
    title: varchar("title", { length: 256 }),
    body: text("body"),
    isVerified: boolean("is_verified").default(false).notNull(),
    isApproved: boolean("is_approved").default(false).notNull(),
    helpfulCount: integer("helpful_count").default(0),
    images: json("images").$type<string[]>().default([]),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    productIdx: index("ecom_review_product_idx").on(t.productId),
    customerIdx: index("ecom_review_customer_idx").on(t.customerId),
    ratingIdx: index("ecom_review_rating_idx").on(t.rating),
  })
);

// ─── Product Bundles ─────────────────────────────────────────────────────────
export const productBundles = pgTable("ecom_product_bundles", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 256 }).notNull(),
  slug: varchar("slug", { length: 128 }).notNull().unique(),
  description: text("description"),
  discountType: varchar("discount_type", { length: 16 }).default("percentage"),
  discountValue: numeric("discount_value", { precision: 8, scale: 2 }).default(
    "0"
  ),
  isActive: boolean("is_active").default(true).notNull(),
  startDate: timestamp("start_date"),
  endDate: timestamp("end_date"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
});

export const bundleItems = pgTable(
  "ecom_bundle_items",
  {
    id: serial("id").primaryKey(),
    bundleId: integer("bundle_id").notNull(),
    productId: integer("product_id").notNull(),
    variantId: integer("variant_id"),
    quantity: integer("quantity").default(1).notNull(),
  },
  t => ({
    bundleIdx: index("ecom_bi_bundle_idx").on(t.bundleId),
  })
);

// ─── Promotions & Coupons ────────────────────────────────────────────────────
export const promotionTypeEnum = pgEnum("ecom_promotion_type", [
  "percentage",
  "fixed_amount",
  "bogo",
  "free_shipping",
  "bundle",
  "flash_sale",
  "loyalty_points",
]);

export const promotions = pgTable(
  "ecom_promotions",
  {
    id: serial("id").primaryKey(),
    storeId: integer("store_id"),
    name: varchar("name", { length: 256 }).notNull(),
    code: varchar("code", { length: 32 }).unique(),
    type: promotionTypeEnum("type").notNull(),
    value: numeric("value", { precision: 12, scale: 2 }).notNull(),
    minOrderAmount: numeric("min_order_amount", { precision: 12, scale: 2 }),
    maxDiscount: numeric("max_discount", { precision: 12, scale: 2 }),
    usageLimit: integer("usage_limit"),
    usedCount: integer("used_count").default(0).notNull(),
    perCustomerLimit: integer("per_customer_limit").default(1),
    applicableProducts: json("applicable_products")
      .$type<number[]>()
      .default([]),
    applicableCategories: json("applicable_categories")
      .$type<number[]>()
      .default([]),
    isActive: boolean("is_active").default(true).notNull(),
    startDate: timestamp("start_date").notNull(),
    endDate: timestamp("end_date").notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    codeIdx: uniqueIndex("ecom_promo_code_idx").on(t.code),
    activeIdx: index("ecom_promo_active_idx").on(
      t.isActive,
      t.startDate,
      t.endDate
    ),
  })
);

// ─── Loyalty & Referrals ─────────────────────────────────────────────────────
export const loyaltyAccounts = pgTable(
  "ecom_loyalty_accounts",
  {
    id: serial("id").primaryKey(),
    customerId: integer("customer_id").notNull().unique(),
    points: integer("points").default(0).notNull(),
    tier: varchar("tier", { length: 32 }).default("bronze").notNull(),
    lifetimePoints: integer("lifetime_points").default(0).notNull(),
    referralCode: varchar("referral_code", { length: 16 }).notNull().unique(),
    referredBy: integer("referred_by"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    customerIdx: uniqueIndex("ecom_loyalty_customer_idx").on(t.customerId),
  })
);

export const loyaltyTransactions = pgTable(
  "ecom_loyalty_transactions",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    accountId: integer("account_id").notNull(),
    points: integer("points").notNull(),
    type: varchar("type", { length: 32 }).notNull(),
    description: varchar("description", { length: 256 }),
    orderId: integer("order_id"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    accountIdx: index("ecom_lt_account_idx").on(t.accountId),
  })
);

// ─── Marketplace Integrations ────────────────────────────────────────────────
export const marketplaceStatusEnum = pgEnum("marketplace_sync_status", [
  "active",
  "paused",
  "error",
  "pending",
]);

export const marketplaceConnections = pgTable(
  "ecom_marketplace_connections",
  {
    id: serial("id").primaryKey(),
    storeId: integer("store_id").notNull(),
    platform: varchar("platform", { length: 32 }).notNull(),
    credentials: json("credentials")
      .$type<Record<string, string>>()
      .default({}),
    syncStatus: marketplaceStatusEnum("sync_status")
      .default("pending")
      .notNull(),
    lastSyncAt: timestamp("last_sync_at"),
    settings: json("settings").$type<Record<string, unknown>>().default({}),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    storeIdx: index("ecom_mkt_store_idx").on(t.storeId),
    platformIdx: index("ecom_mkt_platform_idx").on(t.platform),
  })
);

export const marketplaceListings = pgTable(
  "ecom_marketplace_listings",
  {
    id: serial("id").primaryKey(),
    connectionId: integer("connection_id").notNull(),
    productId: integer("product_id").notNull(),
    externalId: varchar("external_id", { length: 128 }),
    externalUrl: varchar("external_url", { length: 512 }),
    status: varchar("status", { length: 32 }).default("pending"),
    lastSyncAt: timestamp("last_sync_at"),
    syncErrors: json("sync_errors").$type<string[]>().default([]),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    connectionIdx: index("ecom_listing_conn_idx").on(t.connectionId),
    productIdx: index("ecom_listing_product_idx").on(t.productId),
  })
);

// ─── Supply Chain: Warehouses ────────────────────────────────────────────────
export const warehouses = pgTable(
  "sc_warehouses",
  {
    id: serial("id").primaryKey(),
    code: varchar("code", { length: 16 }).notNull().unique(),
    name: varchar("name", { length: 256 }).notNull(),
    type: varchar("type", { length: 32 }).default("standard").notNull(),
    address: json("address").$type<{
      street: string;
      city: string;
      state: string;
      country: string;
      zipCode: string;
      lat?: number;
      lng?: number;
    }>(),
    capacity: integer("capacity").default(10000).notNull(),
    currentOccupancy: integer("current_occupancy").default(0).notNull(),
    isActive: boolean("is_active").default(true).notNull(),
    managerId: integer("manager_id"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    codeIdx: uniqueIndex("sc_wh_code_idx").on(t.code),
  })
);

// ─── Supply Chain: Warehouse Zones & Locations ───────────────────────────────
export const warehouseZoneTypeEnum = pgEnum("warehouse_zone_type", [
  "receiving",
  "storage",
  "picking",
  "packing",
  "shipping",
  "returns",
  "quarantine",
]);

export const warehouseZones = pgTable(
  "sc_warehouse_zones",
  {
    id: serial("id").primaryKey(),
    warehouseId: integer("warehouse_id").notNull(),
    name: varchar("name", { length: 128 }).notNull(),
    type: warehouseZoneTypeEnum("type").notNull(),
    capacity: integer("capacity").default(1000).notNull(),
    temperature: varchar("temperature", { length: 32 }),
    isActive: boolean("is_active").default(true).notNull(),
  },
  t => ({
    whIdx: index("sc_zone_wh_idx").on(t.warehouseId),
  })
);

export const warehouseLocations = pgTable(
  "sc_warehouse_locations",
  {
    id: serial("id").primaryKey(),
    zoneId: integer("zone_id").notNull(),
    aisle: varchar("aisle", { length: 8 }).notNull(),
    rack: varchar("rack", { length: 8 }).notNull(),
    shelf: varchar("shelf", { length: 8 }).notNull(),
    bin: varchar("bin", { length: 8 }).notNull(),
    label: varchar("label", { length: 32 }).notNull(),
    capacity: integer("capacity").default(100).notNull(),
    currentQuantity: integer("current_quantity").default(0).notNull(),
    sku: varchar("sku", { length: 64 }),
    isActive: boolean("is_active").default(true).notNull(),
  },
  t => ({
    zoneIdx: index("sc_loc_zone_idx").on(t.zoneId),
    labelIdx: uniqueIndex("sc_loc_label_idx").on(t.label),
    skuIdx: index("sc_loc_sku_idx").on(t.sku),
  })
);

// ─── Supply Chain: Stock Movements ───────────────────────────────────────────
export const stockMovementTypeEnum = pgEnum("stock_movement_type", [
  "receiving",
  "transfer",
  "adjustment",
  "reservation",
  "pick",
  "return",
  "damaged",
  "cycle_count",
]);

export const stockMovements = pgTable(
  "sc_stock_movements",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    sku: varchar("sku", { length: 64 }).notNull(),
    type: stockMovementTypeEnum("type").notNull(),
    quantity: integer("quantity").notNull(),
    fromWarehouseId: integer("from_warehouse_id"),
    toWarehouseId: integer("to_warehouse_id"),
    fromLocationId: integer("from_location_id"),
    toLocationId: integer("to_location_id"),
    referenceType: varchar("reference_type", { length: 32 }),
    referenceId: integer("reference_id"),
    reason: text("reason"),
    performedBy: integer("performed_by").notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    skuIdx: index("sc_mv_sku_idx").on(t.sku),
    typeIdx: index("sc_mv_type_idx").on(t.type),
    dateIdx: index("sc_mv_date_idx").on(t.createdAt),
  })
);

// ─── Supply Chain: Inventory Valuation ───────────────────────────────────────
export const valuationMethodEnum = pgEnum("valuation_method", [
  "fifo",
  "lifo",
  "weighted_average",
]);

export const inventoryValuations = pgTable(
  "sc_inventory_valuations",
  {
    id: serial("id").primaryKey(),
    sku: varchar("sku", { length: 64 }).notNull(),
    warehouseId: integer("warehouse_id").notNull(),
    method: valuationMethodEnum("method").notNull(),
    quantity: integer("quantity").notNull(),
    unitCost: numeric("unit_cost", { precision: 12, scale: 4 }).notNull(),
    totalValue: numeric("total_value", { precision: 14, scale: 2 }).notNull(),
    batchNumber: varchar("batch_number", { length: 64 }),
    receivedAt: timestamp("received_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  t => ({
    skuWhIdx: index("sc_val_sku_wh_idx").on(t.sku, t.warehouseId),
  })
);

// ─── Supply Chain: Procurement / Suppliers ───────────────────────────────────
export const suppliers = pgTable(
  "sc_suppliers",
  {
    id: serial("id").primaryKey(),
    code: varchar("code", { length: 16 }).notNull().unique(),
    name: varchar("name", { length: 256 }).notNull(),
    contactName: varchar("contact_name", { length: 128 }),
    email: varchar("email", { length: 256 }),
    phone: varchar("phone", { length: 32 }),
    address: json("address").$type<Record<string, string>>().default({}),
    paymentTerms: varchar("payment_terms", { length: 32 }).default("net30"),
    leadTimeDays: integer("lead_time_days").default(7),
    rating: numeric("rating", { precision: 3, scale: 2 }).default("0"),
    totalOrders: integer("total_orders").default(0),
    onTimeDeliveryRate: numeric("on_time_delivery_rate", {
      precision: 5,
      scale: 2,
    }).default("0"),
    isActive: boolean("is_active").default(true).notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    codeIdx: uniqueIndex("sc_supplier_code_idx").on(t.code),
  })
);

export const purchaseOrderStatusEnum = pgEnum("purchase_order_status", [
  "draft",
  "submitted",
  "approved",
  "ordered",
  "partially_received",
  "received",
  "cancelled",
]);

export const purchaseOrders = pgTable(
  "sc_purchase_orders",
  {
    id: serial("id").primaryKey(),
    poNumber: varchar("po_number", { length: 32 }).notNull().unique(),
    supplierId: integer("supplier_id").notNull(),
    warehouseId: integer("warehouse_id").notNull(),
    status: purchaseOrderStatusEnum("status").default("draft").notNull(),
    subTotal: numeric("sub_total", { precision: 14, scale: 2 }).notNull(),
    tax: numeric("tax", { precision: 12, scale: 2 }).default("0"),
    shippingCost: numeric("shipping_cost", { precision: 12, scale: 2 }).default(
      "0"
    ),
    total: numeric("total", { precision: 14, scale: 2 }).notNull(),
    currency: varchar("currency", { length: 3 }).default("NGN"),
    expectedDelivery: timestamp("expected_delivery"),
    receivedAt: timestamp("received_at"),
    notes: text("notes"),
    approvedBy: integer("approved_by"),
    createdBy: integer("created_by").notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  t => ({
    poNumIdx: uniqueIndex("sc_po_num_idx").on(t.poNumber),
    supplierIdx: index("sc_po_supplier_idx").on(t.supplierId),
    statusIdx: index("sc_po_status_idx").on(t.status),
  })
);

export const purchaseOrderItems = pgTable(
  "sc_purchase_order_items",
  {
    id: serial("id").primaryKey(),
    poId: integer("po_id").notNull(),
    sku: varchar("sku", { length: 64 }).notNull(),
    productName: varchar("product_name", { length: 256 }).notNull(),
    quantityOrdered: integer("quantity_ordered").notNull(),
    quantityReceived: integer("quantity_received").default(0).notNull(),
    unitCost: numeric("unit_cost", { precision: 12, scale: 4 }).notNull(),
    total: numeric("total", { precision: 14, scale: 2 }).notNull(),
  },
  t => ({
    poIdx: index("sc_poi_po_idx").on(t.poId),
  })
);

// ─── Supply Chain: Logistics / Shipments ─────────────────────────────────────
export const shipmentStatusEnum = pgEnum("shipment_status", [
  "pending",
  "label_created",
  "picked_up",
  "in_transit",
  "out_for_delivery",
  "delivered",
  "failed",
  "returned",
]);

export const carriers = pgTable("sc_carriers", {
  id: serial("id").primaryKey(),
  code: varchar("code", { length: 16 }).notNull().unique(),
  name: varchar("name", { length: 128 }).notNull(),
  trackingUrlTemplate: varchar("tracking_url_template", { length: 512 }),
  apiEndpoint: varchar("api_endpoint", { length: 512 }),
  isActive: boolean("is_active").default(true).notNull(),
  supportedCountries: json("supported_countries").$type<string[]>().default([]),
  ratePerKg: numeric("rate_per_kg", { precision: 8, scale: 2 }),
  baseRate: numeric("base_rate", { precision: 8, scale: 2 }),
});

export const shipments = pgTable(
  "sc_shipments",
  {
    id: serial("id").primaryKey(),
    orderId: integer("order_id").notNull(),
    carrierId: integer("carrier_id").notNull(),
    trackingNumber: varchar("tracking_number", { length: 128 }),
    labelUrl: varchar("label_url", { length: 512 }),
    status: shipmentStatusEnum("status").default("pending").notNull(),
    estimatedDelivery: timestamp("estimated_delivery"),
    actualDelivery: timestamp("actual_delivery"),
    shippingCost: numeric("shipping_cost", { precision: 10, scale: 2 }),
    weight: numeric("weight", { precision: 8, scale: 2 }),
    dimensions: json("dimensions").$type<{
      length: number;
      width: number;
      height: number;
    }>(),
    fromAddress: json("from_address")
      .$type<Record<string, string>>()
      .default({}),
    toAddress: json("to_address").$type<Record<string, string>>().default({}),
    proofOfDelivery: varchar("proof_of_delivery", { length: 512 }),
    deliveryNotes: text("delivery_notes"),
    createdAt: timestamp("created_at").defaultNow().notNull(),
    updatedAt: timestamp("updated_at").defaultNow().notNull(),
  },
  t => ({
    orderIdx: index("sc_ship_order_idx").on(t.orderId),
    trackingIdx: index("sc_ship_tracking_idx").on(t.trackingNumber),
    statusIdx: index("sc_ship_status_idx").on(t.status),
  })
);

// ─── Supply Chain: Demand Forecasting ────────────────────────────────────────
export const demandForecasts = pgTable(
  "sc_demand_forecasts",
  {
    id: bigserial("id", { mode: "number" }).primaryKey(),
    sku: varchar("sku", { length: 64 }).notNull(),
    warehouseId: integer("warehouse_id"),
    forecastDate: timestamp("forecast_date").notNull(),
    predictedDemand: numeric("predicted_demand", {
      precision: 10,
      scale: 2,
    }).notNull(),
    confidence: numeric("confidence", { precision: 5, scale: 4 }),
    method: varchar("method", { length: 32 }).notNull(),
    seasonalFactor: numeric("seasonal_factor", { precision: 5, scale: 4 }),
    isAnomaly: boolean("is_anomaly").default(false),
    actualDemand: numeric("actual_demand", { precision: 10, scale: 2 }),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    skuDateIdx: index("sc_forecast_sku_date_idx").on(t.sku, t.forecastDate),
    whIdx: index("sc_forecast_wh_idx").on(t.warehouseId),
  })
);

// ─── Abandoned Carts ─────────────────────────────────────────────────────────
export const abandonedCarts = pgTable(
  "ecom_abandoned_carts",
  {
    id: serial("id").primaryKey(),
    customerId: integer("customer_id"),
    email: varchar("email", { length: 256 }),
    cartData: json("cart_data").$type<unknown>(),
    totalValue: numeric("total_value", { precision: 12, scale: 2 }),
    recoveryEmailSent: boolean("recovery_email_sent").default(false),
    recoveredAt: timestamp("recovered_at"),
    expiresAt: timestamp("expires_at").notNull(),
    createdAt: timestamp("created_at").defaultNow().notNull(),
  },
  t => ({
    customerIdx: index("ecom_abandoned_customer_idx").on(t.customerId),
    expiryIdx: index("ecom_abandoned_expiry_idx").on(t.expiresAt),
  })
);
