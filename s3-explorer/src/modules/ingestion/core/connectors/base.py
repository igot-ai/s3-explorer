"""Abstract base class for source connectors."""

from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator, List

from src.modules.ingestion.core.models import FileContext


class SourceConnector(ABC):
    """Abstract interface for reading files from a source (S3, local, etc.).

    Implementations should provide methods to:
    - List top-level folders
    - Recursively walk folder contents
    - Download files
    - Get file metadata
    """

    @abstractmethod
    def list_folders(self, prefix: str = "") -> List[str]:
        """List top-level folders under the given prefix.

        Args:
            prefix: Path prefix to search under

        Returns:
            List of folder paths
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def download_file(self, file_path: str) -> BinaryIO:
        """Download a file and return as binary stream.

        Args:
            file_path: Path to the file to download

        Returns:
            Binary file object
        """
        pass

    @abstractmethod
    def get_file_metadata(self, file_path: str) -> dict:
        """Get file metadata (size, last_modified, etc.).

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with metadata fields
        """
        pass

    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists.

        Args:
            file_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        pass
