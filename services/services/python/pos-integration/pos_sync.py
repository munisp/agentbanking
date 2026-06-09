"""
Fluvio Bi-directional Synchronization & Conflict Resolution
Handles data consistency, conflict detection, and resolution strategies
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
import hashlib
import uuid

logger = logging.getLogger(__name__)

# ============================================================================
# CONFLICT RESOLUTION STRATEGIES
# ============================================================================

class ConflictResolutionStrategy(str, Enum):
    """Strategies for resolving data conflicts"""
    LAST_WRITE_WINS = "last_write_wins"           # Most recent timestamp wins
    FIRST_WRITE_WINS = "first_write_wins"         # First write is authoritative
    HIGHEST_VERSION_WINS = "highest_version_wins" # Highest version number wins
    MERGE = "merge"                                # Merge both changes
    MANUAL = "manual"                              # Require manual resolution
    SOURCE_PRIORITY = "source_priority"            # Priority based on source
    BUSINESS_RULE = "business_rule"                # Custom business logic

class ConflictType(str, Enum):
    """Types of conflicts"""
    UPDATE_UPDATE = "update_update"     # Both sides updated same record
    UPDATE_DELETE = "update_delete"     # One updated, one deleted
    DELETE_DELETE = "delete_delete"     # Both deleted (no conflict)
    CREATE_CREATE = "create_create"     # Both created same ID
    VERSION_MISMATCH = "version_mismatch" # Version number conflict

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class SyncMetadata:
    """Metadata for synchronization"""
    entity_id: str
    entity_type: str
    version: int
    timestamp: datetime
    source: str  # "pos", "central", "terminal"
    checksum: str  # SHA-256 hash of data
    operation: str  # "create", "update", "delete"
    conflict_resolved: bool = False
    resolution_strategy: Optional[str] = None

@dataclass
class SyncEvent:
    """Synchronization event"""
    sync_id: str
    metadata: SyncMetadata
    data: Dict[str, Any]
    previous_version: Optional[Dict[str, Any]] = None

@dataclass
class Conflict:
    """Data conflict"""
    conflict_id: str
    conflict_type: ConflictType
    entity_id: str
    entity_type: str
    local_version: SyncEvent
    remote_version: SyncEvent
    detected_at: datetime
    resolved: bool = False
    resolution: Optional[Dict[str, Any]] = None
    resolution_strategy: Optional[ConflictResolutionStrategy] = None

# ============================================================================
# VERSION VECTOR CLOCK (For Distributed Consistency)
# ============================================================================

class VectorClock:
    """
    Vector clock for tracking causality in distributed systems
    Helps detect concurrent updates and conflicts
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clock: Dict[str, int] = {node_id: 0}
    
    def increment(self):
        """Increment local clock"""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
    
    def update(self, other_clock: Dict[str, int]):
        """Update clock with remote clock (merge)"""
        for node, timestamp in other_clock.items():
            self.clock[node] = max(self.clock.get(node, 0), timestamp)
        self.increment()
    
    def compare(self, other_clock: Dict[str, int]) -> str:
        """
        Compare with another clock
        Returns: "before", "after", "concurrent", "equal"
        """
        self_greater = False
        other_greater = False
        
        all_nodes = set(self.clock.keys()) | set(other_clock.keys())
        
        for node in all_nodes:
            self_ts = self.clock.get(node, 0)
            other_ts = other_clock.get(node, 0)
            
            if self_ts > other_ts:
                self_greater = True
            elif other_ts > self_ts:
                other_greater = True
        
        if self_greater and not other_greater:
            return "after"
        elif other_greater and not self_greater:
            return "before"
        elif not self_greater and not other_greater:
            return "equal"
        else:
            return "concurrent"  # Conflict!
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary"""
        return self.clock.copy()
    
    @classmethod
    def from_dict(cls, node_id: str, clock_dict: Dict[str, int]) -> 'VectorClock':
        """Create from dictionary"""
        vc = cls(node_id)
        vc.clock = clock_dict.copy()
        return vc

# ============================================================================
# SYNCHRONIZATION MANAGER
# ============================================================================

class SyncManager:
    """
    Manages bi-directional synchronization between POS and Fluvio
    Handles conflict detection and resolution
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.vector_clock = VectorClock(node_id)
        
        # Local state
        self.local_state: Dict[str, SyncEvent] = {}
        
        # Conflict queue
        self.conflicts: List[Conflict] = []
        
        # Sync log (for audit trail)
        self.sync_log: List[Dict[str, Any]] = []
        
        # Configuration
        self.default_strategy = ConflictResolutionStrategy.LAST_WRITE_WINS
        self.strategy_by_entity: Dict[str, ConflictResolutionStrategy] = {
            "transaction": ConflictResolutionStrategy.FIRST_WRITE_WINS,
            "terminal_config": ConflictResolutionStrategy.LAST_WRITE_WINS,
            "fraud_rule": ConflictResolutionStrategy.HIGHEST_VERSION_WINS,
            "price": ConflictResolutionStrategy.LAST_WRITE_WINS,
            "inventory": ConflictResolutionStrategy.MERGE,
        }
    
    # ========================================================================
    # OUTBOUND SYNC (Local → Fluvio)
    # ========================================================================
    
    async def prepare_sync_event(
        self,
        entity_id: str,
        entity_type: str,
        data: Dict[str, Any],
        operation: str
    ) -> SyncEvent:
        """
        Prepare data for synchronization
        Adds metadata, version, and checksum
        """
        # Increment vector clock
        self.vector_clock.increment()
        
        # Calculate checksum
        checksum = self._calculate_checksum(data)
        
        # Get current version
        current = self.local_state.get(entity_id)
        version = (current.metadata.version + 1) if current else 1
        
        # Create metadata
        metadata = SyncMetadata(
            entity_id=entity_id,
            entity_type=entity_type,
            version=version,
            timestamp=datetime.utcnow(),
            source=self.node_id,
            checksum=checksum,
            operation=operation
        )
        
        # Create sync event
        sync_event = SyncEvent(
            sync_id=str(uuid.uuid4()),
            metadata=metadata,
            data=data,
            previous_version=current.data if current else None
        )
        
        # Update local state
        self.local_state[entity_id] = sync_event
        
        # Log sync
        self._log_sync("outbound", sync_event)
        
        logger.info(f"📤 Prepared sync: {entity_type}/{entity_id} v{version}")
        
        return sync_event
    
    # ========================================================================
    # INBOUND SYNC (Fluvio → Local)
    # ========================================================================
    
    async def process_incoming_event(
        self,
        sync_event: SyncEvent
    ) -> Tuple[bool, Optional[Conflict]]:
        """
        Process incoming synchronization event
        Returns: (success, conflict)
        """
        entity_id = sync_event.metadata.entity_id
        entity_type = sync_event.metadata.entity_type
        
        logger.info(f"📥 Processing incoming: {entity_type}/{entity_id}")
        
        # Check if we have local version
        local_version = self.local_state.get(entity_id)
        
        if not local_version:
            # No local version, accept remote
            return await self._accept_remote(sync_event)
        
        # Detect conflict
        conflict = await self._detect_conflict(local_version, sync_event)
        
        if conflict:
            logger.warning(f"⚠️  Conflict detected: {conflict.conflict_type.value}")
            self.conflicts.append(conflict)
            
            # Attempt automatic resolution
            resolved = await self._resolve_conflict(conflict)
            
            if resolved:
                return True, None
            else:
                return False, conflict
        
        # No conflict, accept remote
        return await self._accept_remote(sync_event)
    
    async def _accept_remote(self, sync_event: SyncEvent) -> Tuple[bool, None]:
        """Accept remote version"""
        entity_id = sync_event.metadata.entity_id
        
        # Update local state
        self.local_state[entity_id] = sync_event
        
        # Update vector clock
        if hasattr(sync_event.data, 'vector_clock'):
            self.vector_clock.update(sync_event.data['vector_clock'])
        
        # Log sync
        self._log_sync("inbound", sync_event)
        
        logger.info(f"✓ Accepted remote: {entity_id}")
        
        return True, None
    
    # ========================================================================
    # CONFLICT DETECTION
    # ========================================================================
    
    async def _detect_conflict(
        self,
        local: SyncEvent,
        remote: SyncEvent
    ) -> Optional[Conflict]:
        """
        Detect if there's a conflict between local and remote versions
        """
        # Check operations
        local_op = local.metadata.operation
        remote_op = remote.metadata.operation
        
        # Determine conflict type
        if local_op == "update" and remote_op == "update":
            # Both updated - check if concurrent
            if self._is_concurrent(local, remote):
                conflict_type = ConflictType.UPDATE_UPDATE
            else:
                return None  # One happened after the other
        
        elif local_op == "update" and remote_op == "delete":
            conflict_type = ConflictType.UPDATE_DELETE
        
        elif local_op == "delete" and remote_op == "update":
            conflict_type = ConflictType.UPDATE_DELETE
        
        elif local_op == "delete" and remote_op == "delete":
            # Both deleted - no conflict
            return None
        
        elif local_op == "create" and remote_op == "create":
            conflict_type = ConflictType.CREATE_CREATE
        
        else:
            # Check version mismatch
            if local.metadata.version != remote.metadata.version:
                conflict_type = ConflictType.VERSION_MISMATCH
            else:
                return None
        
        # Create conflict
        conflict = Conflict(
            conflict_id=str(uuid.uuid4()),
            conflict_type=conflict_type,
            entity_id=local.metadata.entity_id,
            entity_type=local.metadata.entity_type,
            local_version=local,
            remote_version=remote,
            detected_at=datetime.utcnow()
        )
        
        return conflict
    
    def _is_concurrent(self, local: SyncEvent, remote: SyncEvent) -> bool:
        """Check if two events are concurrent (conflict)"""
        # Compare timestamps
        time_diff = abs((local.metadata.timestamp - remote.metadata.timestamp).total_seconds())
        
        # If within 1 second, consider concurrent
        if time_diff < 1.0:
            return True
        
        # Compare checksums
        if local.metadata.checksum != remote.metadata.checksum:
            return True
        
        return False
    
    # ========================================================================
    # CONFLICT RESOLUTION
    # ========================================================================
    
    async def _resolve_conflict(self, conflict: Conflict) -> bool:
        """
        Automatically resolve conflict based on strategy
        Returns True if resolved, False if needs manual resolution
        """
        # Get resolution strategy
        strategy = self.strategy_by_entity.get(
            conflict.entity_type,
            self.default_strategy
        )
        
        logger.info(f"🔧 Resolving conflict with strategy: {strategy.value}")
        
        # Apply strategy
        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            resolved = await self._resolve_last_write_wins(conflict)
        
        elif strategy == ConflictResolutionStrategy.FIRST_WRITE_WINS:
            resolved = await self._resolve_first_write_wins(conflict)
        
        elif strategy == ConflictResolutionStrategy.HIGHEST_VERSION_WINS:
            resolved = await self._resolve_highest_version_wins(conflict)
        
        elif strategy == ConflictResolutionStrategy.MERGE:
            resolved = await self._resolve_merge(conflict)
        
        elif strategy == ConflictResolutionStrategy.SOURCE_PRIORITY:
            resolved = await self._resolve_source_priority(conflict)
        
        elif strategy == ConflictResolutionStrategy.BUSINESS_RULE:
            resolved = await self._resolve_business_rule(conflict)
        
        else:
            # Manual resolution required
            logger.warning(f"⚠️  Manual resolution required for {conflict.conflict_id}")
            return False
        
        if resolved:
            conflict.resolved = True
            conflict.resolution_strategy = strategy
            logger.info(f"✓ Conflict resolved: {conflict.conflict_id}")
        
        return resolved
    
    async def _resolve_last_write_wins(self, conflict: Conflict) -> bool:
        """Last write wins - most recent timestamp"""
        local = conflict.local_version
        remote = conflict.remote_version
        
        if remote.metadata.timestamp > local.metadata.timestamp:
            winner = remote
            logger.info("Remote wins (newer)")
        else:
            winner = local
            logger.info("Local wins (newer)")
        
        # Apply winner
        self.local_state[conflict.entity_id] = winner
        conflict.resolution = winner.data
        
        return True
    
    async def _resolve_first_write_wins(self, conflict: Conflict) -> bool:
        """First write wins - earliest timestamp (for transactions)"""
        local = conflict.local_version
        remote = conflict.remote_version
        
        if remote.metadata.timestamp < local.metadata.timestamp:
            winner = remote
            logger.info("Remote wins (earlier)")
        else:
            winner = local
            logger.info("Local wins (earlier)")
        
        self.local_state[conflict.entity_id] = winner
        conflict.resolution = winner.data
        
        return True
    
    async def _resolve_highest_version_wins(self, conflict: Conflict) -> bool:
        """Highest version number wins"""
        local = conflict.local_version
        remote = conflict.remote_version
        
        if remote.metadata.version > local.metadata.version:
            winner = remote
            logger.info(f"Remote wins (v{remote.metadata.version})")
        else:
            winner = local
            logger.info(f"Local wins (v{local.metadata.version})")
        
        self.local_state[conflict.entity_id] = winner
        conflict.resolution = winner.data
        
        return True
    
    async def _resolve_merge(self, conflict: Conflict) -> bool:
        """Merge both versions (for non-conflicting fields)"""
        local = conflict.local_version
        remote = conflict.remote_version
        
        # Start with local data
        merged = local.data.copy()
        
        # Merge remote changes
        for key, remote_value in remote.data.items():
            local_value = merged.get(key)
            
            # If field doesn't exist locally, add it
            if local_value is None:
                merged[key] = remote_value
            
            # If values differ, use most recent
            elif local_value != remote_value:
                if remote.metadata.timestamp > local.metadata.timestamp:
                    merged[key] = remote_value
                    logger.info(f"Merged field '{key}' from remote")
        
        # Create merged version
        merged_metadata = SyncMetadata(
            entity_id=conflict.entity_id,
            entity_type=conflict.entity_type,
            version=max(local.metadata.version, remote.metadata.version) + 1,
            timestamp=datetime.utcnow(),
            source=self.node_id,
            checksum=self._calculate_checksum(merged),
            operation="update",
            conflict_resolved=True,
            resolution_strategy="merge"
        )
        
        merged_event = SyncEvent(
            sync_id=str(uuid.uuid4()),
            metadata=merged_metadata,
            data=merged
        )
        
        self.local_state[conflict.entity_id] = merged_event
        conflict.resolution = merged
        
        logger.info("✓ Merged both versions")
        
        return True
    
    async def _resolve_source_priority(self, conflict: Conflict) -> bool:
        """Resolve based on source priority (central > terminal)"""
        source_priority = {
            "central": 3,
            "pos": 2,
            "terminal": 1
        }
        
        local = conflict.local_version
        remote = conflict.remote_version
        
        local_priority = source_priority.get(local.metadata.source, 0)
        remote_priority = source_priority.get(remote.metadata.source, 0)
        
        if remote_priority > local_priority:
            winner = remote
            logger.info(f"Remote wins (source: {remote.metadata.source})")
        else:
            winner = local
            logger.info(f"Local wins (source: {local.metadata.source})")
        
        self.local_state[conflict.entity_id] = winner
        conflict.resolution = winner.data
        
        return True
    
    async def _resolve_business_rule(self, conflict: Conflict) -> bool:
        """Resolve using custom business rules"""
        entity_type = conflict.entity_type
        
        # Example: For transactions, first write always wins
        if entity_type == "transaction":
            return await self._resolve_first_write_wins(conflict)
        
        # Example: For prices, last write wins
        elif entity_type == "price":
            return await self._resolve_last_write_wins(conflict)
        
        # Example: For inventory, merge quantities
        elif entity_type == "inventory":
            return await self._resolve_inventory_conflict(conflict)
        
        # Default: manual resolution
        return False
    
    async def _resolve_inventory_conflict(self, conflict: Conflict) -> bool:
        """Special resolution for inventory conflicts"""
        local = conflict.local_version
        remote = conflict.remote_version
        
        # Merge inventory quantities (sum adjustments)
        local_qty = local.data.get('quantity', 0)
        remote_qty = remote.data.get('quantity', 0)
        
        # Calculate adjustment
        local_adj = local.data.get('adjustment', 0)
        remote_adj = remote.data.get('adjustment', 0)
        
        # Merged quantity = base + both adjustments
        merged_qty = local_qty + remote_adj
        
        merged = local.data.copy()
        merged['quantity'] = merged_qty
        merged['last_sync'] = datetime.utcnow().isoformat()
        
        # Create merged version
        merged_metadata = SyncMetadata(
            entity_id=conflict.entity_id,
            entity_type="inventory",
            version=max(local.metadata.version, remote.metadata.version) + 1,
            timestamp=datetime.utcnow(),
            source=self.node_id,
            checksum=self._calculate_checksum(merged),
            operation="update",
            conflict_resolved=True,
            resolution_strategy="inventory_merge"
        )
        
        merged_event = SyncEvent(
            sync_id=str(uuid.uuid4()),
            metadata=merged_metadata,
            data=merged
        )
        
        self.local_state[conflict.entity_id] = merged_event
        conflict.resolution = merged
        
        logger.info(f"✓ Merged inventory: {local_qty} + {remote_adj} = {merged_qty}")
        
        return True
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate SHA-256 checksum of data"""
        data_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_json.encode()).hexdigest()
    
    def _log_sync(self, direction: str, sync_event: SyncEvent):
        """Log synchronization event"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "direction": direction,
            "sync_id": sync_event.sync_id,
            "entity_id": sync_event.metadata.entity_id,
            "entity_type": sync_event.metadata.entity_type,
            "version": sync_event.metadata.version,
            "operation": sync_event.metadata.operation,
            "source": sync_event.metadata.source
        }
        
        self.sync_log.append(log_entry)
    
    # ========================================================================
    # MONITORING & REPORTING
    # ========================================================================
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        total_syncs = len(self.sync_log)
        outbound = len([s for s in self.sync_log if s['direction'] == 'outbound'])
        inbound = len([s for s in self.sync_log if s['direction'] == 'inbound'])
        
        total_conflicts = len(self.conflicts)
        resolved = len([c for c in self.conflicts if c.resolved])
        unresolved = total_conflicts - resolved
        
        return {
            "total_syncs": total_syncs,
            "outbound_syncs": outbound,
            "inbound_syncs": inbound,
            "total_conflicts": total_conflicts,
            "resolved_conflicts": resolved,
            "unresolved_conflicts": unresolved,
            "resolution_rate": (resolved / total_conflicts * 100) if total_conflicts > 0 else 100,
            "entities_synced": len(self.local_state)
        }
    
    def get_unresolved_conflicts(self) -> List[Conflict]:
        """Get list of unresolved conflicts"""
        return [c for c in self.conflicts if not c.resolved]

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

# Create sync manager (node_id should be unique per POS instance)
sync_manager = SyncManager(node_id="pos_001")

