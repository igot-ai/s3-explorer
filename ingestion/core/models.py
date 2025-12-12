"""Core data models for the ingestion pipeline."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, field_validator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FileStatus(Enum):
    """Status of a file in the ingestion pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    CONVERTED = "converted"
    CLASSIFIED = "classified"
    UPLOADED = "uploaded"
    FAILED = "failed"


@dataclass
class Catalog:
    """Represents a document collection/category.
    
    Attributes:
        id: Unique identifier for the catalog
        information: Classification instruction for LLM (how to identify documents)
        content: Human-readable description of this catalog
        fetch_all_metadata: If True, aggregate metadata from all catalogs for the folder
        metadata_scan: Schema of metadata fields to extract (field_name -> type/description)
    """
    id: str
    information: str
    content: str
    fetch_all_metadata: bool = False
    metadata_scan: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate catalog configuration."""
        if not self.id:
            raise ValueError("Catalog id cannot be empty")
        if not self.information:
            raise ValueError("Catalog information cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert catalog to dictionary."""
        return {
            "id": self.id,
            "information": self.information,
            "content": self.content,
            "fetch_all_metadata": self.fetch_all_metadata,
            "metadata_scan": self.metadata_scan,
        }


@dataclass
class FileContext:
    """Represents a file being processed through the pipeline.
    
    Tracks the complete lifecycle of a file from source to destination.
    """
    source_path: str
    local_path: Optional[str] = None
    file_type: str = ""
    extracted_text: str = ""
    classified_catalog_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: FileStatus = FileStatus.PENDING
    error_message: Optional[str] = None
    parent_folder: Optional[str] = None  # Track which folder this file belongs to

    def is_successful(self) -> bool:
        """Check if file processing was successful."""
        return self.status == FileStatus.UPLOADED

    def is_failed(self) -> bool:
        """Check if file processing failed."""
        return self.status == FileStatus.FAILED


@dataclass
class FolderContext:
    """Tracks all files within a source folder.
    
    Maintains state for folder-level operations and metadata aggregation.
    """
    folder_path: str
    files: List[FileContext] = field(default_factory=list)
    catalog_summary: Dict[str, List[str]] = field(default_factory=dict)  # catalog_id -> [file_paths]
    aggregated_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # catalog_id -> metadata

    def add_file(self, file_context: FileContext) -> None:
        """Add a file to this folder context."""
        file_context.parent_folder = self.folder_path
        self.files.append(file_context)

    def get_successful_files(self) -> List[FileContext]:
        """Get all successfully processed files."""
        return [f for f in self.files if f.is_successful()]

    def get_failed_files(self) -> List[FileContext]:
        """Get all failed files."""
        return [f for f in self.files if f.is_failed()]

    def aggregate_by_catalog(self) -> None:
        """Aggregate files by their classified catalog."""
        self.catalog_summary.clear()
        for file_ctx in self.files:
            if file_ctx.classified_catalog_id and file_ctx.is_successful():
                catalog_id = file_ctx.classified_catalog_id
                if catalog_id not in self.catalog_summary:
                    self.catalog_summary[catalog_id] = []
                self.catalog_summary[catalog_id].append(file_ctx.source_path)


@dataclass
class IngestionJobConfig:
    """Configuration for a single ingestion job.
    
    Defines what to process and how to process it.
    """
    source_path: str
    catalogs: List[Catalog]
    pages_to_read: int = 3
    recursive: bool = True
    temp_dir: Optional[str] = None

    def __post_init__(self):
        """Validate job configuration."""
        if not self.source_path:
            raise ValueError("source_path cannot be empty")
        if not self.catalogs:
            raise ValueError("At least one catalog must be provided")
        if self.pages_to_read < 1:
            raise ValueError("pages_to_read must be at least 1")

    def get_catalog_by_id(self, catalog_id: str) -> Optional[Catalog]:
        """Find a catalog by its ID."""
        for catalog in self.catalogs:
            if catalog.id == catalog_id:
                return catalog
        return None


class ClassificationResult(BaseModel):
    """Result of document classification.
    
    Contains the classified catalog and confidence information.
    """
    category_id: str
    confidence: int  # 1-5 scale
    reason: str
    
    @field_validator('confidence', mode='before')
    @classmethod
    def coerce_confidence(cls, v: Union[str, int, float]) -> int:
        """Convert confidence to int, handling string and float inputs from LLM."""
        if v is None:
            return 0
        if isinstance(v, str):
            try:
                # Handle string numbers like "3" or "0.8"
                v = float(v)
            except ValueError:
                return 0
        if isinstance(v, float):
            # Round float to int, scale if needed (0-1 range to 1-5)
            if 0 <= v <= 1:
                v = int(v * 5)  # Scale 0-1 to 0-5
            else:
                v = int(round(v))
        return max(0, min(5, int(v)))  # Clamp to 0-5 range


@dataclass
class PipelineResult:
    """Result of a complete pipeline execution.
    
    Contains summary statistics and all folder contexts.
    """
    total_folders: int
    total_files: int
    successful: int
    failed: int
    folder_contexts: List[FolderContext]
    execution_time_seconds: float = 0.0

    def get_success_rate(self) -> float:
        """Calculate the success rate as a percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.successful / self.total_files) * 100

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the pipeline execution."""
        return {
            "total_folders": self.total_folders,
            "total_files": self.total_files,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": f"{self.get_success_rate():.2f}%",
            "execution_time": f"{self.execution_time_seconds:.2f}s",
        }

