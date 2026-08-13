#!/usr/bin/env python3
"""
TigerBeetle Zig Service - Python wrapper for TigerBeetle Zig implementation
Provides ultra-fast double-entry accounting using TigerBeetle's native Zig binary
"""

import os
import sys
import json
import time
import uuid
import asyncio
import logging
import subprocess
import threading
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

import tigerbeetle as tb

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TigerBeetle Zig Service",
    description="Ultra-fast double-entry accounting with TigerBeetle Zig",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
TIGERBEETLE_DATA_DIR = os.getenv("TIGERBEETLE_DATA_DIR", "./tigerbeetle-data")
TIGERBEETLE_PORT = int(os.getenv("TIGERBEETLE_PORT", "3001"))
TB_CLUSTER_ID = int(os.getenv("TB_CLUSTER_ID", "0"))

class TigerBeetleZigService:
    """TigerBeetle Zig service managing the native binary"""
    
    def __init__(self):
        self.db_pool = None
        self.redis_client = None
        self.tigerbeetle_process = None
        self.tigerbeetle_client = None
        self.tigerbeetle_port = TIGERBEETLE_PORT
        self.data_dir = TIGERBEETLE_DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
    
    async def initialize(self):
        """Initialize the service. Fails loudly if the TigerBeetle binary or the
        real client is unavailable — there is no silent fallback ledger."""
        try:
            self.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
        
        try:
            self.redis_client = redis.from_url(REDIS_URL)
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
        
        await self.init_tigerbeetle_db()
        await self._setup_tigerbeetle()
    
    async def init_tigerbeetle_db(self):
        """Initialize sync-metadata tables (the ledger itself lives in TigerBeetle)"""
        async with self.db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS tigerbeetle_sync (
                    id VARCHAR(50) PRIMARY KEY,
                    account_id VARCHAR(50) NOT NULL,
                    user_id VARCHAR(50) NOT NULL,
                    balance BIGINT NOT NULL,
                    currency VARCHAR(3) NOT NULL,
                    last_sync TIMESTAMP DEFAULT NOW()
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS tigerbeetle_events (
                    id VARCHAR(50) PRIMARY KEY,
                    event_type VARCHAR(50) NOT NULL,
                    account_id VARCHAR(50),
                    transfer_id VARCHAR(50),
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            logger.info("TigerBeetle sync metadata tables initialized")
    
    async def _setup_tigerbeetle(self):
        """Setup TigerBeetle: binary + real client. Any failure aborts startup."""
        # Ensure binary exists
        binary_path = self._get_binary_path()
        if not os.path.exists(binary_path):
            logger.info("TigerBeetle binary not found, downloading...")
            await self.download_tigerbeetle()
        
        # Start TigerBeetle server
        await self.start_tigerbeetle()
        
        # Initialize real client connected to the spawned binary
        await self.init_tigerbeetle_client()
        
        logger.info("TigerBeetle setup completed")
    
    def _get_binary_path(self) -> str:
        """Get TigerBeetle binary path"""
        return os.path.join(self.data_dir, "tigerbeetle")
    
    async def download_tigerbeetle(self):
        """Download TigerBeetle binary. Fails loudly — no fake fallback binary."""
        import urllib.request
        
        binary_url = "https://github.com/tigerbeetle/tigerbeetle/releases/latest/download/tigerbeetle-x86_64-linux"
        binary_path = self._get_binary_path()
        
        try:
            logger.info(f"Downloading TigerBeetle from {binary_url}")
            urllib.request.urlretrieve(binary_url, binary_path)
            os.chmod(binary_path, 0o755)
            logger.info("TigerBeetle downloaded successfully")
        except Exception as e:
            raise RuntimeError(
                f"TigerBeetle binary download failed and no local binary exists at {binary_path}: {e}"
            )
    
    async def start_tigerbeetle(self):
        """Start TigerBeetle server process"""
        binary_path = self._get_binary_path()
        
        if not os.path.exists(binary_path):
            raise RuntimeError("TigerBeetle binary not found")
        
        try:
            # Check if TigerBeetle is already running
            if self.tigerbeetle_process and self.tigerbeetle_process.poll() is None:
                logger.info("TigerBeetle is already running")
                return
            
            # Start TigerBeetle server
            data_file = os.path.join(self.data_dir, "tigerbeetle.db")
            
            # Initialize data file if it doesn't exist
            if not os.path.exists(data_file):
                logger.info("Initializing TigerBeetle data file...")
                init_result = subprocess.run([
                    binary_path, "format",
                    f"--cluster={TB_CLUSTER_ID}",
                    "--replica=0",
                    "--replica-count=1",
                    data_file
                ], capture_output=True, text=True)
                
                if init_result.returncode != 0:
                    raise RuntimeError(f"Failed to initialize TigerBeetle data: {init_result.stderr}")
            
            # Start TigerBeetle server
            logger.info(f"Starting TigerBeetle server on port {self.tigerbeetle_port}...")
            self.tigerbeetle_process = subprocess.Popen([
                binary_path, "start",
                "--addresses=0.0.0.0:3001",
                data_file
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for server to start
            await asyncio.sleep(2)
            
            # Check if process is running
            if self.tigerbeetle_process.poll() is not None:
                stdout, stderr = self.tigerbeetle_process.communicate()
                raise RuntimeError(f"TigerBeetle failed to start: {stderr.decode()}")
            
            logger.info(f"TigerBeetle server started with PID {self.tigerbeetle_process.pid}")
            
        except Exception as e:
            logger.error(f"Failed to start TigerBeetle: {e}")
            raise
    
    async def init_tigerbeetle_client(self):
        """Initialize the real TigerBeetle client against the spawned binary."""
        try:
            self.tigerbeetle_client = tb.ClientSync(
                cluster_id=TB_CLUSTER_ID,
                replica_addresses=[f"127.0.0.1:{self.tigerbeetle_port}"],
            )
            # Probe the cluster — refuse to run if unreachable
            await asyncio.to_thread(self.tigerbeetle_client.lookup_accounts, [1])
            logger.info(f"TigerBeetle client connected to cluster {TB_CLUSTER_ID} on port {self.tigerbeetle_port}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize TigerBeetle client: {e}")
    
    async def create_tigerbeetle_accounts(self, accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create accounts via the real TigerBeetle client"""
        if not self.tigerbeetle_client:
            raise RuntimeError("TigerBeetle client not initialized")
        
        tb_accounts = []
        for account in accounts:
            tb_account = tb.Account(
                id=account['id'],
                ledger=account['ledger'],
                code=account['code'],
                flags=account.get('flags', 0),
                user_data64=account.get('user_data64', 0),
                user_data32=account.get('user_data32', 0),
            )
            tb_accounts.append(tb_account)
        
        try:
            errors = await asyncio.to_thread(self.tigerbeetle_client.create_accounts, tb_accounts)
            error_by_index = {e.index: str(e.result) for e in errors}
            
            results = []
            for i, account in enumerate(accounts):
                if i in error_by_index:
                    logger.error(f"Failed to create account {account['id']}: {error_by_index[i]}")
                    results.append({
                        "id": account['id'],
                        "status": "failed",
                        "error": error_by_index[i],
                    })
                else:
                    results.append({
                        "id": account['id'],
                        "status": "created",
                    })
                    await self.store_sync_event("account_created", {
                        "account_id": account['id'],
                        "ledger": account['ledger'],
                        "code": account['code'],
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to create accounts: {e}")
            raise HTTPException(status_code=503, detail=f"TigerBeetle account creation failed: {e}")
    
    async def create_tigerbeetle_transfers(self, transfers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create transfers via the real TigerBeetle client"""
        if not self.tigerbeetle_client:
            raise RuntimeError("TigerBeetle client not initialized")
        
        tb_transfers = []
        for transfer in transfers:
            tb_transfer = tb.Transfer(
                id=transfer['id'],
                debit_account_id=transfer['debit_account_id'],
                credit_account_id=transfer['credit_account_id'],
                amount=transfer['amount'],
                ledger=transfer['ledger'],
                code=transfer['code'],
                flags=transfer.get('flags', 0),
                pending_id=transfer.get('pending_id', 0),
                timeout=transfer.get('timeout', 0),
            )
            tb_transfers.append(tb_transfer)
        
        try:
            errors = await asyncio.to_thread(self.tigerbeetle_client.create_transfers, tb_transfers)
            error_by_index = {e.index: str(e.result) for e in errors}
            
            results = []
            for i, transfer in enumerate(transfers):
                if i in error_by_index:
                    logger.error(f"Failed to create transfer {transfer['id']}: {error_by_index[i]}")
                    results.append({
                        "id": transfer['id'],
                        "status": "failed",
                        "error": error_by_index[i],
                    })
                else:
                    results.append({
                        "id": transfer['id'],
                        "status": "posted",
                    })
                    await self.store_sync_event("transfer_created", {
                        "transfer_id": transfer['id'],
                        "debit_account_id": transfer['debit_account_id'],
                        "credit_account_id": transfer['credit_account_id'],
                        "amount": transfer['amount'],
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to create transfers: {e}")
            raise HTTPException(status_code=503, detail=f"TigerBeetle transfer creation failed: {e}")
    
    async def store_sync_event(self, event_type: str, data: Dict[str, Any]):
        """Store sync event in database"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO tigerbeetle_events (id, event_type, account_id, transfer_id, data)
                    VALUES ($1, $2, $3, $4, $5)
                ''', str(uuid.uuid4()), event_type, 
                    data.get('account_id'), data.get('transfer_id'), json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to store sync event: {e}")
    
    async def sync_balance_to_db(self, account_id: str, balance: int, currency: str = "NGN"):
        """Sync balance to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO tigerbeetle_sync (id, account_id, user_id, balance, currency)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (account_id) DO UPDATE SET
                    balance = $4, last_sync = NOW()
                ''', str(uuid.uuid4()), account_id, account_id, balance, currency)
        except Exception as e:
            logger.error(f"Failed to sync balance to database: {e}")
    
    async def get_tigerbeetle_metrics(self) -> Dict[str, Any]:
        """Get TigerBeetle metrics — only verifiable data, no fabricated counters."""
        events_count = None
        try:
            async with self.db_pool.acquire() as conn:
                events_count = await conn.fetchval("SELECT COUNT(*) FROM tigerbeetle_events")
        except Exception as e:
            logger.warning(f"Failed to read sync event count: {e}")
        
        return {
            "tigerbeetle_running": self.tigerbeetle_process is not None and self.tigerbeetle_process.poll() is None,
            "tigerbeetle_client_connected": self.tigerbeetle_client is not None,
            "cluster_id": TB_CLUSTER_ID,
            "port": self.tigerbeetle_port,
            "sync_events_recorded": events_count,
            "data_directory": self.data_dir,
            "binary_path": self._get_binary_path(),
        }
    
    async def shutdown(self):
        """Shutdown service"""
        if self.tigerbeetle_process:
            self.tigerbeetle_process.terminate()
            try:
                self.tigerbeetle_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.tigerbeetle_process.kill()
            logger.info("TigerBeetle server stopped")
        
        if self.db_pool:
            await self.db_pool.close()
        
        if self.redis_client:
            await self.redis_client.close()

# Global service instance
service = TigerBeetleZigService()

@app.on_event("startup")
async def startup_event():
    await service.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    await service.shutdown()

# API Endpoints
@app.get("/health")
async def health_check():
    metrics = await service.get_tigerbeetle_metrics()
    return {
        "status": "healthy",
        "service": "tigerbeetle-zig",
        "version": "2.0.0",
        "tigerbeetle_running": metrics["tigerbeetle_running"],
        "timestamp": datetime.utcnow().isoformat(),
    }

@app.post("/api/v1/accounts")
async def create_accounts(accounts: List[Dict[str, Any]]):
    """Create accounts"""
    try:
        results = await service.create_tigerbeetle_accounts(accounts)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.post("/api/v1/transfers")
async def create_transfers(transfers: List[Dict[str, Any]]):
    """Create transfers"""
    try:
        results = await service.create_tigerbeetle_transfers(transfers)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/api/v1/accounts/{account_id}/balance")
async def get_account_balance(account_id: str):
    """Get account balance from TigerBeetle"""
    try:
        if not service.tigerbeetle_client:
            raise HTTPException(status_code=503, detail="TigerBeetle client not initialized")
        
        accounts = await asyncio.to_thread(
            service.tigerbeetle_client.lookup_accounts, [int(account_id)]
        )
        
        if not accounts:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found in TigerBeetle")
        
        account = accounts[0]
        balance = int(account.credits_posted) - int(account.debits_posted)
        
        return {
            "account_id": account_id,
            "balance": balance,
            "debits_posted": int(account.debits_posted),
            "credits_posted": int(account.credits_posted),
            "debits_pending": int(account.debits_pending),
            "credits_pending": int(account.credits_pending),
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="account_id must be numeric")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TigerBeetle lookup failed: {e}")

@app.get("/api/v1/transfers/{transfer_id}")
async def get_transfer(transfer_id: str):
    """Get transfer details from TigerBeetle"""
    try:
        if not service.tigerbeetle_client:
            raise HTTPException(status_code=503, detail="TigerBeetle client not initialized")
        
        transfers = await asyncio.to_thread(
            service.tigerbeetle_client.lookup_transfers, [int(transfer_id)]
        )
        
        if not transfers:
            raise HTTPException(status_code=404, detail=f"Transfer {transfer_id} not found in TigerBeetle")
        
        transfer = transfers[0]
        return {
            "id": transfer_id,
            "debit_account_id": str(transfer.debit_account_id),
            "credit_account_id": str(transfer.credit_account_id),
            "amount": int(transfer.amount),
            "ledger": transfer.ledger,
            "code": transfer.code,
            "flags": transfer.flags,
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="transfer_id must be numeric")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TigerBeetle lookup failed: {e}")

@app.get("/api/v1/metrics")
async def get_metrics():
    """Get service metrics"""
    return await service.get_tigerbeetle_metrics()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8028))
    uvicorn.run(app, host="0.0.0.0", port=port)
