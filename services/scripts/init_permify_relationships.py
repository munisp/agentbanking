"""
Initialize Permify Relationships
Remittance Platform V11.0

Creates initial relationships for:
- Organizations
- Agents
- Customers
- Wallets
- Transactions

Author: Manus AI
Date: November 11, 2025
"""

import asyncio
import sys
sys.path.insert(0, "/home/ubuntu/remittance-platform/backend/python-services/shared")

from permify_client import PermifyClient

async def main():
    client = PermifyClient()
    
    print("🔐 Initializing Permify relationships...")
    
    # Organization relationships
    org_relationships = [
        {"entity": "organization", "id": "org-001", "relation": "admin", "subject": "user:admin-001"},
        {"entity": "organization", "id": "org-001", "relation": "member", "subject": "user:agent-001"},
        {"entity": "organization", "id": "org-001", "relation": "member", "subject": "user:agent-002"},
    ]
    
    await client.write_relationships(org_relationships)
    print("✅ Organization relationships created")
    
    # Agent relationships
    agent_relationships = [
        {"entity": "agent", "id": "agent-001", "relation": "owner", "subject": "user:agent-001"},
        {"entity": "agent", "id": "agent-001", "relation": "organization", "subject": "organization:org-001"},
        {"entity": "agent", "id": "agent-002", "relation": "owner", "subject": "user:agent-002"},
        {"entity": "agent", "id": "agent-002", "relation": "supervisor", "subject": "user:agent-001"},
        {"entity": "agent", "id": "agent-002", "relation": "organization", "subject": "organization:org-001"},
    ]
    
    await client.write_relationships(agent_relationships)
    print("✅ Agent relationships created")
    
    # Customer relationships
    customer_relationships = [
        {"entity": "customer", "id": "customer-001", "relation": "owner", "subject": "user:customer-001"},
        {"entity": "customer", "id": "customer-001", "relation": "agent", "subject": "agent:agent-001"},
        {"entity": "customer", "id": "customer-001", "relation": "organization", "subject": "organization:org-001"},
    ]
    
    await client.write_relationships(customer_relationships)
    print("✅ Customer relationships created")
    
    # Wallet relationships
    wallet_relationships = [
        {"entity": "wallet", "id": "wallet-agent-001", "relation": "owner", "subject": "user:agent-001"},
        {"entity": "wallet", "id": "wallet-agent-001", "relation": "agent", "subject": "agent:agent-001"},
        {"entity": "wallet", "id": "wallet-customer-001", "relation": "owner", "subject": "user:customer-001"},
    ]
    
    await client.write_relationships(wallet_relationships)
    print("✅ Wallet relationships created")
    
    print("\n✅ All relationships initialized successfully!")
    
    # Test permission checks
    print("\n🧪 Testing permission checks...")
    
    # Test 1: Agent can view own wallet
    allowed = await client.check_permission(
        entity="wallet",
        entity_id="wallet-agent-001",
        permission="view_balance",
        subject="user:agent-001"
    )
    print(f"Test 1 - Agent can view own wallet: {allowed}")
    
    # Test 2: Admin can view agent
    allowed = await client.check_permission(
        entity="agent",
        entity_id="agent-001",
        permission="view",
        subject="user:admin-001"
    )
    print(f"Test 2 - Admin can view agent: {allowed}")
    
    # Test 3: Supervisor can manage downline
    allowed = await client.check_permission(
        entity="agent",
        entity_id="agent-002",
        permission="manage_downline",
        subject="user:agent-001"
    )
    print(f"Test 3 - Supervisor can manage downline: {allowed}")
    
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
