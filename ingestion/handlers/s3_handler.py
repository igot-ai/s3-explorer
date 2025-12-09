"""S3-based collection handler implementation."""

import logging
from typing import Dict, Any, BinaryIO
from pathlib import Path
from .base import CollectionHandler
from ..core.models import FileContext, Catalog, FolderContext
from ..connectors.storage import StorageProvider

logger = logging.getLogger(__name__)


class S3CollectionHandler(CollectionHandler):
    """Upload files to S3 collections using existing StorageProvider.
    
    Organizes files by catalog ID in separate S3 paths.
    """

    def __init__(self, storage_provider: StorageProvider):
        """Initialize S3 collection handler.
        
        Args:
            storage_provider: Configured StorageProvider instance
        """
        self.provider = storage_provider

    def upload(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        metadata: Dict[str, Any]
    ) -> str:
        """Upload file to S3 collection.
        
        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            metadata: Metadata to attach to the file
            
        Returns:
            Destination path in S3
        """
        try:
            destination_path = self.build_destination_path(file_context, catalog)
            
            # Upload file
            self.provider.upload_file(file_stream, destination_path)
            
            # Log metadata (S3 basic upload doesn't support custom metadata easily,
            # but this could be extended to use S3 tags or a metadata file)
            logger.info(f"Uploaded {file_context.source_path} to {destination_path}")
            logger.debug(f"Metadata: {metadata}")
            
            return destination_path
            
        except Exception as e:
            logger.error(f"Error uploading to S3: {str(e)}")
            raise

    def upload_with_folder_context(
        self,
        file_context: FileContext,
        catalog: Catalog,
        file_stream: BinaryIO,
        file_metadata: Dict[str, Any],
        folder_context: FolderContext
    ) -> str:
        """Upload file with full folder context for metadata aggregation.
        
        Args:
            file_context: Context of the file being uploaded
            catalog: Target catalog/collection
            file_stream: File content as binary stream
            file_metadata: File-specific metadata
            folder_context: Context of the parent folder
            
        Returns:
            Destination path in S3
        """
        try:
            # Prepare metadata with folder context
            prepared_metadata = self.prepare_metadata(file_metadata, folder_context, catalog)
            
            # Upload file
            destination_path = self.upload(file_context, catalog, file_stream, prepared_metadata)
            
            # If catalog requires all metadata, upload a metadata file alongside
            if catalog.fetch_all_metadata:
                self._upload_metadata_file(destination_path, prepared_metadata)
            
            return destination_path
            
        except Exception as e:
            logger.error(f"Error uploading with folder context: {str(e)}")
            raise

    def build_destination_path(
        self,
        file_context: FileContext,
        catalog: Catalog
    ) -> str:
        """Construct the destination path for the file.
        
        Organizes files as: collections/{catalog_id}/{original_filename}
        
        Args:
            file_context: File being uploaded
            catalog: Target catalog
            
        Returns:
            Destination path
        """
        # Get base filename
        filename = Path(file_context.source_path).name
        
        # Build path using catalog ID
        return f"collections/{catalog.id}/{filename}"

    def _upload_metadata_file(self, file_path: str, metadata: Dict[str, Any]) -> None:
        """Upload metadata as a separate JSON file.
        
        Args:
            file_path: Path of the uploaded file
            metadata: Metadata to save
        """
        try:
            import json
            from io import BytesIO
            
            # Create metadata filename
            metadata_path = f"{file_path}.metadata.json"
            
            # Convert metadata to JSON
            metadata_json = json.dumps(metadata, indent=2)
            metadata_stream = BytesIO(metadata_json.encode('utf-8'))
            
            # Upload metadata file
            self.provider.upload_file(metadata_stream, metadata_path)
            logger.debug(f"Uploaded metadata file: {metadata_path}")
            
        except Exception as e:
            logger.warning(f"Failed to upload metadata file: {str(e)}")

