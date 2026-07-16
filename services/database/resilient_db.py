"""
Next-Generation Database Resilience
Enterprise-grade connection pooling, failover, circuit breakers, and health checks
"""

import asyncio
import asyncpg
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import time
from dataclasses import dataclass, field
import random

import os
logger = logging.getLogger(__name__)

# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures
    """
    failure_threshold: int = 5  # Open after 5 failures
    success_threshold: int = 2  # Close after 2 successes in half-open
    timeout: int = 60  # Seconds before trying again
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_state_change: datetime = field(default_factory=datetime.utcnow)
    
    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._close()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._open()
        elif self.state == CircuitState.HALF_OPEN:
            self._open()
    
    def can_attempt(self) -> bool:
        """Check if operation can be attempted"""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._half_open()
                return True
            return False
        
        # HALF_OPEN state
        return True
    
    def _open(self):
        """Open circuit (stop requests)"""
        self.state = CircuitState.OPEN
        self.last_state_change = datetime.utcnow()
        logger.warning("Circuit breaker OPENED")
    
    def _half_open(self):
        """Half-open circuit (test recovery)"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        self.last_state_change = datetime.utcnow()
        logger.info("Circuit breaker HALF-OPEN (testing recovery)")
    
    def _close(self):
        """Close circuit (normal operation)"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.utcnow()
        logger.info("Circuit breaker CLOSED (recovered)")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout

# ============================================================================
# RETRY MECHANISM
# ============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry mechanism"""
    max_attempts: int = 3
    initial_delay: float = 0.1  # seconds
    max_delay: float = 10.0  # seconds
    exponential_base: float = 2.0
    jitter: bool = True

async def retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args,
    **kwargs
) -> Any:
    """
    Retry function with exponential backoff and jitter
    """
    delay = config.initial_delay
    
    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == config.max_attempts - 1:
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** attempt),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random())
            
            logger.warning(
                f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            
            await asyncio.sleep(delay)

# ============================================================================
# DATABASE NODE
# ============================================================================

@dataclass
class DatabaseNode:
    """Represents a database node (primary or replica)"""
    host: str
    port: int
    database: str
    user: str
    password: str
    role: str  # "primary" or "replica"
    weight: int = 1  # For load balancing
    
    # Health tracking
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    
    # Circuit breaker
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)
    
    def get_dsn(self) -> str:
        """Get PostgreSQL DSN"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    def record_request(self, success: bool, response_time: float):
        """Record request metrics"""
        self.total_requests += 1
        
        if success:
            self.consecutive_failures = 0
            self.circuit_breaker.record_success()
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.circuit_breaker.record_failure()
        
        # Update average response time (exponential moving average)
        alpha = 0.3
        self.avg_response_time = (
            alpha * response_time + (1 - alpha) * self.avg_response_time
        )
    
    def get_health_score(self) -> float:
        """Calculate health score (0-100)"""
        if self.total_requests == 0:
            return 100.0
        
        success_rate = (
            (self.total_requests - self.failed_requests) / self.total_requests * 100
        )
        
        # Penalize for high response time
        response_penalty = min(self.avg_response_time / 10.0, 50.0)
        
        # Penalize for consecutive failures
        failure_penalty = min(self.consecutive_failures * 10, 50.0)
        
        score = success_rate - response_penalty - failure_penalty
        return max(0.0, min(100.0, score))

# ============================================================================
# RESILIENT CONNECTION POOL
# ============================================================================

class ResilientConnectionPool:
    """
    Enterprise-grade connection pool with:
    - Multiple database nodes (primary + replicas)
    - Automatic failover
    - Load balancing
    - Circuit breakers
    - Health checks
    - Retry mechanisms
    """
    
    def __init__(
        self,
        primary_node: DatabaseNode,
        replica_nodes: List[DatabaseNode] = None,
        min_size: int = 5,
        max_size: int = 20,
        health_check_interval: int = 30,
        retry_config: Optional[RetryConfig] = None
    ):
        self.primary_node = primary_node
        self.replica_nodes = replica_nodes or []
        self.min_size = min_size
        self.max_size = max_size
        self.health_check_interval = health_check_interval
        self.retry_config = retry_config or RetryConfig()
        
        # Connection pools
        self.primary_pool: Optional[asyncpg.Pool] = None
        self.replica_pools: Dict[str, asyncpg.Pool] = {}
        
        # Health check task
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.total_queries = 0
        self.failed_queries = 0
        self.failover_count = 0
    
    async def initialize(self):
        """Initialize connection pools"""
        logger.info("Initializing resilient connection pool...")
        
        # Create primary pool
        try:
            self.primary_pool = await self._create_pool(self.primary_node)
            logger.info(f"✓ Primary pool created: {self.primary_node.host}")
        except Exception as e:
            logger.error(f"Failed to create primary pool: {e}")
            self.primary_node.is_healthy = False
        
        # Create replica pools
        for replica in self.replica_nodes:
            try:
                pool = await self._create_pool(replica)
                self.replica_pools[replica.host] = pool
                logger.info(f"✓ Replica pool created: {replica.host}")
            except Exception as e:
                logger.warning(f"Failed to create replica pool {replica.host}: {e}")
                replica.is_healthy = False
        
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("✓ Resilient connection pool initialized")
    
    async def _create_pool(self, node: DatabaseNode) -> asyncpg.Pool:
        """Create connection pool for a node"""
        return await asyncpg.create_pool(
            dsn=node.get_dsn(),
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60,
            timeout=30,
            max_queries=50000,
            max_inactive_connection_lifetime=300
        )
    
    async def execute(
        self,
        query: str,
        *args,
        read_only: bool = False,
        timeout: float = 30.0
    ) -> Any:
        """
        Execute query with automatic failover and retry
        """
        self.total_queries += 1
        
        # Choose node based on query type
        if read_only and self.replica_nodes:
            node = self._select_replica()
            pool = self.replica_pools.get(node.host) if node else None
        else:
            node = self.primary_node
            pool = self.primary_pool
        
        # Check circuit breaker
        if not node.circuit_breaker.can_attempt():
            logger.warning(f"Circuit breaker open for {node.host}, trying fallback...")
            return await self._execute_with_fallback(query, *args, timeout=timeout)
        
        # Execute with retry
        try:
            start_time = time.time()
            
            result = await retry_with_backoff(
                self._execute_on_pool,
                self.retry_config,
                pool,
                query,
                *args,
                timeout=timeout
            )
            
            response_time = time.time() - start_time
            node.record_request(success=True, response_time=response_time)
            
            return result
            
        except Exception as e:
            self.failed_queries += 1
            response_time = time.time() - start_time
            node.record_request(success=False, response_time=response_time)
            
            logger.error(f"Query failed on {node.host}: {e}")
            
            # Try fallback
            return await self._execute_with_fallback(query, *args, timeout=timeout)
    
    async def _execute_on_pool(
        self,
        pool: asyncpg.Pool,
        query: str,
        *args,
        timeout: float = 30.0
    ) -> Any:
        """Execute query on specific pool"""
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def _execute_with_fallback(
        self,
        query: str,
        *args,
        timeout: float = 30.0
    ) -> Any:
        """Execute query with fallback to other nodes"""
        self.failover_count += 1
        
        # Try all nodes in order of health
        all_nodes = [self.primary_node] + self.replica_nodes
        sorted_nodes = sorted(
            [n for n in all_nodes if n.is_healthy],
            key=lambda n: n.get_health_score(),
            reverse=True
        )
        
        for node in sorted_nodes:
            if not node.circuit_breaker.can_attempt():
                continue
            
            pool = (
                self.primary_pool if node == self.primary_node
                else self.replica_pools.get(node.host)
            )
            
            if not pool:
                continue
            
            try:
                start_time = time.time()
                result = await self._execute_on_pool(pool, query, *args, timeout=timeout)
                response_time = time.time() - start_time
                
                node.record_request(success=True, response_time=response_time)
                logger.info(f"✓ Failover successful to {node.host}")
                
                return result
                
            except Exception as e:
                response_time = time.time() - start_time
                node.record_request(success=False, response_time=response_time)
                logger.warning(f"Failover attempt failed on {node.host}: {e}")
                continue
        
        raise Exception("All database nodes are unavailable")
    
    def _select_replica(self) -> Optional[DatabaseNode]:
        """Select replica node using weighted round-robin"""
        healthy_replicas = [
            r for r in self.replica_nodes
            if r.is_healthy and r.circuit_breaker.can_attempt()
        ]
        
        if not healthy_replicas:
            return None
        
        # Weighted selection based on health score
        total_weight = sum(r.weight * r.get_health_score() for r in healthy_replicas)
        
        if total_weight == 0:
            return random.choice(healthy_replicas)
        
        rand = random.uniform(0, total_weight)
        cumulative = 0
        
        for replica in healthy_replicas:
            cumulative += replica.weight * replica.get_health_score()
            if rand <= cumulative:
                return replica
        
        return healthy_replicas[-1]
    
    async def _health_check_loop(self):
        """Periodic health check for all nodes"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_nodes()
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_all_nodes(self):
        """Check health of all database nodes"""
        all_nodes = [self.primary_node] + self.replica_nodes
        
        for node in all_nodes:
            await self._check_node_health(node)
    
    async def _check_node_health(self, node: DatabaseNode):
        """Check health of a single node"""
        pool = (
            self.primary_pool if node == self.primary_node
            else self.replica_pools.get(node.host)
        )
        
        if not pool:
            node.is_healthy = False
            return
        
        try:
            async with pool.acquire() as conn:
                await conn.fetchval('SELECT 1', timeout=5.0)
            
            node.is_healthy = True
            node.last_health_check = datetime.utcnow()
            
        except Exception as e:
            logger.warning(f"Health check failed for {node.host}: {e}")
            node.is_healthy = False
    
    async def close(self):
        """Close all connection pools"""
        logger.info("Closing resilient connection pool...")
        
        if self.health_check_task:
            self.health_check_task.cancel()
        
        if self.primary_pool:
            await self.primary_pool.close()
        
        for pool in self.replica_pools.values():
            await pool.close()
        
        logger.info("✓ Connection pool closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "total_queries": self.total_queries,
            "failed_queries": self.failed_queries,
            "success_rate": (
                (self.total_queries - self.failed_queries) / self.total_queries * 100
                if self.total_queries > 0 else 100.0
            ),
            "failover_count": self.failover_count,
            "primary_health": self.primary_node.get_health_score(),
            "replica_health": [
                {
                    "host": r.host,
                    "health_score": r.get_health_score(),
                    "circuit_state": r.circuit_breaker.state.value
                }
                for r in self.replica_nodes
            ]
        }

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using resilient connection pool"""
    
    # Define database nodes
    primary = DatabaseNode(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database="remittance",
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        role="primary"
    )
    
    replica1 = DatabaseNode(
        host="replica1.example.com",
        port=5432,
        database="remittance",
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        role="replica",
        weight=2
    )
    
    replica2 = DatabaseNode(
        host="replica2.example.com",
        port=5432,
        database="remittance",
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        role="replica",
        weight=1
    )
    
    # Create resilient pool
    pool = ResilientConnectionPool(
        primary_node=primary,
        replica_nodes=[replica1, replica2],
        min_size=5,
        max_size=20,
        health_check_interval=30
    )
    
    await pool.initialize()
    
    # Execute queries
    try:
        # Write query (goes to primary)
        await pool.execute(
            "INSERT INTO transactions (id, amount) VALUES ($1, $2)",
            "txn_123",
            100.50,
            read_only=False
        )
        
        # Read query (goes to replica with load balancing)
        result = await pool.execute(
            "SELECT * FROM transactions WHERE id = $1",
            "txn_123",
            read_only=True
        )
        
        # Get stats
        stats = pool.get_stats()
        print(f"Pool stats: {stats}")
        
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(example_usage())

