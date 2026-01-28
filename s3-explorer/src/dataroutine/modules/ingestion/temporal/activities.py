"""Temporal activities for the ingestion pipeline.

Activities handle all non-deterministic operations like file I/O, API calls,
and database queries. They are the bridge between Temporal workflows and
the actual pipeline execution.
"""

import logging
import os
import uuid
import json
import io
from typing import Any, Dict, List

from dataroutine.modules.ingestion.core.classifiers import ClassifierManager
from dataroutine.modules.ingestion.core.connectors import get_storage_provider
from dataroutine.modules.ingestion.core.connectors.s3_connector import S3SourceConnector
from dataroutine.modules.ingestion.core.handlers import CollectionHandler
from dataroutine.modules.ingestion.core.handlers.api_handler import DataCollectionAPIHandler
from dataroutine.modules.ingestion.core.models import (
    Catalog,
    FileContext,
    FolderContext,
    IngestionJobConfig,
)
from dataroutine.modules.ingestion.core.pipeline import IngestionPipeline
from dataroutine.modules.ingestion.core.processors.base import FileProcessorChain
from dataroutine.modules.ingestion.core.processors.converter import DocxToPdfConverter
from dataroutine.modules.ingestion.core.processors.extractor import (
    ArchiveExtractor,
    SimpleZipExtractor,
)
from dataroutine.modules.ingestion.core.readers.markitdown_reader import MarkitdownReader
from dataroutine.modules.ingestion.core.readers.pdfplumber_reader import PDFPlumberReader
from dataroutine.modules.ingestion.core.readers.pymupdf_reader import PyMuPDFReader
from dataroutine.modules.ingestion.temporal.models import IngestionJobParams, IngestionResult
from temporalio import activity

logger = logging.getLogger(__name__)


def _create_pipeline(params: IngestionJobParams, collection_handler: CollectionHandler = None) -> IngestionPipeline:
    """Create and configure the ingestion pipeline from workflow parameters.

    This factory function creates all pipeline components with proper configuration.
    It's extracted to allow reuse and testing.

    Args:
        params: Workflow parameters containing all configuration

    Returns:
        Configured IngestionPipeline instance

    Raises:
        ValueError: If required configuration is missing
    """
    storage_creds = {
        k: v for k, v in params.storage_credentials.items() if v is not None
    }
    storage_provider = get_storage_provider(params.storage_provider, **storage_creds)
    source_connector = S3SourceConnector(storage_provider)
    processors = []
    converter = DocxToPdfConverter()
    if converter.is_libreoffice_available():
        processors.append(converter)
        logger.info("Using LibreOffice for DOCX conversion")
    archive_extractor = ArchiveExtractor()
    if archive_extractor.available:
        processors.append(archive_extractor)
        logger.info("Using patool for archive extraction")
    else:
        processors.append(SimpleZipExtractor())
        logger.info("Using built-in ZIP extractor")
    processor_chain = FileProcessorChain(processors)
    reader_type = params.reader_type
    if reader_type == "markitdown":
        document_reader = MarkitdownReader()
    elif reader_type == "pdfplumber":
        document_reader = PDFPlumberReader()
    elif reader_type == "pymupdf":
        document_reader = PyMuPDFReader()
    else:
        document_reader = MarkitdownReader()
    classifier = ClassifierManager.get_instance().classifier

    if collection_handler is None:
        collection_handler = DataCollectionAPIHandler(
            base_url=params.api_base_url or os.getenv("API_BASE_URL"),
            workspace_id=params.workspace_id,
            project_id=params.project_id,
        )

    def on_file_processed(file_ctx: FileContext):  # Progress callback
        status_emoji = "✅" if file_ctx.is_successful() else "❌"
        logger.info(f"{status_emoji} {file_ctx.source_path} - {file_ctx.status.value}")

    def on_folder_completed(folder_ctx: FolderContext):  # Folder completion callback
        successful = len(folder_ctx.get_successful_files())
        failed = len(folder_ctx.get_failed_files())
        logger.info(
            f"📁 Completed folder: {folder_ctx.folder_path} ({successful} successful, {failed} failed)"
        )

    return IngestionPipeline(
        source_connector=source_connector,
        processor_chain=processor_chain,
        document_reader=document_reader,
        classifier=classifier,
        collection_handler=collection_handler,
        on_file_processed=on_file_processed,
        on_folder_completed=on_folder_completed,
    )


def _build_job_config(params: IngestionJobParams) -> IngestionJobConfig:
    """Build job configuration from workflow parameters.

    Args:
        params: Workflow parameters

    Returns:
        IngestionJobConfig instance
    """
    source_path = params.source_path if params.source_path is not None else ""
    catalogs = [
        Catalog(
            id=cat["id"],
            instruction=cat["instruction"],
            fetch_all_metadata=cat.get("fetch_all_metadata", False),
            metadata_scan=cat.get("metadata_scan", []),
        )
        for cat in params.catalogs
    ]
    return IngestionJobConfig(
        source_path=source_path,
        catalogs=catalogs,
        recursive=params.recursive,
        temp_dir=params.temp_dir,
        pages_to_read=params.pages_to_read,
    )


def _build_result(pipeline_result, task_id: str) -> IngestionResult:
    """Build workflow result from pipeline result.

    Args:
        pipeline_result: PipelineResult from pipeline execution
        task_id: Task identifier

    Returns:
        IngestionResult for workflow completion
    """
    folders = []
    for folder_ctx in pipeline_result.folder_contexts:
        files = [
            {
                "source_path": f.source_path,
                "status": f.status.value,
                "classified_catalog_id": f.classified_catalog_id,
                "error_message": f.error_message,
                "metadata": f.metadata,
            }
            for f in folder_ctx.files
        ]
        folders.append(
            {
                "folder_path": folder_ctx.folder_path,
                "successful_count": len(folder_ctx.get_successful_files()),
                "failed_count": len(folder_ctx.get_failed_files()),
                "files": files,
            }
        )
    return IngestionResult(
        success=pipeline_result.failed == 0,
        task_id=task_id,
        total_folders=pipeline_result.total_folders,
        total_files=pipeline_result.total_files,
        successful=pipeline_result.successful,
        failed=pipeline_result.failed,
        success_rate=f"{pipeline_result.get_success_rate():.2f}%",
        execution_time=f"{pipeline_result.execution_time_seconds:.2f}s",
        folders=folders,
    )


@activity.defn(name="run_ingestion_pipeline_activity")
async def run_ingestion_pipeline_activity(params: IngestionJobParams) -> Dict[str, Any]:
    """Execute the ingestion pipeline as a Temporal activity.

    This activity wraps the entire pipeline execution, making it suitable for
    distributed processing via Temporal. External services can trigger this
    activity through the IngestionPipelineWorkflow.

    Args:
        params: IngestionJobParams containing all configuration

    Returns:
        Dictionary representation of IngestionResult

    Raises:
        ValueError: If configuration is invalid
        Exception: If pipeline execution fails
    """
    task_id = params.task_id or str(uuid.uuid4())
    logger.info("=" * 80)
    logger.info(f"Starting Data Ingestion Pipeline Activity (task_id={task_id})")
    logger.info("=" * 80)
    try:
        pipeline = _create_pipeline(params)
        job_config = _build_job_config(params)
        result = await pipeline.run(job_config)
        ingestion_result = _build_result(result, task_id)
        logger.info("=" * 80)
        logger.info("Pipeline Activity Completed")
        logger.info(f"Total folders: {ingestion_result.total_folders}")
        logger.info(f"Total files: {ingestion_result.total_files}")
        logger.info(f"Successful: {ingestion_result.successful}")
        logger.info(f"Failed: {ingestion_result.failed}")
        logger.info(f"Success rate: {ingestion_result.success_rate}")
        logger.info(f"Execution time: {ingestion_result.execution_time}")
        logger.info("=" * 80)
        return ingestion_result.to_dict()
    except Exception as e:
        logger.error(f"❌ Pipeline activity failed: {e}", exc_info=True)
        return IngestionResult.failure(task_id, str(e)).to_dict()


@activity.defn(name="discover_folders_activity")
async def discover_folders_activity(params: IngestionJobParams) -> Dict[str, Any]:
    """Discover top-level folders and cache the list in storage.

    Args:
        params: IngestionJobParams containing storage configuration

    Returns:
        Dictionary with cache_key and total_folders
    """
    task_id = params.task_id or str(uuid.uuid4())
    logger.info(f"Discovering folders for task_id: {task_id}")

    try:
        if not params.source_path or params.source_path.strip("/") == "": 
            raise ValueError("Scanning the root directory ('/') is not allowed to avoid expensive operations. Please specify a specific folder path.") 

        # 1. Setup connector
        storage_creds = {k: v for k, v in params.storage_credentials.items() if v is not None}
        storage_provider = get_storage_provider(params.storage_provider, **storage_creds)
        source_connector = S3SourceConnector(storage_provider)

        # 2. List folders
        prefix = params.source_path
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        folders = source_connector.list_folders(prefix=prefix)
        total_folders = len(folders)

        # 3. Cache the list
        cache_key = f"_ingestion_cache/{task_id}/folders.json"
        folders_json = json.dumps(folders)
        storage_provider.upload_file(io.BytesIO(folders_json.encode("utf-8")), cache_key)

        logger.info(f"Discovered {total_folders} folders, cached at {cache_key}")
        return {"cache_key": cache_key, "total_folders": total_folders}
    except Exception as e:
        logger.error(f"❌ Folder discovery failed: {e}", exc_info=True)
        raise


@activity.defn(name="run_ingestion_folder_batch_activity")
async def run_ingestion_folder_batch_activity(
    params: IngestionJobParams, cache_key: str, start_index: int, end_index: int
) -> Dict[str, Any]:
    """Process a batch of folders from the cached list.

    Args:
        params: IngestionJobParams
        cache_key: Key for the cached folder list
        start_index: Start index in the folder list
        end_index: End index in the folder list

    Returns:
        Dictionary with batch execution summary
    """
    task_id = params.task_id or str(uuid.uuid4())
    logger.info(f"Processing batch {start_index} to {end_index} for task_id: {task_id}")

    try:
        # 1. Setup components
        storage_creds = {k: v for k, v in params.storage_credentials.items() if v is not None}
        storage_provider = get_storage_provider(params.storage_provider, **storage_creds)
        pipeline = _create_pipeline(params)
        job_config = _build_job_config(params)

        # 2. Download and slice folder list
        cache_stream = storage_provider.download_file(cache_key)
        all_folders = json.loads(cache_stream.read().decode("utf-8"))
        batch_folders = all_folders[start_index:end_index]

        # 3. Run pipeline for this batch
        result = await pipeline.run(job_config, folder_prefixes=batch_folders)

        # 4. Return summary counts
        return {
            "folders_processed": len(batch_folders),
            "files_processed": result.total_files,
            "successful": result.successful,
            "failed": result.failed,
            "next_index": end_index,
        }
    except Exception as e:
        logger.error(f"❌ Batch processing failed: {e}", exc_info=True)
        raise


@activity.defn(name="fetch_folders_batch_from_cache")
async def fetch_folders_batch_from_cache(
    params: IngestionJobParams, cache_key: str, start_index: int, end_index: int
) -> List[str]:
    """Fetch a slice of folders from the cached list.

    Args:
        params: IngestionJobParams
        cache_key: Key for the cached folder list
        start_index: Start index
        end_index: End index

    Returns:
        List of folder paths
    """
    try:
        storage_creds = {k: v for k, v in params.storage_credentials.items() if v is not None}
        storage_provider = get_storage_provider(params.storage_provider, **storage_creds)
        
        cache_stream = storage_provider.download_file(cache_key)
        all_folders = json.loads(cache_stream.read().decode("utf-8"))
        return all_folders[start_index:end_index]
    except Exception as e:
        logger.error(f"❌ Failed to fetch folder batch: {e}", exc_info=True)
        raise


@activity.defn(name="run_folder_ingestion_activity")
async def run_folder_ingestion_activity(params: IngestionJobParams) -> Dict[str, Any]:
    """Process a single folder ingestion (Phase 1 & 2).

    Args:
        params: IngestionJobParams (source_path should be the folder to process)

    Returns:
        Summary statistics for the folder
    """
    task_id = params.task_id or str(uuid.uuid4())
    logger.info(f"Processing folder: {params.source_path} (task_id: {task_id})")

    try:
        pipeline = _create_pipeline(params)
        job_config = _build_job_config(params)
        
        # Run pipeline locally for this specific folder prefix
        # We pass folder_prefixes=[params.source_path] to ensure it only processes that
        result = await pipeline.run(job_config, folder_prefixes=[params.source_path])
        
        return {
            "success": result.failed == 0,
            "total_files": result.total_files,
            "successful": result.successful,
            "failed": result.failed,
        }
    except Exception as e:
        logger.error(f"❌ Folder ingestion activity failed: {e}", exc_info=True)
        raise


@activity.defn(name="delete_cache_key_activity")
async def delete_cache_key_activity(params: IngestionJobParams, cache_key: str) -> bool:
    """Delete the cached folder list.

    Args:
        params: IngestionJobParams
        cache_key: Key to delete

    Returns:
        True if successful
    """
    try:
        storage_creds = {k: v for k, v in params.storage_credentials.items() if v is not None}
        storage_provider = get_storage_provider(params.storage_provider, **storage_creds)
        storage_provider.delete_file(cache_key)
        logger.info(f"Deleted cache key: {cache_key}")
        return True
    except Exception as e:
        logger.warning(f"Could not delete cache key {cache_key}: {e}")
        return False
