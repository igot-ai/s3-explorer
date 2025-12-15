"""API router for ingestion pipeline endpoints."""

from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from ingestion.schemas.ingestion_schemas import (
    ingestion_request_schema,
    ingestion_response_schema,
)
from ingestion.config.settings import IngestionConfig
from ingestion.core.models import IngestionJobConfig, Catalog, FileContext, FolderContext
from ingestion.core.pipeline import IngestionPipeline

# Import implementations
from ingestion.core.connectors.s3_connector import S3SourceConnector
from ingestion.core.processors.base import FileProcessorChain
from ingestion.core.processors.converter import DocxToPdfConverter
from ingestion.core.processors.extractor import ArchiveExtractor, SimpleZipExtractor
from ingestion.core.readers.markitdown_reader import MarkitdownReader
from ingestion.core.readers.pdfplumber_reader import PDFPlumberReader
from ingestion.core.readers.pymupdf_reader import PyMuPDFReader
from ingestion.core.classifiers.llm_classifier import LLMClassifier
from ingestion.core.handlers.api_handler import DataCollectionAPIHandler
from ingestion.core.connectors import get_storage_provider
from shared._logging import get_logger


logger = get_logger(__name__)

ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/v1/ingestion")


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
    
    # Select document reader based on config (uses env default)
    reader_type = config.reader_type
    if reader_type == "markitdown":
        document_reader = MarkitdownReader()
    elif reader_type == "pdfplumber":
        document_reader = PDFPlumberReader()
    elif reader_type == "pymupdf":
        document_reader = PyMuPDFReader()
    else:
        document_reader = MarkitdownReader()
    # Classifier uses LLM settings from env.py
    classifier = LLMClassifier()
    
    # Create collection handler
    if not config.api_base_url:
        raise ValueError("API base URL required for API handler")

    collection_handler = DataCollectionAPIHandler(
        base_url=config.api_base_url,
        workspace_id=workspace_id,
        project_id=project_id,
        auth_token=auth_token
    )
    
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
                "source_path": "raw-documents/",  # Required
                "storage_provider": "aws",  # Optional, default: "aws"
                "storage_credentials": {  # Required for S3 access
                    "access_key": "YOUR_AWS_ACCESS_KEY",
                    "secret_key": "YOUR_AWS_SECRET_KEY",
                    "bucket": "your-bucket-name",
                    "region": "us-east-1"
                },
                "workspace_id": "YOUR_WORKSPACE_ID",  # Required
                "project_id": "YOUR_PROJECT_ID",  # Required
                "auth_token": "YOUR_AUTH_TOKEN",  # Required
                "recursive": true,  # Optional, default: true
                "pages_to_read": 3,  # Optional, default: 3
                "reader_type": "pymupdf",  # Optional, uses env READER_TYPE
                "temp_dir": "./tmp/ingestion",  # Optional, uses env TEMP_DIR
                "api_base_url": "http://..."  # Optional, uses env API_BASE_URL
            },
            "catalogs": [
                {
                    "id": "legal-contracts",
                    "information": "Documents containing legal contracts...",
                    "content": "Legal domain documents",
                    "fetch_all_metadata": false,
                    "metadata_scan": {
                        "legal_entity": "string - name of the legal entity",
                        "contract_type": "string - type of contract"
                    }
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
        
        try:
            req = ingestion_request_schema.load(data)
        except ValidationError as e:
            errors = [f"{field}: {', '.join(msgs)}" for field, msgs in e.messages.items()]
            return jsonify({
                "success": False,
                "message": "Validation error",
                "errors": errors
            }), 400
        
        # Convert validated data to internal models
        config_data = req["config"]
        storage_creds = config_data.get("storage_credentials", {})
        # Filter out None values from storage credentials
        storage_creds = {k: v for k, v in storage_creds.items() if v is not None}
        
        config = IngestionConfig(
            source_path=config_data["source_path"],
            recursive=config_data.get("recursive", True),
            pages_to_read=config_data.get("pages_to_read", 3),
            storage_provider=config_data.get("storage_provider", "aws"),
            storage_credentials=storage_creds
        )
        
        # Override with request values if provided
        if config_data.get("temp_dir"):
            config.temp_dir = config_data["temp_dir"]
        if config_data.get("reader_type"):
            config.reader_type = config_data["reader_type"]
        if config_data.get("api_base_url"):
            config.api_base_url = config_data["api_base_url"]
        
        # Convert catalog data to Catalog dataclass instances
        catalogs = [
            Catalog(
                id=cat["id"],
                information=cat["information"],
                content=cat["content"],
                fetch_all_metadata=cat.get("fetch_all_metadata", False),
                metadata_scan=cat.get("metadata_scan", {})
            )
            for cat in req["catalogs"]
        ]
        
        # Create job configuration
        job_config = IngestionJobConfig(
            source_path=config.source_path,
            catalogs=catalogs,
            recursive=config.recursive,
            temp_dir=config.temp_dir
        )
        
        # Get API handler settings
        workspace_id = config_data.get("workspace_id")
        project_id = config_data.get("project_id")
        auth_token = config_data.get("auth_token")
        
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
                {
                    "source_path": f.source_path,
                    "status": f.status.value,
                    "classified_catalog_id": f.classified_catalog_id,
                    "error_message": f.error_message,
                    "metadata": f.metadata
                }
                for f in folder_ctx.files
            ]
            folders.append({
                "folder_path": folder_ctx.folder_path,
                "successful_count": len(folder_ctx.get_successful_files()),
                "failed_count": len(folder_ctx.get_failed_files()),
                "files": files
            })
        
        response_data = {
            "success": result.failed == 0,
            "message": "Pipeline completed successfully" if result.failed == 0 else "Pipeline completed with some failures",
            "total_folders": result.total_folders,
            "total_files": result.total_files,
            "successful": result.successful,
            "failed": result.failed,
            "success_rate": f"{result.get_success_rate():.2f}%",
            "execution_time": f"{result.execution_time_seconds:.2f}s",
            "folders": folders
        }
        
        logger.info("=" * 80)
        logger.info("Pipeline Completed")
        logger.info("=" * 80)
        logger.info(f"Total folders processed: {result.total_folders}")
        logger.info(f"Total files processed: {result.total_files}")
        logger.info(f"Successful: {result.successful}")
        logger.info(f"Failed: {result.failed}")
        logger.info(f"Success rate: {result.get_success_rate():.2f}%")
        logger.info(f"Execution time: {result.execution_time_seconds:.2f}s")
        
        return jsonify(ingestion_response_schema.dump(response_data)), 200
        
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

