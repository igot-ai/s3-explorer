"""Temporal activities for the ingestion pipeline.

Activities handle all non-deterministic operations like file I/O, API calls,
and database queries. They are the bridge between Temporal workflows and
the actual pipeline execution.
"""

import logging
import uuid
from typing import Any, Dict

from dataroutine.modules.ingestion.core.classifiers import ClassifierManager
from dataroutine.modules.ingestion.core.connectors import get_storage_provider
from dataroutine.modules.ingestion.core.connectors.s3_connector import S3SourceConnector
from dataroutine.modules.ingestion.core.handlers import CollectionHandlerManager
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
from dataroutine.modules.ingestion.core.readers.markitdown_reader import (
    MarkitdownReader,
)
from dataroutine.modules.ingestion.core.readers.pdfplumber_reader import (
    PDFPlumberReader,
)
from dataroutine.modules.ingestion.core.readers.pymupdf_reader import PyMuPDFReader
from dataroutine.modules.ingestion.temporal.models import (
    IngestionJobParams,
    IngestionResult,
)
from temporalio import activity

logger = logging.getLogger(__name__)


def _create_pipeline(params: IngestionJobParams) -> IngestionPipeline:
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

    collection_handler_class = CollectionHandlerManager.get_prototype()
    collection_handler = collection_handler_class(
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
    source_path = params.source_path.rstrip("/") if params.source_path else ""
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
        result = pipeline.run(job_config)
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
