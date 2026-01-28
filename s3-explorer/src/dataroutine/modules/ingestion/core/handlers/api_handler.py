"""API-based collection handler implementation with Datalog integration."""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import Any, BinaryIO, Dict, Optional

from dataroutine.modules.ingestion.core.handlers.base import APICollectionHandler
from dataroutine.modules.ingestion.core.models import Catalog, FileContext, FolderContext
from dataroutine.modules.ingestion.env import API_BASE_URL, DATALOG_AUTH_TOKEN
from dataroutine.modules.ingestion.services.datalog import DatalogService
from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)


class DataCollectionAPIHandler(APICollectionHandler):
    """Datalog-based collection handler.

    Uploads files to Datalog catalog projects via REST API.
    Maps Catalog concepts to Datalog projects/tables.
    """

    def __init__(
        self,
        auth_token: Optional[str] = None,
        base_url: str = API_BASE_URL,
        workspace_id: str = "default",
        project_id: Optional[str] = None,
    ):
        """Initialize Datalog collection handler.

        Args:
            auth_token: Datalog authentication token (if None, uses DATALOG_AUTH_TOKEN env)
            base_url: Base URL of the Datalog API (default: API_BASE_URL)
            workspace_id: Workspace ID for creating projects (default: "default")
            project_id: Optional existing project ID to use (creates new if not provided)
        """
        self.auth_token = auth_token or DATALOG_AUTH_TOKEN
        if not self.auth_token:
            logger.warning("No auth_token provided and DATALOG_AUTH_TOKEN env not set")

        self.base_url = base_url
        self.workspace_id = workspace_id
        self.project_id = project_id
        self._service = DatalogService(auth_token=self.auth_token, base_url=base_url)
        self._authenticated = True  # Token-based auth is always "authenticated"

    def __del__(self):
        """Cleanup async client on destruction."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._service.close())
        except RuntimeError:
            asyncio.run(self._service.close())

    def _run_async_in_thread(self, coro_factory):
        """Run async coroutine factory in a separate thread with fresh event loop.

        This avoids event loop conflicts when called from an async context.

        Args:
            coro_factory: A callable that takes a DatalogService and returns a coroutine
        """

        def run_in_new_loop():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                fresh_service = DatalogService(
                    auth_token=self.auth_token, base_url=self.base_url
                )
                try:
                    coro = coro_factory(fresh_service)
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.run_until_complete(fresh_service.close())
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_in_new_loop)
            return future.result()

    def _run_async(self, coro_factory):
        """Run async coroutine synchronously.

        Args:
            coro_factory: A callable that takes a DatalogService and returns a coroutine

        When called from an async context, runs in a separate thread with
        a fresh event loop and HTTP client to avoid conflicts.
        """
        try:
            asyncio.get_running_loop()
            # A loop is running - use thread to avoid conflicts
            return self._run_async_in_thread(coro_factory)
        except RuntimeError:
            # No running event loop - create fresh service to avoid stale client issues
            async def run_with_fresh_service():
                fresh_service = DatalogService(
                    auth_token=self.auth_token, base_url=self.base_url
                )
                try:
                    return await coro_factory(fresh_service)
                finally:
                    await fresh_service.close()

            return asyncio.run(run_with_fresh_service())

    def authenticate(self) -> None:
        """Authenticate with Datalog API.

        For token-based auth, this is a no-op since we're already authenticated.
        """
        self._authenticated = True
        logger.info("Datalog authentication token configured")

    def is_authenticated(self) -> bool:
        """Check if currently authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        return self._authenticated

    def exists_collection(self, collection_id: str) -> bool:
        """Retrieve collection (table) details by catalog ID.

        Args:
            catalog_id: ID of the catalog/collection

        Returns:
            Table details dictionary or None if not found
        """
        if collection_id:
            return self._run_async(lambda svc: svc.exists_table(collection_id))
        return False

    def create_collection(self, catalog: Catalog) -> Dict:
        """Create a new collection (table) from a catalog definition.

        Args:
            catalog: Catalog definition

        Returns:
            Created table details
        """
        raise NotImplementedError(
            "Creating collections is not supported in this class since user have to create collection first"
        )

    def update_collection_metadata(
        self, catalog_id: str, metadata: Dict[str, Any]
    ) -> bool:
        """Update metadata for a collection.

        Note: Datalog doesn't have a direct metadata update endpoint for tables.
        This could be implemented by updating columns or using transformation.

        Args:
            catalog_id: ID of the catalog/collection
            metadata: Metadata to update

        Returns:
            True if successful, False otherwise
        """
        # Datalog doesn't support direct metadata updates on tables
        # Metadata is typically managed through columns and transformations
        logger.warning("Datalog doesn't support direct metadata updates on collections")
        return False

    def get_collection(self, collection_id: str) -> Dict:
        """Get collection details by collection ID.

        Args:
            collection_id: ID of the collection

        Returns:
            Collection details dictionary
        """
        raise NotImplementedError(
            "Datalog is not supported the API call to get collection details"
        )

    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Upload file to Datalog collection.

        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            metadata: Metadata to attach to the file

        Returns:
            Asset ID from Datalog
        """
        try:
            is_collection_exists = self.exists_collection(catalog.id)

            if not is_collection_exists:
                raise ValueError(f"Collection {catalog.id} does not exist")

            file_bytes = file_stream.read()
            if file_context.local_path:
                filename = os.path.basename(file_context.local_path)
                content_type = self._guess_content_type(file_context.local_path)
            else:
                filename = file_context.source_path.split("/")[-1]
                content_type = self._guess_content_type(file_context.source_path)

            table_id = catalog.id
            source_id = file_context.source_path
            column_static_data = metadata.get("folder_metadata", {})

            result = self._run_async(
                lambda svc: svc.upload_asset(
                    table_id=table_id,
                    file_bytes=file_bytes,
                    filename=filename,
                    content_type=content_type,
                    plain_text=None,
                    source_id=source_id,
                    column_static_data=column_static_data,
                )
            )

            uploaded_files = result.get("uploaded_files") or []
            if isinstance(uploaded_files, list):

                def _pick_asset(files: list[Dict[str, Any]]) -> Optional[str]:
                    for item in files:
                        if not isinstance(item, dict):
                            continue
                        if item.get("asset_id") and item.get("filename") == filename:
                            return item.get("asset_id")

                    for item in files:
                        if not isinstance(item, dict):
                            continue
                        if item.get("asset_id") or item.get("id"):
                            return item.get("asset_id") or item.get("id")
                    return None

                return True if _pick_asset(uploaded_files) is not None else False

            return False
        except Exception as e:
            logger.error(f"Error uploading to Datalog: {str(e)}")
            return False

    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext,
    ) -> Dict[str, Any]:
        """Upload file with full folder context for metadata aggregation.

        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            file_metadata: File-specific metadata
            folder_context: Context of the parent folder

        Returns:
            Dict containing asset_id and extracted_metadata
        """
        # Prepare metadata with folder context
        prepared_metadata = self.prepare_metadata(
            file_metadata, folder_context, catalog
        )

        # Upload file (metadata is included in the file context)
        return self.upload(file_context, catalog, file_stream, prepared_metadata)

    def build_destination_path(
        self, file_context: FileContext, catalog: Catalog
    ) -> str:
        """Construct the destination path for the file.

        For Datalog handler, this returns the API endpoint path.

        Args:
            file_context: File being uploaded
            catalog: Target catalog

        Returns:
            Datalog API endpoint path
        """
        table_id = catalog.id or "unknown"
        return f"{self.base_url}/tables/{table_id}/assets"

    def _guess_content_type(self, file_path: str) -> str:
        """Guess content type from file extension.

        Args:
            file_path: Path to the file

        Returns:
            MIME type string
        """
        import mimetypes

        content_type, _ = mimetypes.guess_type(file_path)
        return content_type or "application/octet-stream"
