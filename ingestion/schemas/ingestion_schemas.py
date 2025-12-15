"""Marshmallow schemas for ingestion API validation."""

from marshmallow import Schema, fields, validate, post_load, ValidationError


class CatalogSchema(Schema):
    """Schema for a document catalog/category."""
    
    id = fields.Str(required=True, metadata={"description": "Unique identifier for the catalog"})
    information = fields.Str(required=True, metadata={"description": "Classification instruction for LLM"})
    content = fields.Str(required=True, metadata={"description": "Human-readable description of this catalog"})
    fetch_all_metadata = fields.Bool(load_default=False, metadata={"description": "If True, aggregate metadata from all catalogs for the folder"})
    metadata_scan = fields.Dict(keys=fields.Str(), values=fields.Raw(), load_default=dict, metadata={"description": "Schema of metadata fields to extract"})


class StorageCredentialsSchema(Schema):
    """Schema for storage credentials."""
    
    access_key = fields.Str(load_default=None, metadata={"description": "Access key for storage provider"})
    secret_key = fields.Str(load_default=None, metadata={"description": "Secret key for storage provider"})
    bucket = fields.Str(load_default=None, metadata={"description": "Bucket name"})
    region = fields.Str(load_default="us-east-1", metadata={"description": "Region for storage provider"})
    account_id = fields.Str(load_default=None, metadata={"description": "Account ID (for Cloudflare)"})
    project_id = fields.Str(load_default=None, metadata={"description": "Project ID (for GCS)"})
    bucket_name = fields.Str(load_default=None, metadata={"description": "Bucket name (for GCS/Backblaze)"})
    credentials_json = fields.Str(load_default=None, metadata={"description": "Credentials JSON (for GCS)"})
    application_key_id = fields.Str(load_default=None, metadata={"description": "Application Key ID (for Backblaze)"})
    application_key = fields.Str(load_default=None, metadata={"description": "Application Key (for Backblaze)"})


class IngestionConfigSchema(Schema):
    """Schema for ingestion pipeline configuration.
    
    Note: Classifier settings (LLM_PROVIDER, LLM_MODEL_ID, LLM_API_KEY, etc.)
    are loaded from environment variables in env.py.
    """
    
    # Source settings
    source_path = fields.Str(required=True, metadata={"description": "S3 source path to process"})
    recursive = fields.Bool(load_default=True, metadata={"description": "Process subfolders recursively"})
    
    # Processing settings
    pages_to_read = fields.Int(load_default=3, validate=validate.Range(min=1), metadata={"description": "Number of pages to read from each document"})
    temp_dir = fields.Str(load_default=None, metadata={"description": "Temporary directory (uses env TEMP_DIR if not provided)"})
    
    # Reader settings (uses env READER_TYPE if not provided)
    reader_type = fields.Str(load_default=None, metadata={"description": "Document reader type (markitdown, pdfplumber, pymupdf)"})
    
    # API settings (uses env API_BASE_URL if not provided)
    api_base_url = fields.Str(load_default=None, metadata={"description": "API base URL for collection handler"})
    
    # Storage provider settings
    storage_provider = fields.Str(load_default="aws", metadata={"description": "Storage provider type (aws, gcs, cloudflare, etc.)"})
    storage_credentials = fields.Nested(StorageCredentialsSchema, load_default=dict)

    # API Handler settings (required)
    workspace_id = fields.Str(load_default=None, metadata={"description": "Workspace ID for API handler (required)"})
    project_id = fields.Str(load_default=None, metadata={"description": "Project ID for API handler (required)"})
    auth_token = fields.Str(load_default=None, metadata={"description": "Auth token for API handler (required)"})


class IngestionRequestSchema(Schema):
    """Schema for the ingestion API request body."""
    
    config = fields.Nested(IngestionConfigSchema, required=True, metadata={"description": "Pipeline configuration"})
    catalogs = fields.List(
        fields.Nested(CatalogSchema), 
        required=True, 
        validate=validate.Length(min=1),
        metadata={"description": "List of catalogs for classification"}
    )


class FileResultSchema(Schema):
    """Schema for individual file processing result."""
    
    source_path = fields.Str(required=True)
    status = fields.Str(required=True)
    classified_catalog_id = fields.Str(load_default=None)
    error_message = fields.Str(load_default=None)
    metadata = fields.Dict(keys=fields.Str(), values=fields.Raw(), load_default=dict)


class FolderResultSchema(Schema):
    """Schema for folder processing result."""
    
    folder_path = fields.Str(required=True)
    successful_count = fields.Int(required=True)
    failed_count = fields.Int(required=True)
    files = fields.List(fields.Nested(FileResultSchema), load_default=list)


class IngestionResponseSchema(Schema):
    """Schema for the ingestion API response."""
    
    success = fields.Bool(required=True)
    message = fields.Str(required=True)
    total_folders = fields.Int(load_default=0)
    total_files = fields.Int(load_default=0)
    successful = fields.Int(load_default=0)
    failed = fields.Int(load_default=0)
    success_rate = fields.Str(load_default="0.00%")
    execution_time = fields.Str(load_default="0.00s")
    folders = fields.List(fields.Nested(FolderResultSchema), load_default=list)
    errors = fields.List(fields.Str(), load_default=list)


# Schema instances for validation
ingestion_request_schema = IngestionRequestSchema()
ingestion_response_schema = IngestionResponseSchema()
file_result_schema = FileResultSchema()
folder_result_schema = FolderResultSchema()

