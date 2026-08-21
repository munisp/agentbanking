#!/usr/bin/env python3
"""
TB Account Replay Script
Run this inside the account-service pod or anywhere with TB + postgres access.
"""
import os

import tigerbeetle as tb
from decimal import Decimal
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]
TB_CLUSTER_ID = int(os.environ["TB_CLUSTER_ID"])
TB_ADDRESS = os.environ["TB_ADDRESS"]

engine = create_engine(DATABASE_URL)
client = tb.ClientSync(cluster_id=int(Decimal(str(TB_CLUSTER_ID))), replica_addresses=TB_ADDRESS)

with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, account_type, ledger_id FROM account ORDER BY id")).fetchall()

print(f"Found {len(rows)} accounts to replay")

for row in rows:
    account_id = int(row.id)
    account_type = row.account_type
    ledger_id = int(row.ledger_id)

    # Map account_type to TB code (customize as needed)
    code = 1 if account_type == 'customer' else 2

    try:
        errors = client.create_accounts([
            tb.Account(
                id=account_id,
                ledger=ledger_id,
                code=code,
                flags=tb.AccountFlags.NONE,
            )
        ])
        if errors:
            print(f"Account {account_id}: {errors}")
        else:
            print(f"Replayed account {account_id}")
    except Exception as e:
        print(f"Failed account {account_id}: {e}")

print("Replay complete")
