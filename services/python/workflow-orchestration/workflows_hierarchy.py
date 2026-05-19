"""
Agent Hierarchy & Override Commission Workflow Implementation
Remittance Platform V11.0

This module implements the Agent Hierarchy Workflow for MLM-style agent recruitment.

Author: Manus AI
Date: November 11, 2025
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional, Dict
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities (will be implemented in activities_hierarchy.py)
with workflow.unsafe.imports_passed_through():
    from activities_hierarchy import (
        build_agent_hierarchy_tree,
        add_agent_to_hierarchy,
        get_upline_agents,
        calculate_override_commission,
        validate_commission_eligibility,
        credit_override_commission,
        update_hierarchy_analytics,
        send_override_notification,
        get_team_performance,
        send_team_message,
        generate_team_report,
    )


@dataclass
class AgentRecruitmentInput:
    """Input for agent recruitment."""
    upline_agent_id: str
    new_agent_id: str
    recruitment_metadata: dict


@dataclass
class OverrideCommissionInput:
    """Input for override commission calculation."""
    downline_agent_id: str
    downline_transaction_id: str
    downline_commission_amount: float
    transaction_type: str


@dataclass
class TeamPerformanceInput:
    """Input for team performance query."""
    agent_id: str
    time_period: str  # daily, weekly, monthly, all_time


@dataclass
class TeamMessageInput:
    """Input for team messaging."""
    sender_agent_id: str
    target_level: Optional[int]  # None = all levels, 1 = only L1, etc.
    message: str


@dataclass
class AgentRecruitmentOutput:
    """Output for agent recruitment."""
    success: bool
    new_agent_id: str
    upline_agent_id: str
    hierarchy_level: int
    recruitment_bonus: float


@dataclass
class OverrideCommissionOutput:
    """Output for override commission."""
    success: bool
    override_commission_id: str
    upline_commissions: List[Dict]  # List of {agent_id, level, amount}
    total_override_paid: float


# ============================================================================
# Workflow 1: Agent Recruitment Workflow
# ============================================================================

@workflow.defn(name="AgentRecruitmentWorkflow")
class AgentRecruitmentWorkflow:
    """
    Workflow for recruiting new agents into hierarchy.
    
    Steps:
    1. Validate upline agent eligibility
    2. Add new agent to hierarchy
    3. Build hierarchy tree path
    4. Calculate recruitment bonus
    5. Credit recruitment bonus
    6. Send recruitment notifications
    7. Update hierarchy analytics
    
    Duration: < 10 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, input: AgentRecruitmentInput) -> AgentRecruitmentOutput:
        """Execute agent recruitment workflow."""
        
        # Step 1: Validate upline agent eligibility
        is_eligible = await workflow.execute_activity(
            validate_commission_eligibility,
            args=[input.upline_agent_id],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if not is_eligible:
            return AgentRecruitmentOutput(
                success=False,
                new_agent_id=input.new_agent_id,
                upline_agent_id=input.upline_agent_id,
                hierarchy_level=0,
                recruitment_bonus=0.0,
            )
        
        # Step 2: Add new agent to hierarchy
        hierarchy_result = await workflow.execute_activity(
            add_agent_to_hierarchy,
            args=[input.upline_agent_id, input.new_agent_id],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        hierarchy_level = hierarchy_result["hierarchy_level"]
        
        # Step 3: Calculate recruitment bonus (₦5,000 for every 10 recruits)
        total_recruits = hierarchy_result["total_direct_recruits"]
        recruitment_bonus = 0.0
        
        if total_recruits % 10 == 0:
            recruitment_bonus = 5000.0
            
            # Credit recruitment bonus
            await workflow.execute_activity(
                credit_override_commission,
                args=[
                    input.upline_agent_id,
                    recruitment_bonus,
                    f"recruitment-bonus-{input.new_agent_id}",
                    "recruitment_bonus",
                ],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        
        # Step 4: Send recruitment notification
        await workflow.execute_activity(
            send_override_notification,
            args=[
                input.upline_agent_id,
                "recruitment",
                {
                    "new_agent_id": input.new_agent_id,
                    "hierarchy_level": hierarchy_level,
                    "recruitment_bonus": recruitment_bonus,
                    "total_recruits": total_recruits,
                },
            ],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        # Step 5: Update hierarchy analytics
        await workflow.execute_activity(
            update_hierarchy_analytics,
            args=[input.upline_agent_id, "recruitment"],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return AgentRecruitmentOutput(
            success=True,
            new_agent_id=input.new_agent_id,
            upline_agent_id=input.upline_agent_id,
            hierarchy_level=hierarchy_level,
            recruitment_bonus=recruitment_bonus,
        )


# ============================================================================
# Workflow 2: Override Commission Workflow
# ============================================================================

@workflow.defn(name="OverrideCommissionWorkflow")
class OverrideCommissionWorkflow:
    """
    Workflow for calculating and distributing override commissions.
    
    Steps:
    1. Get upline agents (up to 5 levels)
    2. Calculate override commission for each level
    3. Validate eligibility for each upline agent
    4. Credit override commission to eligible agents
    5. Send override commission notifications
    6. Update hierarchy analytics
    
    Duration: < 15 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, input: OverrideCommissionInput) -> OverrideCommissionOutput:
        """Execute override commission workflow."""
        
        # Step 1: Get upline agents (up to 5 levels)
        upline_agents = await workflow.execute_activity(
            get_upline_agents,
            args=[input.downline_agent_id, 5],  # Max 5 levels
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        if not upline_agents:
            return OverrideCommissionOutput(
                success=True,
                override_commission_id="",
                upline_commissions=[],
                total_override_paid=0.0,
            )
        
        # Step 2: Calculate override commission for each level
        override_percentages = {
            1: 0.10,  # 10% for Level 1 (direct recruit)
            2: 0.05,  # 5% for Level 2
            3: 0.02,  # 2% for Level 3
            4: 0.01,  # 1% for Level 4
            5: 0.005, # 0.5% for Level 5
        }
        
        upline_commissions = []
        total_override_paid = 0.0
        
        for upline in upline_agents:
            agent_id = upline["agent_id"]
            level = upline["level"]
            
            # Validate eligibility
            is_eligible = await workflow.execute_activity(
                validate_commission_eligibility,
                args=[agent_id],
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
            
            if not is_eligible:
                continue
            
            # Calculate override amount
            override_percentage = override_percentages.get(level, 0.0)
            override_amount = input.downline_commission_amount * override_percentage
            
            # Check monthly cap (₦50,000 per month)
            commission_result = await workflow.execute_activity(
                calculate_override_commission,
                args=[
                    agent_id,
                    override_amount,
                    input.downline_agent_id,
                    level,
                ],
                start_to_close_timeout=timedelta(seconds=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            
            actual_override_amount = commission_result["actual_amount"]
            
            if actual_override_amount > 0:
                # Credit override commission
                await workflow.execute_activity(
                    credit_override_commission,
                    args=[
                        agent_id,
                        actual_override_amount,
                        f"override-{input.downline_transaction_id}-{agent_id}",
                        "override_commission",
                    ],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                
                upline_commissions.append({
                    "agent_id": agent_id,
                    "level": level,
                    "override_percentage": override_percentage * 100,
                    "override_amount": actual_override_amount,
                    "capped": commission_result["is_capped"],
                })
                
                total_override_paid += actual_override_amount
                
                # Send override commission notification
                await workflow.execute_activity(
                    send_override_notification,
                    args=[
                        agent_id,
                        "override_commission",
                        {
                            "downline_agent_id": input.downline_agent_id,
                            "downline_level": level,
                            "override_amount": actual_override_amount,
                            "transaction_type": input.transaction_type,
                        },
                    ],
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                
                # Update hierarchy analytics
                await workflow.execute_activity(
                    update_hierarchy_analytics,
                    args=[agent_id, "override_commission"],
                    start_to_close_timeout=timedelta(seconds=5),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
        
        return OverrideCommissionOutput(
            success=True,
            override_commission_id=f"override-{input.downline_transaction_id}",
            upline_commissions=upline_commissions,
            total_override_paid=total_override_paid,
        )


# ============================================================================
# Workflow 3: Team Performance Query Workflow
# ============================================================================

@workflow.defn(name="TeamPerformanceQueryWorkflow")
class TeamPerformanceQueryWorkflow:
    """
    Workflow for querying team performance metrics.
    
    Steps:
    1. Build hierarchy tree for agent
    2. Get performance metrics for all downline agents
    3. Aggregate team performance
    4. Return performance dashboard data
    
    Duration: < 10 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, input: TeamPerformanceInput) -> Dict:
        """Execute team performance query workflow."""
        
        # Step 1: Build hierarchy tree
        hierarchy_tree = await workflow.execute_activity(
            build_agent_hierarchy_tree,
            args=[input.agent_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 2: Get team performance metrics
        team_performance = await workflow.execute_activity(
            get_team_performance,
            args=[input.agent_id, input.time_period],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return {
            "success": True,
            "agent_id": input.agent_id,
            "hierarchy_tree": hierarchy_tree,
            "team_performance": team_performance,
            "time_period": input.time_period,
        }


# ============================================================================
# Workflow 4: Team Messaging Workflow
# ============================================================================

@workflow.defn(name="TeamMessagingWorkflow")
class TeamMessagingWorkflow:
    """
    Workflow for sending messages to downline agents.
    
    Steps:
    1. Get target downline agents (by level)
    2. Validate message content
    3. Send message to all target agents
    4. Track message delivery
    
    Duration: < 30 seconds
    Success Rate: > 95%
    """
    
    @workflow.run
    async def run(self, input: TeamMessageInput) -> Dict:
        """Execute team messaging workflow."""
        
        # Step 1: Build hierarchy tree to get downline agents
        hierarchy_tree = await workflow.execute_activity(
            build_agent_hierarchy_tree,
            args=[input.sender_agent_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 2: Send message to downline agents
        message_result = await workflow.execute_activity(
            send_team_message,
            args=[
                input.sender_agent_id,
                hierarchy_tree,
                input.target_level,
                input.message,
            ],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        
        return {
            "success": True,
            "message_id": message_result["message_id"],
            "recipients_count": message_result["recipients_count"],
            "delivery_status": message_result["delivery_status"],
        }


# ============================================================================
# Workflow 5: Team Report Generation Workflow
# ============================================================================

@workflow.defn(name="TeamReportGenerationWorkflow")
class TeamReportGenerationWorkflow:
    """
    Workflow for generating team performance reports.
    
    Steps:
    1. Build hierarchy tree
    2. Get team performance metrics
    3. Generate PDF report
    4. Send report to agent
    
    Duration: < 60 seconds
    Success Rate: > 99%
    """
    
    @workflow.run
    async def run(self, agent_id: str, report_period: str) -> Dict:
        """Execute team report generation workflow."""
        
        # Step 1: Build hierarchy tree
        hierarchy_tree = await workflow.execute_activity(
            build_agent_hierarchy_tree,
            args=[agent_id],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 2: Get team performance
        team_performance = await workflow.execute_activity(
            get_team_performance,
            args=[agent_id, report_period],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        # Step 3: Generate report
        report_result = await workflow.execute_activity(
            generate_team_report,
            args=[agent_id, hierarchy_tree, team_performance, report_period],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        
        return {
            "success": True,
            "report_id": report_result["report_id"],
            "report_url": report_result["report_url"],
            "generated_at": report_result["generated_at"],
        }

