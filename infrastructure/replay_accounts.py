#!/usr/bin/env python3
"""
TB Account Replay Script
Run this inside the account-service pod or anywhere with TB + postgres access.
"""
import tigerbeetle as tb
from decimal import Decimal
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://doadmin:AVNS_MSy6CW3EGXnA8wJgkLv@db-postgresql-nyc1-18193-do-user-10555812-0.e.db.ondigitalocean.com:25060/link_core_banking"
TB_CLUSTER_ID = 233240165285264747596733200182526600436
TB_ADDRESS = "10.233.107.176:3000,10.233.85.61:3000,10.233.95.243:3000"

engine = create_engine(DATABASE_URL)
client = tb.ClientSync(cluster_id=int(Decimal(str(TB_CLUSTER_ID))), replica_addresses=TB_ADDRESS)

with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, account_type, ledger_id FROM account ORDER BY id")).fetchall()

print(f"Found {len(rows)} accounts to replay")

accounts_to_create = []
for row in rows:
    account_id, account_type, ledger_id = row
    is_system = account_type == "mint"

    flags = tb.AccountFlags.NONE if is_system else tb.AccountFlags.DEBITS_MUST_NOT_EXCEED_CREDITS
    flags = flags | tb.AccountFlags.HISTORY

    accounts_to_create.append(tb.Account(
        id=account_id,
        debits_pending=0,
        debits_posted=0,
        credits_pending=0,
        credits_posted=0,
        user_data_128=0,
        user_data_64=0,
        user_data_32=0,
        ledger=1,
        code=1,
        timestamp=0,
        flags=flags,
    ))

# Create in batches of 8190
batch_size = 8190
errors_total = []
for i in range(0, len(accounts_to_create), batch_size):
    batch = accounts_to_create[i:i+batch_size]
    errors = client.create_accounts(batch)
    if errors:
        print(f"Errors in batch starting at {i}: {errors}")
        errors_total.extend(errors)
    else:
        print(f"Batch {i} to {i+len(batch)}: OK")

if not errors_total:
    print("\n✅ All accounts recreated successfully in TigerBeetle.")
    print("NOTE: Balances are all zero. You need to replay transactions separately.")
else:
    print(f"\n⚠️  Completed with {len(errors_total)} errors.")

client.close()