"""
Seed script to populate transaction ledger with test data for account 4172458952
"""

import os
import sys
import uuid
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from database.setup import SessionFactory
from models.transaction import Transaction
from utils.enums import TransactionStatus, CurrencyEnum

# Test account number
TEST_ACCOUNT = "4172458952"
TENANT_ID = "54agent-agent-banking"
LEDGER_ID = str(uuid.uuid4())  # Generate a ledger ID for agent banking

# Common Nigerian names for counterparties
NIGERIAN_NAMES = [
    "Adebayo Ogunleye",
    "Chioma Nwankwo",
    "Emeka Okoro",
    "Folake Adeleke",
    "Ibrahim Musa",
    "Jumoke Adeyemi",
    "Kemi Okonkwo",
    "Lekan Balogun",
    "Ngozi Eze",
    "Oluwaseun Ajayi",
    "Patience Okafor",
    "Rasheed Lawal",
    "Sade Babatunde",
    "Tunde Olaniyan",
    "Uche Obi",
    "Victoria Nwosu",
    "Yakubu Ahmed",
    "Zainab Hassan",
    "Akin Fashola",
    "Blessing Udo",
]

# Transaction types and typical amounts
TRANSACTION_TYPES = [
    {"type": "airtime_purchase", "min": 100, "max": 5000, "note": "Airtime purchase"},
    {"type": "data_bundle", "min": 500, "max": 10000, "note": "Data bundle purchase"},
    {"type": "transfer", "min": 1000, "max": 50000, "note": "Bank transfer"},
    {"type": "bill_payment", "min": 2000, "max": 25000, "note": "Bill payment"},
    {"type": "withdrawal", "min": 5000, "max": 100000, "note": "Cash withdrawal"},
    {"type": "deposit", "min": 10000, "max": 200000, "note": "Cash deposit"},
    {"type": "commission", "min": 50, "max": 5000, "note": "Agent commission"},
    {"type": "float_topup", "min": 50000, "max": 500000, "note": "Float top-up"},
]


# Nigerian bank account number patterns (10 digits)
def generate_account_number():
    """Generate realistic Nigerian bank account number"""
    return f"{random.randint(1000000000, 9999999999)}"


def generate_transaction_id():
    """Generate realistic transaction ID"""
    prefix = random.choice(["TXN", "PAY", "TRF", "DEP", "WDR"])
    timestamp = datetime.now().strftime("%Y%m%d")
    suffix = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return f"{prefix}{timestamp}{suffix}"


def seed_transactions():
    """Seed transaction ledger with mock data"""
    session = SessionFactory()

    try:
        print(f"🌱 Starting transaction seed for account {TEST_ACCOUNT}...")
        print(f"📋 Tenant ID: {TENANT_ID}")
        print(f"📒 Ledger ID: {LEDGER_ID}\n")

        transactions = []
        now = datetime.now()

        # Generate 80 transactions over the past 90 days
        for i in range(80):
            # Random timestamp within past 90 days
            days_ago = random.randint(0, 90)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            timestamp = now - timedelta(
                days=days_ago, hours=hours_ago, minutes=minutes_ago
            )

            # Select transaction type
            tx_type = random.choice(TRANSACTION_TYPES)
            amount = random.randint(tx_type["min"], tx_type["max"])

            # Determine if test account is payer or payee (60% payer, 40% payee)
            is_payer = random.random() < 0.6

            # Generate counterparty details
            counterparty_name = random.choice(NIGERIAN_NAMES)
            counterparty_account = generate_account_number()

            # Determine status (80% success, 10% pending, 8% failed, 2% reversed)
            status_roll = random.random()
            if status_roll < 0.80:
                status = TransactionStatus.SUCCESS
                completed_at = timestamp
            elif status_roll < 0.90:
                status = TransactionStatus.PENDING
                completed_at = None
            elif status_roll < 0.98:
                status = TransactionStatus.FAILED
                completed_at = timestamp
            else:
                status = TransactionStatus.REVERSED
                completed_at = timestamp

            # Build transaction
            if is_payer:
                transaction = Transaction(
                    id=uuid.uuid4(),
                    transaction_id=generate_transaction_id(),
                    payer=f"acc_{TEST_ACCOUNT}",
                    payer_account_number=TEST_ACCOUNT,
                    payer_name="Test Agent Account",
                    payee=f"acc_{counterparty_account}",
                    payee_account_number=counterparty_account,
                    payee_name=counterparty_name,
                    amount=str(amount),
                    status=status,
                    currency=CurrencyEnum.NGN,
                    completed_at=completed_at,
                    note=tx_type["note"],
                    tag=tx_type["type"],
                    tenant_id=TENANT_ID,
                    ledger_id=LEDGER_ID,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            else:
                transaction = Transaction(
                    id=uuid.uuid4(),
                    transaction_id=generate_transaction_id(),
                    payer=f"acc_{counterparty_account}",
                    payer_account_number=counterparty_account,
                    payer_name=counterparty_name,
                    payee=f"acc_{TEST_ACCOUNT}",
                    payee_account_number=TEST_ACCOUNT,
                    payee_name="Test Agent Account",
                    amount=str(amount),
                    status=status,
                    currency=CurrencyEnum.NGN,
                    completed_at=completed_at,
                    note=tx_type["note"],
                    tag=tx_type["type"],
                    tenant_id=TENANT_ID,
                    ledger_id=LEDGER_ID,
                    created_at=timestamp,
                    updated_at=timestamp,
                )

            transactions.append(transaction)

        # Insert all transactions
        session.add_all(transactions)
        session.commit()

        # Print summary
        print(f"✅ Successfully seeded {len(transactions)} transactions")
        print("\n📊 Summary:")
        print(f"   • Account: {TEST_ACCOUNT}")
        print(f"   • Total transactions: {len(transactions)}")

        # Count by status
        status_counts = {}
        payer_count = 0
        payee_count = 0
        total_out = 0
        total_in = 0

        for tx in transactions:
            status_counts[tx.status.value] = status_counts.get(tx.status.value, 0) + 1
            if tx.payer_account_number == TEST_ACCOUNT:
                payer_count += 1
                total_out += int(tx.amount)
            else:
                payee_count += 1
                total_in += int(tx.amount)

        print("\n   Status breakdown:")
        for status, count in sorted(status_counts.items()):
            print(f"     - {status}: {count}")

        print("\n   Direction:")
        print(f"     - Outgoing (payer): {payer_count}")
        print(f"     - Incoming (payee): {payee_count}")

        print("\n   💰 Amounts:")
        print(f"     - Total outgoing: ₦{total_out:,}")
        print(f"     - Total incoming: ₦{total_in:,}")
        print(f"     - Net: ₦{total_in - total_out:,}")

        print("\n✨ Seeding complete!")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding transactions: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Safety guard: seeding real transaction data against a live database is
    # destructive in production.  This script must NEVER be executed in
    # production environments.  Set SEED_ON_STARTUP=true only in local
    # development or CI environments — it must NEVER be set in production.
    if os.environ.get("SEED_ON_STARTUP", "").lower() != "true":
        print(
            "Skipping seed: SEED_ON_STARTUP is not set to 'true'.\n"
            "Export SEED_ON_STARTUP=true to run this script intentionally.\n"
            "WARNING: never set this variable in a production environment."
        )
        sys.exit(0)

    print("=" * 60)
    print("Transaction Ledger Seed Script")
    print("=" * 60)
    print()

    seed_transactions()
