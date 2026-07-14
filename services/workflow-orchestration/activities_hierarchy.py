"""
Agent Hierarchy & Override Commission Activity Implementations
Remittance Platform V11.0

This module implements all activities for the Agent Hierarchy Workflow.

Author: Manus AI
Date: November 11, 2025
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from temporalio import activity
import asyncpg
import json

# Database connection (injected via dependency injection)
db_pool: Optional[asyncpg.Pool] = None


# ============================================================================
# Activity 1: Build Agent Hierarchy Tree
# ============================================================================

@activity.defn(name="build_agent_hierarchy_tree")
async def build_agent_hierarchy_tree(agent_id: str) -> Dict:
    """
    Build complete hierarchy tree for an agent (all downline agents).
    
    Uses recursive CTE to traverse the hierarchy efficiently.
    
    Args:
        agent_id: ID of the root agent
    
    Returns:
        Hierarchy tree with all downline agents
    """
    async with db_pool.acquire() as conn:
        # Use recursive CTE to build hierarchy tree
        hierarchy = await conn.fetch(
            """
            WITH RECURSIVE hierarchy_tree AS (
                -- Base case: the root agent
                SELECT 
                    agent_id,
                    upline_agent_id,
                    hierarchy_level,
                    1 as depth,
                    ARRAY[agent_id] as path
                FROM agent_hierarchy
                WHERE agent_id = $1
                
                UNION ALL
                
                -- Recursive case: all downline agents
                SELECT 
                    ah.agent_id,
                    ah.upline_agent_id,
                    ah.hierarchy_level,
                    ht.depth + 1,
                    ht.path || ah.agent_id
                FROM agent_hierarchy ah
                INNER JOIN hierarchy_tree ht ON ah.upline_agent_id = ht.agent_id
                WHERE ht.depth < 5  -- Max 5 levels
            )
            SELECT 
                ht.*,
                u.full_name,
                u.phone_number,
                u.email,
                tp.total_downline_agents,
                tp.total_override_commission
            FROM hierarchy_tree ht
            LEFT JOIN users u ON ht.agent_id = u.id
            LEFT JOIN team_performance tp ON ht.agent_id = tp.agent_id
            ORDER BY ht.depth, ht.agent_id
            """,
            agent_id
        )
        
        # Convert to tree structure
        tree = {
            "root_agent_id": agent_id,
            "total_downline": len(hierarchy) - 1,  # Exclude root
            "max_depth": max([h['depth'] for h in hierarchy]) if hierarchy else 0,
            "agents": [
                {
                    "agent_id": h['agent_id'],
                    "upline_agent_id": h['upline_agent_id'],
                    "hierarchy_level": h['hierarchy_level'],
                    "depth": h['depth'],
                    "full_name": h['full_name'],
                    "phone_number": h['phone_number'],
                    "total_downline_agents": h['total_downline_agents'] or 0,
                    "total_override_commission": float(h['total_override_commission'] or 0),
                }
                for h in hierarchy
            ]
        }
        
        activity.logger.info(f"Built hierarchy tree for agent {agent_id}: {tree['total_downline']} downline agents")
        return tree


# ============================================================================
# Activity 2: Add Agent to Hierarchy
# ============================================================================

@activity.defn(name="add_agent_to_hierarchy")
async def add_agent_to_hierarchy(upline_agent_id: str, new_agent_id: str) -> Dict:
    """
    Add a new agent to the hierarchy under an upline agent.
    
    Args:
        upline_agent_id: ID of the upline agent (recruiter)
        new_agent_id: ID of the new agent being recruited
    
    Returns:
        Hierarchy information for the new agent
    """
    async with db_pool.acquire() as conn:
        # Get upline agent's hierarchy level
        upline = await conn.fetchrow(
            "SELECT hierarchy_level FROM agent_hierarchy WHERE agent_id = $1",
            upline_agent_id
        )
        
        if not upline:
            # Upline agent not in hierarchy, add them as root (level 0)
            await conn.execute(
                """
                INSERT INTO agent_hierarchy (agent_id, upline_agent_id, hierarchy_level, recruitment_date)
                VALUES ($1, NULL, 0, NOW())
                ON CONFLICT (agent_id) DO NOTHING
                """,
                upline_agent_id
            )
            new_hierarchy_level = 1
        else:
            new_hierarchy_level = upline['hierarchy_level'] + 1
        
        # Add new agent to hierarchy
        await conn.execute(
            """
            INSERT INTO agent_hierarchy (agent_id, upline_agent_id, hierarchy_level, recruitment_date)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (agent_id) DO UPDATE SET
                upline_agent_id = EXCLUDED.upline_agent_id,
                hierarchy_level = EXCLUDED.hierarchy_level,
                recruitment_date = EXCLUDED.recruitment_date
            """,
            new_agent_id,
            upline_agent_id,
            new_hierarchy_level
        )
        
        # Get total direct recruits for upline agent
        total_direct_recruits = await conn.fetchval(
            """
            SELECT COUNT(*) FROM agent_hierarchy 
            WHERE upline_agent_id = $1
            """,
            upline_agent_id
        )
        
        # Initialize team performance record
        await conn.execute(
            """
            INSERT INTO team_performance (agent_id, total_downline_agents, level_1_count, total_override_commission)
            VALUES ($1, 0, 0, 0)
            ON CONFLICT (agent_id) DO NOTHING
            """,
            new_agent_id
        )
        
        # Update upline agent's team performance
        await conn.execute(
            """
            UPDATE team_performance 
            SET total_downline_agents = total_downline_agents + 1,
                level_1_count = level_1_count + 1,
                last_updated = NOW()
            WHERE agent_id = $1
            """,
            upline_agent_id
        )
        
        activity.logger.info(
            f"Added agent {new_agent_id} to hierarchy under {upline_agent_id} at level {new_hierarchy_level}"
        )
        
        return {
            "hierarchy_level": new_hierarchy_level,
            "total_direct_recruits": total_direct_recruits
        }


# ============================================================================
# Activity 3: Get Upline Agents
# ============================================================================

@activity.defn(name="get_upline_agents")
async def get_upline_agents(agent_id: str, max_levels: int = 5) -> List[Dict]:
    """
    Get all upline agents up to max_levels.
    
    Args:
        agent_id: ID of the downline agent
        max_levels: Maximum number of levels to traverse (default 5)
    
    Returns:
        List of upline agents with their levels
    """
    async with db_pool.acquire() as conn:
        # Use recursive CTE to get upline agents
        upline_agents = await conn.fetch(
            """
            WITH RECURSIVE upline_tree AS (
                -- Base case: the agent itself
                SELECT 
                    agent_id,
                    upline_agent_id,
                    hierarchy_level,
                    0 as level_distance
                FROM agent_hierarchy
                WHERE agent_id = $1
                
                UNION ALL
                
                -- Recursive case: upline agents
                SELECT 
                    ah.agent_id,
                    ah.upline_agent_id,
                    ah.hierarchy_level,
                    ut.level_distance + 1
                FROM agent_hierarchy ah
                INNER JOIN upline_tree ut ON ah.agent_id = ut.upline_agent_id
                WHERE ut.level_distance < $2
            )
            SELECT 
                agent_id,
                level_distance as level
            FROM upline_tree
            WHERE level_distance > 0  -- Exclude the agent itself
            ORDER BY level_distance
            """,
            agent_id,
            max_levels
        )
        
        result = [
            {
                "agent_id": agent['agent_id'],
                "level": agent['level']
            }
            for agent in upline_agents
        ]
        
        activity.logger.info(f"Found {len(result)} upline agents for {agent_id}")
        return result


# ============================================================================
# Activity 4: Calculate Override Commission
# ============================================================================

@activity.defn(name="calculate_override_commission")
async def calculate_override_commission(
    agent_id: str,
    override_amount: float,
    downline_agent_id: str,
    level: int
) -> Dict:
    """
    Calculate override commission with monthly cap enforcement.
    
    Args:
        agent_id: ID of the upline agent receiving commission
        override_amount: Calculated override amount
        downline_agent_id: ID of the downline agent
        level: Level distance (1-5)
    
    Returns:
        Actual override amount after cap enforcement
    """
    MONTHLY_CAP = 50000.0  # ₦50,000 per month
    
    async with db_pool.acquire() as conn:
        # Get total override commission this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_this_month = await conn.fetchval(
            """
            SELECT COALESCE(SUM(override_amount), 0)
            FROM override_commissions
            WHERE upline_agent_id = $1
            AND created_at >= $2
            """,
            agent_id,
            month_start
        )
        
        # Calculate remaining cap
        remaining_cap = MONTHLY_CAP - float(total_this_month)
        
        if remaining_cap <= 0:
            activity.logger.warning(f"Agent {agent_id} has reached monthly cap of ₦{MONTHLY_CAP}")
            return {
                "actual_amount": 0.0,
                "is_capped": True,
                "remaining_cap": 0.0
            }
        
        # Apply cap
        actual_amount = min(override_amount, remaining_cap)
        is_capped = actual_amount < override_amount
        
        if is_capped:
            activity.logger.info(
                f"Override commission capped for agent {agent_id}: "
                f"₦{override_amount:.2f} → ₦{actual_amount:.2f}"
            )
        
        return {
            "actual_amount": actual_amount,
            "is_capped": is_capped,
            "remaining_cap": remaining_cap - actual_amount
        }


# ============================================================================
# Activity 5: Validate Commission Eligibility
# ============================================================================

@activity.defn(name="validate_commission_eligibility")
async def validate_commission_eligibility(agent_id: str) -> bool:
    """
    Validate that an agent is eligible for override commissions.
    
    Eligibility criteria:
    - Agent must be active (at least 10 transactions in last 30 days)
    - Agent must maintain minimum balance (₦10,000 float)
    - Agent must be verified (KYC complete)
    
    Args:
        agent_id: ID of the agent to validate
    
    Returns:
        True if eligible, False otherwise
    """
    async with db_pool.acquire() as conn:
        # Check if agent exists and is verified
        agent = await conn.fetchrow(
            """
            SELECT 
                kyc_status,
                account_status,
                balance
            FROM users
            WHERE id = $1 AND user_type = 'agent'
            """,
            agent_id
        )
        
        if not agent:
            activity.logger.warning(f"Agent {agent_id} not found")
            return False
        
        # Check KYC status
        if agent['kyc_status'] != 'verified':
            activity.logger.warning(f"Agent {agent_id} KYC not verified")
            return False
        
        # Check account status
        if agent['account_status'] != 'active':
            activity.logger.warning(f"Agent {agent_id} account not active")
            return False
        
        # Check minimum balance (₦10,000)
        if float(agent['balance']) < 10000.0:
            activity.logger.warning(f"Agent {agent_id} balance below minimum")
            return False
        
        # Check activity (at least 10 transactions in last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        transaction_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE user_id = $1
            AND created_at >= $2
            """,
            agent_id,
            thirty_days_ago
        )
        
        if transaction_count < 10:
            activity.logger.warning(
                f"Agent {agent_id} insufficient activity: {transaction_count} transactions"
            )
            return False
        
        activity.logger.info(f"Agent {agent_id} is eligible for override commissions")
        return True


# ============================================================================
# Activity 6: Credit Override Commission
# ============================================================================

@activity.defn(name="credit_override_commission")
async def credit_override_commission(
    agent_id: str,
    amount: float,
    commission_id: str,
    commission_type: str
) -> bool:
    """
    Credit override commission to agent's account.
    
    Args:
        agent_id: ID of the agent to credit
        amount: Amount to credit
        commission_id: Unique commission ID
        commission_type: Type of commission (override_commission, recruitment_bonus)
    
    Returns:
        True if successful
    """
    async with db_pool.acquire() as conn:
        # Credit to agent's wallet
        await conn.execute(
            """
            UPDATE user_wallets 
            SET balance = balance + $1,
                updated_at = NOW()
            WHERE user_id = $2
            """,
            amount,
            agent_id
        )
        
        # Record transaction
        await conn.execute(
            """
            INSERT INTO transactions 
            (id, user_id, type, amount, description, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            f"txn-{commission_id}",
            agent_id,
            commission_type,
            amount,
            f"{commission_type.replace('_', ' ').title()}"
        )
        
        activity.logger.info(f"Credited ₦{amount:.2f} to agent {agent_id} ({commission_type})")
        return True


# ============================================================================
# Activity 7: Update Hierarchy Analytics
# ============================================================================

@activity.defn(name="update_hierarchy_analytics")
async def update_hierarchy_analytics(agent_id: str, event_type: str) -> Dict:
    """
    Update hierarchy analytics for an agent.
    
    Args:
        agent_id: ID of the agent
        event_type: Type of event (recruitment, override_commission)
    
    Returns:
        Updated analytics
    """
    async with db_pool.acquire() as conn:
        if event_type == "recruitment":
            # Update recruitment count
            await conn.execute(
                """
                UPDATE team_performance
                SET total_downline_agents = total_downline_agents + 1,
                    last_updated = NOW()
                WHERE agent_id = $1
                """,
                agent_id
            )
        
        elif event_type == "override_commission":
            # Recalculate total override commission
            total_override = await conn.fetchval(
                """
                SELECT COALESCE(SUM(override_amount), 0)
                FROM override_commissions
                WHERE upline_agent_id = $1
                """,
                agent_id
            )
            
            await conn.execute(
                """
                UPDATE team_performance
                SET total_override_commission = $1,
                    last_updated = NOW()
                WHERE agent_id = $2
                """,
                total_override,
                agent_id
            )
        
        # Get updated analytics
        analytics = await conn.fetchrow(
            """
            SELECT 
                total_downline_agents,
                level_1_count,
                level_2_count,
                level_3_count,
                total_override_commission
            FROM team_performance
            WHERE agent_id = $1
            """,
            agent_id
        )
        
        return {
            "total_downline_agents": analytics['total_downline_agents'],
            "level_1_count": analytics['level_1_count'],
            "total_override_commission": float(analytics['total_override_commission'])
        }


# ============================================================================
# Activity 8: Send Override Notification
# ============================================================================

@activity.defn(name="send_override_notification")
async def send_override_notification(
    agent_id: str,
    notification_type: str,
    metadata: dict
) -> bool:
    """
    Send notification about override commission or recruitment.
    
    Args:
        agent_id: ID of the agent to notify
        notification_type: Type of notification (recruitment, override_commission)
        metadata: Additional metadata
    
    Returns:
        True if successful
    """
    async with db_pool.acquire() as conn:
        # Get agent info
        agent = await conn.fetchrow(
            "SELECT full_name, phone_number, email FROM users WHERE id = $1",
            agent_id
        )
        
        if not agent:
            return False
        
        # Create notification message
        if notification_type == "recruitment":
            new_agent_id = metadata.get('new_agent_id')
            hierarchy_level = metadata.get('hierarchy_level')
            recruitment_bonus = metadata.get('recruitment_bonus', 0)
            total_recruits = metadata.get('total_recruits', 0)
            
            message = (
                f"Congratulations! You've recruited a new agent (Level {hierarchy_level}). "
                f"Total recruits: {total_recruits}."
            )
            
            if recruitment_bonus > 0:
                message += f" You've earned a recruitment bonus of ₦{recruitment_bonus:.2f}!"
        
        elif notification_type == "override_commission":
            downline_level = metadata.get('downline_level')
            override_amount = metadata.get('override_amount')
            transaction_type = metadata.get('transaction_type')
            
            message = (
                f"You've earned ₦{override_amount:.2f} in override commission "
                f"from your Level {downline_level} downline agent's {transaction_type} transaction."
            )
        
        # In production: integrate with notification service
        activity.logger.info(f"Notification sent to agent {agent_id}: {message}")
        
        return True


# ============================================================================
# Activity 9: Get Team Performance
# ============================================================================

@activity.defn(name="get_team_performance")
async def get_team_performance(agent_id: str, time_period: str) -> Dict:
    """
    Get team performance metrics for an agent.
    
    Args:
        agent_id: ID of the agent
        time_period: Time period (daily, weekly, monthly, all_time)
    
    Returns:
        Team performance metrics
    """
    # Calculate time range
    now = datetime.utcnow()
    if time_period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_period == "weekly":
        start_date = now - timedelta(days=7)
    elif time_period == "monthly":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:  # all_time
        start_date = datetime(2020, 1, 1)
    
    async with db_pool.acquire() as conn:
        # Get all downline agents
        downline_agents = await conn.fetch(
            """
            WITH RECURSIVE downline_tree AS (
                SELECT agent_id, 1 as level
                FROM agent_hierarchy
                WHERE upline_agent_id = $1
                
                UNION ALL
                
                SELECT ah.agent_id, dt.level + 1
                FROM agent_hierarchy ah
                INNER JOIN downline_tree dt ON ah.upline_agent_id = dt.agent_id
                WHERE dt.level < 5
            )
            SELECT agent_id, level FROM downline_tree
            """,
            agent_id
        )
        
        downline_ids = [agent['agent_id'] for agent in downline_agents]
        
        if not downline_ids:
            return {
                "total_downline_agents": 0,
                "total_transactions": 0,
                "total_transaction_volume": 0.0,
                "total_override_commission": 0.0,
                "by_level": {}
            }
        
        # Get transaction metrics
        metrics = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_transactions,
                COALESCE(SUM(amount), 0) as total_volume
            FROM transactions
            WHERE user_id = ANY($1)
            AND created_at >= $2
            """,
            downline_ids,
            start_date
        )
        
        # Get override commission
        override_commission = await conn.fetchval(
            """
            SELECT COALESCE(SUM(override_amount), 0)
            FROM override_commissions
            WHERE upline_agent_id = $1
            AND created_at >= $2
            """,
            agent_id,
            start_date
        )
        
        # Group by level
        by_level = {}
        for agent in downline_agents:
            level = agent['level']
            if level not in by_level:
                by_level[level] = 0
            by_level[level] += 1
        
        return {
            "total_downline_agents": len(downline_ids),
            "total_transactions": metrics['total_transactions'],
            "total_transaction_volume": float(metrics['total_volume']),
            "total_override_commission": float(override_commission),
            "by_level": by_level,
            "time_period": time_period
        }


# ============================================================================
# Activity 10: Send Team Message
# ============================================================================

@activity.defn(name="send_team_message")
async def send_team_message(
    sender_agent_id: str,
    hierarchy_tree: Dict,
    target_level: Optional[int],
    message: str
) -> Dict:
    """
    Send message to downline agents.
    
    Args:
        sender_agent_id: ID of the sender agent
        hierarchy_tree: Hierarchy tree from build_agent_hierarchy_tree
        target_level: Target level (None = all levels, 1 = only L1, etc.)
        message: Message content
    
    Returns:
        Message delivery result
    """
    # Filter agents by target level
    if target_level:
        target_agents = [
            agent for agent in hierarchy_tree['agents']
            if agent['depth'] == target_level
        ]
    else:
        target_agents = [
            agent for agent in hierarchy_tree['agents']
            if agent['agent_id'] != sender_agent_id  # Exclude sender
        ]
    
    message_id = f"msg-{sender_agent_id}-{datetime.utcnow().timestamp()}"
    
    async with db_pool.acquire() as conn:
        # Store message
        await conn.execute(
            """
            INSERT INTO team_messages 
            (id, sender_agent_id, target_level, message, created_at, recipients_count)
            VALUES ($1, $2, $3, $4, NOW(), $5)
            """,
            message_id,
            sender_agent_id,
            target_level,
            message,
            len(target_agents)
        )
        
        # In production: send actual notifications via SMS/push
        activity.logger.info(
            f"Message {message_id} sent to {len(target_agents)} agents "
            f"(level {target_level or 'all'})"
        )
    
    return {
        "message_id": message_id,
        "recipients_count": len(target_agents),
        "delivery_status": "sent"
    }


# ============================================================================
# Activity 11: Generate Team Report
# ============================================================================

@activity.defn(name="generate_team_report")
async def generate_team_report(
    agent_id: str,
    hierarchy_tree: Dict,
    team_performance: Dict,
    report_period: str
) -> Dict:
    """
    Generate team performance report (PDF).
    
    Args:
        agent_id: ID of the agent
        hierarchy_tree: Hierarchy tree
        team_performance: Team performance metrics
        report_period: Report period
    
    Returns:
        Report generation result
    """
    report_id = f"report-{agent_id}-{datetime.utcnow().timestamp()}"
    
    # In production: generate actual PDF report
    # For now, create JSON report
    report_data = {
        "report_id": report_id,
        "agent_id": agent_id,
        "generated_at": datetime.utcnow().isoformat(),
        "report_period": report_period,
        "hierarchy_summary": {
            "total_downline": hierarchy_tree['total_downline'],
            "max_depth": hierarchy_tree['max_depth'],
        },
        "performance_summary": team_performance,
    }
    
    # In production: upload to S3 and return URL
    report_url = f"https://reports.remittance.app/{report_id}.pdf"
    
    activity.logger.info(f"Generated team report {report_id} for agent {agent_id}")
    
    return {
        "report_id": report_id,
        "report_url": report_url,
        "generated_at": datetime.utcnow().isoformat()
    }
