"""
Permify Client Library for Remittance Platform V11.0

Provides a reusable Permify client for fine-grained authorization.

Features:
- Permission checking
- Relationship management (write, delete)
- Relationship expansion
- Resource lookup
- Bulk operations
- Caching for performance

Author: Manus AI
Date: November 11, 2025
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
import httpx
from functools import lru_cache


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PermifyClient:
    """
    Permify client wrapper for Remittance Platform.
    
    Usage:
        client = PermifyClient()
        
        # Check permission
        allowed = await client.check_permission(
            entity="transaction",
            entity_id="txn-123",
            permission="view",
            subject="user:agent-001"
        )
        
        # Write relationships
        await client.write_relationships([
            {
                "entity": "agent",
                "id": "agent-001",
                "relation": "owner",
                "subject": "user:agent-001"
            }
        ])
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        tenant_id: str = "remittance",
        api_key: Optional[str] = None,
        cache_ttl: int = 300  # 5 minutes
    ):
        """
        Initialize Permify client.
        
        Args:
            endpoint: Permify HTTP endpoint (default: http://localhost:3478)
            tenant_id: Tenant ID for multi-tenancy
            api_key: Optional API key for authentication
            cache_ttl: Cache TTL in seconds
        """
        self.endpoint = endpoint or os.getenv("PERMIFY_ENDPOINT", "http://localhost:3476")
        self.tenant_id = tenant_id
        self.api_key = api_key or os.getenv("PERMIFY_API_KEY")
        self.cache_ttl = cache_ttl
        
        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.endpoint,
            headers=self._get_headers(),
            timeout=30.0
        )
        
        # Metrics
        self.permission_checks = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.relationship_writes = 0
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers."""
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        return headers
    
    # ========================================================================
    # Permission Checking
    # ========================================================================
    
    async def check_permission(
        self,
        entity: str,
        entity_id: str,
        permission: str,
        subject: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if subject has permission on entity.
        
        Args:
            entity: Entity type (e.g., "transaction", "agent")
            entity_id: Entity ID (e.g., "txn-123", "agent-001")
            permission: Permission name (e.g., "view", "edit")
            subject: Subject (e.g., "user:agent-001")
            context: Optional context data
            
        Returns:
            True if permission granted
        """
        try:
            # Check cache first
            cache_key = f"{entity}:{entity_id}:{permission}:{subject}"
            cached_result = self._get_from_cache(cache_key)
            
            if cached_result is not None:
                self.cache_hits += 1
                return cached_result
            
            self.cache_misses += 1
            
            # Make API call
            payload = {
                "tenant_id": self.tenant_id,
                "entity": {
                    "type": entity,
                    "id": entity_id
                },
                "permission": permission,
                "subject": {
                    "type": subject.split(":")[0],
                    "id": subject.split(":")[1]
                },
                "context": context or {}
            }
            
            response = await self.client.post(
                f"/v1/tenants/{self.tenant_id}/permissions/check",
                json=payload
            )

            response.raise_for_status()

            result = response.json()
            allowed = result.get("can") == "CHECK_RESULT_ALLOWED"
            
            # Cache result
            self._set_in_cache(cache_key, allowed)
            
            self.permission_checks += 1
            
            logger.debug(f"✅ Permission check: {entity}:{entity_id}.{permission} for {subject} = {allowed}")
            
            return allowed
        
        except Exception as e:
            logger.error(f"❌ Permission check failed: {e}")
            # Fail closed (deny by default)
            return False
    
    async def check_bulk_permissions(
        self,
        checks: List[Dict[str, Any]]
    ) -> List[bool]:
        """
        Check multiple permissions in bulk.
        
        Args:
            checks: List of permission checks
                [
                    {
                        "entity": "transaction",
                        "entity_id": "txn-123",
                        "permission": "view",
                        "subject": "user:agent-001"
                    }
                ]
                
        Returns:
            List of boolean results
        """
        tasks = [
            self.check_permission(
                entity=check["entity"],
                entity_id=check["entity_id"],
                permission=check["permission"],
                subject=check["subject"],
                context=check.get("context")
            )
            for check in checks
        ]
        
        return await asyncio.gather(*tasks)
    
    # ========================================================================
    # Relationship Management
    # ========================================================================
    
    async def write_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> bool:
        """
        Write relationships to Permify.
        
        Args:
            relationships: List of relationships
                [
                    {
                        "entity": "agent",
                        "id": "agent-001",
                        "relation": "owner",
                        "subject": "user:agent-001"
                    }
                ]
                
        Returns:
            True if successful
        """
        try:
            tuples = []
            
            for rel in relationships:
                subject_parts = rel["subject"].split(":")
                
                tuples.append({
                    "entity": {
                        "type": rel["entity"],
                        "id": rel["id"]
                    },
                    "relation": rel["relation"],
                    "subject": {
                        "type": subject_parts[0],
                        "id": subject_parts[1] if len(subject_parts) > 1 else ""
                    }
                })
            
            payload = {
                "tenant_id": self.tenant_id,
                "metadata": {
                    "snap_token": ""
                },
                "tuples": tuples
            }
            
            response = await self.client.post(
                "/v1/relationships/write",
                json=payload
            )
            
            response.raise_for_status()
            
            self.relationship_writes += len(relationships)
            
            logger.debug(f"✅ Relationships written: {len(relationships)}")
            
            # Invalidate cache
            self._invalidate_cache()
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Write relationships failed: {e}")
            raise
    
    async def delete_relationships(
        self,
        relationships: List[Dict[str, Any]]
    ) -> bool:
        """
        Delete relationships from Permify.
        
        Args:
            relationships: List of relationships to delete
                [
                    {
                        "entity": "agent",
                        "id": "agent-001",
                        "relation": "supervisor",
                        "subject": "user:super-agent-001"
                    }
                ]
                
        Returns:
            True if successful
        """
        try:
            tuples = []
            
            for rel in relationships:
                subject_parts = rel["subject"].split(":")
                
                tuples.append({
                    "entity": {
                        "type": rel["entity"],
                        "id": rel["id"]
                    },
                    "relation": rel["relation"],
                    "subject": {
                        "type": subject_parts[0],
                        "id": subject_parts[1] if len(subject_parts) > 1 else ""
                    }
                })
            
            payload = {
                "tenant_id": self.tenant_id,
                "tuples": tuples
            }
            
            response = await self.client.post(
                "/v1/relationships/delete",
                json=payload
            )
            
            response.raise_for_status()
            
            logger.debug(f"✅ Relationships deleted: {len(relationships)}")
            
            # Invalidate cache
            self._invalidate_cache()
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Delete relationships failed: {e}")
            raise
    
    # ========================================================================
    # Relationship Expansion
    # ========================================================================
    
    async def expand(
        self,
        entity: str,
        entity_id: str,
        permission: str
    ) -> List[str]:
        """
        Expand relationships to get all subjects with permission.
        
        Args:
            entity: Entity type
            entity_id: Entity ID
            permission: Permission name
            
        Returns:
            List of subjects (e.g., ["user:agent-001", "user:admin-001"])
        """
        try:
            payload = {
                "tenant_id": self.tenant_id,
                "entity": {
                    "type": entity,
                    "id": entity_id
                },
                "permission": permission
            }
            
            response = await self.client.post(
                "/v1/permissions/expand",
                json=payload
            )
            
            response.raise_for_status()
            
            result = response.json()
            
            # Extract subjects from expansion tree
            subjects = self._extract_subjects_from_tree(result.get("tree", {}))
            
            logger.debug(f"✅ Expansion: {entity}:{entity_id}.{permission} = {len(subjects)} subjects")
            
            return subjects
        
        except Exception as e:
            logger.error(f"❌ Expand failed: {e}")
            return []
    
    def _extract_subjects_from_tree(self, tree: Dict[str, Any]) -> List[str]:
        """Extract subjects from expansion tree."""
        subjects = []
        
        if "leaf" in tree and "subjects" in tree["leaf"]:
            for subject in tree["leaf"]["subjects"]:
                subject_type = subject.get("type", "")
                subject_id = subject.get("id", "")
                if subject_type and subject_id:
                    subjects.append(f"{subject_type}:{subject_id}")
        
        if "expand" in tree:
            for child in tree["expand"].get("children", []):
                subjects.extend(self._extract_subjects_from_tree(child))
        
        return subjects
    
    # ========================================================================
    # Resource Lookup
    # ========================================================================
    
    async def lookup_resources(
        self,
        entity: str,
        permission: str,
        subject: str
    ) -> List[str]:
        """
        Lookup resources that subject has permission on.
        
        Args:
            entity: Entity type
            permission: Permission name
            subject: Subject (e.g., "user:agent-001")
            
        Returns:
            List of entity IDs
        """
        try:
            subject_parts = subject.split(":")
            
            payload = {
                "tenant_id": self.tenant_id,
                "entity_type": entity,
                "permission": permission,
                "subject": {
                    "type": subject_parts[0],
                    "id": subject_parts[1] if len(subject_parts) > 1 else ""
                }
            }
            
            response = await self.client.post(
                "/v1/permissions/lookup-resource",
                json=payload
            )
            
            response.raise_for_status()
            
            result = response.json()
            resource_ids = result.get("resource_ids", [])
            
            logger.debug(f"✅ Lookup resources: {entity}.{permission} for {subject} = {len(resource_ids)} resources")
            
            return resource_ids
        
        except Exception as e:
            logger.error(f"❌ Lookup resources failed: {e}")
            return []
    
    # ========================================================================
    # Caching
    # ========================================================================
    
    _cache: Dict[str, tuple] = {}  # {key: (value, expiry_time)}
    
    def _get_from_cache(self, key: str) -> Optional[bool]:
        """Get value from cache."""
        if key in self._cache:
            value, expiry_time = self._cache[key]
            if datetime.utcnow() < expiry_time:
                return value
            else:
                del self._cache[key]
        return None
    
    def _set_in_cache(self, key: str, value: bool):
        """Set value in cache."""
        expiry_time = datetime.utcnow() + timedelta(seconds=self.cache_ttl)
        self._cache[key] = (value, expiry_time)
    
    def _invalidate_cache(self):
        """Invalidate all cache."""
        self._cache.clear()
    
    # ========================================================================
    # Metrics
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics."""
        cache_hit_rate = 0.0
        if self.permission_checks > 0:
            cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) * 100
        
        return {
            "permission_checks": self.permission_checks,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "relationship_writes": self.relationship_writes
        }
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Decorator for permission checking
def require_permission(entity: str, permission: str, entity_id_param: str = "id", subject_param: str = "user_id"):
    """
    Decorator to require permission for endpoint.
    
    Usage:
        @app.post("/transactions/{transaction_id}/reverse")
        @require_permission(entity="transaction", permission="reverse", entity_id_param="transaction_id")
        async def reverse_transaction(transaction_id: str, user_id: str):
            # Only executed if user has permission
            pass
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract entity_id and subject from kwargs
            entity_id = kwargs.get(entity_id_param)
            subject = kwargs.get(subject_param)
            
            if not entity_id or not subject:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Missing entity_id or subject")
            
            # Check permission
            client = PermifyClient()
            allowed = await client.check_permission(
                entity=entity,
                entity_id=entity_id,
                permission=permission,
                subject=f"user:{subject}"
            )
            
            if not allowed:
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Permission denied")
            
            # Execute function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# Example usage
async def main():
    """Example usage of Permify client."""
    client = PermifyClient()
    
    # Write relationships
    await client.write_relationships([
        {
            "entity": "agent",
            "id": "agent-001",
            "relation": "owner",
            "subject": "user:agent-001"
        },
        {
            "entity": "agent",
            "id": "agent-001",
            "relation": "organization",
            "subject": "organization:org-001"
        }
    ])
    
    # Check permission
    allowed = await client.check_permission(
        entity="agent",
        entity_id="agent-001",
        permission="view",
        subject="user:agent-001"
    )
    print(f"Permission allowed: {allowed}")
    
    # Expand relationships
    subjects = await client.expand(
        entity="agent",
        entity_id="agent-001",
        permission="view"
    )
    print(f"Subjects with view permission: {subjects}")
    
    # Lookup resources
    resources = await client.lookup_resources(
        entity="agent",
        permission="view",
        subject="user:agent-001"
    )
    print(f"Resources user can view: {resources}")
    
    # Get metrics
    metrics = client.get_metrics()
    print(f"Metrics: {metrics}")
    
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())

