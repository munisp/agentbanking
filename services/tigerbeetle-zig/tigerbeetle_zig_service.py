import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
#!/usr/bin/env python3
"""
TigerBeetle Zig Primary Service
High-performance accounting engine with REST API interface

Fail-loud doctrine: the service drives the spawned TigerBeetle binary through the
official `tigerbeetle` python client. If the binary or client is unavailable,
startup FAILS — unless TIGERBEETLE_ZIG_SIMULATION_MODE=true is explicitly set in a
non-production environment, in which case a clearly-labelled in-memory simulation
is used (that combination hard-fails when ENVIRONMENT=production).
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# TigerBeetle Data Models
@dataclass
class TigerBeetleAccount:
    id: int
    user_data: int = 0
    ledger: int = 1
    code: int = 1
    flags: int = 0
    debits_pending: int = 0
    debits_posted: int = 0
    credits_pending: int = 0
    credits_posted: int = 0
    timestamp: int = 0

@dataclass
class TigerBeetleTransfer:
    id: int
    debit_account_id: int
    credit_account_id: int
    user_data: int = 0
    pending_id: int = 0
    timeout: int = 0
    ledger: int = 1
    code: int = 1
    flags: int = 0
    amount: int = 0
    timestamp: int = 0

# Pydantic Models for API
class AccountCreate(BaseModel):
    id: int = Field(..., description="Unique account ID")
    user_data: int = Field(0, description="User-defined data")
    ledger: int = Field(1, description="Ledger ID")
    code: int = Field(1, description="Account code")
    flags: int = Field(0, description="Account flags")

class TransferCreate(BaseModel):
    id: int = Field(..., description="Unique transfer ID")
    debit_account_id: int = Field(..., description="Source account ID")
    credit_account_id: int = Field(..., description="Destination account ID")
    user_data: int = Field(0, description="User-defined data")
    pending_id: int = Field(0, description="Pending transfer ID")
    timeout: int = Field(0, description="Transfer timeout")
    ledger: int = Field(1, description="Ledger ID")
    code: int = Field(1, description="Transfer code")
    flags: int = Field(0, description="Transfer flags")
    amount: int = Field(..., description="Transfer amount in cents")

class AccountBalance(BaseModel):
    account_id: int
    debits_pending: int
    debits_posted: int
    credits_pending: int
    credits_posted: int
    balance: int
    available_balance: int

class TransferResult(BaseModel):
    transfer_id: int
    status: str
    error_code: Optional[int] = None
    error_message: Optional[str] = None

class TigerBeetleZigService:
    def __init__(self):
        self.app = FastAPI(
            title="TigerBeetle Zig Primary Service",
            description="High-performance accounting engine with TigerBeetle Zig",
            version="1.0.0"
        )

        # Configuration
        self.database_url = os.getenv("DATABASE_URL", "postgresql://banking_user:secure_banking_password@localhost:5432/remittance")
        self.redis_url = os.getenv("REDIS_URL", "redis://:redis_secure_password@localhost:6379")
        self.tigerbeetle_data_file = os.getenv("TIGERBEETLE_DATA_FILE", "/tmp/tigerbeetle_data.tigerbeetle")
        self.tigerbeetle_port = int(os.getenv("TIGERBEETLE_PORT", "3001"))

        # Simulation gating: an in-memory dict client is only permitted outside
        # production and only when explicitly requested.
        self.simulation_mode = os.getenv("TIGERBEETLE_ZIG_SIMULATION_MODE", "false").lower() == "true"
        self.environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()
        if self.simulation_mode and self.environment in ("production", "prod"):
            raise RuntimeError(
                "TIGERBEETLE_ZIG_SIMULATION_MODE=true is forbidden when ENVIRONMENT=production"
            )

        # TigerBeetle process and official client
        self.tigerbeetle_process = None
        self.tb_client = None
        self._tb = None

        # Tracked IDs (for metrics) — populated as real creates are accepted
        self._account_ids = set()
        self._transfer_ids = set()

        # Simulation-mode stores (only used when simulation_mode is True)
        self.tigerbeetle_accounts = {}
        self.tigerbeetle_transfers = {}

        # Database connections
        self.db_pool = None
        self.redis_client = None

        # Sync tracking
        self.sync_events = []
        self.last_sync_timestamp = 0

        # Setup FastAPI
        self.setup_fastapi()

    def setup_fastapi(self):
        """Setup FastAPI application with middleware and routes"""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Event handlers
        self.app.add_event_handler("startup", self.startup)
        self.app.add_event_handler("shutdown", self.shutdown)

        # Routes
        self.setup_routes()

    def setup_routes(self):
        """Setup API routes"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "service": "tigerbeetle-zig-primary",
                "timestamp": datetime.utcnow().isoformat(),
                "tigerbeetle_running": self.tigerbeetle_process is not None and self.tigerbeetle_process.poll() is None,
                "tigerbeetle_client_connected": self.tb_client is not None,
                "simulation_mode": self.simulation_mode,
                "database_connected": self.db_pool is not None,
                "redis_connected": self.redis_client is not None
            }

        @self.app.post("/accounts", response_model=Dict[str, Any])
        async def create_accounts(accounts: List[AccountCreate]):
            """Create TigerBeetle accounts"""
            try:
                # Convert to TigerBeetle format
                tb_accounts = []
                for acc in accounts:
                    tb_account = TigerBeetleAccount(
                        id=acc.id,
                        user_data=acc.user_data,
                        ledger=acc.ledger,
                        code=acc.code,
                        flags=acc.flags,
                        timestamp=int(time.time() * 1_000_000_000)  # Nanoseconds
                    )
                    tb_accounts.append(tb_account)

                # Create accounts in TigerBeetle
                result = await self.create_tigerbeetle_accounts(tb_accounts)

                # Store sync event
                await self.store_sync_event("account", "create", tb_accounts)

                # Publish to Redis for edge sync
                await self.publish_sync_event("account", "create", tb_accounts)

                return {
                    "success": True,
                    "accounts_created": len(accounts),
                    "result": result
                }

            except Exception as e:
                logger.error(f"Error creating accounts: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/transfers", response_model=Dict[str, Any])
        async def create_transfers(transfers: List[TransferCreate]):
            """Create TigerBeetle transfers"""
            try:
                # Convert to TigerBeetle format
                tb_transfers = []
                for transfer in transfers:
                    tb_transfer = TigerBeetleTransfer(
                        id=transfer.id,
                        debit_account_id=transfer.debit_account_id,
                        credit_account_id=transfer.credit_account_id,
                        user_data=transfer.user_data,
                        pending_id=transfer.pending_id,
                        timeout=transfer.timeout,
                        ledger=transfer.ledger,
                        code=transfer.code,
                        flags=transfer.flags,
                        amount=transfer.amount,
                        timestamp=int(time.time() * 1_000_000_000)  # Nanoseconds
                    )
                    tb_transfers.append(tb_transfer)

                # Create transfers in TigerBeetle
                result = await self.create_tigerbeetle_transfers(tb_transfers)

                # Store sync event
                await self.store_sync_event("transfer", "create", tb_transfers)

                # Publish to Redis for edge sync
                await self.publish_sync_event("transfer", "create", tb_transfers)

                return {
                    "success": True,
                    "transfers_created": len(transfers),
                    "result": result
                }

            except Exception as e:
                logger.error(f"Error creating transfers: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/accounts/{account_id}", response_model=AccountBalance)
        async def get_account_balance(account_id: int):
            """Get account balance"""
            try:
                account = await self.get_tigerbeetle_account(account_id)
                if not account:
                    raise HTTPException(status_code=404, detail="Account not found")

                balance = account.credits_posted - account.debits_posted
                available_balance = balance - account.credits_pending + account.debits_pending

                return AccountBalance(
                    account_id=account.id,
                    debits_pending=account.debits_pending,
                    debits_posted=account.debits_posted,
                    credits_pending=account.credits_pending,
                    credits_posted=account.credits_posted,
                    balance=balance,
                    available_balance=available_balance
                )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting account balance: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/transfers/{transfer_id}")
        async def get_transfer(transfer_id: int):
            """Get transfer details"""
            try:
                transfer = await self.get_tigerbeetle_transfer(transfer_id)
                if not transfer:
                    raise HTTPException(status_code=404, detail="Transfer not found")

                return asdict(transfer)

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error getting transfer: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/sync/events")
        async def get_sync_events(limit: int = 100, processed: bool = False):
            """Get sync events for edge synchronization"""
            try:
                events = await self.get_pending_sync_events(limit, processed)
                return {
                    "events": events,
                    "count": len(events),
                    "last_sync": self.last_sync_timestamp
                }

            except Exception as e:
                logger.error(f"Error getting sync events: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/sync/events/mark-processed")
        async def mark_sync_events_processed(event_ids: List[str]):
            """Mark sync events as processed"""
            try:
                await self.mark_events_processed(event_ids)
                return {"success": True, "processed_count": len(event_ids)}

            except Exception as e:
                logger.error(f"Error marking events processed: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/sync/from-edge")
        async def sync_from_edge(events: List[Dict[str, Any]]):
            """Receive sync events from edge instances"""
            try:
                processed_count = 0

                for event in events:
                    if event["type"] == "account":
                        # Process account sync from edge
                        await self.process_account_sync_from_edge(event)
                    elif event["type"] == "transfer":
                        # Process transfer sync from edge
                        await self.process_transfer_sync_from_edge(event)

                    processed_count += 1

                return {
                    "success": True,
                    "processed_count": processed_count
                }

            except Exception as e:
                logger.error(f"Error syncing from edge: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/metrics")
        async def get_metrics():
            """Get TigerBeetle metrics"""
            try:
                # Get basic metrics
                account_count = await self.get_account_count()
                transfer_count = await self.get_transfer_count()
                pending_sync_events = len(await self.get_pending_sync_events(1000, False))

                return {
                    "accounts_total": account_count,
                    "transfers_total": transfer_count,
                    "pending_sync_events": pending_sync_events,
                    "last_sync_timestamp": self.last_sync_timestamp,
                    "tigerbeetle_running": self.tigerbeetle_process is not None and self.tigerbeetle_process.poll() is None,
                    "simulation_mode": self.simulation_mode,
                    "uptime_seconds": time.time() - getattr(self, 'start_time', time.time())
                }

            except Exception as e:
                logger.error(f"Error getting metrics: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))

    async def startup(self):
        """Startup event handler"""
        logger.info("Starting TigerBeetle Zig Primary Service...")
        self.start_time = time.time()

        # Initialize database connection
        await self.init_database()

        # Initialize Redis connection
        await self.init_redis()

        # Start TigerBeetle Zig process (skipped in simulation mode)
        await self.start_tigerbeetle()

        # Initialize TigerBeetle client — hard-fails when unavailable outside simulation
        await self.init_tigerbeetle_client()

        # Start background sync task
        asyncio.create_task(self.sync_worker())

        logger.info("TigerBeetle Zig Primary Service started successfully")

    async def shutdown(self):
        """Shutdown event handler"""
        logger.info("Shutting down TigerBeetle Zig Primary Service...")

        # Close TigerBeetle client
        if self.tb_client is not None:
            try:
                self.tb_client.close()
            except Exception:
                pass

        # Stop TigerBeetle process
        if self.tigerbeetle_process:
            self.tigerbeetle_process.terminate()
            try:
                self.tigerbeetle_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.tigerbeetle_process.kill()

        # Close database connection
        if self.db_pool:
            await self.db_pool.close()

        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()

        logger.info("TigerBeetle Zig Primary Service shut down")

    async def init_database(self):
        """Initialize PostgreSQL connection"""
        try:
            self.db_pool = await asyncpg.create_pool(self.database_url)

            # Create tables for sync events
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS tigerbeetle_sync_events (
                        id VARCHAR(100) PRIMARY KEY,
                        type VARCHAR(20) NOT NULL,
                        operation VARCHAR(20) NOT NULL,
                        data JSONB NOT NULL,
                        source VARCHAR(50) NOT NULL,
                        timestamp BIGINT NOT NULL,
                        processed BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tigerbeetle_sync_events_processed
                    ON tigerbeetle_sync_events(processed, timestamp)
                """)

                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_tigerbeetle_sync_events_type
                    ON tigerbeetle_sync_events(type, operation)
                """)

            logger.info("Database connection initialized")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)}")
            raise

    async def start_tigerbeetle(self):
        """Start TigerBeetle Zig process"""
        if self.simulation_mode:
            logger.warning("SIMULATION MODE: TigerBeetle binary NOT started; using in-memory dict client (non-production only)")
            return
        try:
            # Download TigerBeetle if not exists
            tigerbeetle_binary = "/usr/local/bin/tigerbeetle"
            if not os.path.exists(tigerbeetle_binary):
                await self.download_tigerbeetle()

            if not os.path.exists(tigerbeetle_binary):
                raise RuntimeError("TigerBeetle binary not available after download attempt")

            # Create data file if not exists
            if not os.path.exists(self.tigerbeetle_data_file):
                # Format the data file
                format_cmd = [
                    tigerbeetle_binary,
                    "format",
                    "--cluster=0",
                    "--replica=0",
                    self.tigerbeetle_data_file
                ]

                result = subprocess.run(format_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Failed to format TigerBeetle data file: {result.stderr}")

                logger.info(f"TigerBeetle data file formatted: {self.tigerbeetle_data_file}")

            # Start TigerBeetle server
            start_cmd = [
                tigerbeetle_binary,
                "start",
                "--cluster=0",
                "--replica=0",
                f"--addresses={self.tigerbeetle_port}",
                self.tigerbeetle_data_file
            ]

            self.tigerbeetle_process = subprocess.Popen(
                start_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait a moment for startup
            await asyncio.sleep(2)

            # Check if process is running
            if self.tigerbeetle_process.poll() is not None:
                stdout, stderr = self.tigerbeetle_process.communicate()
                raise Exception(f"TigerBeetle failed to start: {stderr}")

            logger.info(f"TigerBeetle Zig process started on port {self.tigerbeetle_port}")

        except Exception as e:
            logger.error(f"Failed to start TigerBeetle: {str(e)}")
            raise

    async def download_tigerbeetle(self):
        """Download TigerBeetle binary"""
        try:
            import httpx

            # Download URL for Linux x64
            download_url = "https://github.com/tigerbeetle/tigerbeetle/releases/latest/download/tigerbeetle-x86_64-linux.zip"

            logger.info("Downloading TigerBeetle binary...")

            async with httpx.AsyncClient() as client:
                response = await client.get(download_url)
                response.raise_for_status()

                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
                    tmp_file.write(response.content)
                    zip_path = tmp_file.name

                # Extract binary
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extract("tigerbeetle", "/tmp/")

                # Move to /usr/local/bin/
                os.makedirs("/usr/local/bin", exist_ok=True)
                subprocess.run(["sudo", "mv", "/tmp/tigerbeetle", "/usr/local/bin/tigerbeetle"])
                subprocess.run(["sudo", "chmod", "+x", "/usr/local/bin/tigerbeetle"])

                # Cleanup
                os.unlink(zip_path)

                logger.info("TigerBeetle binary downloaded and installed")

        except Exception as e:
            logger.error(f"Failed to download TigerBeetle: {str(e)}")
            # No silent fallback: production deployments fail startup instead of
            # degrading to a database-backed fake ledger.
            raise RuntimeError(
                "TigerBeetle binary unavailable and simulation mode is disabled — refusing to start"
            ) from e

    async def init_tigerbeetle_client(self):
        """Initialize the official TigerBeetle python client against the spawned binary."""
        if self.simulation_mode:
            logger.warning("SIMULATION MODE: dict-based client active — results are NOT real ledger postings")
            return

        try:
            import tigerbeetle as tb
        except ImportError as e:
            raise RuntimeError(
                "The 'tigerbeetle' python package is required (pip install tigerbeetle); "
                "refusing to start without the official client"
            ) from e

        self._tb = tb
        address = f"127.0.0.1:{self.tigerbeetle_port}"
        try:
            self.tb_client = tb.ClientSync(cluster_id=0, replica_addresses=address)
            # Verify connectivity with a harmless empty lookup
            await asyncio.to_thread(self.tb_client.lookup_accounts, [])
        except Exception as e:
            raise RuntimeError(
                f"Cannot connect TigerBeetle client to {address}: {e} — refusing to start"
            ) from e

        logger.info(f"TigerBeetle client connected to cluster at {address}")

    async def create_tigerbeetle_accounts(self, accounts: List[TigerBeetleAccount]) -> List[Dict]:
        """Create accounts in TigerBeetle"""
        if self.tb_client is None:
            return await self._create_accounts_simulated(accounts)

        tb_accounts = [
            self._tb.Account(
                id=a.id,
                ledger=a.ledger,
                code=a.code,
                flags=self._tb.AccountFlags(a.flags),
            )
            for a in accounts
        ]
        errors = await asyncio.to_thread(self.tb_client.create_accounts, tb_accounts)
        if errors:
            msgs = "; ".join(f"index {e.index}: {getattr(e, 'result', e)}" for e in errors)
            raise RuntimeError(f"TigerBeetle rejected {len(errors)} account(s): {msgs}")

        for a in accounts:
            self._account_ids.add(a.id)

        logger.info(f"Created {len(accounts)} accounts in TigerBeetle")
        return [
            {"account_id": a.id, "status": "created", "timestamp": a.timestamp}
            for a in accounts
        ]

    async def _create_accounts_simulated(self, accounts: List[TigerBeetleAccount]) -> List[Dict]:
        """SIMULATION ONLY: dict-based account store (non-production)."""
        logger.warning("SIMULATION MODE: accounts stored in memory, not in TigerBeetle")
        results = []
        for account in accounts:
            self.tigerbeetle_accounts[account.id] = account
            results.append({
                "account_id": account.id,
                "status": "created_simulated",
                "timestamp": account.timestamp
            })
        return results

    async def create_tigerbeetle_transfers(self, transfers: List[TigerBeetleTransfer]) -> List[Dict]:
        """Create transfers in TigerBeetle"""
        if self.tb_client is None:
            return await self._create_transfers_simulated(transfers)

        tb_transfers = [
            self._tb.Transfer(
                id=t.id,
                debit_account_id=t.debit_account_id,
                credit_account_id=t.credit_account_id,
                amount=t.amount,
                ledger=t.ledger,
                code=t.code,
                flags=self._tb.TransferFlags(t.flags),
                pending_id=t.pending_id,
                timeout=t.timeout,
            )
            for t in transfers
        ]
        errors = await asyncio.to_thread(self.tb_client.create_transfers, tb_transfers)

        failed = {e.index: str(getattr(e, "result", e)) for e in errors}
        results = []
        for i, transfer in enumerate(transfers):
            if i in failed:
                results.append({
                    "transfer_id": transfer.id,
                    "status": "failed",
                    "error": failed[i]
                })
            else:
                self._transfer_ids.add(transfer.id)
                results.append({
                    "transfer_id": transfer.id,
                    "status": "posted",
                    "timestamp": transfer.timestamp
                })
        logger.info(f"Posted {len(transfers) - len(failed)} of {len(transfers)} transfers in TigerBeetle")
        return results

    async def _create_transfers_simulated(self, transfers: List[TigerBeetleTransfer]) -> List[Dict]:
        """SIMULATION ONLY: dict-based transfer store (non-production)."""
        logger.warning("SIMULATION MODE: transfers applied to in-memory dicts, not to TigerBeetle")
        results = []
        for transfer in transfers:
            if transfer.debit_account_id not in self.tigerbeetle_accounts:
                results.append({
                    "transfer_id": transfer.id,
                    "status": "failed",
                    "error": "debit_account_not_found"
                })
                continue
            if transfer.credit_account_id not in self.tigerbeetle_accounts:
                results.append({
                    "transfer_id": transfer.id,
                    "status": "failed",
                    "error": "credit_account_not_found"
                })
                continue
            debit_account = self.tigerbeetle_accounts[transfer.debit_account_id]
            credit_account = self.tigerbeetle_accounts[transfer.credit_account_id]
            debit_account.debits_posted += transfer.amount
            credit_account.credits_posted += transfer.amount
            self.tigerbeetle_transfers[transfer.id] = transfer
            results.append({
                "transfer_id": transfer.id,
                "status": "posted_simulated",
                "timestamp": transfer.timestamp
            })
        return results

    async def get_tigerbeetle_account(self, account_id: int) -> Optional[TigerBeetleAccount]:
        """Get account from TigerBeetle"""
        if self.tb_client is None:
            return self.tigerbeetle_accounts.get(account_id)

        accounts = await asyncio.to_thread(self.tb_client.lookup_accounts, [account_id])
        if not accounts:
            return None
        a = accounts[0]
        return TigerBeetleAccount(
            id=a.id,
            user_data=a.user_data_64,
            ledger=a.ledger,
            code=a.code,
            flags=int(a.flags),
            debits_pending=a.debits_pending,
            debits_posted=a.debits_posted,
            credits_pending=a.credits_pending,
            credits_posted=a.credits_posted,
            timestamp=a.timestamp,
        )

    async def get_tigerbeetle_transfer(self, transfer_id: int) -> Optional[TigerBeetleTransfer]:
        """Get transfer from TigerBeetle"""
        if self.tb_client is None:
            return self.tigerbeetle_transfers.get(transfer_id)

        transfers = await asyncio.to_thread(self.tb_client.lookup_transfers, [transfer_id])
        if not transfers:
            return None
        t = transfers[0]
        return TigerBeetleTransfer(
            id=t.id,
            debit_account_id=t.debit_account_id,
            credit_account_id=t.credit_account_id,
            user_data=t.user_data_64,
            pending_id=t.pending_id,
            timeout=t.timeout,
            ledger=t.ledger,
            code=t.code,
            flags=int(t.flags),
            amount=t.amount,
            timestamp=t.timestamp,
        )

    async def get_account_count(self) -> int:
        """Get count of accounts tracked by this service"""
        if self.tb_client is None:
            return len(self.tigerbeetle_accounts)
        return len(self._account_ids)

    async def get_transfer_count(self) -> int:
        """Get count of transfers tracked by this service"""
        if self.tb_client is None:
            return len(self.tigerbeetle_transfers)
        return len(self._transfer_ids)

    async def store_sync_event(self, event_type: str, operation: str, data: Any):
        """Store sync event in database"""
        try:
            event_id = str(uuid.uuid4())
            timestamp = int(time.time() * 1_000_000_000)  # Nanoseconds

            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO tigerbeetle_sync_events
                    (id, type, operation, data, source, timestamp, processed)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, event_id, event_type, operation, json.dumps([asdict(item) for item in data]),
                "zig-primary", timestamp, False)

            logger.debug(f"Stored sync event: {event_id}")

        except Exception as e:
            logger.error(f"Failed to store sync event: {str(e)}")

    async def publish_sync_event(self, event_type: str, operation: str, data: Any):
        """Publish sync event to Redis"""
        try:
            event = {
                "id": str(uuid.uuid4()),
                "type": event_type,
                "operation": operation,
                "data": [asdict(item) for item in data],
                "source": "zig-primary",
                "timestamp": int(time.time() * 1_000_000_000)
            }

            await self.redis_client.publish("tigerbeetle_sync", json.dumps(event))
            logger.debug(f"Published sync event: {event['id']}")

        except Exception as e:
            logger.error(f"Failed to publish sync event: {str(e)}")

    async def get_pending_sync_events(self, limit: int = 100, processed: bool = False) -> List[Dict]:
        """Get pending sync events"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, type, operation, data, source, timestamp, processed
                    FROM tigerbeetle_sync_events
                    WHERE processed = $1
                    ORDER BY timestamp ASC
                    LIMIT $2
                """, processed, limit)

                events = []
                for row in rows:
                    events.append({
                        "id": row["id"],
                        "type": row["type"],
                        "operation": row["operation"],
                        "data": json.loads(row["data"]),
                        "source": row["source"],
                        "timestamp": row["timestamp"],
                        "processed": row["processed"]
                    })

                return events

        except Exception as e:
            logger.error(f"Failed to get pending sync events: {str(e)}")
            return []

    async def mark_events_processed(self, event_ids: List[str]):
        """Mark sync events as processed"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE tigerbeetle_sync_events
                    SET processed = TRUE
                    WHERE id = ANY($1)
                """, event_ids)

            logger.debug(f"Marked {len(event_ids)} events as processed")

        except Exception as e:
            logger.error(f"Failed to mark events processed: {str(e)}")

    async def process_account_sync_from_edge(self, event: Dict[str, Any]):
        """Process account sync event from edge"""
        try:
            data = event["data"]

            for account_data in data:
                account = TigerBeetleAccount(**account_data)

                # Check if account exists
                existing_account = await self.get_tigerbeetle_account(account.id)

                if existing_account:
                    # Accounts are immutable in TigerBeetle — nothing to update
                    logger.debug(f"Account {account.id} already exists; skipping edge sync update")
                else:
                    # Create new account
                    await self.create_tigerbeetle_accounts([account])
                    logger.debug(f"Created account {account.id} from edge sync")

        except Exception as e:
            logger.error(f"Failed to process account sync from edge: {str(e)}")

    async def process_transfer_sync_from_edge(self, event: Dict[str, Any]):
        """Process transfer sync event from edge"""
        try:
            data = event["data"]

            for transfer_data in data:
                transfer = TigerBeetleTransfer(**transfer_data)

                # Check if transfer exists
                existing_transfer = await self.get_tigerbeetle_transfer(transfer.id)

                if not existing_transfer:
                    # Create new transfer
                    await self.create_tigerbeetle_transfers([transfer])
                    logger.debug(f"Created transfer {transfer.id} from edge sync")

        except Exception as e:
            logger.error(f"Failed to process transfer sync from edge: {str(e)}")

    async def sync_worker(self):
        """Background sync worker"""
        while True:
            try:
                # Update last sync timestamp
                self.last_sync_timestamp = int(time.time() * 1_000_000_000)

                # Perform any periodic sync tasks
                await asyncio.sleep(5)  # Sync every 5 seconds

            except Exception as e:
                logger.error(f"Sync worker error: {str(e)}")
                await asyncio.sleep(10)  # Wait longer on error

# Create service instance
service = TigerBeetleZigService()
app = service.app

apply_middleware(app)
setup_logging("tigerbeetle-zig-primary-service")
app.include_router(metrics_router)

if __name__ == "__main__":
    uvicorn.run(
        "tigerbeetle_zig_service:app",
        host="0.0.0.0",
        port=8030,
        reload=False,
        log_level="info"
    )
