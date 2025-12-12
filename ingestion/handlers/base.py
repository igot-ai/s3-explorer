"""Abstract base class for collection handlers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, BinaryIO, Optional, List
from ingestion.core.models import FileContext, Catalog, FolderContext


class CollectionHandler(ABC):
    """Abstract interface for uploading files to target collections.
    
    Implementations can upload to:
    - S3 storage
    - API endpoints
    - Database systems
    - Other storage providers
    """

    @abstractmethod
    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any]
    ) -> Any:
        """Upload file to the target collection.

        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            metadata: Metadata to attach to the file

        Returns:
            Upload result (asset_id, extracted metadata, etc.)
        """
        pass

    @abstractmethod
    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext
    ) -> Any:
        """Upload file with full folder context for metadata aggregation.
        
        Used when catalog.fetch_all_metadata is True to include aggregated
        metadata from all catalogs in the folder.
        
        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            file_metadata: File-specific metadata
            folder_context: Context of the parent folder
            
        Returns:
            Destination path/URL or API response ID
        """
        pass

    @abstractmethod
    def build_destination_path(
        self,
        file_context: FileContext,
        catalog: Catalog
    ) -> str:
        """Construct the destination path for the file.
        
        Args:
            file_context: File being uploaded
            catalog: Target catalog
            
        Returns:
            Destination path
        """
        pass

    def prepare_metadata(
        self,
        file_metadata: Dict[str, Any],
        folder_context: Optional[FolderContext] = None,
        catalog: Optional[Catalog] = None
    ) -> Dict[str, Any]:
        """Prepare metadata for upload.
        
        Can be overridden to customize metadata preparation.
        
        Args:
            file_metadata: File-specific metadata
            folder_context: Optional folder context for aggregation
            catalog: Optional catalog for context
            
        Returns:
            Prepared metadata dictionary
        """
        prepared = file_metadata.copy()
        
        # Add folder-level aggregated metadata if available
        if folder_context and catalog and catalog.fetch_all_metadata:
            if catalog.id in folder_context.aggregated_metadata:
                prepared["folder_metadata"] = folder_context.aggregated_metadata[catalog.id]
        
        return prepared


class APICollectionHandler(CollectionHandler):
    """Base class for API-based collection management systems.
    
    Provides additional methods for API authentication and collection management.
    """

    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate with the collection management API.
        
        Should store authentication tokens/session for subsequent requests.
        """
        pass

    @abstractmethod
    def get_collection(self, catalog_id: str) -> Optional[Dict]:
        """Retrieve collection details by catalog ID.
        
        Args:
            catalog_id: ID of the catalog/collection
            
        Returns:
            Collection details dictionary or None if not found
        """
        pass

    @abstractmethod
    def create_collection(self, catalog: Catalog) -> Dict:
        """Create a new collection from a catalog definition.
        
        Args:
            catalog: Catalog definition
            
        Returns:
            Created collection details
        """
        pass

    @abstractmethod
    def update_collection_metadata(
        self,
        catalog_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Update metadata for a collection.
        
        Args:
            catalog_id: ID of the catalog/collection
            metadata: Metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        pass

    def is_authenticated(self) -> bool:
        """Check if currently authenticated.
        
        Can be overridden for custom authentication checks.
        
        Returns:
            True if authenticated, False otherwise
        """
        return False

    @abstractmethod
    def aggregate_metadata(
        self,
        catalogs: List[Catalog],
    ) -> bool:
        """Aggregate metadata for a collection.
        
        Args:
            catalogs: List of target catalogs/collections
            catalog_ids_with_assets: Optional list of catalog IDs that have uploaded assets.
                                     If provided, only trigger for these catalogs.
                                     If None, trigger for all provided catalogs.
            
        Returns:
            True if all transformations were triggered successfully, False otherwise
        """
        pass    

