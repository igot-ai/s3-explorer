"""Temporal workflows for the ingestion pipeline.

Workflows handle orchestration logic only - they must be deterministic.
All actual processing is delegated to activities.
"""

import logging
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

with workflow.unsafe.imports_passed_through():  # Activities need to be imported through unsafe context
    from dataroutine.modules.ingestion.temporal.activities import run_ingestion_pipeline_activity, notify_ingestion_complete_activity
    from dataroutine.modules.ingestion.temporal.models import IngestionJobParams, IngestionResult


# Default task queue for ingestion workflows - can be imported by other modules
INGESTION_TASK_QUEUE = "ingestion-pipeline-task-queue"
DEFAULT_TIMEOUT_MINUTES = 60  # 1 hour default timeout for pipeline execution


@workflow.defn(name="IngestionPipelineWorkflow", sandboxed=False)
class IngestionPipelineWorkflow:
    """Workflow that orchestrates the data ingestion pipeline.
    
    This workflow provides a clean interface for external services (like catalog)
    to trigger ingestion jobs without coupling to the pipeline implementation.
    
    The workflow:
    1. Executes the ingestion pipeline activity
    2. Optionally triggers a callback workflow on completion
    3. Returns the pipeline result
    
    Usage from external services:
        ```python
        from temporalio.client import Client
        
        params = IngestionJobParams(
            source_path="raw-documents/",
            workspace_id="...",
            project_id="...",
            auth_token="...",
            catalogs=[{"id": "legal", "instruction": "Legal documents"}],
            callback_workflow="ProcessCatalogResults",  # Optional
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
        if params.callback_workflow and params.callback_params:  # Optionally notify external systems
            workflow.logger.info(f"📢 Triggering callback: {params.callback_workflow}")
            await workflow.execute_activity(
                notify_ingestion_complete_activity,
                args=[result, params.callback_params],
                task_queue=INGESTION_TASK_QUEUE,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )
        workflow.logger.info(f"✅ IngestionPipelineWorkflow completed (task_id={params.task_id})")
        return result


@workflow.defn(name="IngestionStatusWorkflow", sandboxed=False)
class IngestionStatusWorkflow:
    """Parent workflow for managing multiple ingestion jobs.
    
    Similar to TransformCatalogStatusWorkflow, this workflow can coordinate
    multiple ingestion pipelines and track overall status.
    
    This is useful when:
    - Processing multiple source paths in parallel
    - Coordinating with other workflows (e.g., catalog transformation)
    - Tracking overall job progress
    """

    @workflow.run
    async def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multiple ingestion jobs and aggregate results.
        
        Args:
            params: Dictionary containing:
                - jobs: List of IngestionJobParams dictionaries
                - task_id: Parent task identifier
                - parallel: Whether to run jobs in parallel (default: False)
                
        Returns:
            Aggregated result dictionary
        """
        task_id = params.get("task_id", "")
        jobs = params.get("jobs", [])
        parallel = params.get("parallel", False)
        workflow.logger.info(f"🚀 Starting IngestionStatusWorkflow (task_id={task_id}, jobs={len(jobs)})")
        results = []
        if parallel:  # Run jobs in parallel using child workflows
            handles = []
            for idx, job_dict in enumerate(jobs):
                job_params = IngestionJobParams.from_dict(job_dict)
                job_params.task_id = job_params.task_id or f"{task_id}-{idx}"
                handle = await workflow.start_child_workflow(
                    "IngestionPipelineWorkflow",
                    job_params,
                    id=f"ingestion-{job_params.task_id}",
                    task_queue=INGESTION_TASK_QUEUE,
                )
                handles.append(handle)
            for handle in handles:
                result = await handle
                results.append(result)
        else:  # Run jobs sequentially
            for idx, job_dict in enumerate(jobs):
                job_params = IngestionJobParams.from_dict(job_dict)
                job_params.task_id = job_params.task_id or f"{task_id}-{idx}"
                result = await workflow.execute_child_workflow(
                    "IngestionPipelineWorkflow",
                    job_params,
                    id=f"ingestion-{job_params.task_id}",
                    task_queue=INGESTION_TASK_QUEUE,
                )
                results.append(result)
        total_files = sum(r.get("total_files", 0) for r in results)
        total_successful = sum(r.get("successful", 0) for r in results)
        total_failed = sum(r.get("failed", 0) for r in results)
        overall_success = all(r.get("success", False) for r in results)
        workflow.logger.info(f"✅ IngestionStatusWorkflow completed: jobs={len(results)}, files={total_files}")
        return {
            "success": overall_success,
            "task_id": task_id,
            "total_jobs": len(results),
            "total_files": total_files,
            "successful": total_successful,
            "failed": total_failed,
            "results": results,
        }

