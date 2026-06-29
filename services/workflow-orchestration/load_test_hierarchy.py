"""
Load Testing Script for Agent Hierarchy & Override Commission Workflow
Remittance Platform V11.0

This script implements comprehensive load testing using Locust framework.

Usage:
    # Run baseline load test
    locust -f load_test_hierarchy.py --scenario baseline --host http://localhost:8000

    # Run all scenarios
    python3 load_test_hierarchy.py --all-scenarios

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import time
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, List
import asyncio
from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging
from temporalio.client import Client
from workflows_hierarchy import (
    AgentRecruitmentWorkflow,
    OverrideCommissionWorkflow,
    TeamPerformanceQueryWorkflow,
    TeamMessagingWorkflow,
    TeamReportGenerationWorkflow,
    AgentRecruitmentInput,
    OverrideCommissionInput,
    TeamPerformanceInput,
    TeamMessageInput,
)


# ============================================================================
# Configuration
# ============================================================================

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "workflow-orchestration")

# Test data
AGENT_IDS = [f"agent-{i:05d}" for i in range(1, 15001)]  # 15,000 agents
SUPER_AGENT_IDS = [f"agent-{i:05d}" for i in range(1, 501)]  # 500 super agents


# ============================================================================
# Locust User Classes
# ============================================================================

class HierarchyWorkflowUser(HttpUser):
    """
    Locust user simulating agent hierarchy workflow interactions.
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.temporal_client = None
    
    def on_start(self):
        """Initialize Temporal client when user starts."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.temporal_client = loop.run_until_complete(
            Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
        )
    
    @task(10)  # 10% of requests
    def recruit_agent(self):
        """Test agent recruitment workflow."""
        upline_agent_id = random.choice(AGENT_IDS)
        new_agent_id = f"agent-test-{int(time.time() * 1000000)}"
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.temporal_client.execute_workflow(
                    AgentRecruitmentWorkflow.run,
                    AgentRecruitmentInput(
                        upline_agent_id=upline_agent_id,
                        new_agent_id=new_agent_id,
                        recruitment_metadata={}
                    ),
                    id=f"test-recruitment-{new_agent_id}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                )
            )
            
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="AgentRecruitment",
                response_time=duration,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="AgentRecruitment",
                response_time=duration,
                response_length=0,
                exception=e,
                context={}
            )
    
    @task(70)  # 70% of requests
    def calculate_override_commission(self):
        """Test override commission workflow."""
        downline_agent_id = random.choice(AGENT_IDS)
        downline_transaction_id = f"txn-{int(time.time() * 1000000)}"
        downline_commission_amount = random.uniform(100, 1000)
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.temporal_client.execute_workflow(
                    OverrideCommissionWorkflow.run,
                    OverrideCommissionInput(
                        downline_agent_id=downline_agent_id,
                        downline_transaction_id=downline_transaction_id,
                        downline_commission_amount=downline_commission_amount,
                        transaction_type="cash_in"
                    ),
                    id=f"test-override-{downline_transaction_id}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                )
            )
            
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="OverrideCommission",
                response_time=duration,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="OverrideCommission",
                response_time=duration,
                response_length=0,
                exception=e,
                context={}
            )
    
    @task(15)  # 15% of requests
    def query_team_performance(self):
        """Test team performance query workflow."""
        agent_id = random.choice(SUPER_AGENT_IDS)  # Use super agents for better data
        time_period = random.choice(["daily", "weekly", "monthly"])
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.temporal_client.execute_workflow(
                    TeamPerformanceQueryWorkflow.run,
                    TeamPerformanceInput(
                        agent_id=agent_id,
                        time_period=time_period
                    ),
                    id=f"test-performance-{agent_id}-{int(time.time() * 1000)}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                )
            )
            
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamPerformanceQuery",
                response_time=duration,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamPerformanceQuery",
                response_time=duration,
                response_length=0,
                exception=e,
                context={}
            )
    
    @task(3)  # 3% of requests
    def send_team_message(self):
        """Test team messaging workflow."""
        sender_agent_id = random.choice(SUPER_AGENT_IDS)
        target_level = random.choice([None, 1, 2])  # None = all levels
        message = "Great job this month! Keep up the good work."
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.temporal_client.execute_workflow(
                    TeamMessagingWorkflow.run,
                    TeamMessageInput(
                        sender_agent_id=sender_agent_id,
                        target_level=target_level,
                        message=message
                    ),
                    id=f"test-message-{sender_agent_id}-{int(time.time() * 1000)}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                )
            )
            
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamMessaging",
                response_time=duration,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamMessaging",
                response_time=duration,
                response_length=0,
                exception=e,
                context={}
            )
    
    @task(2)  # 2% of requests
    def generate_team_report(self):
        """Test team report generation workflow."""
        agent_id = random.choice(SUPER_AGENT_IDS)
        report_period = random.choice(["daily", "weekly", "monthly"])
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.temporal_client.execute_workflow(
                    TeamReportGenerationWorkflow.run,
                    agent_id,
                    report_period,
                    id=f"test-report-{agent_id}-{int(time.time() * 1000)}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                )
            )
            
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamReportGeneration",
                response_time=duration,
                response_length=len(str(result)),
                exception=None,
                context={}
            )
        except Exception as e:
            duration = int((time.time() - start_time) * 1000)
            events.request.fire(
                request_type="workflow",
                name="TeamReportGeneration",
                response_time=duration,
                response_length=0,
                exception=e,
                context={}
            )


# ============================================================================
# Load Test Scenarios
# ============================================================================

def run_baseline_load_test():
    """
    Scenario 1: Baseline Load Test
    50 workflows/second for 60 minutes
    """
    print("=" * 80)
    print("SCENARIO 1: Baseline Load Test")
    print("=" * 80)
    print("Target: 50 workflows/second for 60 minutes")
    print("Starting load test...")
    
    setup_logging("INFO")
    env = Environment(user_classes=[HierarchyWorkflowUser])
    env.create_local_runner()
    
    # Start load test
    env.runner.start(user_count=50, spawn_rate=10)
    
    # Run for 60 minutes
    time.sleep(3600)
    
    # Stop load test
    env.runner.quit()
    
    # Print stats
    print("\n" + "=" * 80)
    print("BASELINE LOAD TEST RESULTS")
    print("=" * 80)
    env.stats.print_stats()


def run_peak_load_test():
    """
    Scenario 2: Peak Load Test
    150 workflows/second for 60 minutes
    """
    print("=" * 80)
    print("SCENARIO 2: Peak Load Test")
    print("=" * 80)
    print("Target: 150 workflows/second for 60 minutes")
    print("Starting load test...")
    
    setup_logging("INFO")
    env = Environment(user_classes=[HierarchyWorkflowUser])
    env.create_local_runner()
    
    # Start load test
    env.runner.start(user_count=150, spawn_rate=15)
    
    # Run for 60 minutes
    time.sleep(3600)
    
    # Stop load test
    env.runner.quit()
    
    # Print stats
    print("\n" + "=" * 80)
    print("PEAK LOAD TEST RESULTS")
    print("=" * 80)
    env.stats.print_stats()


def run_stress_test():
    """
    Scenario 3: Stress Test
    300 workflows/second for 90 minutes
    """
    print("=" * 80)
    print("SCENARIO 3: Stress Test")
    print("=" * 80)
    print("Target: 300 workflows/second for 90 minutes")
    print("Starting load test...")
    
    setup_logging("INFO")
    env = Environment(user_classes=[HierarchyWorkflowUser])
    env.create_local_runner()
    
    # Start load test
    env.runner.start(user_count=300, spawn_rate=15)
    
    # Run for 90 minutes
    time.sleep(5400)
    
    # Stop load test
    env.runner.quit()
    
    # Print stats
    print("\n" + "=" * 80)
    print("STRESS TEST RESULTS")
    print("=" * 80)
    env.stats.print_stats()


def run_spike_test():
    """
    Scenario 5: Spike Test
    Alternating between 20 and 200 workflows/second every 5 minutes
    """
    print("=" * 80)
    print("SCENARIO 5: Spike Test")
    print("=" * 80)
    print("Pattern: 20 → 200 → 20 → 200 (every 5 minutes)")
    print("Starting load test...")
    
    setup_logging("INFO")
    env = Environment(user_classes=[HierarchyWorkflowUser])
    env.create_local_runner()
    
    # Run 6 spikes (60 minutes total)
    for i in range(6):
        # Low load (20 workflows/second)
        print(f"\nSpike {i+1}/6: Low load (20 workflows/second)")
        env.runner.start(user_count=20, spawn_rate=10)
        time.sleep(300)  # 5 minutes
        
        # High load (200 workflows/second)
        print(f"Spike {i+1}/6: High load (200 workflows/second)")
        env.runner.start(user_count=200, spawn_rate=50)
        time.sleep(300)  # 5 minutes
    
    # Stop load test
    env.runner.quit()
    
    # Print stats
    print("\n" + "=" * 80)
    print("SPIKE TEST RESULTS")
    print("=" * 80)
    env.stats.print_stats()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point for load testing."""
    parser = argparse.ArgumentParser(description="Load test Agent Hierarchy workflows")
    parser.add_argument(
        "--scenario",
        choices=["baseline", "peak", "stress", "spike", "all"],
        default="baseline",
        help="Load test scenario to run"
    )
    parser.add_argument(
        "--all-scenarios",
        action="store_true",
        help="Run all load test scenarios sequentially"
    )
    
    args = parser.parse_args()
    
    if args.all_scenarios or args.scenario == "all":
        print("Running all load test scenarios...")
        run_baseline_load_test()
        time.sleep(300)  # 5 minute break
        run_peak_load_test()
        time.sleep(300)  # 5 minute break
        run_stress_test()
        time.sleep(300)  # 5 minute break
        run_spike_test()
    elif args.scenario == "baseline":
        run_baseline_load_test()
    elif args.scenario == "peak":
        run_peak_load_test()
    elif args.scenario == "stress":
        run_stress_test()
    elif args.scenario == "spike":
        run_spike_test()
    
    print("\n" + "=" * 80)
    print("LOAD TESTING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
