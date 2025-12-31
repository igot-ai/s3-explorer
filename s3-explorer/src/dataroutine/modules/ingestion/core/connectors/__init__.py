"""Connectors for reading files from various sources."""

from dataroutine.modules.ingestion.core.connectors.base import SourceConnector
from dataroutine.modules.ingestion.core.connectors.s3_connector import S3SourceConnector
from dataroutine.shared.storage import StorageProvider, get_storage_provider

__all__ = [
    "SourceConnector",
    "StorageProvider",
    "get_storage_provider",
    "S3SourceConnector",
]
