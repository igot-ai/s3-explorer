# Re-export storage providers from the ingestion module for backward compatibility
from ingestion.core.connectors.storage import (
    StorageProvider,
    S3CompatibleProvider,
    AWSS3Provider,
    BackblazeB2Provider,
    WasabiProvider,
    GoogleCloudStorageProvider,
    DigitalOceanSpacesProvider,
    CloudflareR2Provider,
    HetznerStorageProvider,
    get_storage_provider,
)

__all__ = [
    'StorageProvider',
    'S3CompatibleProvider',
    'AWSS3Provider',
    'BackblazeB2Provider',
    'WasabiProvider',
    'GoogleCloudStorageProvider',
    'DigitalOceanSpacesProvider',
    'CloudflareR2Provider',
    'HetznerStorageProvider',
    'get_storage_provider',
] 