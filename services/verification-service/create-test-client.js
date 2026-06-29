#!/usr/bin/env node

/**
 * Create a test client for verification testing
 *
 * This script creates a test client in the database that can be used
 * to initialize verification sessions during development.
 */

const { DataSource } = require("typeorm");
const path = require("path");
const crypto = require("crypto");

// Load environment variables
require("dotenv").config();

const DB_HOST = process.env.DB_HOST || "localhost";
const DB_PORT = process.env.DB_PORT || "5432";
const DB_USER = process.env.DB_USER || "admin";
const DB_PASSWORD = process.env.DB_PASSWORD || "Test1234";
const DB_DATABASE = process.env.DB_DATABASE || "link_core_banking";

async function createTestClient() {
  console.log("\n🔧 Creating test client...\n");

  const dataSource = new DataSource({
    type: "postgres",
    host: DB_HOST,
    port: Number(DB_PORT),
    username: DB_USER,
    password: DB_PASSWORD,
    database: DB_DATABASE,
    entities: [path.join(__dirname, "src/entity/*.ts")],
    synchronize: true,
  });

  try {
    await dataSource.initialize();
    console.log("✅ Database connected\n");

    const clientId = "test-client-" + crypto.randomBytes(8).toString("hex");
    const clientSecret =
      "test-secret-" + crypto.randomBytes(16).toString("hex");

    // Check if test client already exists
    const existingClient = await dataSource.query(
      "SELECT * FROM client WHERE client_name = $1",
      ["Test Client"],
    );

    if (existingClient && existingClient.length > 0) {
      console.log("⚠️  Test client already exists!\n");
      console.log("📋 Existing Client Details:");
      console.log("   Client ID:", existingClient[0].client_id);
      console.log("   Client Secret:", existingClient[0].client_secret);
      console.log("   Client Name:", existingClient[0].client_name);
      console.log(
        "\n💡 Use these credentials to create verification sessions.\n",
      );
      console.log(
        "🔄 To create a new client, delete the existing one first or use a different name.\n",
      );
      await dataSource.destroy();
      return;
    }

    // Insert test client
    const result = await dataSource.query(
      `INSERT INTO client (
        client_id, 
        client_secret, 
        client_name, 
        redirect_urls, 
        logo, 
        callback_url,
        contact
      ) VALUES ($1, $2, $3, $4, $5, $6, $7) 
      RETURNING *`,
      [
        clientId,
        clientSecret,
        "Test Client",
        ["http://localhost:3000", "http://localhost:8005"],
        null,
        "http://localhost:3000/webhook",
        JSON.stringify({
          firstName: "Test",
          lastName: "Admin",
          email: "test@54agent.com",
        }),
      ],
    );

    console.log("✅ Test client created successfully!\n");
    console.log("📋 Client Details:");
    console.log("   Client ID:", clientId);
    console.log("   Client Secret:", clientSecret);
    console.log("   Client Name: Test Client");
    console.log("   Callback URL: http://localhost:3000/webhook\n");

    console.log("💡 Save these credentials! You can use them with:");
    console.log(`   export TEST_CLIENT_ID="${clientId}"`);
    console.log(`   export TEST_CLIENT_SECRET="${clientSecret}"`);
    console.log("\n📝 Or add to verification-ui/.env:");
    console.log(`   TEST_CLIENT_ID=${clientId}`);
    console.log(`   TEST_CLIENT_SECRET=${clientSecret}\n`);

    await dataSource.destroy();
  } catch (error) {
    console.error("\n❌ Error:", error.message);

    if (error.code === "ECONNREFUSED") {
      console.error(
        "\n💡 Database connection refused. Make sure PostgreSQL is running.\n",
      );
    } else if (error.code === "3D000") {
      console.error(
        `\n💡 Database "${DB_DATABASE}" does not exist. Create it first:\n`,
      );
      console.error(
        `   psql -U ${DB_USER} -c "CREATE DATABASE ${DB_DATABASE};"\n`,
      );
    } else if (error.code === "42P01") {
      console.error(
        "\n💡 Client table does not exist. Run the verification service first to create tables:\n",
      );
      console.error("   cd services/verification-service");
      console.error("   npm run dev\n");
    }

    if (dataSource.isInitialized) {
      await dataSource.destroy();
    }
    process.exit(1);
  }
}

createTestClient();
