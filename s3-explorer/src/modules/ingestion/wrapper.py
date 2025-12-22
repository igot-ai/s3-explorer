"""Wrapper layer for ingestion pipeline integration.

This module provides a clean interface for triggering ingestion jobs via gRPC,
abstracting away the gRPC client details from route handlers.

IMPORTANT: This wrapper must be initialized via init_ingestion_wrapper() during
app bootstrap before use. The wrapper uses dependency injection to avoid circular
dependencies with igotapi.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from src.shared._logging import get_logger

if TYPE_CHECKING:
    from src.modules.ingestion.core.interfaces import IngestionClientProtocol

logger = get_logger(__name__)


@dataclass
class IngestionTaskResult:
    """Result of triggering an ingestion task."""
    task_id: str
    status: str  # "started", "failed"
    success: bool
    error: Optional[str] = None


class IngestionWrapper:
    """Wrapper for triggering ingestion pipeline jobs via gRPC.
    
    This class abstracts the gRPC client call, allowing routes and other
    services to trigger ingestion without directly importing gRPC modules.
    
    The wrapper MUST be initialized with a client implementation via the
    init_ingestion_wrapper() function during app bootstrap.
    """
    
    def __init__(self, ingestion_client: Optional["IngestionClientProtocol"] = None):
        """Initialize wrapper with injected client.
        
        Args:
            ingestion_client: Client implementation that conforms to IngestionClientProtocol.
                            If None, calls to trigger_ingestion will raise RuntimeError.
        """
        self._run_ingestion = ingestion_client
    
    def _get_client(self) -> "IngestionClientProtocol":
        """Get the ingestion client.
        
        Returns:
            IngestionClientProtocol: The configured client
            
        Raises:
            RuntimeError: If wrapper was not initialized with a client
        """
        if self._run_ingestion is None:
            raise RuntimeError( #noqa: Multiple lines OK for error messages
                "Ingestion wrapper not initialized. "
                "Please call init_ingestion_wrapper() during app bootstrap "
                "with a valid client implementation."
            )
        return self._run_ingestion
    
    def trigger_ingestion(
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
        reader_type: str = "pymupdf",
        temp_dir: Optional[str] = None,
        api_base_url: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> IngestionTaskResult:
        """Trigger an ingestion pipeline job.
        
        Args:
            source_path: S3 path to process (e.g., "raw-documents/")
            workspace_id: Workspace ID for data collection API
            project_id: Project ID for data collection API
            auth_token: Authentication token for API calls
            catalogs: List of catalog configurations, each with:
                - id: Catalog ID
                - instruction: Classification instruction for LLM
                - fetch_all_metadata: Whether to aggregate metadata from all catalogs
            task_id: Optional task identifier (auto-generated if not provided)
            storage_provider: Storage provider type (aws, cloudflare, etc.)
            storage_credentials: Storage credentials dict
            recursive: Whether to process folders recursively
            pages_to_read: Number of pages to read for classification
            reader_type: Document reader type (pymupdf, pdfplumber, markitdown)
            temp_dir: Temporary directory for file processing
            api_base_url: Base URL for data collection API
            user_id: Optional user ID who initiated the job
            
        Returns:
            IngestionTaskResult with task_id, status, success, and optional error
        """
        try:
            run_ingestion = self._get_client()
            
            response = run_ingestion(
                source_path=source_path,
                workspace_id=workspace_id,
                project_id=project_id,
                auth_token=auth_token,
                catalogs=catalogs,
                task_id=task_id,
                storage_provider=storage_provider,
                storage_credentials=storage_credentials,
                recursive=recursive,
                pages_to_read=pages_to_read,
                reader_type=reader_type,
                temp_dir=temp_dir,
                api_base_url=api_base_url,
                user_id=user_id,
            )
            
            return IngestionTaskResult(
                task_id=response.task_id,
                status=response.status,
                success=response.success,
                error=response.error if response.error else None,
            )
        except Exception as e:
            logger.error(f"Failed to trigger ingestion pipeline: {e}", exc_info=True)
            return IngestionTaskResult(
                task_id=task_id or "unknown",
                status="failed",
                success=False,
                error=str(e),
            )


# Singleton instance - must be initialized via init_ingestion_wrapper()
_wrapper_instance: Optional[IngestionWrapper] = None


def init_ingestion_wrapper(ingestion_client: "IngestionClientProtocol") -> None:
    """Initialize the ingestion wrapper singleton with a client implementation.
    
    This function MUST be called during app bootstrap (e.g., in FastAPI lifespan)
    before any routes attempt to use the wrapper.
    
    Args:
        ingestion_client: Client implementation conforming to IngestionClientProtocol.
                         Typically this is igotapi.client.run_ingestion_pipeline.
                         
    Raises:
        ValueError: If wrapper is already initialized (prevents re-initialization)
        
    Example:
        ```python
        # In bootstrap.py or app startup
        from igotapi.client import run_ingestion_pipeline
        from dataroutine.modules.ingestion.wrapper import init_ingestion_wrapper
        
        init_ingestion_wrapper(run_ingestion_pipeline)
        ```
    """
    global _wrapper_instance
    if _wrapper_instance is not None:
        logger.warning("Ingestion wrapper already initialized, skipping re-initialization")
        return
    
    logger.info("Initializing ingestion wrapper with client implementation")
    _wrapper_instance = IngestionWrapper(ingestion_client=ingestion_client)
    logger.debug("Ingestion wrapper initialized successfully")


def get_ingestion_wrapper() -> IngestionWrapper:
    """Get singleton instance of IngestionWrapper.
    
    Returns:
        IngestionWrapper: The initialized wrapper instance
        
    Raises:
        RuntimeError: If wrapper has not been initialized via init_ingestion_wrapper()
        
    Note:
        You must call init_ingestion_wrapper() during app bootstrap before
        calling this function.
    """
    global _wrapper_instance
    if _wrapper_instance is None:
        raise RuntimeError( #noqa: Multiple lines OK for error messages
            "Ingestion wrapper not initialized. "
            "Call init_ingestion_wrapper() during app bootstrap "
            "before using get_ingestion_wrapper()."
        )
    return _wrapper_instance


def reset_ingestion_wrapper() -> None:
    """Reset the wrapper singleton (primarily for testing).
    
    Warning:
        This is intended for testing only. Do not use in production code.
    """
    global _wrapper_instance
    logger.debug("Resetting ingestion wrapper singleton")
    _wrapper_instance = None


# --- Temporal Client Function ---

async def _run_ingestion_pipeline_async(
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
    reader_type: str = "pymupdf",
    temp_dir: Optional[str] = None,
    api_base_url: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs,
) -> "IngestionTaskResult":
    """Async function to trigger ingestion workflow via Temporal.
    
    This is the actual implementation that starts the Temporal workflow.
    """
    import uuid
    from src.shared.temporal_client import get_temporal_client
    from src.modules.ingestion.temporal.workflows import INGESTION_TASK_QUEUE
    from src.modules.ingestion.temporal.models import IngestionJobParams
    
    task_id = task_id or str(uuid.uuid4())
    
    try:
        client = await get_temporal_client()
        
        # Build params for the workflow
        params = IngestionJobParams(
            source_path=source_path,
            workspace_id=workspace_id,
            project_id=project_id,
            auth_token=auth_token,
            catalogs=catalogs,
            task_id=task_id,
            storage_provider=storage_provider,
            storage_credentials=storage_credentials or {},
            recursive=recursive,
            pages_to_read=pages_to_read,
            reader_type=reader_type,
            temp_dir=temp_dir,
            api_base_url=api_base_url,
            user_id=user_id,
        )
        
        # Start the workflow (fire-and-forget for now)
        handle = await client.start_workflow(
            "IngestionPipelineWorkflow",
            params,
            id=f"ingestion-{task_id}",
            task_queue=INGESTION_TASK_QUEUE,
        )
        
        logger.info(f"✅ Started ingestion workflow: {handle.id}")
        
        return IngestionTaskResult(
            task_id=task_id,
            status="started",
            success=True,
        )
    except Exception as e:
        logger.error(f"❌ Failed to start ingestion workflow: {e}", exc_info=True)
        return IngestionTaskResult(
            task_id=task_id,
            status="failed",
            success=False,
            error=str(e),
        )


def run_ingestion_pipeline(**kwargs) -> "IngestionTaskResult":
    """Synchronous wrapper to trigger ingestion pipeline via Temporal.
    
    This function can be passed to init_ingestion_wrapper() as the client.
    It wraps the async workflow trigger for use in sync contexts.
    """
    from src.shared.temporal_client import run_async
    
    return run_async(_run_ingestion_pipeline_async(**kwargs))
