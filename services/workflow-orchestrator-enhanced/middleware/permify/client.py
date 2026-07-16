"""Permify client for fine-grained authorization"""
import logging
import grpc
from typing import Optional

logger = logging.getLogger(__name__)

class PermifyConfig:
    def __init__(self, grpc_addr: str, tenant_id: str):
        self.grpc_addr = grpc_addr
        self.tenant_id = tenant_id

class CheckResult:
    def __init__(self, allowed: bool, reason: str):
        self.allowed = allowed
        self.reason = reason

class PermifyClient:
    def __init__(self, config: PermifyConfig):
        self.config = config
        self.channel = grpc.insecure_channel(config.grpc_addr)

    def check_permission(self, user_id: str, resource: str, relation: str, resource_id: str) -> CheckResult:
        logger.info(f"Checking permission: {user_id} - {resource}:{resource_id} - {relation}")
        # Simplified implementation - actual gRPC calls would go here
        return CheckResult(allowed=True, reason="allowed")

    def write_relationship(self, resource: str, resource_id: str, relation: str, subject_type: str, subject_id: str) -> None:
        logger.info(f"Writing relationship: {resource}:{resource_id} - {relation} - {subject_type}:{subject_id}")

    def delete_relationship(self, resource: str, resource_id: str, relation: str, subject_type: str, subject_id: str) -> None:
        logger.info(f"Deleting relationship: {resource}:{resource_id} - {relation} - {subject_type}:{subject_id}")

    def check_workflow_permission(self, user_id: str, workflow_id: str, action: str) -> bool:
        result = self.check_permission(user_id, "workflow", action, workflow_id)
        return result.allowed

    def grant_workflow_access(self, workflow_id: str, user_id: str, role: str) -> None:
        self.write_relationship("workflow", workflow_id, role, "user", user_id)

    def close(self) -> None:
        self.channel.close()
