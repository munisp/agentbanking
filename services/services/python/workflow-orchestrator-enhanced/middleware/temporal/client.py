"""
Temporal client for long-running workflows
"""
import logging
from typing import Dict, Any, Optional
from temporalio import workflow, activity
from temporalio.client import Client as TemporalClient

logger = logging.getLogger(__name__)


class TemporalConfig:
    """Temporal configuration"""
    def __init__(
        self,
        host_port: str = "localhost:7233",
        namespace: str = "default",
        task_queue: str = "workflow-orchestrator",
    ):
        self.host_port = host_port
        self.namespace = namespace
        self.task_queue = task_queue


class WorkflowInput:
    """Workflow input data"""
    def __init__(
        self,
        workflow_id: str,
        workflow_type: str,
        tenant_id: str,
        user_id: str,
        entity_id: str,
        input_data: Dict[str, Any],
    ):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.entity_id = entity_id
        self.input_data = input_data


class WorkflowResult:
    """Workflow result data"""
    def __init__(
        self,
        workflow_id: str,
        status: str,
        output_data: Dict[str, Any],
        error: Optional[str] = None,
    ):
        self.workflow_id = workflow_id
        self.status = status
        self.output_data = output_data
        self.error = error


class TemporalWorkflowClient:
    """Temporal client for workflow orchestration"""

    def __init__(self, config: TemporalConfig):
        self.config = config
        self.client: Optional[TemporalClient] = None

    async def connect(self) -> None:
        """Connect to Temporal server"""
        self.client = await TemporalClient.connect(
            self.config.host_port, namespace=self.config.namespace
        )

    async def start_workflow(
        self, workflow_type: str, input_data: WorkflowInput
    ) -> str:
        """Start a long-running workflow in Temporal"""
        logger.info(f"Starting Temporal workflow: {workflow_type} - {input_data.workflow_id}")

        handle = await self.client.start_workflow(
            workflow_type,
            input_data,
            id=input_data.workflow_id,
            task_queue=self.config.task_queue,
        )

        return handle.id

    async def get_workflow_status(
        self, workflow_id: str
    ) -> WorkflowResult:
        """Get the status of a running workflow"""
        logger.info(f"Getting Temporal workflow status: {workflow_id}")

        handle = self.client.get_workflow_handle(workflow_id)
        
        try:
            result = await handle.result()
            return WorkflowResult(
                workflow_id=workflow_id,
                status="completed",
                output_data=result,
            )
        except Exception as e:
            return WorkflowResult(
                workflow_id=workflow_id,
                status="failed",
                output_data={},
                error=str(e),
            )

    async def cancel_workflow(self, workflow_id: str) -> None:
        """Cancel a running workflow"""
        logger.info(f"Cancelling Temporal workflow: {workflow_id}")

        handle = self.client.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def close(self) -> None:
        """Close the Temporal client"""
        if self.client:
            await self.client.close()
