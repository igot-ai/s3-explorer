"""Main ingestion pipeline orchestrator."""

import logging
import time
import tempfile
from pathlib import Path
from typing import List, Optional, Callable
from ..core.models import (
    IngestionJobConfig,
    FolderContext,
    FileContext,
    PipelineResult,
    FileStatus,
)
from ..connectors.base import SourceConnector
from ..processors.base import FileProcessorChain
from ..readers.base import DocumentReader
from ..classifiers.base import Classifier
from ..handlers.base import CollectionHandler

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the complete data ingestion workflow.
    
    Follows Single Responsibility Principle - only coordinates, doesn't implement logic.
    """

    def __init__(
        self,
        source_connector: SourceConnector,
        processor_chain: FileProcessorChain,
        document_reader: DocumentReader,
        classifier: Classifier,
        collection_handler: CollectionHandler,
        on_file_processed: Optional[Callable[[FileContext], None]] = None,
        on_folder_completed: Optional[Callable[[FolderContext], None]] = None
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

    def run(self, config: IngestionJobConfig) -> PipelineResult:
        """Execute the full ingestion pipeline.
        
        Args:
            config: Job configuration
            
        Returns:
            PipelineResult with summary statistics
        """
        start_time = time.time()
        folder_contexts = []
        
        logger.info(f"Starting ingestion pipeline for source: {config.source_path}")
        logger.info(f"Processing with {len(config.catalogs)} catalogs")
        
        # Step 1: List all top-level folders
        folders = self.source.list_folders(config.source_path)
        logger.info(f"Found {len(folders)} folders to process")

        for folder_path in folders:
            folder_ctx = FolderContext(folder_path=folder_path)
            logger.info(f"Processing folder: {folder_path}")

            # Create temp directory for the entire folder processing
            base_temp_dir = Path(config.temp_dir) if config.temp_dir else None
            if base_temp_dir:
                base_temp_dir.mkdir(parents=True, exist_ok=True)
            temp_dir_context = tempfile.TemporaryDirectory(
                dir=str(base_temp_dir) if base_temp_dir else None
            )
            temp_dir = Path(temp_dir_context.name)
            
            try:
                # Collect all files from folder
                all_files = list(self.source.walk_folder(folder_path, recursive=config.recursive))
                logger.info(f"Found {len(all_files)} files in folder {folder_path}")
                
                # ============================================================
                # PHASE 1: Download, Convert/Extract, Read text, Classify ALL files
                # ============================================================
                all_processed_files: List[FileContext] = []
                
                for file_ctx in all_files:
                    try:
                        processed_files = self._phase1_extract_and_classify(file_ctx, config, temp_dir)
                        all_processed_files.extend(processed_files)
                    except Exception as e:
                        logger.error(f"Error in phase 1 for {file_ctx.source_path}: {str(e)}")
                        file_ctx.status = FileStatus.FAILED
                        file_ctx.error_message = str(e)
                        all_processed_files.append(file_ctx)
                
                logger.info(f"Phase 1 completed: Extracted and classified {len(all_processed_files)} files")
                
                # ============================================================
                # PHASE 2: Upload ALL files
                # Sort files so fetch_all_metadata=True catalogs are processed last
                # ============================================================
                fetch_all_catalog_ids = {
                    c.id for c in config.catalogs if c.fetch_all_metadata
                }
                
                # Sort: files with fetch_all_metadata=False first, then fetch_all_metadata=True
                sorted_files = sorted(
                    all_processed_files,
                    key=lambda pf: pf.classified_catalog_id in fetch_all_catalog_ids
                )
                
                logger.info(f"Phase 2: Uploading {len(sorted_files)} files (fetch_all_metadata catalogs last)")
                
                for pf in sorted_files:
                    try:
                        # Before uploading fetch_all_metadata files, aggregate metadata from uploaded files
                        if pf.classified_catalog_id in fetch_all_catalog_ids:
                            self._aggregate_folder_metadata(folder_ctx, config.catalogs)
                            logger.debug(f"Aggregated metadata before uploading {pf.source_path}")
                        
                        self._phase2_upload(pf, config, folder_ctx)
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
                
                logger.info(f"Phase 2 completed: Uploaded files")
                
                # Step 3: Aggregate folder metadata before handler aggregation
                self._aggregate_folder_metadata(folder_ctx, config.catalogs)

                # Step 4: Trigger transformations and final aggregation in handler
                self.handler.aggregate_metadata(config.catalogs)
                
                folder_contexts.append(folder_ctx)
                
            finally:
                # Cleanup temp directory after all phases complete
                temp_dir_context.cleanup()
        
        # Build final result
        execution_time = time.time() - start_time
        result = self._build_result(folder_contexts, execution_time)
        
        logger.info(f"Pipeline completed in {execution_time:.2f}s")
        logger.info(f"Summary: {result.get_summary()}")
        
        return result

    def _phase1_extract_and_classify(
        self,
        file_ctx: FileContext,
        config: IngestionJobConfig,
        temp_dir: Path
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
            
            with open(local_path, 'wb') as f:
                f.write(file_stream.read())
            file_ctx.local_path = str(local_path)
        
        # Stage 1: Convert/Extract if needed
        processed_files = self.processor.process(file_ctx, temp_dir)
        
        # Stage 2: Read document text for all processed files
        for pf in processed_files:
            if pf.status == FileStatus.FAILED:
                continue
            
            if pf.local_path and self.reader.can_read(Path(pf.local_path)):
                pf.extracted_text = self.reader.read_pages(
                    Path(pf.local_path),
                    max_pages=config.pages_to_read
                )
                
                if not pf.extracted_text:
                    logger.warning(f"No text extracted from {pf.source_path}")
                    pf.status = FileStatus.FAILED
                    pf.error_message = "No text could be extracted"
                    continue
                
                # Stage 3: Classify
                result = self.classifier.classify(pf.extracted_text, pf.source_path, config.catalogs)
                pf.classified_catalog_id = result.category_id
                pf.status = FileStatus.CLASSIFIED
                logger.debug(f"Classified {pf.source_path} -> catalog: {result.category_id}")
            else:
                logger.warning(f"Cannot read file type: {pf.file_type}")
                pf.status = FileStatus.FAILED
                pf.error_message = f"Unsupported file type: {pf.file_type}"
        
        return processed_files
    
    def _phase2_upload(
        self,
        pf: FileContext,
        config: IngestionJobConfig,
        folder_ctx: FolderContext
    ) -> None:
        """Phase 2: Upload file to collection.
        
        Args:
            pf: Processed file context with classification result
            config: Job configuration
            folder_ctx: Parent folder context
        """
        # Skip if already failed in phase 1
        if pf.status == FileStatus.FAILED:
            folder_ctx.add_file(pf)
            return
        
        # Skip if not classified
        if pf.status != FileStatus.CLASSIFIED or not pf.classified_catalog_id:
            pf.status = FileStatus.FAILED
            pf.error_message = "File not classified"
            folder_ctx.add_file(pf)
            return
        
        logger.debug(f"Phase 2: Uploading: {pf.source_path}")
        
        # Upload to collection
        catalog = config.get_catalog_by_id(pf.classified_catalog_id)
        if catalog:
            with open(pf.local_path, 'rb') as f:
                if catalog.fetch_all_metadata:
                    upload_result = self.handler.upload_with_folder_context(
                        pf, catalog, f, pf.metadata, folder_ctx
                    )
                else:
                    upload_result = self.handler.upload(pf, catalog, f, pf.metadata)

            # Handle both old string format and new dict format
            if isinstance(upload_result, dict):
                pf.asset_id = upload_result.get("asset_id")
                # Update file metadata with extracted data from Datalog
                extracted_metadata = upload_result.get("extracted_metadata", {})
                if extracted_metadata:
                    pf.metadata.update(extracted_metadata)
                    logger.debug(f"Updated metadata for {pf.source_path} with extracted data: {list(extracted_metadata.keys())}")
            else:
                # Legacy format: upload_result is just asset_id string
                pf.asset_id = upload_result

            pf.status = FileStatus.UPLOADED
            logger.info(f"Successfully uploaded {pf.source_path} to collection {catalog.id}, asset_id: {pf.asset_id}")
        else:
            logger.warning(f"Catalog {pf.classified_catalog_id} not found")
            pf.status = FileStatus.FAILED
            pf.error_message = f"Catalog {pf.classified_catalog_id} not found"
        
        folder_ctx.add_file(pf)

    def _aggregate_folder_metadata(
        self,
        folder_ctx: FolderContext,
        catalogs: List
    ) -> None:
        """Aggregate metadata for the folder.
        
        For catalogs with fetch_all_metadata=True, collect metadata from ALL 
        successfully uploaded files in the folder (regardless of their catalog).
        
        Args:
            folder_ctx: Folder context to aggregate
            catalogs: List of catalogs
        """
        # Aggregate files by catalog
        folder_ctx.aggregate_by_catalog()
        
        # Get all successfully uploaded files (from any catalog)
        all_successful_files = [f for f in folder_ctx.files if f.is_successful()]
        
        # For each catalog with fetch_all_metadata=True, aggregate metadata from ALL files
        for catalog in catalogs:
            if catalog.fetch_all_metadata:
                # Merge metadata from ALL successful files (not just same catalog)
                aggregated = {}
                for file_ctx in all_successful_files:
                    for key, value in file_ctx.metadata.items():
                        if key not in aggregated:
                            aggregated[key] = []
                        if value not in aggregated[key]:
                            aggregated[key].append(value)
                
                folder_ctx.aggregated_metadata[catalog.id] = aggregated
                logger.debug(f"Aggregated metadata for catalog {catalog.id} from {len(all_successful_files)} files: {list(aggregated.keys())}")

    def _build_result(
        self,
        folder_contexts: List[FolderContext],
        execution_time: float
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
            execution_time_seconds=execution_time
        )

