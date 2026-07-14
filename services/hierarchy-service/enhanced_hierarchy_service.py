import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Remittance Platform - Enhanced Hierarchy Service
Python API layer with Go-powered hierarchy traversal engine
Provides comprehensive hierarchy management with caching and validation
"""

import os
import uuid
import logging
import subprocess
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
from enum import Enum

import asyncpg
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("enhanced-hierarchy-service")
app.include_router(metrics_router)

from pydantic import BaseModel, validator, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced Hierarchy Service",
    description="Agent hierarchy management with Go-powered traversal engine",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://banking_user:banking_pass@localhost:5432/remittance")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
HIERARCHY_GO_SERVICE = os.getenv("HIERARCHY_GO_SERVICE", "http://localhost:8050")

# Database and Redis connections
db_pool = None
redis_client = None

# Cache TTL
CACHE_TTL = 3600  # 1 hour

# =====================================================
# ENUMS AND CONSTANTS
# =====================================================

class AgentTier(str, Enum):
    SUPER_AGENT = "super_agent"
    SENIOR_AGENT = "senior_agent"
    AGENT = "agent"
    SUB_AGENT = "sub_agent"
    TRAINEE = "trainee"

class NodeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"

# =====================================================
# DATA MODELS
# =====================================================

class HierarchyNodeCreate(BaseModel):
    agent_id: str
    parent_id: Optional[str] = None
    tier: AgentTier
    territory_id: Optional[str] = None
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    metadata: Optional[Dict[str, Any]] = {}

class HierarchyNodeUpdate(BaseModel):
    parent_id: Optional[str] = None
    tier: Optional[AgentTier] = None
    territory_id: Optional[str] = None
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=1)
    status: Optional[NodeStatus] = None
    metadata: Optional[Dict[str, Any]] = None

class HierarchyNodeResponse(BaseModel):
    id: str
    agent_id: str
    parent_id: Optional[str]
    tier: str
    territory_id: Optional[str]
    commission_rate: Optional[Decimal]
    status: str
    depth: int
    path: List[str]
    children_count: int
    descendants_count: int
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class HierarchyTreeNode(BaseModel):
    id: str
    agent_id: str
    tier: str
    children: List['HierarchyTreeNode'] = []
    metadata: Dict[str, Any] = {}

class BulkNodeCreate(BaseModel):
    nodes: List[HierarchyNodeCreate]
    validate_hierarchy: bool = True

class HierarchyStats(BaseModel):
    total_nodes: int
    active_nodes: int
    max_depth: int
    avg_children_per_node: float
    total_super_agents: int
    total_senior_agents: int
    total_agents: int
    total_sub_agents: int
    total_trainees: int

# =====================================================
# DATABASE CONNECTION
# =====================================================

async def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    return await db_pool.acquire()

async def release_db_connection(conn):
    """Release database connection back to pool"""
    await db_pool.release(conn)

async def get_redis_connection():
    """Get Redis connection"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL)
    return redis_client

# =====================================================
# GO SERVICE INTEGRATION
# =====================================================

class GoHierarchyEngine:
    """Integration with Go-powered hierarchy traversal engine"""
    
    @staticmethod
    async def get_ancestors(node_id: str) -> List[str]:
        """Get all ancestors of a node using Go service"""
        try:
            # Call Go service via subprocess (or HTTP in production)
            result = subprocess.run(
                ['go', 'run', '/home/ubuntu/remittance-platform/backend/go-services/hierarchy-engine/main.go',
                 'ancestors', node_id],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Go service error: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Failed to call Go service: {str(e)}")
            # Fallback to Python implementation
            return await GoHierarchyEngine._get_ancestors_python(node_id)
    
    @staticmethod
    async def get_descendants(node_id: str) -> List[str]:
        """Get all descendants of a node using Go service"""
        try:
            result = subprocess.run(
                ['go', 'run', '/home/ubuntu/remittance-platform/backend/go-services/hierarchy-engine/main.go',
                 'descendants', node_id],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return []
        except Exception as e:
            logger.error(f"Failed to call Go service: {str(e)}")
            return await GoHierarchyEngine._get_descendants_python(node_id)
    
    @staticmethod
    async def detect_cycle(node_id: str, parent_id: str) -> bool:
        """Detect if adding parent would create a cycle"""
        try:
            result = subprocess.run(
                ['go', 'run', '/home/ubuntu/remittance-platform/backend/go-services/hierarchy-engine/main.go',
                 'detect-cycle', node_id, parent_id],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                response = json.loads(result.stdout)
                return response.get('has_cycle', False)
            else:
                return False
        except Exception as e:
            logger.error(f"Failed to call Go service: {str(e)}")
            return await GoHierarchyEngine._detect_cycle_python(node_id, parent_id)
    
    @staticmethod
    async def _get_ancestors_python(node_id: str) -> List[str]:
        """Python fallback for getting ancestors"""
        conn = await get_db_connection()
        try:
            ancestors = []
            current_id = node_id
            
            while current_id:
                node = await conn.fetchrow(
                    "SELECT parent_id FROM hierarchy_nodes WHERE id = $1", current_id
                )
                if node and node['parent_id']:
                    ancestors.append(node['parent_id'])
                    current_id = node['parent_id']
                else:
                    break
            
            return ancestors
        finally:
            await release_db_connection(conn)
    
    @staticmethod
    async def _get_descendants_python(node_id: str) -> List[str]:
        """Python fallback for getting descendants"""
        conn = await get_db_connection()
        try:
            descendants = []
            queue = [node_id]
            
            while queue:
                current_id = queue.pop(0)
                children = await conn.fetch(
                    "SELECT id FROM hierarchy_nodes WHERE parent_id = $1", current_id
                )
                for child in children:
                    descendants.append(child['id'])
                    queue.append(child['id'])
            
            return descendants
        finally:
            await release_db_connection(conn)
    
    @staticmethod
    async def _detect_cycle_python(node_id: str, parent_id: str) -> bool:
        """Python fallback for cycle detection"""
        # Check if parent_id is in the descendants of node_id
        descendants = await GoHierarchyEngine._get_descendants_python(node_id)
        return parent_id in descendants

# =====================================================
# HIERARCHY SERVICE
# =====================================================

class HierarchyService:
    """Enhanced hierarchy service with caching and validation"""
    
    def __init__(self, db_connection, redis_connection):
        self.db = db_connection
        self.redis = redis_connection
        self.go_engine = GoHierarchyEngine()
    
    async def create_node(self, node_data: HierarchyNodeCreate) -> str:
        """Create a new hierarchy node"""
        node_id = str(uuid.uuid4())
        
        # Validate parent if specified
        if node_data.parent_id:
            parent = await self.db.fetchrow(
                "SELECT * FROM hierarchy_nodes WHERE id = $1", node_data.parent_id
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Parent node not found")
            
            # Check for circular dependency
            has_cycle = await self.go_engine.detect_cycle(node_id, node_data.parent_id)
            if has_cycle:
                raise HTTPException(status_code=400, detail="Circular dependency detected")
        
        # Calculate depth and path
        depth = 0
        path = [node_id]
        
        if node_data.parent_id:
            parent_node = await self.get_node(node_data.parent_id)
            depth = parent_node['depth'] + 1
            path = parent_node['path'] + [node_id]
        
        # Insert node
        await self.db.execute("""
            INSERT INTO hierarchy_nodes (
                id, agent_id, parent_id, tier, territory_id, commission_rate,
                status, depth, path, metadata, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """, node_id, node_data.agent_id, node_data.parent_id, node_data.tier.value,
            node_data.territory_id, node_data.commission_rate, NodeStatus.ACTIVE,
            depth, path, json.dumps(node_data.metadata), datetime.utcnow(), datetime.utcnow())
        
        # Invalidate cache
        await self._invalidate_cache(node_data.parent_id)
        
        logger.info(f"Created hierarchy node {node_id} for agent {node_data.agent_id}")
        return node_id
    
    async def update_node(self, node_id: str, update_data: HierarchyNodeUpdate) -> bool:
        """Update a hierarchy node"""
        # Get existing node
        node = await self.db.fetchrow("SELECT * FROM hierarchy_nodes WHERE id = $1", node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # If changing parent, validate
        if update_data.parent_id and update_data.parent_id != node['parent_id']:
            # Check for circular dependency
            has_cycle = await self.go_engine.detect_cycle(node_id, update_data.parent_id)
            if has_cycle:
                raise HTTPException(status_code=400, detail="Circular dependency detected")
            
            # Recalculate depth and path for this node and all descendants
            await self._recalculate_hierarchy(node_id, update_data.parent_id)
        
        # Build update query
        updates = []
        params = []
        param_count = 1
        
        if update_data.parent_id is not None:
            params.append(update_data.parent_id)
            updates.append(f"parent_id = ${param_count}")
            param_count += 1
        
        if update_data.tier:
            params.append(update_data.tier.value)
            updates.append(f"tier = ${param_count}")
            param_count += 1
        
        if update_data.territory_id is not None:
            params.append(update_data.territory_id)
            updates.append(f"territory_id = ${param_count}")
            param_count += 1
        
        if update_data.commission_rate is not None:
            params.append(update_data.commission_rate)
            updates.append(f"commission_rate = ${param_count}")
            param_count += 1
        
        if update_data.status:
            params.append(update_data.status.value)
            updates.append(f"status = ${param_count}")
            param_count += 1
        
        if update_data.metadata is not None:
            params.append(json.dumps(update_data.metadata))
            updates.append(f"metadata = ${param_count}")
            param_count += 1
        
        if updates:
            params.append(datetime.utcnow())
            updates.append(f"updated_at = ${param_count}")
            param_count += 1
            
            params.append(node_id)
            query = f"UPDATE hierarchy_nodes SET {', '.join(updates)} WHERE id = ${param_count}"
            
            await self.db.execute(query, *params)
            
            # Invalidate cache
            await self._invalidate_cache(node_id)
            await self._invalidate_cache(node['parent_id'])
            
            logger.info(f"Updated hierarchy node {node_id}")
            return True
        
        return False
    
    async def delete_node(self, node_id: str, reassign_children: bool = False) -> bool:
        """Delete a hierarchy node"""
        node = await self.db.fetchrow("SELECT * FROM hierarchy_nodes WHERE id = $1", node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Check for children
        children = await self.db.fetch(
            "SELECT id FROM hierarchy_nodes WHERE parent_id = $1", node_id
        )
        
        if children and not reassign_children:
            raise HTTPException(
                status_code=400,
                detail=f"Node has {len(children)} children. Set reassign_children=true to reassign them."
            )
        
        if reassign_children and children:
            # Reassign children to this node's parent
            await self.db.execute("""
                UPDATE hierarchy_nodes
                SET parent_id = $1, updated_at = $2
                WHERE parent_id = $3
            """, node['parent_id'], datetime.utcnow(), node_id)
        
        # Delete node
        await self.db.execute("DELETE FROM hierarchy_nodes WHERE id = $1", node_id)
        
        # Invalidate cache
        await self._invalidate_cache(node['parent_id'])
        
        logger.info(f"Deleted hierarchy node {node_id}")
        return True
    
    async def get_node(self, node_id: str) -> Dict:
        """Get node details with caching"""
        # Check cache
        cache_key = f"hierarchy:node:{node_id}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Fetch from database
        node = await self.db.fetchrow("""
            SELECT hn.*,
                   (SELECT COUNT(*) FROM hierarchy_nodes WHERE parent_id = hn.id) as children_count
            FROM hierarchy_nodes hn
            WHERE hn.id = $1
        """, node_id)
        
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        # Get descendants count
        descendants = await self.go_engine.get_descendants(node_id)
        
        result = dict(node)
        result['descendants_count'] = len(descendants)
        
        # Cache result
        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(result, default=str))
        
        return result
    
    async def get_ancestors(self, node_id: str) -> List[Dict]:
        """Get all ancestors of a node"""
        # Check cache
        cache_key = f"hierarchy:ancestors:{node_id}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            ancestor_ids = json.loads(cached)
        else:
            ancestor_ids = await self.go_engine.get_ancestors(node_id)
            await self.redis.setex(cache_key, CACHE_TTL, json.dumps(ancestor_ids))
        
        # Fetch ancestor details
        if not ancestor_ids:
            return []
        
        ancestors = await self.db.fetch("""
            SELECT * FROM hierarchy_nodes
            WHERE id = ANY($1)
            ORDER BY depth ASC
        """, ancestor_ids)
        
        return [dict(a) for a in ancestors]
    
    async def get_descendants(self, node_id: str, max_depth: Optional[int] = None) -> List[Dict]:
        """Get all descendants of a node"""
        # Check cache
        cache_key = f"hierarchy:descendants:{node_id}:{max_depth or 'all'}"
        cached = await self.redis.get(cache_key)
        
        if cached:
            descendant_ids = json.loads(cached)
        else:
            descendant_ids = await self.go_engine.get_descendants(node_id)
            await self.redis.setex(cache_key, CACHE_TTL, json.dumps(descendant_ids))
        
        # Fetch descendant details
        if not descendant_ids:
            return []
        
        query = "SELECT * FROM hierarchy_nodes WHERE id = ANY($1)"
        params = [descendant_ids]
        
        if max_depth is not None:
            node = await self.get_node(node_id)
            params.append(node['depth'] + max_depth)
            query += f" AND depth <= ${len(params)}"
        
        query += " ORDER BY depth ASC, created_at ASC"
        
        descendants = await self.db.fetch(query, *params)
        return [dict(d) for d in descendants]
    
    async def get_children(self, node_id: str) -> List[Dict]:
        """Get direct children of a node"""
        children = await self.db.fetch("""
            SELECT * FROM hierarchy_nodes
            WHERE parent_id = $1
            ORDER BY created_at ASC
        """, node_id)
        
        return [dict(c) for c in children]
    
    async def get_tree(self, root_id: str, max_depth: Optional[int] = None) -> Dict:
        """Get hierarchy tree starting from a node"""
        root = await self.get_node(root_id)
        
        async def build_tree(node_id: str, current_depth: int) -> Dict:
            node = await self.get_node(node_id)
            children = []
            
            if max_depth is None or current_depth < max_depth:
                child_nodes = await self.get_children(node_id)
                for child in child_nodes:
                    children.append(await build_tree(child['id'], current_depth + 1))
            
            return {
                'id': node['id'],
                'agent_id': node['agent_id'],
                'tier': node['tier'],
                'children': children,
                'metadata': node.get('metadata', {})
            }
        
        return await build_tree(root_id, 0)
    
    async def get_path(self, node_id: str) -> List[Dict]:
        """Get path from root to node"""
        node = await self.get_node(node_id)
        path_ids = node['path']
        
        if not path_ids:
            return [node]
        
        path_nodes = await self.db.fetch("""
            SELECT * FROM hierarchy_nodes
            WHERE id = ANY($1)
            ORDER BY depth ASC
        """, path_ids)
        
        return [dict(n) for n in path_nodes]
    
    async def get_stats(self) -> Dict:
        """Get hierarchy statistics"""
        stats = await self.db.fetchrow("""
            SELECT
                COUNT(*) as total_nodes,
                COUNT(*) FILTER (WHERE status = 'active') as active_nodes,
                MAX(depth) as max_depth,
                AVG(children_count) as avg_children_per_node,
                COUNT(*) FILTER (WHERE tier = 'super_agent') as total_super_agents,
                COUNT(*) FILTER (WHERE tier = 'senior_agent') as total_senior_agents,
                COUNT(*) FILTER (WHERE tier = 'agent') as total_agents,
                COUNT(*) FILTER (WHERE tier = 'sub_agent') as total_sub_agents,
                COUNT(*) FILTER (WHERE tier = 'trainee') as total_trainees
            FROM (
                SELECT *,
                       (SELECT COUNT(*) FROM hierarchy_nodes hn2 WHERE hn2.parent_id = hn1.id) as children_count
                FROM hierarchy_nodes hn1
            ) subq
        """)
        
        return dict(stats)
    
    async def bulk_create_nodes(self, nodes: List[HierarchyNodeCreate], validate: bool = True) -> List[str]:
        """Bulk create hierarchy nodes"""
        created_ids = []
        
        for node_data in nodes:
            try:
                node_id = await self.create_node(node_data)
                created_ids.append(node_id)
            except Exception as e:
                if validate:
                    # Rollback all created nodes
                    for created_id in created_ids:
                        await self.db.execute("DELETE FROM hierarchy_nodes WHERE id = $1", created_id)
                    raise HTTPException(
                        status_code=400,
                        detail=f"Bulk create failed at node {len(created_ids) + 1}: {str(e)}"
                    )
                else:
                    logger.warning(f"Failed to create node: {str(e)}")
        
        return created_ids
    
    async def validate_hierarchy(self) -> Dict[str, Any]:
        """Validate entire hierarchy for integrity issues"""
        issues = {
            'orphan_nodes': [],
            'circular_dependencies': [],
            'invalid_depths': [],
            'invalid_paths': []
        }
        
        # Check for orphan nodes (parent_id not null but parent doesn't exist)
        orphans = await self.db.fetch("""
            SELECT hn.id, hn.agent_id, hn.parent_id
            FROM hierarchy_nodes hn
            LEFT JOIN hierarchy_nodes parent ON hn.parent_id = parent.id
            WHERE hn.parent_id IS NOT NULL AND parent.id IS NULL
        """)
        issues['orphan_nodes'] = [dict(o) for o in orphans]
        
        # Check for invalid depths
        invalid_depths = await self.db.fetch("""
            SELECT hn.id, hn.depth, parent.depth as parent_depth
            FROM hierarchy_nodes hn
            JOIN hierarchy_nodes parent ON hn.parent_id = parent.id
            WHERE hn.depth != parent.depth + 1
        """)
        issues['invalid_depths'] = [dict(d) for d in invalid_depths]
        
        return issues
    
    async def _recalculate_hierarchy(self, node_id: str, new_parent_id: Optional[str]):
        """Recalculate depth and path for node and all descendants"""
        # Calculate new depth and path
        new_depth = 0
        new_path = [node_id]
        
        if new_parent_id:
            parent = await self.get_node(new_parent_id)
            new_depth = parent['depth'] + 1
            new_path = parent['path'] + [node_id]
        
        # Update this node
        await self.db.execute("""
            UPDATE hierarchy_nodes
            SET depth = $1, path = $2, updated_at = $3
            WHERE id = $4
        """, new_depth, new_path, datetime.utcnow(), node_id)
        
        # Update all descendants recursively
        descendants = await self.go_engine.get_descendants(node_id)
        for descendant_id in descendants:
            # Recalculate for each descendant
            desc_node = await self.db.fetchrow(
                "SELECT * FROM hierarchy_nodes WHERE id = $1", descendant_id
            )
            if desc_node and desc_node['parent_id']:
                desc_parent = await self.get_node(desc_node['parent_id'])
                desc_depth = desc_parent['depth'] + 1
                desc_path = desc_parent['path'] + [descendant_id]
                
                await self.db.execute("""
                    UPDATE hierarchy_nodes
                    SET depth = $1, path = $2, updated_at = $3
                    WHERE id = $4
                """, desc_depth, desc_path, datetime.utcnow(), descendant_id)
    
    async def _invalidate_cache(self, node_id: Optional[str]):
        """Invalidate cache for a node and related queries"""
        if not node_id:
            return
        
        patterns = [
            f"hierarchy:node:{node_id}",
            f"hierarchy:ancestors:{node_id}",
            f"hierarchy:descendants:{node_id}:*"
        ]
        
        for pattern in patterns:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)

# =====================================================
# API ENDPOINTS
# =====================================================

@app.post("/hierarchy/nodes", response_model=HierarchyNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(node_data: HierarchyNodeCreate):
    """Create a new hierarchy node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        node_id = await service.create_node(node_data)
        node = await service.get_node(node_id)
        return node
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}", response_model=HierarchyNodeResponse)
async def get_node(node_id: str):
    """Get hierarchy node details"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        node = await service.get_node(node_id)
        return node
    finally:
        await release_db_connection(conn)

@app.put("/hierarchy/nodes/{node_id}")
async def update_node(node_id: str, update_data: HierarchyNodeUpdate):
    """Update hierarchy node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        result = await service.update_node(node_id, update_data)
        return {'success': result, 'node_id': node_id}
    finally:
        await release_db_connection(conn)

@app.delete("/hierarchy/nodes/{node_id}")
async def delete_node(node_id: str, reassign_children: bool = False):
    """Delete hierarchy node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        result = await service.delete_node(node_id, reassign_children)
        return {'success': result, 'node_id': node_id}
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}/ancestors")
async def get_ancestors(node_id: str):
    """Get all ancestors of a node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        ancestors = await service.get_ancestors(node_id)
        return {'node_id': node_id, 'ancestors': ancestors}
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}/descendants")
async def get_descendants(node_id: str, max_depth: Optional[int] = None):
    """Get all descendants of a node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        descendants = await service.get_descendants(node_id, max_depth)
        return {'node_id': node_id, 'descendants': descendants, 'count': len(descendants)}
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}/children")
async def get_children(node_id: str):
    """Get direct children of a node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        children = await service.get_children(node_id)
        return {'node_id': node_id, 'children': children, 'count': len(children)}
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}/tree")
async def get_tree(node_id: str, max_depth: Optional[int] = None):
    """Get hierarchy tree starting from a node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        tree = await service.get_tree(node_id, max_depth)
        return tree
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/nodes/{node_id}/path")
async def get_path(node_id: str):
    """Get path from root to node"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        path = await service.get_path(node_id)
        return {'node_id': node_id, 'path': path}
    finally:
        await release_db_connection(conn)

@app.get("/hierarchy/stats", response_model=HierarchyStats)
async def get_stats():
    """Get hierarchy statistics"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        stats = await service.get_stats()
        return stats
    finally:
        await release_db_connection(conn)

@app.post("/hierarchy/nodes/bulk")
async def bulk_create_nodes(bulk_data: BulkNodeCreate):
    """Bulk create hierarchy nodes"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        created_ids = await service.bulk_create_nodes(bulk_data.nodes, bulk_data.validate_hierarchy)
        return {'success': True, 'created_count': len(created_ids), 'node_ids': created_ids}
    finally:
        await release_db_connection(conn)

@app.post("/hierarchy/validate")
async def validate_hierarchy():
    """Validate hierarchy integrity"""
    conn = await get_db_connection()
    redis_conn = await get_redis_connection()
    
    try:
        service = HierarchyService(conn, redis_conn)
        issues = await service.validate_hierarchy()
        has_issues = any(len(v) > 0 for v in issues.values())
        return {'valid': not has_issues, 'issues': issues}
    finally:
        await release_db_connection(conn)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "enhanced-hierarchy-service",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

# =====================================================
# STARTUP AND SHUTDOWN
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    global db_pool, redis_client
    logger.info("Starting Enhanced Hierarchy Service...")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    redis_client = redis.from_url(REDIS_URL)
    logger.info("Enhanced Hierarchy Service started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Close connections on shutdown"""
    global db_pool, redis_client
    logger.info("Shutting down Enhanced Hierarchy Service...")
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    logger.info("Enhanced Hierarchy Service shut down successfully")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8015))
    uvicorn.run(app, host="0.0.0.0", port=port)

