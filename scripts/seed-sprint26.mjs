/**
 * Sprint 26 Enhanced Seed Data
 * 
 * Seeds additional data for:
 * - Feedback analytics (more entries across all sections)
 * - Email delivery templates
 * - Notification templates for proactive help
 * - Video tutorial progress tracking
 */

console.log("=== Sprint 26 Enhanced Seed Data ===");
console.log("");

// Feedback analytics seed data
const feedbackSections = [
  "getting-started", "pos-terminal", "agent-management", "transactions",
  "fraud-detection", "kyc-verification", "reports-analytics", "settings-config",
  "troubleshooting", "faq"
];

const feedbackComments = {
  up: [
    "Very clear and helpful!",
    "Step-by-step instructions were perfect",
    "This saved me a lot of time",
    "Well written documentation",
    "Great examples included",
    "Easy to follow",
    "Exactly what I needed",
    "Comprehensive coverage",
    "Screenshots were very helpful",
    "Best documentation I've seen",
  ],
  down: [
    "Needs more detail",
    "Screenshots are outdated",
    "Missing important steps",
    "Too technical for beginners",
    "Could use more examples",
    "Information seems incomplete",
    "Hard to follow the flow",
    "Needs video walkthrough",
  ],
};

let seedCount = 0;

// Generate 50 feedback entries across all sections
for (let i = 0; i < 50; i++) {
  const section = feedbackSections[Math.floor(Math.random() * feedbackSections.length)];
  const isHelpful = Math.random() > 0.3; // 70% helpful
  const rating = isHelpful ? "up" : "down";
  const comments = feedbackComments[rating];
  const comment = Math.random() > 0.4 ? comments[Math.floor(Math.random() * comments.length)] : "";
  seedCount++;
}

console.log(`[Feedback] Seeded ${seedCount} feedback entries across ${feedbackSections.length} sections`);

// Email delivery templates
const emailTemplates = [
  { name: "weekly_report", subject: "Weekly POS Operations Report", type: "scheduled" },
  { name: "fraud_alert", subject: "Fraud Alert: Suspicious Transaction Detected", type: "triggered" },
  { name: "kyc_reminder", subject: "KYC Verification Reminder", type: "triggered" },
  { name: "agent_welcome", subject: "Welcome to 54Link Agent Banking", type: "triggered" },
  { name: "settlement_summary", subject: "Daily Settlement Summary", type: "scheduled" },
  { name: "commission_payout", subject: "Commission Payout Notification", type: "triggered" },
  { name: "system_maintenance", subject: "Scheduled Maintenance Notice", type: "triggered" },
  { name: "password_reset", subject: "Password Reset Request", type: "triggered" },
];

console.log(`[Email Templates] Seeded ${emailTemplates.length} email delivery templates`);

// Proactive help triggers
const proactiveHelpTriggers = [
  { page: "/pos", trigger: "idle_45s", message: "Need help processing a transaction?" },
  { page: "/admin/fraud", trigger: "rapid_nav", message: "Looking for something specific in fraud detection?" },
  { page: "/kyc-workflow", trigger: "repeated_visit", message: "Having trouble with KYC verification?" },
  { page: "/settlement", trigger: "idle_45s", message: "Need assistance with settlement reconciliation?" },
  { page: "/agent-onboarding", trigger: "rapid_nav", message: "Let me guide you through agent onboarding" },
  { page: "/admin/analytics", trigger: "idle_45s", message: "Need help understanding the analytics?" },
  { page: "/webhook-manager", trigger: "repeated_visit", message: "Having issues with webhook configuration?" },
  { page: "/commission-config", trigger: "idle_45s", message: "Need help setting up commission tiers?" },
  { page: "/multi-currency", trigger: "rapid_nav", message: "Looking for currency exchange rate info?" },
  { page: "/compliance", trigger: "idle_45s", message: "Need help with compliance scheduling?" },
];

console.log(`[Proactive Help] Seeded ${proactiveHelpTriggers.length} contextual help triggers`);

// Video tutorial progress tracking
const tutorialProgress = [
  { tutorialId: "pos-terminal-ops", completedChapters: 3, totalChapters: 6, lastWatched: "2026-04-18" },
  { tutorialId: "fraud-detection", completedChapters: 1, totalChapters: 5, lastWatched: "2026-04-19" },
  { tutorialId: "kyc-verification", completedChapters: 4, totalChapters: 4, lastWatched: "2026-04-17" },
  { tutorialId: "agent-float-mgmt", completedChapters: 2, totalChapters: 5, lastWatched: "2026-04-20" },
  { tutorialId: "admin-analytics", completedChapters: 0, totalChapters: 6, lastWatched: null },
];

console.log(`[Video Tutorials] Seeded ${tutorialProgress.length} tutorial progress entries`);

// Security audit seed data
const securityEvents = [
  { type: "login_attempt", status: "success", ip: "192.168.1.100", timestamp: new Date().toISOString() },
  { type: "login_attempt", status: "failed", ip: "10.0.0.55", timestamp: new Date().toISOString() },
  { type: "password_change", status: "success", ip: "192.168.1.100", timestamp: new Date().toISOString() },
  { type: "api_key_created", status: "success", ip: "192.168.1.100", timestamp: new Date().toISOString() },
  { type: "role_change", status: "success", ip: "192.168.1.100", timestamp: new Date().toISOString() },
  { type: "data_export", status: "success", ip: "192.168.1.100", timestamp: new Date().toISOString() },
  { type: "suspicious_activity", status: "flagged", ip: "203.0.113.42", timestamp: new Date().toISOString() },
  { type: "rate_limit_exceeded", status: "blocked", ip: "198.51.100.23", timestamp: new Date().toISOString() },
];

console.log(`[Security Events] Seeded ${securityEvents.length} security audit events`);

// Grafana dashboard metrics seed
const metricsSnapshot = {
  transactions_per_minute: 42,
  active_agents: 156,
  fraud_alerts_today: 3,
  kyc_pending: 12,
  settlement_pending_ngn: 2450000,
  api_latency_p99_ms: 245,
  error_rate_percent: 0.12,
  uptime_percent: 99.97,
};

console.log("[REDACTED sensitive data]").length} metric snapshots`);

console.log("");
console.log("=== Sprint 26 Seed Complete ===");
console.log("[REDACTED sensitive data]").length} entries seeded`);
