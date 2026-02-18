"""Main ingestion pipeline orchestrator."""

import tempfile
import time
import asyncio
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Any, Dict

from dataroutine.modules.ingestion.core.classifiers.base import Classifier
from dataroutine.modules.ingestion.core.connectors.base import SourceConnector
from dataroutine.modules.ingestion.core.handlers.base import CollectionHandler
from dataroutine.modules.ingestion.core.models import (
    FileContext,
    FileStatus,
    FolderContext,
    IngestionJobConfig,
    PipelineResult,
)
from dataroutine.modules.ingestion.core.processors.base import FileProcessorChain
from dataroutine.modules.ingestion.core.readers.base import DocumentReader
from dataroutine.modules.ingestion.env import INGESTION_TASK_QUEUE
from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)


class IngestionPipeline:
    """Orchestrates the complete data ingestion workflow.

    Follows Single Responsibility Principle - only coordinates, doesn't implement logic.
    """

    def __init__(
        self,
        source_connector: Optional[SourceConnector] = None,
        processor_chain: Optional[FileProcessorChain] = None,
        document_reader: Optional[DocumentReader] = None,
        classifier: Optional[Classifier] = None,
        collection_handler: Optional[CollectionHandler] = None,
        on_file_processed: Optional[Callable[[FileContext], None]] = None,
        on_folder_completed: Optional[Callable[[FolderContext], None]] = None,
    ):
        """Initialize ingestion pipeline.

        Args:
            source_connector: Connector for reading files from source
            processor_chain: Chain of file processors
            document_reader: Reader for extracting text from documents
            classifier: Classifier for categorizing documents
            collection_handler: Handler for uploading to collections
            on_file_processed: Optional callback after each file is processed
            on_folder_completed: Optional callback after each folder is completed
        """
        self.source = source_connector
        self.processor = processor_chain
        self.reader = document_reader
        self.classifier = classifier
        self.handler = collection_handler
        self.on_file_processed = on_file_processed
        self.on_folder_completed = on_folder_completed

    async def run(
        self,
        config: IngestionJobConfig,
        workflow=None,
        folder_prefixes: Optional[List[str]] = None,
    ) -> PipelineResult:
        """Execute the full ingestion pipeline.

        Args:
            config: Job configuration
            workflow: Optional Temporal workflow module for orchestration
            folder_prefixes: Optional list of folder prefixes to process

        Returns:
            PipelineResult with summary statistics
        """
        if workflow:
            return await self._run_temporal_orchestration(config, workflow)

        start_time = time.time()
        folder_contexts = []

        logger.info(f"Starting ingestion pipeline for source: {config.source_path}")
        logger.info(f"Processing with {len(config.catalogs)} catalogs")

        # Phase 0: Discovery - collect all files to process
        if folder_prefixes:
            logger.info(f"Phase 0: Discovering files in {len(folder_prefixes)} specific prefixes")
            all_discovered_files = []
            for prefix in folder_prefixes:
                all_discovered_files.extend(
                    list(self.source.walk_folder(prefix, recursive=config.recursive))
                )
        else:
            logger.info(f"Phase 0: Discovering files in {config.source_path}")
            all_discovered_files = list(
                self.source.walk_folder(config.source_path, recursive=config.recursive)
            )

        logger.info(f"Found {len(all_discovered_files)} total files to process")

        files_by_folder = self._group_files_by_folder(all_discovered_files, config)
        logger.info(f"Grouped into {len(files_by_folder)} folder-based batches")

        for folder_path, all_files in files_by_folder.items():
            folder_ctx = FolderContext(folder_path=folder_path)
            logger.info(
                f"Processing batch folder: {folder_path} ({len(all_files)} files)"
            )

            # Create temp directory for the entire folder processing
            base_temp_dir = Path(config.temp_dir) if config.temp_dir else None
            if base_temp_dir:
                base_temp_dir.mkdir(parents=True, exist_ok=True)
            temp_dir_context = tempfile.TemporaryDirectory(
                dir=str(base_temp_dir) if base_temp_dir else None
            )
            temp_dir = Path(temp_dir_context.name)

            try:
                # PHASE 1: Download, Convert/Extract, Read text, Classify ALL files
                all_processed_files: List[FileContext] = []

                for file_ctx in all_files:
                    try:
                        processed_files = self._read_and_classify(
                            file_ctx, config, temp_dir
                        )
                        all_processed_files.extend(processed_files)
                    except Exception as e:
                        logger.error(
                            f"Error in phase 1 for {file_ctx.source_path}: {str(e)}"
                        )
                        file_ctx.status = FileStatus.FAILED
                        file_ctx.error_message = str(e)
                        all_processed_files.append(file_ctx)

                logger.info(
                    f"Phase 1 completed: Extracted and classified {len(all_processed_files)} files"
                )

                # PHASE 2: Upload ALL files
                fetch_all_catalog_ids = {
                    c.id for c in config.catalogs if c.fetch_all_metadata
                }

                sorted_files = sorted(
                    all_processed_files,
                    key=lambda pf: pf.classified_catalog_id in fetch_all_catalog_ids,
                )

                logger.info(
                    f"Phase 2: Uploading {len(sorted_files)} files (fetch_all_metadata catalogs last)"
                )

                for pf in sorted_files:
                    try:
                        if pf.classified_catalog_id in fetch_all_catalog_ids:
                            self._aggregate_folder_metadata(folder_ctx, config.catalogs)

                        self._extract_and_upload(pf, config, folder_ctx)
                    except Exception as e:
                        logger.error(f"Error in phase 2 for {pf.source_path}: {str(e)}")
                        pf.status = FileStatus.FAILED
                        pf.error_message = str(e)
                        folder_ctx.add_file(pf)

                    if self.on_file_processed:
                        try:
                            self.on_file_processed(pf)
                        except Exception as e:
                            logger.error(f"Error in file callback: {str(e)}")

                logger.info("Phase 2 completed: Uploaded files")

                # Step 3: Aggregate folder metadata before handler aggregation
                self._aggregate_folder_metadata(folder_ctx, config.catalogs)

                folder_contexts.append(folder_ctx)

                if self.on_folder_completed:
                    try:
                        self.on_folder_completed(folder_ctx)
                    except Exception as e:
                        logger.error(f"Error in folder callback: {str(e)}")

            finally:
                # Cleanup temp directory after all phases complete
                temp_dir_context.cleanup()

        # Build final result
        execution_time = time.time() - start_time
        result = self._build_result(folder_contexts, execution_time)

        logger.info(f"Pipeline completed in {execution_time:.2f}s")
        logger.info(f"Summary: {result.get_summary()}")

        return result

    def _read_and_classify(
        self, file_ctx: FileContext, config: IngestionJobConfig, temp_dir: Path
    ) -> List[FileContext]:
        """Phase 1: Download, convert/extract, read text, and classify file.

        Args:
            file_ctx: File to process
            config: Job configuration
            temp_dir: Temporary directory for file processing

        Returns:
            List of processed FileContext objects with classification result
        """
        logger.debug(f"Phase 1: Processing file: {file_ctx.source_path}")

        # Stage 0: Download file
        if not file_ctx.local_path:
            file_stream = self.source.download_file(file_ctx.source_path)
            local_path = temp_dir / Path(file_ctx.source_path).name
            local_path.parent.mkdir(parents=True, exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(file_stream.read())
            file_ctx.local_path = str(local_path)

        # Stage 1: Convert/Extract if needed
        processed_files = self.processor.process(file_ctx, temp_dir)
        logger.debug(f"Processed files: {processed_files}")

        # Stage 2: Read document text for all processed files
        for pf in processed_files:
            if pf.status == FileStatus.FAILED:
                continue

            if pf.local_path and self.reader.can_read(Path(pf.local_path)):
                pf.extracted_text = self.reader.read_pages(
                    Path(pf.local_path), max_pages=config.pages_to_read
                )

                if not pf.extracted_text:
                    logger.warning(f"No text extracted from {pf.source_path}")
                    pf.status = FileStatus.FAILED
                    pf.error_message = "No text could be extracted"
                    continue

                # Stage 3: Classify
                result = self.classifier.classify(
                    pf.extracted_text, pf.source_path, config.catalogs
                )
                pf.classified_catalog_id = result.category_id
                pf.status = FileStatus.CLASSIFIED
                logger.debug(
                    f"Classified {pf.source_path} -> catalog: {result.category_id}"
                )
            else:
                logger.warning(f"Cannot read file type: {pf.file_type}")
                pf.status = FileStatus.FAILED
                pf.error_message = f"Unsupported file type: {pf.file_type}"

        return processed_files

    def _extract_and_upload(
        self, pf: FileContext, config: IngestionJobConfig, folder_ctx: FolderContext
    ) -> None:
        """Phase 2: Extract metadata and upload file to collection.

        Args:
            pf: Processed file context with classification result
            config: Job configuration
            folder_ctx: Parent folder context
        """
        if pf.status == FileStatus.FAILED:
            folder_ctx.add_file(pf)
            return

        if pf.status != FileStatus.CLASSIFIED or not pf.classified_catalog_id:
            pf.status = FileStatus.FAILED
            pf.error_message = "File not classified"
            folder_ctx.add_file(pf)
            return

        catalog = config.get_catalog_by_id(pf.classified_catalog_id)
        if not catalog:
            logger.warning(f"Catalog {pf.classified_catalog_id} not found")
            pf.status = FileStatus.FAILED
            pf.error_message = f"Catalog {pf.classified_catalog_id} not found"
            folder_ctx.add_file(pf)
            return

        logger.debug(f"Phase 2: Extracting metadata and uploading: {pf.source_path}")

        if pf.extracted_text:
            extracted_llm_metadata = self.classifier.extract_metadata(
                pf.extracted_text, catalog
            )
            if extracted_llm_metadata:
                if isinstance(extracted_llm_metadata, dict):
                    pf.metadata.update(extracted_llm_metadata)
                else:
                    logger.warning(
                        f"Extracted metadata is not a dictionary: {type(extracted_llm_metadata)}"
                    )
                logger.debug(f"Extracted metadata via LLM for {pf.source_path}")

        column_static_data = {}
        if catalog.fetch_all_metadata:
            aggregated = folder_ctx.aggregated_metadata.get(catalog.id, {})

            # Priority 1: Aggregated metadata from other files in the same folder
            for key, values in aggregated.items():
                if values and isinstance(values, list):
                    non_empty_values = [v for v in values if v]
                    if non_empty_values:
                        column_static_data[key] = non_empty_values[0]

            # Priority 2: File's own metadata (only if not already provided by aggregated data)
            for key, value in pf.metadata.items():
                if value and (
                    key not in column_static_data or not column_static_data[key]
                ):
                    column_static_data[key] = value

            pf.metadata.update(column_static_data)
        else:
            column_static_data = pf.metadata.copy()

        metadata_to_send = pf.metadata.copy()
        metadata_to_send["folder_metadata"] = column_static_data

        with open(pf.local_path, "rb") as f:
            if catalog.fetch_all_metadata:
                upload_result = self.handler.upload_with_folder_context(
                    pf, catalog, f, metadata_to_send, folder_ctx
                )
            else:
                upload_result = self.handler.upload(pf, catalog, f, metadata_to_send)

        if isinstance(upload_result, dict):
            pf.asset_id = upload_result.get("asset_id")
            extracted_metadata = upload_result.get("extracted_metadata", {})
            if extracted_metadata:
                if isinstance(extracted_metadata, dict):
                    pf.metadata.update(extracted_metadata)
                else:
                    logger.warning(
                        f"API extracted metadata is not a dictionary: {type(extracted_metadata)}"
                    )
                logger.debug(
                    f"Updated metadata for {pf.source_path} with Datalog extracted data"
                )
        else:
            pf.asset_id = upload_result

        pf.status = FileStatus.UPLOADED
        logger.info(
            f"Successfully uploaded {pf.source_path} to collection {catalog.id}, asset_id: {pf.asset_id}"
        )
        folder_ctx.add_file(pf)

    def _aggregate_folder_metadata(
        self, folder_ctx: FolderContext, catalogs: List
    ) -> None:
        """Aggregate metadata for the folder.

        For catalogs with fetch_all_metadata=True, collect metadata from ALL
        successfully uploaded files in the folder (regardless of their catalog).

        Args:
            folder_ctx: Folder context to aggregate
            catalogs: List of catalogs
        """
        folder_ctx.aggregate_by_catalog()

        normal_catalog_ids = {
            c.id for c in catalogs if not getattr(c, "fetch_all_metadata", False)
        }
        for catalog in catalogs:
            if catalog.fetch_all_metadata:
                aggregated = {}
                for file_ctx in folder_ctx.files:
                    if file_ctx.classified_catalog_id in normal_catalog_ids:
                        for key, value in file_ctx.metadata.items():
                            if value:
                                if key not in aggregated:
                                    aggregated[key] = []
                                if value not in aggregated[key]:
                                    aggregated[key].append(value)

                folder_ctx.aggregated_metadata[catalog.id] = aggregated
                logger.debug(
                    f"Aggregated metadata for catalog {catalog.id} from {len(folder_ctx.files)} files: {list(aggregated.keys())}"
                )

    def _build_result(
        self, folder_contexts: List[FolderContext], execution_time: float
    ) -> PipelineResult:
        """Build pipeline result from folder contexts.

        Args:
            folder_contexts: List of processed folder contexts
            execution_time: Total execution time in seconds

        Returns:
            PipelineResult with summary statistics
        """
        total_files = sum(len(fc.files) for fc in folder_contexts)
        successful = sum(len(fc.get_successful_files()) for fc in folder_contexts)
        failed = sum(len(fc.get_failed_files()) for fc in folder_contexts)

        return PipelineResult(
            total_folders=len(folder_contexts),
            total_files=total_files,
            successful=successful,
            failed=failed,
            folder_contexts=folder_contexts,
            execution_time_seconds=execution_time,
        )

    def _group_files_by_folder(
        self, all_discovered_files: List[FileContext], config: IngestionJobConfig
    ) -> dict[str, List[FileContext]]:
        """Group discovered files by their parent folder.

        Args:
            all_discovered_files: List of discovered file contexts
            config: Job configuration

        Returns:
            Dictionary mapping folder paths to lists of file contexts
        """
        files_by_folder: dict[str, List[FileContext]] = {}
        for file_ctx in all_discovered_files:
            if file_ctx.parent_folder:  # Use already assigned parent_folder if available
                parent = file_ctx.parent_folder
            else:
                path_obj = Path(file_ctx.source_path)
                parent = str(path_obj.parent).replace("\\", "/")
                if parent == "." or not parent:
                    parent = config.source_path.rstrip("/") or "/"
            
            if not parent.endswith("/"):
                parent += "/"

            if parent not in files_by_folder:
                files_by_folder[parent] = []
            files_by_folder[parent].append(file_ctx)
        return files_by_folder

    async def _run_temporal_orchestration(self, config: IngestionJobConfig, workflow) -> PipelineResult:
        """Orchestrate processing via Temporal child workflows and continue-as-new.

        Args:
            config: Ingestion job configuration
            workflow: Temporal workflow module

        Returns:
            PipelineResult (partial or final)
        """
        from datetime import timedelta
        from temporalio.common import RetryPolicy
        from temporalio.workflow import ParentClosePolicy

        # Configuration for scalability (can be moved to config later)
        FILES_PER_CONTINUE = getattr(config, "folders_per_continue", 50)
        MAX_PARALLEL_CHILD_WORKFLOWS = 25
        retry_policy = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=1))

        # We assume config has been augmented with temporal params if called this way
        params = getattr(config, "temporal_params", None)
        if not params:
            raise ValueError("Temporal params missing in config for orchestration")

        # 1. Discovery Phase
        if not params.folders_cache_key:
            discovery_res = await workflow.execute_activity(
                "discover_folders_activity",
                args=[params],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy
            )
            params.folders_cache_key = discovery_res["cache_key"]
            params.folders_total = discovery_res["total_folders"]

            # Broadcast total folders discovered
            await workflow.execute_activity(
                "push_sse_event",
                args=[{
                    "task_id": getattr(params, "task_id", ""),
                    "event_type": "ingestion_progress",
                    "message": f"Discovered {params.folders_total} folders to process",
                    "phase": "discovery",
                    "progress": {
                        "total_folders": params.folders_total,
                        "processed_folders": 0
                    }
                }],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=retry_policy
            )

        # 2. Check if completed
        if params.start_index >= params.folders_total:
            return PipelineResult(
                total_folders=params.folders_total,
                total_files=params.acc_total_files,
                successful=params.acc_successful,
                failed=params.acc_failed,
                folder_contexts=[],
                execution_time_seconds=0.0
            )

        # 3. Process Batch
        end_index = min(params.start_index + FILES_PER_CONTINUE, params.folders_total)
        
        for i in range(params.start_index, end_index, MAX_PARALLEL_CHILD_WORKFLOWS):
            batch_end = min(i + MAX_PARALLEL_CHILD_WORKFLOWS, end_index)
            
            # Fetch folder batch
            folders_batch = await workflow.execute_activity(
                "fetch_folders_batch_from_cache",
                args=[params, params.folders_cache_key, i, batch_end],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy
            )
            
            # Start Child Workflows for each folder
            handles = []
            for folder_prefix in folders_batch:
                # Prepare params for child workflow (single folder)
                child_params = params.copy_with(
                    source_path=folder_prefix,
                    recursive=False,  # Process only this folder
                    start_index=0,    # Reset for child
                    folders_cache_key="", # No cache for child
                )
                
                handle = await workflow.start_child_workflow(
                    "FolderIngestionWorkflow",
                    args=[child_params],
                    id=f"ingest-folder-{uuid.uuid4()}",
                    parent_close_policy=ParentClosePolicy.ABANDON,
                    task_queue=INGESTION_TASK_QUEUE,
                    retry_policy=retry_policy
                )
                handles.append(handle)
            
            # Wait for all folder child workflows in this sub-batch
            batch_results = await asyncio.gather(*handles, return_exceptions=True)
            
            # Accumulate results
            for res in batch_results:
                if isinstance(res, Exception):
                    logger.error(f"Child workflow failed: {res}")
                    params.acc_failed += 1 # Or more granular error tracking
                elif isinstance(res, dict):
                    params.acc_successful += res.get("successful", 0)
                    params.acc_failed += res.get("failed", 0)
                    params.acc_total_files += res.get("total_files", 0)

        params.start_index = end_index

        # Broadcast progress/start before continue or return
        await workflow.execute_activity(
            "push_sse_event",
            args=[{
                "task_id": getattr(params, "task_id", ""),
                "event_type": "ingestion_progress",
                "message": "start",
                "phase": "processing",
                "progress": {
                    "total_folders": params.folders_total,
                    "processed_folders": params.start_index,
                    "successful": params.acc_successful,
                    "failed": params.acc_failed,
                    "total_files": params.acc_total_files
                }
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=retry_policy
        )

        # 4. Continue As New
        if params.start_index < params.folders_total:
            await workflow.continue_as_new(params)
        
        return PipelineResult(
            total_folders=params.folders_total,
            total_files=params.acc_total_files,
            successful=params.acc_successful,
            failed=params.acc_failed,
            folder_contexts=[],
            execution_time_seconds=0.0
        )
