/**
 * Drizzle Kit Configuration — Enhanced
 * strict: validates schema vs DB on every push
 * verbose: prints SQL before applying
 * out: aligned with actual migration directory (drizzle/drizzle/)
 * schema: includes both main schema and ecommerce extension
 */
import { defineConfig } from "drizzle-kit";

const connectionString =
  process.env.POSTGRES_URL ??
  process.env.DATABASE_URL;

if (!connectionString) {
  throw new Error(
    "POSTGRES_URL or DATABASE_URL is required to run drizzle commands.\n" +
    "Set it in your .env file or environment before running drizzle-kit."
  );
}

export default defineConfig({
  // Include both schema files
  schema: [
    "./drizzle/schema.ts",
    "./drizzle/ecommerce-extended-schema.ts",
  ],

  // Aligned with actual migration files location
  out: "./drizzle/drizzle",

  dialect: "postgresql",

  dbCredentials: {
    url: connectionString,
  },

  // Strict: validates every table/column in schema exists in DB
  strict: true,

  // Verbose: prints SQL statements before applying
  verbose: true,

  // Introspection casing
  introspect: {
    casing: "camel",
  },

  // Migration tracking table
  migrations: {
    table: "__drizzle_migrations",
    schema: "public",
  },
});
