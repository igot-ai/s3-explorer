"""Interfaces for ingestion module."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from src.modules.ingestion.env import READER_TYPE, TEMP_DIR


@dataclass
class IngestionResponse:
    """Standard response from ingestion client."""

    task_id: str
    status: str
    success: bool
    error: Optional[str] = None


class IngestionClientProtocol(Protocol):
    """Protocol for ingestion client."""

    def __call__(
        self,
        source_path: str,
        workspace_id: str,
        project_id: str,
        auth_token: str,
        catalogs: List[Dict[str, Any]],
        task_id: Optional[str] = None,
        storage_provider: str = "aws",
        storage_credentials: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        pages_to_read: int = 3,
        reader_type: str = READER_TYPE,
        temp_dir: Optional[str] = TEMP_DIR,
        api_base_url: Optional[str] = None,
        user_id: Optional[str] = None,
        callback_workflow: Optional[str] = None,
        callback_params: Optional[Dict[str, Any]] = None,
    ) -> IngestionResponse:
        """Trigger ingestion pipeline."""
        ...
