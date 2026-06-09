# Phase 2 Deployment Guide: Agent Hierarchy & Override Commission Workflow

**Remittance Platform V11.0**  
**Date:** November 11, 2025  
**Author:** Manus AI  
**Status:** Production Ready

---

## Overview

This guide provides step-by-step instructions for deploying the Agent Hierarchy & Override Commission Workflow to production. The workflow enables multi-level marketing (MLM) functionality with automated override commission distribution.

---

## Prerequisites

### System Requirements
- **Python:** 3.11+
- **PostgreSQL:** 14+
- **Redis:** 7+
- **Temporal Server:** 1.20+
- **Docker:** 20.10+ (optional, for containerized deployment)

### Dependencies
```bash
pip3 install temporalio asyncpg redis
```

### Database Access
- PostgreSQL connection string with admin privileges
- Database: `remittance_platform`
- User: `workflow_service` (with appropriate permissions)

---

## Deployment Steps

### Step 1: Database Migration

Run the database migration script to create all required tables:

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d remittance_platform

# Run migration script
\i /home/ubuntu/remittance-platform/backend/python-services/workflow-orchestration/migrations/003_agent_hierarchy.sql

# Verify tables created
\dt agent_hierarchy override_commissions team_performance recruitment_bonuses team_messages team_reports

# Verify materialized views
\dm hierarchy_leaderboard monthly_override_summary

# Verify functions
\df calculate_total_downline get_upline_path refresh_hierarchy_leaderboard refresh_monthly_override_summary
```

**Expected Output:**
```
Agent Hierarchy migration completed successfully
```

### Step 2: Deploy Workflow Files

Copy workflow and activity files to the production server:

```bash
# Copy workflow definitions
cp workflows_hierarchy.py /opt/remittance-platform/workflows/

# Copy activity implementations
cp activities_hierarchy.py /opt/remittance-platform/activities/

# Set permissions
chmod 644 /opt/remittance-platform/workflows/workflows_hierarchy.py
chmod 644 /opt/remittance-platform/activities/activities_hierarchy.py
```

### Step 3: Configure Environment Variables

Add the following environment variables to your `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://workflow_service:password@localhost:5432/remittance_platform
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10

# Temporal Configuration
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=workflow-orchestration

# Override Commission Configuration
OVERRIDE_COMMISSION_MONTHLY_CAP=50000.00  # ₦50,000
OVERRIDE_COMMISSION_LEVEL_1_PCT=10.0      # 10%
OVERRIDE_COMMISSION_LEVEL_2_PCT=5.0       # 5%
OVERRIDE_COMMISSION_LEVEL_3_PCT=2.0       # 2%
OVERRIDE_COMMISSION_LEVEL_4_PCT=1.0       # 1%
OVERRIDE_COMMISSION_LEVEL_5_PCT=0.5       # 0.5%

# Recruitment Bonus Configuration
RECRUITMENT_BONUS_AMOUNT=5000.00          # ₦5,000
RECRUITMENT_BONUS_MILESTONE=10            # Every 10 recruits

# Eligibility Criteria
MIN_AGENT_BALANCE=10000.00                # ₦10,000
MIN_MONTHLY_TRANSACTIONS=10               # 10 transactions
```

### Step 4: Start Temporal Worker

Start the Temporal worker to execute workflows and activities:

```bash
# Navigate to workflow directory
cd /opt/remittance-platform

# Start worker (production mode)
python3 -m workflow_orchestration.worker \
    --task-queue workflow-orchestration \
    --max-concurrent-workflows 100 \
    --max-concurrent-activities 200 \
    --log-level INFO

# Or use systemd service
sudo systemctl start temporal-worker-hierarchy
sudo systemctl enable temporal-worker-hierarchy
```

**Systemd Service File** (`/etc/systemd/system/temporal-worker-hierarchy.service`):
```ini
[Unit]
Description=Temporal Worker for Agent Hierarchy Workflow
After=network.target postgresql.service redis.service temporal.service

[Service]
Type=simple
User=workflow
WorkingDirectory=/opt/remittance-platform
Environment="PATH=/usr/local/bin:/usr/bin"
ExecStart=/usr/bin/python3 -m workflow_orchestration.worker --task-queue workflow-orchestration
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 5: Verify Deployment

Run verification tests to ensure everything is working:

```bash
# Run integration tests
cd /home/ubuntu/remittance-platform/backend/python-services/workflow-orchestration
pytest test_final_3_workflows.py::TestAgentHierarchyWorkflow -v

# Check worker logs
sudo journalctl -u temporal-worker-hierarchy -f

# Verify database connections
psql -h localhost -U workflow_service -d remittance_platform -c "SELECT COUNT(*) FROM agent_hierarchy;"
```

### Step 6: Initialize Scheduled Jobs

Set up cron jobs for periodic tasks:

```bash
# Edit crontab
crontab -e

# Add the following jobs:

# Refresh hierarchy leaderboard every 5 minutes
*/5 * * * * psql -h localhost -U workflow_service -d remittance_platform -c "SELECT refresh_hierarchy_leaderboard();"

# Refresh monthly override summary every hour
0 * * * * psql -h localhost -U workflow_service -d remittance_platform -c "SELECT refresh_monthly_override_summary();"

# Generate team reports daily at midnight
0 0 * * * python3 /opt/remittance-platform/scripts/generate_daily_reports.py
```

---

## Configuration

### Override Commission Percentages

The override commission structure is configured as follows:

| Level | Percentage | Example (₦1,000 commission) |
|-------|------------|----------------------------|
| Level 1 (Direct) | 10% | ₦100 |
| Level 2 | 5% | ₦50 |
| Level 3 | 2% | ₦20 |
| Level 4 | 1% | ₦10 |
| Level 5 | 0.5% | ₦5 |

**Monthly Cap:** ₦50,000 per agent

### Eligibility Criteria

Agents must meet the following criteria to receive override commissions:

- ✅ **KYC Status:** Verified
- ✅ **Account Status:** Active
- ✅ **Minimum Balance:** ₦10,000
- ✅ **Monthly Activity:** At least 10 transactions in the last 30 days

### Recruitment Bonuses

- **Bonus Amount:** ₦5,000
- **Milestone:** Every 10 successful recruits
- **Eligibility:** Same as override commission

---

## Monitoring

### Key Metrics to Monitor

1. **Workflow Execution Metrics**
   - Workflow start rate (workflows/second)
   - Workflow success rate (%)
   - Workflow duration (seconds)
   - Activity failure rate (%)

2. **Business Metrics**
   - Total agents in hierarchy
   - Average hierarchy depth
   - Total override commission paid (daily/monthly)
   - Top 10 agents by downline count
   - Monthly cap reached count

3. **System Metrics**
   - Database connection pool usage
   - Redis cache hit rate
   - Worker CPU/memory usage
   - Query performance (slow queries)

### Monitoring Queries

```sql
-- Total agents in hierarchy
SELECT COUNT(*) FROM agent_hierarchy;

-- Average hierarchy depth
SELECT AVG(hierarchy_level) FROM agent_hierarchy;

-- Total override commission paid today
SELECT SUM(override_amount) 
FROM override_commissions 
WHERE created_at >= CURRENT_DATE;

-- Top 10 agents by downline count
SELECT * FROM hierarchy_leaderboard LIMIT 10;

-- Agents who reached monthly cap
SELECT upline_agent_id, SUM(override_amount) as total
FROM override_commissions
WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY upline_agent_id
HAVING SUM(override_amount) >= 50000
ORDER BY total DESC;
```

### Alerts

Set up alerts for the following conditions:

- Override commission monthly cap reached (>80% of ₦50,000)
- Workflow failure rate > 5%
- Database connection pool exhausted
- Worker process down
- Slow query detected (>5 seconds)

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest test_final_3_workflows.py::TestAgentHierarchyWorkflow -v

# Run specific test
pytest test_final_3_workflows.py::TestAgentHierarchyWorkflow::test_agent_recruitment_success -v
```

### Integration Tests

```bash
# Test agent recruitment
python3 -c "
from temporalio.client import Client
from workflows_hierarchy import AgentRecruitmentWorkflow, AgentRecruitmentInput
import asyncio

async def test():
    client = await Client.connect('localhost:7233')
    result = await client.execute_workflow(
        AgentRecruitmentWorkflow.run,
        AgentRecruitmentInput(
            upline_agent_id='agent-001',
            new_agent_id='agent-test-001',
            recruitment_metadata={}
        ),
        id='test-recruitment-001',
        task_queue='workflow-orchestration'
    )
    print(result)

asyncio.run(test())
"
```

### Load Tests

```bash
# Test with 100 concurrent workflows
python3 scripts/load_test_hierarchy.py --workflows 100 --duration 60
```

---

## Rollback Procedure

If issues are detected after deployment:

### Step 1: Stop Worker

```bash
sudo systemctl stop temporal-worker-hierarchy
```

### Step 2: Rollback Database

```bash
# Connect to database
psql -h localhost -U postgres -d remittance_platform

# Drop tables (WARNING: This will delete all data)
DROP TABLE IF EXISTS team_reports CASCADE;
DROP TABLE IF EXISTS team_messages CASCADE;
DROP TABLE IF EXISTS recruitment_bonuses CASCADE;
DROP TABLE IF EXISTS team_performance CASCADE;
DROP TABLE IF EXISTS override_commissions CASCADE;
DROP TABLE IF EXISTS agent_hierarchy CASCADE;

# Drop materialized views
DROP MATERIALIZED VIEW IF EXISTS monthly_override_summary;
DROP MATERIALIZED VIEW IF EXISTS hierarchy_leaderboard;

# Drop functions
DROP FUNCTION IF EXISTS update_team_performance_on_override();
DROP FUNCTION IF EXISTS update_team_performance_on_recruitment();
DROP FUNCTION IF EXISTS get_upline_path(UUID);
DROP FUNCTION IF EXISTS calculate_total_downline(UUID);
DROP FUNCTION IF EXISTS refresh_monthly_override_summary();
DROP FUNCTION IF EXISTS refresh_hierarchy_leaderboard();
```

### Step 3: Remove Workflow Files

```bash
rm /opt/remittance-platform/workflows/workflows_hierarchy.py
rm /opt/remittance-platform/activities/activities_hierarchy.py
```

### Step 4: Restart Previous Version

```bash
sudo systemctl start temporal-worker-hierarchy
```

---

## Troubleshooting

### Issue 1: Workflow Execution Fails

**Symptoms:**
- Workflows fail with "Activity not found" error

**Solution:**
```bash
# Verify worker is running
sudo systemctl status temporal-worker-hierarchy

# Check worker logs
sudo journalctl -u temporal-worker-hierarchy -n 100

# Restart worker
sudo systemctl restart temporal-worker-hierarchy
```

### Issue 2: Database Connection Errors

**Symptoms:**
- "Connection pool exhausted" errors

**Solution:**
```bash
# Increase database pool size in .env
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=20

# Restart worker
sudo systemctl restart temporal-worker-hierarchy
```

### Issue 3: Slow Query Performance

**Symptoms:**
- Workflows taking >30 seconds to complete

**Solution:**
```sql
-- Analyze query performance
EXPLAIN ANALYZE 
SELECT * FROM agent_hierarchy WHERE upline_agent_id = 'agent-001';

-- Rebuild indexes
REINDEX TABLE agent_hierarchy;
REINDEX TABLE override_commissions;

-- Refresh materialized views
SELECT refresh_hierarchy_leaderboard();
SELECT refresh_monthly_override_summary();
```

### Issue 4: Override Commission Not Credited

**Symptoms:**
- Override commission calculated but not credited to agent

**Solution:**
```sql
-- Check override commission records
SELECT * FROM override_commissions 
WHERE upline_agent_id = 'agent-001' 
ORDER BY created_at DESC LIMIT 10;

-- Check agent wallet balance
SELECT balance FROM user_wallets WHERE user_id = 'agent-001';

-- Check transaction records
SELECT * FROM transactions 
WHERE user_id = 'agent-001' 
AND type = 'override_commission'
ORDER BY created_at DESC LIMIT 10;

-- Manually credit if needed (use with caution)
UPDATE user_wallets 
SET balance = balance + 100.00 
WHERE user_id = 'agent-001';
```

---

## Performance Optimization

### Database Optimization

```sql
-- Vacuum and analyze tables
VACUUM ANALYZE agent_hierarchy;
VACUUM ANALYZE override_commissions;
VACUUM ANALYZE team_performance;

-- Update statistics
ANALYZE agent_hierarchy;
ANALYZE override_commissions;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

### Caching Strategy

```python
# Cache hierarchy tree for 5 minutes
import redis
r = redis.Redis(host='localhost', port=6379, db=0)

# Cache key pattern
cache_key = f"hierarchy:tree:{agent_id}"

# Get from cache
cached_tree = r.get(cache_key)
if cached_tree:
    return json.loads(cached_tree)

# If not in cache, build tree and cache it
tree = await build_agent_hierarchy_tree(agent_id)
r.setex(cache_key, 300, json.dumps(tree))  # 5 minutes TTL
```

---

## Security Considerations

### Access Control

- ✅ Ensure database user has minimum required permissions
- ✅ Use connection pooling with SSL/TLS
- ✅ Encrypt sensitive data at rest
- ✅ Implement rate limiting on API endpoints

### Audit Logging

```sql
-- Create audit log table
CREATE TABLE IF NOT EXISTS hierarchy_audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    agent_id UUID NOT NULL,
    event_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Log all hierarchy changes
CREATE OR REPLACE FUNCTION log_hierarchy_changes()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO hierarchy_audit_log (event_type, agent_id, event_data)
    VALUES (TG_OP, NEW.agent_id, row_to_json(NEW));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_log_hierarchy_changes
AFTER INSERT OR UPDATE ON agent_hierarchy
FOR EACH ROW
EXECUTE FUNCTION log_hierarchy_changes();
```

---

## Support

For issues or questions, contact:
- **Email:** support@remittance.app
- **Slack:** #agent-hierarchy-workflow
- **Documentation:** https://docs.remittance.app/hierarchy

---

**Deployment Status:** ✅ Ready for Production  
**Last Updated:** November 11, 2025  
**Version:** 1.0.0

