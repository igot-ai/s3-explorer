"""Pydantic models for FastAPI request/response validation."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CatalogModel(BaseModel):
    """Model for a document catalog/category."""
    id: str = Field(..., description="Unique identifier for the catalog")
    instruction: str = Field(..., description="Classification instruction for LLM")
    fetch_all_metadata: bool = Field(default=False, description="If True, aggregate metadata from all catalogs for the folder")


class StorageCredentialsModel(BaseModel):
    """Model for storage credentials."""
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


class IngestionConfigModel(BaseModel):
    """Model for ingestion pipeline configuration."""
    source_path: str = Field(..., description="S3 source path to process")
    recursive: bool = Field(default=True, description="Process subfolders recursively")
    pages_to_read: int = Field(default=3, ge=1, description="Number of pages to read from each document")
    temp_dir: Optional[str] = Field(default=None, description="Temporary directory (uses env TEMP_DIR if not provided)")
    reader_type: Optional[str] = Field(default=None, description="Document reader type (markitdown, pdfplumber, pymupdf)")
    api_base_url: Optional[str] = Field(default=None, description="API base URL for collection handler")
    storage_provider: str = Field(default="aws", description="Storage provider type (aws, gcs, cloudflare, etc.)")
    storage_credentials: Optional[StorageCredentialsModel] = Field(default=None)
    workspace_id: Optional[str] = Field(default=None, description="Workspace ID for API handler (required)")
    project_id: Optional[str] = Field(default=None, description="Project ID for API handler (required)")
    auth_token: Optional[str] = Field(default=None, description="Auth token for API handler (required)")
    task_id: Optional[str] = Field(default=None, description="Optional task identifier")
    user_id: Optional[str] = Field(default=None, description="Optional user ID who initiated the job")
    
    @field_validator("storage_credentials", mode="before")
    @classmethod
    def validate_storage_credentials(cls, v):
        """Convert dict to StorageCredentialsModel if needed."""
        if v is None or v == {}:
            return None
        if isinstance(v, dict):
            return StorageCredentialsModel(**v)
        return v


class IngestionRequestModel(BaseModel):
    """Model for the ingestion API request body."""
    config: IngestionConfigModel = Field(..., description="Pipeline configuration")
    catalogs: List[CatalogModel] = Field(..., min_length=1, description="List of catalogs for classification")


class FileResultModel(BaseModel):
    """Model for individual file processing result."""
    source_path: str
    status: str
    classified_catalog_id: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FolderResultModel(BaseModel):
    """Model for folder processing result."""
    folder_path: str
    successful_count: int
    failed_count: int
    files: List[FileResultModel] = Field(default_factory=list)


class IngestionResponseModel(BaseModel):
    """Model for the ingestion API response."""
    success: bool
    message: str
    task_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    total_folders: int = 0
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: str = "0.00%"
    execution_time: str = "0.00s"
    folders: List[FolderResultModel] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class ListPrefixesRequestModel(BaseModel):
    """Model for list-prefixes request."""
    storage_provider: str = Field(default="aws", description="Storage provider type")
    storage_credentials: StorageCredentialsModel = Field(..., description="Storage credentials")
    prefix: str = Field(default="", description="Optional prefix path")


class ListPrefixesResponseModel(BaseModel):
    """Model for list-prefixes response."""
    success: bool
    prefixes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

