"""Pydantic schemas for ingestion API endpoints."""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class CatalogSchema(BaseModel):
    """Schema for a document catalog/category."""
    
    id: str = Field(..., description="Unique identifier for the catalog")
    information: str = Field(..., description="Classification instruction for LLM")
    content: str = Field(..., description="Human-readable description of this catalog")
    fetch_all_metadata: bool = Field(default=False, description="If True, aggregate metadata from all catalogs for the folder")
    metadata_scan: Dict[str, Any] = Field(default_factory=dict, description="Schema of metadata fields to extract")


class StorageCredentialsSchema(BaseModel):
    """Schema for storage credentials."""
    
    access_key: Optional[str] = Field(default=None, description="Access key for storage provider")
    secret_key: Optional[str] = Field(default=None, description="Secret key for storage provider")
    bucket: Optional[str] = Field(default=None, description="Bucket name")
    region: Optional[str] = Field(default="us-east-1", description="Region for storage provider")
    account_id: Optional[str] = Field(default=None, description="Account ID (for Cloudflare)")
    project_id: Optional[str] = Field(default=None, description="Project ID (for GCS)")
    bucket_name: Optional[str] = Field(default=None, description="Bucket name (for GCS/Backblaze)")
    credentials_json: Optional[str] = Field(default=None, description="Credentials JSON (for GCS)")
    application_key_id: Optional[str] = Field(default=None, description="Application Key ID (for Backblaze)")
    application_key: Optional[str] = Field(default=None, description="Application Key (for Backblaze)")


class IngestionConfigSchema(BaseModel):
    """Schema for ingestion pipeline configuration."""
    
    # Source settings
    source_path: str = Field(..., description="S3 source path to process")
    recursive: bool = Field(default=True, description="Process subfolders recursively")
    
    # Processing settings
    pages_to_read: int = Field(default=3, ge=1, description="Number of pages to read from each document")
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory for processing")
    
    # Classifier settings
    classifier_type: str = Field(default="openai", description="Classifier type (openai, anthropic, ollama, azure)")
    classifier_model: Optional[str] = Field(default=None, description="Classifier model name")
    classifier_api_key: Optional[str] = Field(default=None, description="Classifier API key")
    classifier_api_base_url: Optional[str] = Field(default=None, description="Classifier API base URL")
    classifier_api_version: Optional[str] = Field(default=None, description="Classifier API version")
    
    # Handler settings
    handler_type: str = Field(default="api", description="Handler type (s3, api)")
    api_base_url: Optional[str] = Field(default=None, description="API base URL for collection handler")
    api_key: Optional[str] = Field(default=None, description="API key for collection handler")
    
    # Reader settings
    reader_type: str = Field(default="pymupdf", description="Document reader type (pymupdf, pdfplumber)")
    
    # Storage provider settings
    storage_provider: str = Field(default="aws", description="Storage provider type (aws, gcs, cloudflare, etc.)")
    storage_credentials: StorageCredentialsSchema = Field(default_factory=StorageCredentialsSchema)

    # API Handler settings
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID for API handler")
    project_id: Optional[str] = Field(default=None, description="Project ID for API handler")
    auth_token: Optional[str] = Field(default=None, description="Auth token for API handler")


class IngestionRequestSchema(BaseModel):
    """Schema for the ingestion API request body."""
    
    config: IngestionConfigSchema = Field(..., description="Pipeline configuration")
    catalogs: List[CatalogSchema] = Field(..., min_length=1, description="List of catalogs for classification")


class FileResultSchema(BaseModel):
    """Schema for individual file processing result."""
    
    source_path: str
    status: str
    classified_catalog_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FolderResultSchema(BaseModel):
    """Schema for folder processing result."""
    
    folder_path: str
    successful_count: int
    failed_count: int
    files: List[FileResultSchema] = Field(default_factory=list)


class IngestionResponseSchema(BaseModel):
    """Schema for the ingestion API response."""
    
    success: bool
    message: str
    total_folders: int = 0
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: str = "0.00%"
    execution_time: str = "0.00s"
    folders: List[FolderResultSchema] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

