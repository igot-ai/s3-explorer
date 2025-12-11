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
            
            # Step 2: Walk folder and process each file
            for file_ctx in self.source.walk_folder(folder_path, recursive=config.recursive):
                try:
                    self._process_file(file_ctx, config, folder_ctx)
                except Exception as e:
                    logger.error(f"Error processing file {file_ctx.source_path}: {str(e)}")
                    file_ctx.status = FileStatus.FAILED
                    file_ctx.error_message = str(e)
                
                if self.on_file_processed:
                    try:
                        self.on_file_processed(file_ctx)
                    except Exception as e:
                        logger.error(f"Error in file callback: {str(e)}")
            
            # Step 3: Aggregate folder results
            self.handler.aggregate_metadata(config.catalogs)
        
        # Build final result
        execution_time = time.time() - start_time
        result = self._build_result(folder_contexts, execution_time)
        
        logger.info(f"Pipeline completed in {execution_time:.2f}s")
        logger.info(f"Summary: {result.get_summary()}")
        
        return result

    def _process_file(
        self,
        file_ctx: FileContext,
        config: IngestionJobConfig,
        folder_ctx: FolderContext
    ) -> None:
        """Process a single file through the pipeline stages.
        
        Args:
            file_ctx: File to process
            config: Job configuration
            folder_ctx: Parent folder context
        """
        logger.debug(f"Processing file: {file_ctx.source_path}")
        
        # Create temporary directory for processing; always unique and cleaned after use
        base_temp_dir = Path(config.temp_dir) if config.temp_dir else None
        if base_temp_dir:
            base_temp_dir.mkdir(parents=True, exist_ok=True)
        temp_dir_context = tempfile.TemporaryDirectory(
            dir=str(base_temp_dir) if base_temp_dir else None
        )
        temp_dir = Path(temp_dir_context.name)
        
        try:
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
            
            for pf in processed_files:
                # Skip if processing failed
                if pf.status == FileStatus.FAILED:
                    folder_ctx.add_file(pf)
                    continue
                
                # Stage 2: Read document text
                if pf.local_path and self.reader.can_read(Path(pf.local_path)):
                    pf.extracted_text = self.reader.read_pages(
                        Path(pf.local_path),
                        max_pages=config.pages_to_read
                    )

                    logger.info(f"Extracted text from {pf.source_path}: {pf.extracted_text}")
                    
                    if not pf.extracted_text:
                        logger.warning(f"No text extracted from {pf.source_path}")
                        pf.status = FileStatus.FAILED
                        pf.error_message = "No text could be extracted"
                        folder_ctx.add_file(pf)
                        continue
                    
                    # Stage 3: Classify
                    result = self.classifier.classify(pf.extracted_text, pf.source_path, config.catalogs)
                    pf.classified_catalog_id = result.category_id
                    pf.status = FileStatus.CLASSIFIED
                                        
                    # Stage 4: Upload to collection
                    catalog = config.get_catalog_by_id(result.category_id)
                    if catalog:
                        with open(pf.local_path, 'rb') as f:
                            if catalog.fetch_all_metadata:
                                asset_id = self.handler.upload_with_folder_context(
                                    pf, catalog, f, pf.metadata, folder_ctx
                                )
                            else:
                                asset_id = self.handler.upload(pf, catalog, f, pf.metadata)
                        
                        pf.asset_id = asset_id  # Store the returned asset_id
                        pf.status = FileStatus.UPLOADED
                        logger.info(f"Successfully uploaded {pf.source_path} to collection {catalog.id}, asset_id: {asset_id}")
                    else:
                        logger.warning(f"Catalog {result.category_id} not found")
                        pf.status = FileStatus.FAILED
                        pf.error_message = f"Catalog {result.category_id} not found"
                else:
                    logger.warning(f"Cannot read file type: {pf.file_type}")
                    pf.status = FileStatus.FAILED
                    pf.error_message = f"Unsupported file type: {pf.file_type}"
                
                folder_ctx.add_file(pf)
                
        except Exception as e:
            logger.error(f"Error in file processing pipeline: {str(e)}")
            file_ctx.status = FileStatus.FAILED
            file_ctx.error_message = str(e)
            folder_ctx.add_file(file_ctx)
        finally:
            # Remove temporary files created for this source file
            temp_dir_context.cleanup()

    def _aggregate_folder_metadata(
        self,
        folder_ctx: FolderContext,
        catalogs: List
    ) -> None:
        """Aggregate metadata for the folder.
        
        Args:
            folder_ctx: Folder context to aggregate
            catalogs: List of catalogs
        """
        # Aggregate files by catalog
        folder_ctx.aggregate_by_catalog()
        
        # For each catalog, aggregate metadata if fetch_all_metadata is True
        for catalog in catalogs:
            if catalog.fetch_all_metadata:
                catalog_files = [
                    f for f in folder_ctx.files
                    if f.classified_catalog_id == catalog.id and f.is_successful()
                ]
                
                if catalog_files:
                    # Merge all metadata for this catalog
                    aggregated = {}
                    for file_ctx in catalog_files:
                        for key, value in file_ctx.metadata.items():
                            if key not in aggregated:
                                aggregated[key] = []
                            if value not in aggregated[key]:
                                aggregated[key].append(value)
                    
                    folder_ctx.aggregated_metadata[catalog.id] = aggregated
                    logger.debug(f"Aggregated metadata for catalog {catalog.id}: {aggregated}")

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

