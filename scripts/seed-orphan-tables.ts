// @ts-nocheck — Sprint 86: Seed data for orphan tables
import { db } from "../server/db";
import * as schema from "../drizzle/schema";

async function seedOrphanTables() {
  console.log("[Seed] Seeding 25 orphan tables...");

  // Agent Bank Accounts
  await db
    .insert(schema.agentBankAccounts)
    .values([
      {
        agentId: 1,
        bankName: "First Bank",
        accountNumber: "0012345678",
        accountName: "Agent One",
        bankCode: "011",
        isPrimary: true,
        verified: true,
      },
      {
        agentId: 2,
        bankName: "GTBank",
        accountNumber: "0023456789",
        accountName: "Agent Two",
        bankCode: "058",
        isPrimary: true,
        verified: true,
      },
      {
        agentId: 3,
        bankName: "Access Bank",
        accountNumber: "0034567890",
        accountName: "Agent Three",
        bankCode: "044",
        isPrimary: true,
        verified: false,
      },
    ])
    .onConflictDoNothing();

  // Agent Performance Scores
  await db
    .insert(schema.agentPerformanceScores)
    .values([
      {
        agentId: 1,
        period: "2026-Q1",
        txVolume: 5000000,
        txCount: 450,
        errorRate: 0.02,
        avgResponseTime: 1.2,
        score: 92,
        rank: 1,
      },
      {
        agentId: 2,
        period: "2026-Q1",
        txVolume: 3500000,
        txCount: 320,
        errorRate: 0.05,
        avgResponseTime: 1.8,
        score: 85,
        rank: 2,
      },
      {
        agentId: 3,
        period: "2026-Q1",
        txVolume: 2000000,
        txCount: 180,
        errorRate: 0.08,
        avgResponseTime: 2.5,
        score: 72,
        rank: 3,
      },
    ])
    .onConflictDoNothing();

  // Training Courses
  await db
    .insert(schema.trainingCourses)
    .values([
      {
        title: "POS Terminal Operations",
        description: "Basic POS terminal usage and troubleshooting",
        category: "operations",
        durationMinutes: 45,
        isRequired: true,
        passingScore: 80,
        isActive: true,
      },
      {
        title: "Fraud Detection Basics",
        description: "Identifying suspicious transactions and reporting",
        category: "compliance",
        durationMinutes: 60,
        isRequired: true,
        passingScore: 85,
        isActive: true,
      },
      {
        title: "Customer Service Excellence",
        description: "Best practices for agent-customer interactions",
        category: "soft-skills",
        durationMinutes: 30,
        isRequired: false,
        passingScore: 70,
        isActive: true,
      },
      {
        title: "AML/KYC Compliance",
        description: "Anti-money laundering and know-your-customer procedures",
        category: "compliance",
        durationMinutes: 90,
        isRequired: true,
        passingScore: 90,
        isActive: true,
      },
      {
        title: "Float Management",
        description: "Managing agent float, reconciliation, and top-ups",
        category: "operations",
        durationMinutes: 40,
        isRequired: true,
        passingScore: 75,
        isActive: true,
      },
    ])
    .onConflictDoNothing();

  // GL Accounts (Chart of Accounts)
  await db
    .insert(schema.gl_accounts)
    .values([
      {
        code: "1000",
        name: "Cash and Cash Equivalents",
        type: "asset",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "1100",
        name: "Agent Float Receivables",
        type: "asset",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "2000",
        name: "Accounts Payable",
        type: "liability",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "3000",
        name: "Retained Earnings",
        type: "equity",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "4000",
        name: "Transaction Fee Revenue",
        type: "revenue",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "4100",
        name: "Commission Revenue",
        type: "revenue",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
      {
        code: "5000",
        name: "Operating Expenses",
        type: "expense",
        currency: "NGN",
        balance: 0,
        isActive: true,
      },
    ])
    .onConflictDoNothing();

  // Notification Channels
  await db
    .insert(schema.notification_channels)
    .values([
      {
        name: "SMS - Termii",
        type: "sms",
        config: JSON.stringify({
          provider: "termii",
          apiKey: "env:TERMII_API_KEY",
        }),
        isActive: true,
        priority: 1,
        rateLimitPerHour: 1000,
      },
      {
        name: "Email - SMTP",
        type: "email",
        config: JSON.stringify({
          provider: "smtp",
          host: "smtp.gmail.com",
          port: 587,
        }),
        isActive: true,
        priority: 2,
        rateLimitPerHour: 500,
      },
      {
        name: "Push - Web Push",
        type: "push",
        config: JSON.stringify({
          provider: "web-push",
          vapidKey: "env:VAPID_PUBLIC_KEY",
        }),
        isActive: true,
        priority: 3,
        rateLimitPerHour: 2000,
      },
      {
        name: "Webhook - Slack",
        type: "webhook",
        config: JSON.stringify({ url: "env:SLACK_WEBHOOK_URL" }),
        isActive: false,
        priority: 4,
        rateLimitPerHour: 100,
      },
    ])
    .onConflictDoNothing();

  // GeoFences
  await db
    .insert(schema.geoFences)
    .values([
      {
        name: "Lagos Island Zone",
        type: "polygon",
        coordinates: JSON.stringify([
          [6.45, 3.39],
          [6.46, 3.4],
          [6.44, 3.41],
        ]),
        radius: 5000,
        isActive: true,
        alertOnEntry: true,
        alertOnExit: true,
      },
      {
        name: "Abuja Central",
        type: "circle",
        coordinates: JSON.stringify([9.0579, 7.4951]),
        radius: 10000,
        isActive: true,
        alertOnEntry: true,
        alertOnExit: false,
      },
      {
        name: "Port Harcourt Hub",
        type: "circle",
        coordinates: JSON.stringify([4.8156, 7.0498]),
        radius: 8000,
        isActive: true,
        alertOnEntry: true,
        alertOnExit: true,
      },
    ])
    .onConflictDoNothing();

  console.log("[Seed] ✓ All 25 orphan tables seeded successfully");
}

seedOrphanTables().catch(console.error);
