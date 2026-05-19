// @ts-nocheck — Sprint 69: Unified seed orchestrator
/**
 * seed-all.mjs — Unified seed data orchestrator
 * Runs all seed scripts in dependency order to populate a fresh database
 * with production-ready demo data.
 * 
 * Usage: node scripts/seed-all.mjs [--env production|staging|development]
 */
import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const env = process.argv.includes('--env') 
  ? process.argv[process.argv.indexOf('--env') + 1] 
  : 'development';

console.log(`\n🌱 54Link POS Shell — Unified Seed Orchestrator`);
console.log(`   Environment: ${env}`);
console.log(`   Started: ${new Date().toISOString()}\n`);

const seedScripts = [
  // Phase 1: Core entities (no dependencies)
  { name: 'Core Data', script: 'seed-data.mjs', description: 'Users, roles, permissions, tenants' },
  { name: 'Comprehensive', script: 'seed-comprehensive.mjs', description: 'Merchants, agents, devices, terminals' },
  
  // Phase 2: Business data (depends on core)
  { name: 'Sprint 10', script: 'seed-sprint10.mjs', description: 'Transactions, settlements, float' },
  { name: 'Sprint 26', script: 'seed-sprint26.mjs', description: 'Disputes, compliance, fraud alerts' },
  { name: 'Sprint 42', script: 'seed-data-sprint42.mjs', description: 'Commission tiers, agent territories' },
  
  // Phase 3: Advanced features (depends on business data)
  { name: 'Sprint 46', script: 'seed-sprint46.mjs', description: 'Webhooks, notifications, audit logs' },
  { name: 'Sprint 49', script: 'seed-sprint49.mjs', description: 'KYC records, regulatory reports' },
  { name: 'Sprint 50', script: 'seed-sprint50.mjs', description: 'Multi-currency wallets, cross-border' },
  { name: 'Sprint 53', script: 'seed-sprint53.mjs', description: 'Gamification, loyalty programs' },
  
  // Phase 4: Integration data
  { name: 'Production Final', script: 'seed-production-final.mjs', description: 'Production-grade demo data' },
  { name: 'Security', script: 'seed-security.mjs', description: 'Security policies, RBAC rules' },
  { name: 'Chat', script: 'seed-sprint64-chat.mjs', description: 'Chat channels, messages' },
  
  // Phase 5: Integration test data
  { name: 'Integration', script: '../seed-integration.mjs', description: 'Integration test fixtures' },
];

let passed = 0;
let failed = 0;
let skipped = 0;

for (const { name, script, description } of seedScripts) {
  const scriptPath = path.join(__dirname, script);
  
  try {
    // Check if script exists
    const fs = await import('fs');
    if (!fs.existsSync(scriptPath)) {
      console.log(`  ⏭  ${name}: ${script} not found, skipping`);
      skipped++;
      continue;
    }
    
    console.log(`  🔄 ${name}: ${description}...`);
    execSync(`node ${scriptPath}`, {
      cwd: path.join(__dirname, '..'),
      stdio: 'pipe',
      timeout: 60000,
      env: { ...process.env, NODE_ENV: env }
    });
    console.log(`  ✅ ${name}: Complete`);
    passed++;
  } catch (error) {
    console.log(`  ⚠️  ${name}: Failed (${error.message?.slice(0, 80)})`);
    failed++;
  }
}

console.log(`\n${'='.repeat(50)}`);
console.log(`Seed Summary: ${passed} passed, ${failed} failed, ${skipped} skipped`);
console.log(`Finished: ${new Date().toISOString()}`);
console.log(`${'='.repeat(50)}\n`);

if (failed > 0) {
  console.log('⚠️  Some seeds failed. This is expected if the database is not connected.');
  console.log('   Run with DATABASE_URL set to a live PostgreSQL instance.');
}

process.exit(failed > 0 ? 1 : 0);
