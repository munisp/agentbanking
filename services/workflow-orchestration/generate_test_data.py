"""
Test Data Generation Script for Load Testing
Remittance Platform V11.0

Generates 15,000 agents with hierarchical relationships for load testing.

Usage:
    python3 generate_test_data.py --agents 15000 --super-agents 500

Author: Manus AI
Date: November 11, 2025
"""

import os
import sys
import random
import argparse
from datetime import datetime, timedelta
import asyncpg


# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://workflow_service:password@localhost:5432/remittance_platform"
)


async def generate_test_data(total_agents: int, super_agents: int):
    """
    Generate test data for load testing.
    
    Args:
        total_agents: Total number of agents to create
        super_agents: Number of super agents (with >10 recruits)
    """
    print(f"Generating test data: {total_agents} agents, {super_agents} super agents")
    
    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Clear existing test data
        print("Clearing existing test data...")
        await conn.execute("DELETE FROM agent_hierarchy WHERE agent_id LIKE 'agent-%'")
        await conn.execute("DELETE FROM users WHERE id LIKE 'agent-%'")
        
        # Generate users
        print(f"Generating {total_agents} users...")
        users = []
        for i in range(1, total_agents + 1):
            user_id = f"agent-{i:05d}"
            users.append({
                "id": user_id,
                "phone_number": f"+234{7000000000 + i}",
                "full_name": f"Test Agent {i}",
                "email": f"agent{i}@test.com",
                "kyc_verified": True,
                "account_status": "active",
                "created_at": datetime.now() - timedelta(days=random.randint(1, 365))
            })
        
        # Batch insert users
        await conn.executemany(
            """
            INSERT INTO users (id, phone_number, full_name, email, kyc_verified, account_status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO NOTHING
            """,
            [(u["id"], u["phone_number"], u["full_name"], u["email"], 
              u["kyc_verified"], u["account_status"], u["created_at"]) 
             for u in users]
        )
        print(f"✅ Created {total_agents} users")
        
        # Generate hierarchy
        print(f"Generating hierarchy with {super_agents} super agents...")
        hierarchy = []
        
        # Create super agents (root level, level 0)
        for i in range(1, super_agents + 1):
            agent_id = f"agent-{i:05d}"
            hierarchy.append({
                "agent_id": agent_id,
                "upline_agent_id": None,
                "hierarchy_level": 0,
                "recruitment_date": datetime.now() - timedelta(days=random.randint(30, 365))
            })
        
        # Distribute remaining agents under super agents
        remaining_agents = total_agents - super_agents
        agents_per_super = remaining_agents // super_agents
        
        current_agent_idx = super_agents + 1
        
        for super_agent_idx in range(1, super_agents + 1):
            super_agent_id = f"agent-{super_agent_idx:05d}"
            
            # Create 10-20 level 1 agents under each super agent
            level_1_count = random.randint(10, 20)
            level_1_agents = []
            
            for _ in range(level_1_count):
                if current_agent_idx > total_agents:
                    break
                    
                agent_id = f"agent-{current_agent_idx:05d}"
                hierarchy.append({
                    "agent_id": agent_id,
                    "upline_agent_id": super_agent_id,
                    "hierarchy_level": 1,
                    "recruitment_date": datetime.now() - timedelta(days=random.randint(7, 180))
                })
                level_1_agents.append(agent_id)
                current_agent_idx += 1
            
            # Create level 2-5 agents under level 1 agents
            for level_1_agent in level_1_agents:
                # 50% chance to have downline
                if random.random() < 0.5 and current_agent_idx <= total_agents:
                    level_2_count = random.randint(1, 5)
                    level_2_agents = []
                    
                    for _ in range(level_2_count):
                        if current_agent_idx > total_agents:
                            break
                            
                        agent_id = f"agent-{current_agent_idx:05d}"
                        hierarchy.append({
                            "agent_id": agent_id,
                            "upline_agent_id": level_1_agent,
                            "hierarchy_level": 2,
                            "recruitment_date": datetime.now() - timedelta(days=random.randint(1, 90))
                        })
                        level_2_agents.append(agent_id)
                        current_agent_idx += 1
                    
                    # Create level 3 agents (30% chance)
                    for level_2_agent in level_2_agents:
                        if random.random() < 0.3 and current_agent_idx <= total_agents:
                            level_3_count = random.randint(1, 3)
                            
                            for _ in range(level_3_count):
                                if current_agent_idx > total_agents:
                                    break
                                    
                                agent_id = f"agent-{current_agent_idx:05d}"
                                hierarchy.append({
                                    "agent_id": agent_id,
                                    "upline_agent_id": level_2_agent,
                                    "hierarchy_level": 3,
                                    "recruitment_date": datetime.now() - timedelta(days=random.randint(1, 30))
                                })
                                current_agent_idx += 1
        
        # Batch insert hierarchy
        await conn.executemany(
            """
            INSERT INTO agent_hierarchy (agent_id, upline_agent_id, hierarchy_level, recruitment_date)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (agent_id) DO NOTHING
            """,
            [(h["agent_id"], h["upline_agent_id"], h["hierarchy_level"], h["recruitment_date"]) 
             for h in hierarchy]
        )
        print(f"✅ Created {len(hierarchy)} hierarchy relationships")
        
        # Initialize team performance for super agents
        print("Initializing team performance...")
        for i in range(1, super_agents + 1):
            agent_id = f"agent-{i:05d}"
            await conn.execute(
                """
                INSERT INTO team_performance (agent_id, total_downline_agents, level_1_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (agent_id) DO NOTHING
                """,
                agent_id, random.randint(10, 20), random.randint(10, 20)
            )
        print(f"✅ Initialized team performance for {super_agents} super agents")
        
        # Generate sample wallets
        print("Creating wallets...")
        for i in range(1, total_agents + 1):
            user_id = f"agent-{i:05d}"
            balance = random.uniform(10000, 100000)  # ₦10,000 - ₦100,000
            await conn.execute(
                """
                INSERT INTO user_wallets (user_id, balance, currency)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO NOTHING
                """,
                user_id, balance, "NGN"
            )
        print(f"✅ Created {total_agents} wallets")
        
        # Print summary
        print("\n" + "=" * 80)
        print("TEST DATA GENERATION COMPLETE")
        print("=" * 80)
        print(f"Total Agents: {total_agents}")
        print(f"Super Agents (root level): {super_agents}")
        print(f"Hierarchy Relationships: {len(hierarchy)}")
        print(f"Average Hierarchy Depth: {sum(h['hierarchy_level'] for h in hierarchy) / len(hierarchy):.2f}")
        print("=" * 80)
        
    finally:
        await conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate test data for load testing")
    parser.add_argument(
        "--agents",
        type=int,
        default=15000,
        help="Total number of agents to create"
    )
    parser.add_argument(
        "--super-agents",
        type=int,
        default=500,
        help="Number of super agents (with >10 recruits)"
    )
    
    args = parser.parse_args()
    
    import asyncio
    asyncio.run(generate_test_data(args.agents, args.super_agents))


if __name__ == "__main__":
    main()
