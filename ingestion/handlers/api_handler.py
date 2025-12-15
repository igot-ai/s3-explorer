"""API-based collection handler implementation with Datalog integration."""

from __future__ import annotations

import asyncio
import hashlib
from _logging import get_logger
import time
from typing import Dict, Any, BinaryIO, Optional, List
from uuid import UUID
import json
import concurrent.futures

import httpx

from ingestion.handlers.base import APICollectionHandler
from ingestion.core.models import FileContext, Catalog, FolderContext
from ingestion.env import API_BASE_URL

logger = get_logger(__name__)

class DatalogService:
    """Service to interact with catalog projects, tables, and assets."""

    def __init__(self, auth_token: str, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.auth_token = auth_token
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def close(self):
        await self.client.aclose()

    def _build_headers(
        self, extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build request headers with authentication and optional extras."""
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.auth_token}",
        }
        if extra_headers:
            headers.update(extra_headers)
        return headers

    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Execute GET request with authentication."""
        headers = self._build_headers(extra_headers)
        return await self.client.get(url, headers=headers, params=params)

    async def _post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Execute POST request with authentication and return JSON response."""
        headers = self._build_headers(extra_headers)
        resp = await self.client.post(url, headers=headers, json=json_data)
        resp.raise_for_status()
        return resp.json()

    async def _delete(
        self,
        url: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """Execute DELETE request with authentication."""
        headers = self._build_headers(extra_headers)
        resp = await self.client.delete(url, headers=headers)
        resp.raise_for_status()
        return resp

    async def _poll_until(
        self,
        url: str,
        condition_check: callable,
        params: Optional[Dict[str, Any]] = None,
        interval_seconds: float = 10.0,
        max_attempts: int = 30,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Any]:
        """Poll a URL until a condition is met or timeout.

        Args:
            url: URL to poll
            condition_check: Function that takes response and returns (done: bool, result: Any)
            params: Query parameters (optional)
            interval_seconds: Time to wait between polling attempts
            max_attempts: Maximum number of polling attempts
            extra_headers: Optional additional headers

        Returns:
            Result from condition_check if successful, None if timeout
        """
        for attempt in range(max_attempts):
            try:
                resp = await self._get(url, params=params, extra_headers=extra_headers)
                done, result = condition_check(resp, attempt)
                if done:
                    return result
            except Exception as e:
                logger.warning(
                    f"Polling attempt {attempt + 1}/{max_attempts} failed: {e}"
                )

            if attempt < max_attempts - 1:
                await asyncio.sleep(interval_seconds)

        return None

    async def upload_asset(
        self,
        table_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        column_static_data: Optional[Dict[str, Any]] = None,
        plain_text: str = "",
        source_id: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Upload a single file as an asset for a given table.

        Args:
            table_id: Catalog table ID
            file_bytes: File content
            filename: File name to send
            content_type: MIME type (e.g., image/jpeg, application/pdf)
            column_static_data: Column static data (optional)
            plain_text: Plain text content (optional)
            source_id: Source ID (optional)
            extra_headers: Optional additional headers

        Returns:
            Parsed JSON response as dict
        """
        url = f"/tables/{table_id}/assets"

        data = {}
        files = {}

        if plain_text:
            data["plain_text"] = plain_text
        if source_id:
            data["source_id"] = source_id
        if column_static_data:
            data["column_static_data"] = json.dumps(column_static_data)

        files["upload_files"] = (filename, file_bytes, content_type)

        logger.info(f"Uploading asset to {url} with data: {data}")

        headers = self._build_headers(extra_headers)
        resp = await self.client.post(url, headers=headers, data=data, files=files)
        resp.raise_for_status()
        return resp.json()

    async def get_project(
        self,
        project_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a catalog project by ID.

        Endpoint:
            GET /v1/catalog/projects/{project_id}

        Args:
            project_id: Catalog project ID to retrieve
            extra_headers: Optional additional headers

        Returns:
            Project details as dict if it exists, None if not found
        """
        if not project_id:
            return None

        url = f"/projects/{project_id}"

        try:
            resp = await self._get(url, extra_headers=extra_headers)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return None
            else:
                resp.raise_for_status()
                return None
        except Exception as e:
            logger.warning(f"Error getting project {project_id}: {e}")
            return None

    async def delete_project(
        self,
        project_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Delete a catalog project.

        Endpoint:
            DELETE /v1/catalog/projects/{project_id}

        Args:
            project_id: Catalog project ID to delete
            extra_headers: Optional additional headers

        Returns:
            True if deletion was successful
        """
        if not project_id:
            return False

        url = f"/projects/{project_id}"
        await self._delete(url, extra_headers=extra_headers)
        return True

    async def create_project(
        self,
        name: str,
        workspace_id: str = "default",
        description: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new catalog project.

        Endpoint:
            POST /v1/catalog/projects

        Args:
            name: Project name (Must be 4-15 chars, lowercase, start with letter, only letters/numbers/underscores)
            workspace_id: Workspace ID (default: "default")
            description: Project description (optional)
            extra_headers: Optional additional headers

        Returns:
            Parsed JSON response with project details including id, owner_id, etc.
        """
        url = "/projects"
        payload = {
            "name": name,
            "workspace_id": workspace_id,
            "description": description,
        }

        return await self._post(url, json_data=payload, extra_headers=extra_headers)

    async def exists_table(
        self,
        table_id: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Get a catalog table by ID.

        Args:
            table_id: Catalog table ID to retrieve
            extra_headers: Optional additional headers

        Returns:
            True if table exists, False if not found
        """
        if not table_id:
            return False

        url = f"/tables/{table_id}/json"

        try:
            resp = await self._get(url, extra_headers=extra_headers)
            if resp.status_code == 200:
                return True
            elif resp.status_code == 404:
                return False
            else:
                resp.raise_for_status()
                return False
        except Exception as e:
            logger.warning(f"Error getting table {table_id}: {e}")
            return False

    async def create_table(
        self,
        project_id: str,
        name: str,
        table_type: str = "TABLE",
        model_transform: str = "FLASH",
        description: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new table (collection) in a catalog project.

        Endpoint:
            POST /v1/catalog/projects/{project_id}/tables

        Args:
            project_id: Catalog project ID
            name: Table name
            table_type: Type of table (default: "TABLE")
            model_transform: Model transformation type (default: "FLASH")
            description: Table description (optional)
            extra_headers: Optional additional headers

        Returns:
            Parsed JSON response with table details including id, project_id, etc.
        """
        url = f"/projects/{project_id}/tables"
        payload = {
            "name": name,
            "project_id": project_id,
            "table_type": table_type,
            "model_transform": model_transform,
            "description": description,
        }

        return await self._post(url, json_data=payload, extra_headers=extra_headers)

    async def create_columns_bulk(
        self,
        table_id: str,
        columns: list[Dict[str, Any]],
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> list[Dict[str, Any]]:
        """Create multiple columns in a catalog table using bulk endpoint.

        Endpoint:
            POST /v1/catalog/tables/{table_id}/columns/bulk

        Args:
            table_id: Catalog table ID
            columns: List of column configurations, each containing:
                - name (required): Column name
                - data_type (optional): Data type (default: "text")
                - content_location (optional): Content location (default: "top-left")
                - scan_ranges (optional): List of scan ranges (default: ["all"])
                - prompt_template (optional): Prompt template for extraction
            extra_headers: Optional additional headers

        Returns:
            List of created column objects with id, table_id, name, etc.
        """
        url = f"/tables/{table_id}/columns/bulk"
        return await self._post(url, json_data=columns, extra_headers=extra_headers)

    async def poll_data_status(
        self,
        table_id: str,
        asset_id: str,
        interval_seconds: float = 10.0,
        max_attempts: int = 120,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Poll the asset status until it becomes SCANNED or timeout.

        Endpoint:
            GET /tables/{table_id}/assets/{asset_id}
        """

        def check_scanned_status(
            resp: httpx.Response, attempt: int
        ) -> tuple[bool, bool]:
            if resp.status_code == 200:
                payload = resp.json()
                status = payload.get("status") if isinstance(payload, dict) else None
                if status == "SCANNED":
                    logger.info(
                        f"Datalog asset {asset_id} for table {table_id} is SCANNED; stopping status poll"
                    )
                    return True, True
            elif resp.status_code in (202, 204):
                pass
            else:
                resp.raise_for_status()
            return False, False

        url = f"/tables/{table_id}/assets/{asset_id}"
        result = await self._poll_until(
            url,
            check_scanned_status,
            interval_seconds=interval_seconds,
            max_attempts=max_attempts,
            extra_headers=extra_headers,
        )
        return result if result is not None else False

    async def trigger_transformation(
        self,
        project_id: str,
        table_id: str,
        asset_ids: Optional[List[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Trigger transformation for a specific catalog table.

        Endpoint pattern:
            POST /projects/{project_id}/tables/{table_id}/transformation

        Args:
            project_id: Catalog project ID
            table_id: Catalog table ID
            asset_ids: List of Asset IDs to trigger transformation for
            extra_headers: Optional additional headers

        Returns:
            Parsed JSON response as dict
        """

        url = f"/projects/{project_id}/tables/{table_id}/transformation"
        # Always set to_prod to False because if we use production mode, we cannot switch back to draft mode
        payload = {"enable_scan_batch": False, "to_prod": False}
        if asset_ids:
            payload["asset_ids"] = asset_ids

        return await self._post(url, json_data=payload, extra_headers=extra_headers)

    async def poll_data_assets(
        self,
        table_id: str,
        asset_id: str,
        interval_seconds: float = 10.0,
        max_attempts: int = 30,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Poll the data assets endpoint until data is available or timeout.

        Endpoint:
            GET /tables/{table_id}/data_assets?asset_ids={asset_id}

        Args:
            table_id: Catalog table ID
            asset_id: Asset ID to poll for
            interval_seconds: Time to wait between polling attempts (default: 10 seconds)
            max_attempts: Maximum number of polling attempts (default: 30)
            extra_headers: Optional additional headers

        Returns:
            Parsed JSON response as dict if data is available, None if timeout or no data
        """

        def check_data_ready(
            resp: httpx.Response, attempt: int
        ) -> tuple[bool, Optional[Dict[str, Any]]]:
            if resp.status_code == 200:
                payload = resp.json()

                # Check if we have valid data
                if payload and isinstance(payload, list) and len(payload) > 0:
                    logger.info(
                        f"Datalog data assets for table {table_id}, asset {asset_id} ready after {attempt + 1} attempts"
                    )
                    return True, {
                        item["column_name"]: item["value"] for item in payload
                    }

                logger.debug(
                    f"Datalog data assets not ready yet (attempt {attempt + 1}/{max_attempts})"
                )
            else:
                resp.raise_for_status()
            return False, None

        url = f"/tables/{table_id}/data_assets"
        params = {"asset_ids": asset_id}

        result = await self._poll_until(
            url,
            check_data_ready,
            params=params,
            interval_seconds=interval_seconds,
            max_attempts=max_attempts,
            extra_headers=extra_headers,
        )

        if result is None:
            logger.warning(
                f"Datalog data assets polling timeout after {max_attempts} attempts for table {table_id}, asset {asset_id}"
            )
            return {}

        return result

    async def setup_project(
        self,
        folder_id: UUID,
    ) -> str:
        """
        Setup datalog project for a folder.
        Creates project with a unique name based on folder ID.

        Args:
            folder_id: The ID of the folder

        Returns:
            String containing the created project ID

        Raises:
            Exception: If project creation fails
        """
        folder_id_str = str(folder_id)
        folder_id_short = folder_id_str.replace("-", "")[:6]
        base_project_name = f"fld_{folder_id_short}"

        timestamp = int(time.time() * 1000)
        suffix_hash = hashlib.sha1(f"{timestamp}".encode()).hexdigest()[:4]
        current_project_name = f"{base_project_name}{suffix_hash}"

        project_resp = await self.create_project(
            name=current_project_name,
            description=f"Project for folder {folder_id_str}",
        )

        return project_resp.get("id")

    async def setup_tables(
        self,
        project_id: str,
        table_configs: list[Dict[str, Any]],
    ) -> list[str]:
        """
        Setup tables and columns for a datalog project.

        Args:
            project_id: The ID of the datalog project
            table_configs: List of table configurations, each containing:
                - name (required): Table name
                - description (optional): Table description
                - columns (optional): List of column configurations

        Returns:
            List of created table IDs

        Raises:
            Exception: If table creation fails
        """
        datalog_table_ids = []

        for table_config in table_configs:
            table_resp = await self.create_table(
                project_id=project_id,
                name=table_config["name"],
                description=table_config.get("description", ""),
                table_type="TABLE",
                model_transform="FLASH",
            )
            table_id = table_resp.get("id")
            if not table_id:
                logger.warning(
                    f"Failed to create table {table_config['name']}: missing table_id"
                )
                continue

            logger.info(f"Created table {table_config['name']} with id: {table_id}")
            datalog_table_ids.append(table_id)

            columns = table_config.get("columns", [])
            if columns:
                try:
                    await self.create_columns_bulk(
                        table_id=table_id,
                        columns=columns,
                    )
                    logger.info(
                        f"Created {len(columns)} columns for table {table_config['name']}"
                    )
                except Exception as col_err:
                    logger.warning(
                        f"Failed to create columns for table {table_config['name']}: {col_err}"
                    )

        return datalog_table_ids


class DataCollectionAPIHandler(APICollectionHandler):
    """Datalog-based collection handler.
    
    Uploads files to Datalog catalog projects via REST API.
    Maps Catalog concepts to Datalog projects/tables.
    """

    def __init__(
        self,
        auth_token: str,
        base_url: str = API_BASE_URL,
        workspace_id: str = "default",
        project_id: Optional[str] = None,
    ):
        """Initialize Datalog collection handler.
        
        Args:
            auth_token: Datalog authentication token
            base_url: Base URL of the Datalog API (default: API_BASE_URL)
            workspace_id: Workspace ID for creating projects (default: "default")
            project_id: Optional existing project ID to use (creates new if not provided)
        """
        self.auth_token = auth_token
        self.base_url = base_url
        self.workspace_id = workspace_id
        self.project_id = project_id
        self._service = DatalogService(auth_token=auth_token, base_url=base_url)
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
                    auth_token=self.auth_token,
                    base_url=self.base_url
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
                    auth_token=self.auth_token,
                    base_url=self.base_url
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
        raise NotImplementedError("Creating collections is not supported in this class since user have to create collection first")

    def update_collection_metadata(
        self,
        catalog_id: str,
        metadata: Dict[str, Any]
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
        raise NotImplementedError("Datalog is not supported the API call to get collection details")

    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any]
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
            content_type = self._guess_content_type(file_context.source_path)
            table_id = catalog.id
            filename = file_context.source_path.split('/')[-1]
            source_id = file_context.source_path
            column_static_data = metadata.get("folder_metadata", {})
            project_id = self.project_id
            
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
                
                asset_id = _pick_asset(uploaded_files)

                self._run_async(
                    lambda svc: svc.trigger_transformation(
                        project_id=project_id,
                        table_id=table_id,
                        asset_ids=[asset_id],
                    )
                )

                extracted_metadata = self._run_async(
                    lambda svc: svc.poll_data_assets(
                        table_id=table_id,
                        asset_id=asset_id,
                        interval_seconds=10.0,
                        max_attempts=60  # Wait up to 10 minutes per asset
                    )
                )

                # Return both asset_id and extracted metadata
                return {
                    "asset_id": asset_id,
                    "extracted_metadata": extracted_metadata or {}
                }
            
            if not asset_id:
                raise ValueError(f"Upload response missing asset_id (response keys: {list(result.keys())})")

            return []
            
        except Exception as e:
            logger.error(f"Error uploading to Datalog: {str(e)}")
            raise

    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext
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
        prepared_metadata = self.prepare_metadata(file_metadata, folder_context, catalog)

        # Upload file (metadata is included in the file context)
        return self.upload(file_context, catalog, file_stream, prepared_metadata)

    def build_destination_path(
        self,
        file_context: FileContext,
        catalog: Catalog
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
