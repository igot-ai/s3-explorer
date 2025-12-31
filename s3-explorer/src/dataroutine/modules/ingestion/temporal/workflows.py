"""Temporal workflows for the ingestion pipeline.

Workflows handle orchestration logic only - they must be deterministic.
All actual processing is delegated to activities.
"""

import logging
import os
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

with workflow.unsafe.imports_passed_through():  # Activities need to be imported through unsafe context
    from dataroutine.modules.ingestion.temporal.activities import run_ingestion_pipeline_activity
    from dataroutine.modules.ingestion.temporal.models import IngestionJobParams


# Task queue for ingestion workflows - defaults to model-training queue for consolidated deployment
# Can be overridden via INGESTION_TASK_QUEUE environment variable
INGESTION_TASK_QUEUE = os.getenv("INGESTION_TASK_QUEUE", "model-training-task-queue")
DEFAULT_TIMEOUT_MINUTES = 60  # 1 hour default timeout for pipeline execution


@workflow.defn(name="IngestionPipelineWorkflow", sandboxed=False)
class IngestionPipelineWorkflow:
    """Workflow that orchestrates the data ingestion pipeline.
    
    This workflow provides a clean interface for external services (like catalog)
    to trigger ingestion jobs without coupling to the pipeline implementation.
    
    Usage from external services:
        ```python
        from temporalio.client import Client
        
        params = IngestionJobParams(
            source_path="raw-documents/",
            workspace_id="...",
            project_id="...",
            auth_token="...",
            catalogs=[{"id": "legal", "instruction": "Legal documents"}],
        )
        
        await client.start_workflow(
            "IngestionPipelineWorkflow",
            params,
            id=f"ingestion-{task_id}",
            task_queue="ingestion-pipeline-task-queue",
        )
        ```
    """

    @workflow.run
    async def run(self, params: IngestionJobParams) -> Dict[str, Any]:
        """Execute the ingestion pipeline workflow.
        
        Args:
            params: IngestionJobParams containing all configuration
            
        Returns:
            Dictionary representation of IngestionResult
        """
        workflow.logger.info(f"🚀 Starting IngestionPipelineWorkflow (task_id={params.task_id})")
        retry_policy = RetryPolicy(initial_interval=timedelta(seconds=10), maximum_interval=timedelta(minutes=5), maximum_attempts=3, backoff_coefficient=2.0)
        result = await workflow.execute_activity(
            run_ingestion_pipeline_activity,
            params,
            task_queue=INGESTION_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=DEFAULT_TIMEOUT_MINUTES),
            retry_policy=retry_policy,
        )
        workflow.logger.info(f"📊 Pipeline result: success={result.get('success')}, files={result.get('total_files')}")
        workflow.logger.info(f"✅ IngestionPipelineWorkflow completed (task_id={params.task_id})")
        return result

