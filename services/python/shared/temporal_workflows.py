"""
Temporal Workflow Client for 54Agent Banking Platform

Provides a unified client for starting, signalling, and querying Temporal
workflows used for KYC/KYB orchestration, onboarding, and long-running
business processes.

Usage::

    from shared.temporal_workflows import TemporalClient

    tc = TemporalClient()
    await tc.connect()
    run_id = await tc.start_workflow("kyc-verification", "KYCWorkflow", {"agent_id": "A1"})
    status = await tc.query_workflow(run_id, "status")
    await tc.close()
"""

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("platform.temporal")

try:
    import httpx as _httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


class TemporalClient:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        namespace: str = "",
        task_queue: str = "",
    ):
        self.endpoint = endpoint or os.getenv("TEMPORAL_ENDPOINT", "http://temporal:7233")
        self.namespace = namespace or os.getenv("TEMPORAL_NAMESPACE", "agent-banking")
        self.task_queue = task_queue or os.getenv("TEMPORAL_TASK_QUEUE", "agent-banking-queue")
        self._http: Optional[Any] = None

    async def connect(self) -> None:
        if _HAS_HTTPX:
            self._http = _httpx.AsyncClient(base_url=self.endpoint, timeout=30.0)
            logger.info("Temporal client connected to %s (ns=%s)", self.endpoint, self.namespace)

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    async def start_workflow(
        self,
        workflow_id: str,
        workflow_type: str,
        input_data: Dict[str, Any],
        task_queue: Optional[str] = None,
    ) -> str:
        if not self._http:
            await self.connect()
        payload = {
            "namespace": self.namespace,
            "workflowId": workflow_id,
            "workflowType": {"name": workflow_type},
            "taskQueue": {"name": task_queue or self.task_queue},
            "input": {"payloads": [{"data": input_data}]},
        }
        try:
            resp = await self._http.post(
                f"/api/v1/namespaces/{self.namespace}/workflows",
                json=payload,
            )
            if resp.status_code < 300:
                result = resp.json()
                run_id = result.get("runId", workflow_id)
                logger.info("Started workflow %s (run=%s)", workflow_type, run_id)
                return run_id
            logger.warning("Temporal start_workflow HTTP %d: %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.error("Temporal start_workflow error: %s", exc)
        return workflow_id

    async def signal_workflow(
        self,
        workflow_id: str,
        signal_name: str,
        signal_data: Optional[Dict[str, Any]] = None,
        run_id: str = "",
    ) -> bool:
        if not self._http:
            await self.connect()
        payload = {
            "signalName": signal_name,
            "input": {"payloads": [{"data": signal_data or {}}]},
        }
        try:
            resp = await self._http.post(
                f"/api/v1/namespaces/{self.namespace}/workflows/{workflow_id}/signal",
                json=payload,
            )
            return resp.status_code < 300
        except Exception as exc:
            logger.error("Temporal signal error: %s", exc)
            return False

    async def query_workflow(
        self,
        workflow_id: str,
        query_type: str,
        run_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not self._http:
            await self.connect()
        try:
            resp = await self._http.post(
                f"/api/v1/namespaces/{self.namespace}/workflows/{workflow_id}/query/{query_type}",
                json={},
            )
            if resp.status_code < 300:
                return resp.json()
        except Exception as exc:
            logger.error("Temporal query error: %s", exc)
        return None

    async def terminate_workflow(
        self,
        workflow_id: str,
        reason: str = "",
    ) -> bool:
        if not self._http:
            await self.connect()
        try:
            resp = await self._http.post(
                f"/api/v1/namespaces/{self.namespace}/workflows/{workflow_id}/terminate",
                json={"reason": reason},
            )
            return resp.status_code < 300
        except Exception as exc:
            logger.error("Temporal terminate error: %s", exc)
            return False

    async def get_workflow_status(self, workflow_id: str) -> Optional[str]:
        if not self._http:
            await self.connect()
        try:
            resp = await self._http.get(
                f"/api/v1/namespaces/{self.namespace}/workflows/{workflow_id}",
            )
            if resp.status_code < 300:
                data = resp.json()
                return data.get("workflowExecutionInfo", {}).get("status", "UNKNOWN")
        except Exception as exc:
            logger.error("Temporal status error: %s", exc)
        return None
