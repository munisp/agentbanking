#!/usr/bin/env python3
"""
Test script to send transaction notifications to mobile agents
Usage: python test_notification.py <agent_id>
"""

import sys
import json
import requests
from datetime import datetime

# Configuration
NOTIFICATION_SERVICE_URL = "http://localhost:8094"  # Update with your service URL
DEFAULT_TENANT_ID = "bpmgd"


def send_test_notification(agent_id, amount=5000.0, sender="Test User"):
    """
    Send a test transaction notification to an agent
    """
    print(f"\n🔔 Sending test notification to agent: {agent_id}")
    print(f"   Amount: ₦{amount:,.2f}")
    print(f"   Sender: {sender}")

    # Prepare transaction payload
    payload = {
        "transaction_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "agent_id": agent_id,
        "tenant_id": DEFAULT_TENANT_ID,
        "amount": amount,
        "transaction_type": "credit",
        "sender_name": sender,
        "account_number": f"ACC{agent_id[:6].upper()}",
    }

    try:
        # Send notification via HTTP endpoint
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/v1/transaction/notify",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-tenant-id": DEFAULT_TENANT_ID,
            },
            timeout=10,
        )

        response.raise_for_status()
        result = response.json()

        print(f"\n✅ Notification sent successfully!")
        print(f"   Notification ID: {result.get('notification_id')}")
        print(f"   Status: {result.get('status')}")
        print(f"\n   The agent should receive a beep on their mobile app! 📱🔊")

        return result

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error sending notification: {e}")
        if hasattr(e.response, "text"):
            print(f"   Response: {e.response.text}")
        return None


def send_dapr_event(agent_id, amount=5000.0, sender="Test User"):
    """
    Send notification by publishing a Dapr event (simulates payment service)
    """
    print(f"\n📤 Publishing Dapr event for agent: {agent_id}")

    # Prepare event data in the format that payment service uses
    event_data = {
        "transaction_id": f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "amount": str(amount),
        "payee": agent_id,  # In real implementation, this would be mapped to agent_id
        "payer": sender,
        "tenant_id": DEFAULT_TENANT_ID,
        "ledger_id": "1",
        "currency": "NGN",
        "note": "Test transaction",
        "status": "SUCCESS",
        "completed_at": datetime.now().isoformat(),
    }

    try:
        # Publish to Dapr pubsub (requires Dapr sidecar running)
        response = requests.post(
            "http://localhost:3500/v1.0/publish/pubsub/transaction_initiated",
            json={"data": event_data},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        response.raise_for_status()
        print(f"✅ Dapr event published successfully!")
        print(f"   The notification service should pick this up and notify the agent.")

        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ Error publishing Dapr event: {e}")
        print(f"   Make sure Dapr sidecar is running on port 3500")
        return False


def check_health():
    """Check if notification service is running"""
    try:
        response = requests.get(f"{NOTIFICATION_SERVICE_URL}/health", timeout=5)
        data = response.json()

        print(f"\n🏥 Notification Service Health Check:")
        print(f"   Status: {data.get('status')}")
        print(f"   WebSocket Connections: {data.get('websocket_connections', 0)}")
        print(f"   MQTT Connected: {data.get('mqtt_connected', False)}")

        return data.get("status") == "healthy"

    except requests.exceptions.RequestException as e:
        print(
            f"\n❌ Cannot connect to notification service at {NOTIFICATION_SERVICE_URL}"
        )
        print(f"   Error: {e}")
        print(f"   Make sure the service is running!")
        return False


def main():
    """Main function"""
    print("=" * 60)
    print("   📱 Mobile Agent Notification Test Script")
    print("=" * 60)

    # Check service health
    if not check_health():
        sys.exit(1)

    # Get agent ID from command line or use default
    if len(sys.argv) > 1:
        agent_id = sys.argv[1]
    else:
        print("\nUsage: python test_notification.py <agent_id>")
        agent_id = input("Enter agent ID (keycloak ID): ").strip()

        if not agent_id:
            print("❌ Agent ID is required!")
            sys.exit(1)

    # Get amount and sender (optional)
    amount = 5000.0
    if len(sys.argv) > 2:
        try:
            amount = float(sys.argv[2])
        except ValueError:
            print(f"⚠️  Invalid amount, using default: ₦{amount}")

    sender = "Test Sender"
    if len(sys.argv) > 3:
        sender = sys.argv[3]

    print(f"\n{'=' * 60}")
    print(f"   Test Notification Details")
    print(f"{'=' * 60}")

    # Send notification via HTTP endpoint
    send_test_notification(agent_id, amount, sender)

    # Ask if user wants to test Dapr event too
    print(f"\n{'=' * 60}")
    test_dapr = (
        input("\nDo you want to test Dapr event publishing too? (y/N): ")
        .strip()
        .lower()
    )

    if test_dapr == "y":
        send_dapr_event(agent_id, amount, sender)

    print(f"\n{'=' * 60}")
    print("   Test complete! Check the mobile app for notifications.")
    print("=" * 60)


if __name__ == "__main__":
    main()
