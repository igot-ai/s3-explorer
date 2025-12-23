"""Data models for Temporal workflow parameters and results.

These models are designed to be serializable by Temporal and decoupled from
the internal pipeline implementation, allowing external services like catalog
to delegate to the pipeline without tight coupling.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.modules.ingestion.env import API_BASE_URL, READER_TYPE, TEMP_DIR


@dataclass
class CatalogParams:
    """Catalog configuration for document classification.

    Attributes:
        id: Unique identifier for the catalog/collection
        instruction: Classification instruction for LLM
        fetch_all_metadata: If True, aggregate metadata from all catalogs for the folder
    """

    id: str
    instruction: str
    fetch_all_metadata: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "instruction": self.instruction,
            "fetch_all_metadata": self.fetch_all_metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CatalogParams":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            instruction=data["instruction"],
            fetch_all_metadata=data.get("fetch_all_metadata", False),
        )


@dataclass
class StorageCredentials:
    """Storage provider credentials.

    Attributes:
        access_key: AWS/S3 compatible access key
        secret_key: AWS/S3 compatible secret key
        bucket: Bucket name
        region: AWS region (optional)
        account_id: Cloudflare account ID (for R2)
        endpoint_url: Custom endpoint URL (for S3-compatible services)
    """

    access_key: str = ""
    secret_key: str = ""
    bucket: str = ""
    region: Optional[str] = None
    account_id: Optional[str] = None
    endpoint_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        result = {
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket": self.bucket,
        }
        if self.region:
            result["region"] = self.region
        if self.account_id:
            result["account_id"] = self.account_id
        if self.endpoint_url:
            result["endpoint_url"] = self.endpoint_url
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StorageCredentials":
        """Create from dictionary."""
        return cls(
            access_key=data.get("access_key", ""),
            secret_key=data.get("secret_key", ""),
            bucket=data.get("bucket", ""),
            region=data.get("region"),
            account_id=data.get("account_id"),
            endpoint_url=data.get("endpoint_url"),
        )


@dataclass
class IngestionJobParams:
    """Parameters for an ingestion pipeline workflow.

    This is the single dataclass used as workflow input, following Temporal best practices.
    External services (like catalog) can construct this to delegate to the ingestion pipeline.

    Attributes:
        source_path: S3 path to process (e.g., "raw-documents/")
        workspace_id: Workspace ID for data collection API
        project_id: Project ID for data collection API
        auth_token: Authentication token for API calls
        catalogs: List of catalog configurations for classification
        task_id: Unique task identifier for tracking
        storage_provider: Storage provider type (aws, cloudflare, etc.)
        storage_credentials: Storage credentials as dictionary
        recursive: Whether to process folders recursively
        pages_to_read: Number of pages to read for classification
        reader_type: Document reader type (pymupdf, pdfplumber, markitdown)
        temp_dir: Temporary directory for file processing
        api_base_url: Base URL for data collection API
        user_id: Optional user ID who initiated the job
    """

    source_path: str
    workspace_id: str
    project_id: str
    auth_token: str
    catalogs: List[Dict[str, Any]] = field(default_factory=list)
    task_id: str = ""
    storage_provider: str = "aws"
    storage_credentials: Dict[str, Any] = field(default_factory=dict)
    recursive: bool = True
    pages_to_read: int = 3
    temp_dir: Optional[str] = field(default_factory=lambda: TEMP_DIR)
    reader_type: str = field(default_factory=lambda: READER_TYPE)
    api_base_url: str = field(default_factory=lambda: API_BASE_URL)
    user_id: Optional[str] = None

    def get_catalogs(self) -> List[CatalogParams]:
        """Convert catalog dictionaries to CatalogParams objects."""
        return [CatalogParams.from_dict(c) for c in self.catalogs]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_path": self.source_path,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "auth_token": self.auth_token,
            "catalogs": self.catalogs,
            "task_id": self.task_id,
            "storage_provider": self.storage_provider,
            "storage_credentials": self.storage_credentials,
            "recursive": self.recursive,
            "pages_to_read": self.pages_to_read,
            "reader_type": self.reader_type,
            "temp_dir": self.temp_dir,
            "api_base_url": self.api_base_url,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionJobParams":
        """Create from dictionary."""
        return cls(
            source_path=data["source_path"],
            workspace_id=data["workspace_id"],
            project_id=data["project_id"],
            auth_token=data["auth_token"],
            catalogs=data.get("catalogs", []),
            task_id=data.get("task_id", ""),
            storage_provider=data.get("storage_provider", "aws"),
            storage_credentials=data.get("storage_credentials", {}),
            recursive=data.get("recursive", True),
            pages_to_read=data.get("pages_to_read", 3),
            reader_type=data.get("reader_type", READER_TYPE),
            temp_dir=data.get("temp_dir"),
            api_base_url=data.get("api_base_url"),
            user_id=data.get("user_id"),
        )


@dataclass
class IngestionResult:
    """Result of an ingestion pipeline execution.

    This is returned by the workflow and can be used by callback workflows.

    Attributes:
        success: Whether the pipeline completed without failures
        task_id: Task identifier
        total_folders: Total number of folders processed
        total_files: Total number of files processed
        successful: Number of successfully processed files
        failed: Number of failed files
        success_rate: Success rate as percentage string
        execution_time: Execution time in seconds
        folders: List of folder results
        error: Error message if the pipeline failed entirely
    """

    success: bool
    task_id: str
    total_folders: int = 0
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: str = "0.00%"
    execution_time: str = "0.00s"
    folders: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "task_id": self.task_id,
            "total_folders": self.total_folders,
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "execution_time": self.execution_time,
            "folders": self.folders,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IngestionResult":
        """Create from dictionary."""
        return cls(
            success=data["success"],
            task_id=data["task_id"],
            total_folders=data.get("total_folders", 0),
            total_files=data.get("total_files", 0),
            successful=data.get("successful", 0),
            failed=data.get("failed", 0),
            success_rate=data.get("success_rate", "0.00%"),
            execution_time=data.get("execution_time", "0.00s"),
            folders=data.get("folders", []),
            error=data.get("error"),
        )

    @classmethod
    def failure(cls, task_id: str, error: str) -> "IngestionResult":
        """Create a failure result."""
        return cls(success=False, task_id=task_id, error=error)
