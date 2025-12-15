"""Command-line interface for the ingestion pipeline."""

import argparse
import sys
from pathlib import Path

from ingestion.config.registry import CatalogRegistry
from ingestion.config.settings import IngestionConfig
from ingestion.core.classifiers.llm_classifier import LLMClassifier
from ingestion.core.connectors import get_storage_provider

# Import implementations
from ingestion.core.connectors.s3_connector import S3SourceConnector
from ingestion.core.handlers.api_handler import DataCollectionAPIHandler
from ingestion.core.models import FileContext, FolderContext, IngestionJobConfig
from ingestion.core.pipeline import IngestionPipeline
from ingestion.core.processors.base import FileProcessorChain
from ingestion.core.processors.converter import DocxToPdfConverter
from ingestion.core.processors.extractor import ArchiveExtractor, SimpleZipExtractor
from ingestion.core.readers.markitdown_reader import MarkitdownReader

from shared._logging import get_logger

logger = get_logger(__name__)


def create_pipeline(
    config: IngestionConfig, catalogs: CatalogRegistry
) -> IngestionPipeline:
    """Create and configure the ingestion pipeline.

    Args:
        config: Pipeline configuration
        catalogs: Catalog registry

    Returns:
        Configured IngestionPipeline instance
    """
    # Create storage provider
    storage_provider = get_storage_provider(
        config.storage_provider, **config.storage_credentials
    )

    # Create source connector
    source_connector = S3SourceConnector(storage_provider)

    # Create processor chain
    processors = []
    converter = DocxToPdfConverter()
    if converter.is_libreoffice_available():
        processors.append(converter)
        logger.info("Using LibreOffice for DOCX conversion")

    # Add archive extractors
    archive_extractor = ArchiveExtractor()
    if archive_extractor.available:
        processors.append(archive_extractor)
        logger.info("Using patool for archive extraction")
    else:
        processors.append(SimpleZipExtractor())
        logger.info("Using built-in ZIP extractor")

    processor_chain = FileProcessorChain(processors)

    # Create document reader
    document_reader = MarkitdownReader()

    classifier = LLMClassifier()
    logger.info(
        f"Using {config.classifier_type} classifier with model: {classifier.model}"
    )

    # Create collection handler
    if not config.api_base_url:
        raise ValueError("API base URL required for API handler")

    collection_handler = DataCollectionAPIHandler(
        workspace_id="igotai",
        project_id="31ad152d-0a91-48f6-b8f4-d335db1ad441",
        auth_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjIxNjAxNDJiLThmYWItNDA4Ny1hODQ3LThiNDAwY2I4YmRkZiIsImVtYWlsIjoibnRuaGFuMjFAY2xjLmZpdHVzLmVkdS52biIsIndvcmtzcGFjZV9pZCI6Imlnb3RhaSIsImp3dF9pZCI6IjBhMTQ3OWJkLTZjMjktNDgwOS1hMzA5LWM1MDk1NzZiY2EyNCIsImFwcF9wZXJtaXNzaW9ucyI6WyJjYXRhbG9nIiwic3R1ZGlvIl0sImV4cCI6MTc2NTk0NDk4MH0.ZbheI_OuCULOa_qsvE7fDeii8Rse0moCnJ2Ck4lbhmw",
    )
    logger.info(f"Using API collection handler: {config.api_base_url}")

    # Create callbacks for progress tracking
    def on_file_processed(file_ctx: FileContext):
        status_emoji = "✅" if file_ctx.is_successful() else "❌"
        logger.info(f"{status_emoji} {file_ctx.source_path} - {file_ctx.status.value}")

    def on_folder_completed(folder_ctx: FolderContext):
        successful = len(folder_ctx.get_successful_files())
        failed = len(folder_ctx.get_failed_files())
        logger.info(
            f"📁 Completed folder: {folder_ctx.folder_path} ({successful} successful, {failed} failed)"
        )

    # Create pipeline
    pipeline = IngestionPipeline(
        source_connector=source_connector,
        processor_chain=processor_chain,
        document_reader=document_reader,
        classifier=classifier,
        collection_handler=collection_handler,
        on_file_processed=on_file_processed,
        on_folder_completed=on_folder_completed,
    )

    return pipeline


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Data Ingestion Pipeline - Process documents from S3 and classify them"
    )

    parser.add_argument(
        "--config", type=str, help="Path to configuration file (JSON or YAML)"
    )
    parser.add_argument(
        "--catalogs",
        type=str,
        required=True,
        help="Path to catalogs file (JSON or YAML)",
    )
    parser.add_argument(
        "--source", type=str, help="S3 source path to process (overrides config)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        if args.config:
            config_path = Path(args.config)
            if config_path.suffix in [".yaml", ".yml"]:
                config = IngestionConfig.from_yaml(str(config_path))
            else:
                config = IngestionConfig.from_json(str(config_path))
            logger.info(f"Loaded configuration from {args.config}")
        else:
            config = IngestionConfig.from_env()
            logger.info("Using configuration from environment variables")

        # Override source path if provided
        if args.source:
            config.source_path = args.source

        # Validate configuration
        if not config.source_path:
            logger.error("Source path is required")
            sys.exit(1)

        # Load catalogs
        catalog_registry = CatalogRegistry()
        catalog_path = Path(args.catalogs)
        if catalog_path.suffix in [".yaml", ".yml"]:
            catalog_registry.load_from_yaml(str(catalog_path))
        else:
            catalog_registry.load_from_json(str(catalog_path))

        logger.info(f"Loaded {len(catalog_registry)} catalogs from {args.catalogs}")

        if len(catalog_registry) == 0:
            logger.error("No catalogs found in catalog file")
            sys.exit(1)

        # Create job configuration
        job_config = IngestionJobConfig(
            source_path=config.source_path,
            catalogs=catalog_registry.get_all(),
            pages_to_read=config.pages_to_read,
            recursive=config.recursive,
            temp_dir=config.temp_dir,
        )

        # Create and run pipeline
        logger.info("=" * 80)
        logger.info("Starting Data Ingestion Pipeline")
        logger.info("=" * 80)

        pipeline = create_pipeline(config, catalog_registry)
        result = pipeline.run(job_config)

        # Print results
        logger.info("=" * 80)
        logger.info("Pipeline Completed")
        logger.info("=" * 80)
        logger.info(f"Total folders processed: {result.total_folders}")
        logger.info(f"Total files processed: {result.total_files}")
        logger.info(f"Successful: {result.successful}")
        logger.info(f"Failed: {result.failed}")
        logger.info(f"Success rate: {result.get_success_rate():.2f}%")
        logger.info(f"Execution time: {result.execution_time_seconds:.2f}s")

        # Exit with appropriate code
        sys.exit(0 if result.failed == 0 else 1)

    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
