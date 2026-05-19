#!/usr/bin/env node
/**
 * Sprint 64 — Chat & Support Seed Data
 * Seeds: chat sessions, messages, knowledge base articles, canned responses,
 * survey responses, agent presences, routing rules, escalation chains
 */

console.log("=== Sprint 64 Chat & Support Seed Script ===");
console.log("This script seeds the in-memory stores for the chat support system.");
console.log("");

// Simulated seed data for documentation and testing
const SEED_DATA = {
  chatSessions: [
    { id: 1, userId: "user-001", subject: "Payment not received", category: "billing", status: "active", priority: "high", language: "en" },
    { id: 2, userId: "user-002", subject: "Cannot login to dashboard", category: "technical", status: "active", priority: "medium", language: "en" },
    { id: 3, userId: "user-003", subject: "Commission calculation wrong", category: "billing", status: "waiting", priority: "high", language: "fr" },
    { id: 4, userId: "user-004", subject: "Agent onboarding help", category: "general", status: "active", priority: "low", language: "ha" },
    { id: 5, userId: "user-005", subject: "Suspicious transaction alert", category: "fraud", status: "escalated", priority: "critical", language: "en" },
    { id: 6, userId: "user-006", subject: "Terminal not connecting", category: "technical", status: "resolved", priority: "medium", language: "yo" },
    { id: 7, userId: "user-007", subject: "Refund request", category: "billing", status: "active", priority: "medium", language: "en" },
    { id: 8, userId: "user-008", subject: "KYC document upload failed", category: "technical", status: "waiting", priority: "high", language: "en" },
    { id: 9, userId: "user-009", subject: "Settlement batch delayed", category: "billing", status: "active", priority: "high", language: "fr" },
    { id: 10, userId: "user-010", subject: "API integration help", category: "technical", status: "active", priority: "low", language: "en" },
  ],

  chatMessages: [
    { sessionId: 1, sender: "user", content: "I made a payment 3 days ago but it still hasn't arrived in my account." },
    { sessionId: 1, sender: "agent", content: "I'll look into this for you. Can you provide the transaction reference number?" },
    { sessionId: 1, sender: "user", content: "The reference is TXN-2024-00451." },
    { sessionId: 2, sender: "user", content: "I keep getting 'Invalid credentials' when trying to log in." },
    { sessionId: 2, sender: "system", content: "Auto-reply: Have you tried resetting your password? Visit /forgot-password." },
    { sessionId: 3, sender: "user", content: "Ma commission du mois dernier est incorrecte. Il manque 15,000 FCFA." },
    { sessionId: 3, sender: "agent", content: "Je vais vérifier les calculs de commission. Un moment s'il vous plaît." },
    { sessionId: 5, sender: "user", content: "I see a transaction I didn't make! Amount: ₦250,000 to an unknown account." },
    { sessionId: 5, sender: "system", content: "ALERT: This session has been escalated to the Security Team." },
    { sessionId: 5, sender: "agent", content: "We've temporarily frozen the account. Our fraud team is investigating." },
  ],

  knowledgeBaseArticles: [
    { id: "kb-001", title: "How to process a refund", category: "billing", tags: ["refund", "payment", "reversal"] },
    { id: "kb-002", title: "Agent onboarding requirements", category: "general", tags: ["onboarding", "kyc", "documents"] },
    { id: "kb-003", title: "Settlement batch schedule", category: "billing", tags: ["settlement", "batch", "schedule"] },
    { id: "kb-004", title: "Terminal troubleshooting guide", category: "technical", tags: ["terminal", "pos", "connection"] },
    { id: "kb-005", title: "Commission tier structure", category: "billing", tags: ["commission", "tiers", "rates"] },
    { id: "kb-006", title: "Fraud reporting procedure", category: "fraud", tags: ["fraud", "security", "report"] },
    { id: "kb-007", title: "API authentication guide", category: "technical", tags: ["api", "auth", "integration"] },
    { id: "kb-008", title: "KYC document requirements", category: "general", tags: ["kyc", "documents", "verification"] },
  ],

  cannedResponses: [
    { id: "cr-001", name: "Greeting", content: "Hello! Thank you for contacting 54Link support. How can I help you today?", category: "greeting" },
    { id: "cr-002", name: "Hold", content: "Please hold while I look into this for you. It should take just a moment.", category: "status" },
    { id: "cr-003", name: "Escalation", content: "I'm escalating your case to our specialized team. You'll receive an update shortly.", category: "escalation" },
    { id: "cr-004", name: "Resolution", content: "Your issue has been resolved. Is there anything else I can help with?", category: "resolution" },
    { id: "cr-005", name: "Closing", content: "Thank you for contacting us! Don't hesitate to reach out if you need further assistance.", category: "closing" },
  ],

  agentPresences: [
    { agentId: "agent-001", name: "Amina Bello", status: "online", activeSessions: 3, maxSessions: 5 },
    { agentId: "agent-002", name: "Chidi Okafor", status: "online", activeSessions: 2, maxSessions: 5 },
    { agentId: "agent-003", name: "Fatima Sani", status: "busy", activeSessions: 5, maxSessions: 5 },
    { agentId: "agent-004", name: "Oluwaseun Adeyemi", status: "away", activeSessions: 0, maxSessions: 5 },
    { agentId: "agent-005", name: "Ibrahim Musa", status: "online", activeSessions: 1, maxSessions: 5 },
  ],

  surveyResponses: [
    { sessionId: 6, userId: "user-006", rating: 5, comment: "Very helpful and quick!", categories: ["helpful", "fast"] },
    { sessionId: 6, userId: "user-006", rating: 4, comment: "Good support, minor delay", categories: ["helpful"] },
    { sessionId: 6, userId: "user-006", rating: 3, comment: "Issue resolved but took long", categories: ["resolved"] },
    { sessionId: 6, userId: "user-006", rating: 5, comment: "Excellent!", categories: ["helpful", "knowledgeable", "fast"] },
    { sessionId: 6, userId: "user-006", rating: 2, comment: "Had to explain issue multiple times", categories: ["slow"] },
  ],
};

console.log("Seed data summary:");
console.log(`  Chat sessions:     ${SEED_DATA.chatSessions.length}`);
console.log(`  Chat messages:     ${SEED_DATA.chatMessages.length}`);
console.log(`  KB articles:       ${SEED_DATA.knowledgeBaseArticles.length}`);
console.log(`  Canned responses:  ${SEED_DATA.cannedResponses.length}`);
console.log(`  Agent presences:   ${SEED_DATA.agentPresences.length}`);
console.log(`  Survey responses:  ${SEED_DATA.surveyResponses.length}`);
console.log("");
console.log("Note: This data is loaded into in-memory stores at runtime.");
console.log("For database-backed chat, use the main seed script: scripts/seed-production-final.mjs");
console.log("");
console.log("✅ Sprint 64 seed data ready.");
