"""API router for ingestion pipeline endpoints."""

import logging
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from ingestion.schemas import (
    IngestionRequestSchema,
    IngestionResponseSchema,
    FolderResultSchema,
    FileResultSchema,
)
from ingestion.config.settings import IngestionConfig
from ingestion.core.models import IngestionJobConfig, Catalog, FileContext, FolderContext
from ingestion.core.pipeline import IngestionPipeline

# Import implementations
from ingestion.connectors.s3_connector import S3SourceConnector
from ingestion.processors.base import FileProcessorChain
from ingestion.processors.converter import DocxToPdfConverter
from ingestion.processors.extractor import ArchiveExtractor, SimpleZipExtractor
from ingestion.readers.markitdown_reader import MarkitdownReader
from ingestion.classifiers.llm_classifier import LLMClassifier
from ingestion.handlers.api_handler import DataCollectionAPIHandler
from ingestion.connectors import get_storage_provider

logger = logging.getLogger(__name__)

ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/ingestion")


def create_pipeline_from_request(config: IngestionConfig, workspace_id: str, project_id: str, auth_token: str) -> IngestionPipeline:
    """Create and configure the ingestion pipeline from request data.
    
    Args:
        config: Pipeline configuration
        workspace_id: Workspace ID for API handler
        project_id: Project ID for API handler  
        auth_token: Auth token for API handler
        
    Returns:
        Configured IngestionPipeline instance
    """
    # Create storage provider
    storage_provider = get_storage_provider(
        config.storage_provider,
        **config.storage_credentials
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
    
    document_reader = MarkitdownReader()
    
    classifier = LLMClassifier()
    logger.info(f"Using {config.classifier_type} classifier with model: {classifier.model}")
    
    # Create collection handler
    if not config.api_base_url:
        raise ValueError("API base URL required for API handler")

    collection_handler = DataCollectionAPIHandler(
        workspace_id=workspace_id,
        project_id=project_id,
        auth_token=auth_token
    )
    logger.info(f"Using API collection handler: {config.api_base_url}")
    
    # Create callbacks for progress tracking
    def on_file_processed(file_ctx: FileContext):
        status_emoji = "✅" if file_ctx.is_successful() else "❌"
        logger.info(f"{status_emoji} {file_ctx.source_path} - {file_ctx.status.value}")
    
    def on_folder_completed(folder_ctx: FolderContext):
        successful = len(folder_ctx.get_successful_files())
        failed = len(folder_ctx.get_failed_files())
        logger.info(f"📁 Completed folder: {folder_ctx.folder_path} ({successful} successful, {failed} failed)")
    
    # Create pipeline
    pipeline = IngestionPipeline(
        source_connector=source_connector,
        processor_chain=processor_chain,
        document_reader=document_reader,
        classifier=classifier,
        collection_handler=collection_handler,
        on_file_processed=on_file_processed,
        on_folder_completed=on_folder_completed
    )
    
    return pipeline


@ingestion_bp.route("/run", methods=["POST"])
def run_ingestion():
    """Run the ingestion pipeline with configuration from request body.
    
    Request Body:
        {
            "config": {
                "source_path": "s3://bucket/path",
                "recursive": true,
                "pages_to_read": 3,
                "classifier_type": "openai",
                "reader_type": "pymupdf",
                "storage_provider": "aws",
                "storage_credentials": {
                    "access_key": "...",
                    "secret_key": "...",
                    "bucket": "...",
                    "region": "us-east-1"
                },
                "api_base_url": "https://api.example.com",
                "workspace_id": "...",
                "project_id": "...",
                "auth_token": "..."
            },
            "catalogs": [
                {
                    "id": "catalog1",
                    "information": "Classification instruction",
                    "content": "Description",
                    "fetch_all_metadata": false,
                    "metadata_scan": {}
                }
            ]
        }
    
    Returns:
        JSON response with pipeline execution results
    """
    try:
        # Parse and validate request body
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "Request body is required",
                "errors": ["No JSON data provided"]
            }), 400
        
        # Validate with Pydantic
        try:
            req = IngestionRequestSchema(**data)
        except ValidationError as e:
            errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
            return jsonify({
                "success": False,
                "message": "Validation error",
                "errors": errors
            }), 400
        
        # Convert Pydantic models to dataclass/internal models
        config = IngestionConfig(
            source_path=req.config.source_path,
            recursive=req.config.recursive,
            pages_to_read=req.config.pages_to_read,
            temp_dir=req.config.temp_dir,
            classifier_type=req.config.classifier_type,
            classifier_model=req.config.classifier_model or "",
            classifier_api_key=req.config.classifier_api_key,
            classifier_api_base_url=req.config.classifier_api_base_url,
            classifier_api_version=req.config.classifier_api_version,
            handler_type=req.config.handler_type,
            api_base_url=req.config.api_base_url,
            api_key=req.config.api_key,
            reader_type=req.config.reader_type,
            storage_provider=req.config.storage_provider,
            storage_credentials=req.config.storage_credentials.model_dump(exclude_none=True)
        )
        
        # Convert catalog schemas to Catalog dataclass instances
        catalogs = [
            Catalog(
                id=cat.id,
                information=cat.information,
                content=cat.content,
                fetch_all_metadata=cat.fetch_all_metadata,
                metadata_scan=cat.metadata_scan
            )
            for cat in req.catalogs
        ]
        
        # Create job configuration
        job_config = IngestionJobConfig(
            source_path=config.source_path,
            catalogs=catalogs,
            pages_to_read=config.pages_to_read,
            recursive=config.recursive,
            temp_dir=config.temp_dir
        )
        
        # Get API handler settings
        workspace_id = req.config.workspace_id
        project_id = req.config.project_id
        auth_token = req.config.auth_token
        
        if not workspace_id or not project_id or not auth_token:
            return jsonify({
                "success": False,
                "message": "Missing required API handler settings",
                "errors": ["workspace_id, project_id, and auth_token are required"]
            }), 400
        
        # Create and run pipeline
        logger.info("=" * 80)
        logger.info("Starting Data Ingestion Pipeline (API)")
        logger.info("=" * 80)
        
        pipeline = create_pipeline_from_request(config, workspace_id, project_id, auth_token)
        result = pipeline.run(job_config)
        
        # Build response
        folders = []
        for folder_ctx in result.folder_contexts:
            files = [
                FileResultSchema(
                    source_path=f.source_path,
                    status=f.status.value,
                    classified_catalog_id=f.classified_catalog_id,
                    error_message=f.error_message,
                    metadata=f.metadata
                )
                for f in folder_ctx.files
            ]
            folders.append(FolderResultSchema(
                folder_path=folder_ctx.folder_path,
                successful_count=len(folder_ctx.get_successful_files()),
                failed_count=len(folder_ctx.get_failed_files()),
                files=files
            ))
        
        response = IngestionResponseSchema(
            success=result.failed == 0,
            message="Pipeline completed successfully" if result.failed == 0 else "Pipeline completed with some failures",
            total_folders=result.total_folders,
            total_files=result.total_files,
            successful=result.successful,
            failed=result.failed,
            success_rate=f"{result.get_success_rate():.2f}%",
            execution_time=f"{result.execution_time_seconds:.2f}s",
            folders=folders
        )
        
        logger.info("=" * 80)
        logger.info("Pipeline Completed")
        logger.info("=" * 80)
        logger.info(f"Total folders processed: {result.total_folders}")
        logger.info(f"Total files processed: {result.total_files}")
        logger.info(f"Successful: {result.successful}")
        logger.info(f"Failed: {result.failed}")
        logger.info(f"Success rate: {result.get_success_rate():.2f}%")
        logger.info(f"Execution time: {result.execution_time_seconds:.2f}s")
        
        return jsonify(response.model_dump()), 200
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Configuration error",
            "errors": [str(e)]
        }), 400
        
    except Exception as e:
        logger.error(f"Pipeline failed with error: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "Pipeline execution failed",
            "errors": [str(e)]
        }), 500


@ingestion_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for the ingestion API."""
    return jsonify({
        "status": "healthy",
        "service": "ingestion-pipeline"
    }), 200

