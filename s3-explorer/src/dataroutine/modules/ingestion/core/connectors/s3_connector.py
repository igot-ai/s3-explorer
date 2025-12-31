"""S3 source connector implementation."""

from pathlib import Path
from typing import BinaryIO, Iterator, List

from dataroutine.modules.ingestion.core.connectors.base import SourceConnector
from dataroutine.modules.ingestion.core.models import FileContext, FileStatus
from dataroutine.shared._logging import get_logger
from dataroutine.shared.storage import StorageProvider

logger = get_logger(__name__)


class S3SourceConnector(SourceConnector):
    """S3-based source connector using existing StorageProvider.

    Leverages the existing storage_providers infrastructure for S3 access.
    """

    def __init__(self, storage_provider: StorageProvider):
        """Initialize S3 source connector.

        Args:
            storage_provider: Configured StorageProvider instance (from storage_providers.py)
        """
        self.provider = storage_provider

    def list_folders(self, prefix: str = "") -> List[str]:
        """List top-level folders under the given prefix.

        Args:
            prefix: Path prefix to search under

        Returns:
            List of folder paths (ending with /)
        """
        try:
            files = self.provider.list_files(prefix)
            folders = set()

            logger.debug(
                f"Listing folders for prefix '{prefix}', got {len(files)} items from provider"
            )

            for file in files:
                file_name = file["name"]
                file_type = file.get("type")

                # Handle explicit directory entries
                if file_type == "directory" or file_name.endswith("/"):
                    # Ensure it ends with /
                    folder_path = (
                        file_name if file_name.endswith("/") else file_name + "/"
                    )
                    # Check if it's under the prefix
                    if prefix:
                        if folder_path.startswith(prefix):
                            folders.add(folder_path)
                    else:
                        folders.add(folder_path)
                    continue

                # Remove prefix to get relative path
                if prefix and file_name.startswith(prefix):
                    relative_path = file_name[len(prefix) :]
                else:
                    relative_path = file_name

                # Skip if empty
                if not relative_path:
                    continue

                # Extract top-level folder from file path
                if "/" in relative_path:
                    # This is a file in a folder - extract the folder name
                    folder_name = relative_path.split("/")[0]
                    full_folder_path = prefix + folder_name + "/"
                    folders.add(full_folder_path)
                elif not prefix:
                    # At root level, if there's no slash, it's a file at root, skip
                    pass

            result = sorted(list(folders))
            logger.info(
                f"Found {len(result)} folders under prefix '{prefix}': {result}"
            )
            return result

        except Exception as e:
            logger.error(f"Error listing folders: {str(e)}", exc_info=True)
            return []

    def walk_folder(
        self, folder_path: str, recursive: bool = True
    ) -> Iterator[FileContext]:
        """Recursively yield all files within a folder.

        Args:
            folder_path: Path to the folder to walk
            recursive: If True, walk subfolders recursively

        Yields:
            FileContext objects for each file found
        """
        try:
            files = self.provider.list_files(folder_path)

            for file in files:
                file_name = file["name"]
                file_size = file.get("size", 0)
                is_dir = file_name.endswith("/") or file.get("type") == "directory"

                # Descend into subfolders when requested
                if is_dir:
                    if recursive:
                        subfolder = (
                            file_name if file_name.endswith("/") else file_name + "/"
                        )
                        # Avoid infinite loop if provider returns the current folder marker
                        if subfolder != folder_path:
                            yield from self.walk_folder(subfolder, recursive=True)
                    continue

                # Skip empty placeholders
                if file_size == 0:
                    continue

                # Determine file type from extension
                file_path = Path(file_name)
                file_type = file_path.suffix.lower().lstrip(".")

                yield FileContext(
                    source_path=file_name,
                    file_type=file_type,
                    status=FileStatus.PENDING,
                )

            logger.debug(f"Walked folder '{folder_path}' successfully")

        except Exception as e:
            logger.error(f"Error walking folder '{folder_path}': {str(e)}")
            raise

    def download_file(self, file_path: str) -> BinaryIO:
        """Download a file and return as binary stream.

        Args:
            file_path: Path to the file to download

        Returns:
            Binary file object
        """
        try:
            logger.debug(f"Downloading file: {file_path}")
            file_obj = self.provider.download_file(file_path)
            return file_obj
        except Exception as e:
            logger.error(f"Error downloading file '{file_path}': {str(e)}")
            raise

    def get_file_metadata(self, file_path: str) -> dict:
        """Get file metadata (size, last_modified, etc.).

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with metadata fields
        """
        try:
            files = self.provider.list_files("")
            for file in files:
                if file["name"] == file_path:
                    return {"size": file.get("size", 0), "name": file["name"]}
            return {}
        except Exception as e:
            logger.error(f"Error getting metadata for '{file_path}': {str(e)}")
            return {}

    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            metadata = self.get_file_metadata(file_path)
            return bool(metadata)
        except Exception as e:
            logger.error(f"Error checking existence of '{file_path}': {str(e)}")
            return False
