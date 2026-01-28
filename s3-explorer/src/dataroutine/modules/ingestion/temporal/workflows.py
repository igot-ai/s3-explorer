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
    from dataroutine.modules.ingestion.temporal.activities import (
        run_ingestion_pipeline_activity,
        discover_folders_activity,
        run_ingestion_folder_batch_activity,
        delete_cache_key_activity,
        run_folder_ingestion_activity,
        fetch_folders_batch_from_cache,
    )
    from dataroutine.modules.ingestion.temporal.models import IngestionJobParams
    from dataroutine.modules.ingestion.core.pipeline import IngestionPipeline
    from dataroutine.modules.ingestion.core.models import IngestionJobConfig, Catalog


# Task queue for ingestion workflows - defaults to model-training queue for consolidated deployment
# Can be overridden via INGESTION_TASK_QUEUE environment variable
INGESTION_TASK_QUEUE = os.getenv("INGESTION_TASK_QUEUE", "model-training-task-queue")
DEFAULT_TIMEOUT_MINUTES = 60  # 1 hour default timeout for pipeline execution


@workflow.defn(name="FolderIngestionWorkflow")
class FolderIngestionWorkflow:
    """Child workflow that processes a single folder."""

    @workflow.run
    async def run(self, params: IngestionJobParams) -> Dict[str, Any]:
        """Execute the folder ingestion activity.

        Args:
            params: IngestionJobParams for a single folder

        Returns:
            Summary result for the folder
        """
        retry_policy = RetryPolicy(initial_interval=timedelta(seconds=5), maximum_attempts=3)
        return await workflow.execute_activity(
            run_folder_ingestion_activity,
            params,
            task_queue=INGESTION_TASK_QUEUE,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=retry_policy,
        )


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
        """Execute the ingestion pipeline workflow using the Pipeline orchestrator.

        Args:
            params: IngestionJobParams containing all configuration

        Returns:
            Dictionary representation of IngestionResult
        """
        workflow.logger.info(f"🚀 Starting IngestionPipelineWorkflow (task_id={params.task_id}, start_index={params.start_index})")
        
        # 1. Prepare configuration and inject temporal state
        catalogs = [Catalog.from_dict(c) for c in params.catalogs]
        config = IngestionJobConfig(
            source_path=params.source_path,
            catalogs=catalogs,
            recursive=params.recursive,
            temp_dir=params.temp_dir,
            pages_to_read=params.pages_to_read
        )
        
        # Inject Temporal parameters and module into the config for Pipeline.run to use
        # This makes the Pipeline "Temporal-compatible" as requested.
        setattr(config, "temporal_params", params)
        setattr(config, "folders_per_continue", params.folders_per_continue)
        
        # 2. Instantiate a "shell" pipeline for orchestration
        # It doesn't need real connectors because it will delegate to child workflows/activities.
        pipeline = IngestionPipeline()
        
        # 3. Delegate orchestration to Pipeline.run
        result = await pipeline.run(config, workflow=workflow)
        
        return result.get_summary()

