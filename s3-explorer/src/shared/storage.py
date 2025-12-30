import datetime
import io
import json
from abc import ABC, abstractmethod
from typing import BinaryIO, List, Optional

import b2sdk.v2 as b2
import boto3
import s3fs
from google.cloud import storage
from google.oauth2 import service_account
from src.shared._logging import get_logger

logger = get_logger(__name__)


class StorageProvider(ABC):
    """Abstract base class for storage providers"""

    @abstractmethod
    def upload_file(self, file_obj: BinaryIO, filename: str) -> None:
        pass

    @abstractmethod
    def download_file(self, filename: str) -> BinaryIO:
        pass

    @abstractmethod
    def delete_file(self, filename: str) -> None:
        pass

    @abstractmethod
    def list_files(self, prefix: str = "") -> List[dict]:
        pass

    @abstractmethod
    def get_file_url(self, filename: str, expires_in: int = 3600) -> str:
        pass

    @abstractmethod
    def create_folder(self, folder_name: str) -> None:
        pass

    @abstractmethod
    def delete_folder(self, folder_name: str) -> None:
        pass


class S3CompatibleProvider(StorageProvider):
    """Base class for S3-compatible storage providers using s3fs

    This class implements all common S3 operations. Subclasses only need to:
    1. Call super().__init__() with initialized s3fs filesystem
    2. Set self.bucket attribute
    """

    def __init__(self, fs: s3fs.S3FileSystem, bucket: str):
        """Initialize with s3fs filesystem"""
        self.fs = fs
        self.bucket = bucket

    def upload_file(self, file_obj: BinaryIO, filename: str) -> None:
        """Upload file using s3fs"""
        s3_path = f"{self.bucket}/{filename}"
        with self.fs.open(s3_path, "wb") as f:
            f.write(file_obj.read())

    def download_file(self, filename: str) -> BinaryIO:
        """Download file using s3fs"""
        s3_path = f"{self.bucket}/{filename}"
        with self.fs.open(s3_path, "rb") as f:
            return io.BytesIO(f.read())

    def delete_file(self, filename: str) -> None:
        """Delete file using s3fs"""
        s3_path = f"{self.bucket}/{filename}"
        self.fs.rm(s3_path)

    def list_files(self, prefix: str = "") -> List[dict]:
        """List files and directories using s3fs"""
        # When prefix is empty, use bucket/ to list contents (not bucket itself)
        if prefix:
            s3_prefix = f"{self.bucket}/{prefix}"
        else:
            s3_prefix = f"{self.bucket}/"
        try:
            files = []
            for item in self.fs.ls(s3_prefix, detail=True):
                # Include both files and directories
                # Files have type="file" or StorageClass, directories have type="directory"
                item_type = item.get("type")
                if item_type in ("file", "directory") or item.get("StorageClass"):
                    key = item.get("Key", item.get("name", ""))
                    if key.startswith(f"{self.bucket}/"):
                        key = key[len(f"{self.bucket}/") :]
                    # Ensure directories end with /
                    if item_type == "directory" and not key.endswith("/"):
                        key = key + "/"
                    files.append(
                        {
                            "name": key,
                            "size": item.get("Size", item.get("size", 0)),
                            "type": item_type,  # Include type for caller to distinguish
                        }
                    )
            return files
        except FileNotFoundError:
            return []

    def get_file_url(self, filename: str, expires_in: int = 3600) -> str:
        """Generate presigned URL using s3fs"""
        s3_path = f"{self.bucket}/{filename}"
        return self.fs.sign(s3_path, expiration=expires_in)

    def create_folder(self, folder_name: str) -> None:
        """Create a folder using s3fs"""
        if not folder_name.endswith("/"):
            folder_name += "/"
        s3_path = f"{self.bucket}/{folder_name}"
        self.fs.touch(s3_path)

    def delete_folder(self, folder_name: str) -> None:
        """Delete a folder and its contents using s3fs.

        Note: "folders" in S3-compatible object stores are key prefixes. We delete
        all objects under the prefix and then attempt to delete the prefix marker.
        """
        if not folder_name.endswith("/"):
            folder_name += "/"

        s3_path = f"{self.bucket}/{folder_name}"

        # Delete all objects within the folder (prefix)
        try:
            objects = self.fs.glob(f"{s3_path}**")
            if objects:
                self.fs.rm(objects, recursive=True)
        except FileNotFoundError:
            pass

        # Delete the folder marker object if present
        try:
            self.fs.rm(s3_path)
        except FileNotFoundError:
            pass


class AWSS3Provider(S3CompatibleProvider):
    """Amazon S3 storage provider using s3fs
    Authentication:
    - AWS Access Key ID
    - AWS Secret Access Key
    - Bucket Name
    - Region
    """

    def __init__(
        self, access_key: str, secret_key: str, bucket: str, region: str, **kwargs
    ):
        # Initialize s3fs filesystem for all operations including presigned URLs
        fs = s3fs.S3FileSystem(
            key=access_key, secret=secret_key, client_kwargs={"region_name": region}
        )

        # Initialize base class with configured filesystem
        super().__init__(fs, bucket)


class BackblazeB2Provider(StorageProvider):
    """Backblaze B2 storage provider
    Authentication:
    - Application Key ID (different from AWS)
    - Application Key
    - Bucket Name
    No region needed
    """

    def __init__(
        self, application_key_id: str, application_key: str, bucket_name: str, **kwargs
    ):
        self.info = b2.InMemoryAccountInfo()
        self.b2_api = b2.B2Api(self.info)
        self.b2_api.authorize_account("production", application_key_id, application_key)
        self.bucket = self.b2_api.get_bucket_by_name(bucket_name)

    def upload_file(self, file_obj: BinaryIO, filename: str) -> None:
        self.bucket.upload_stream(file_obj, filename)

    def download_file(self, filename: str) -> BinaryIO:
        download_dest = b2.DownloadDestBytes()
        self.bucket.download_file_by_name(filename, download_dest)
        return io.BytesIO(download_dest.get_bytes_written())

    def delete_file(self, filename: str) -> None:
        file_version = self.bucket.get_file_info_by_name(filename)
        self.bucket.delete_file_version(file_version.id_, filename)

    def list_files(self, prefix: str = "") -> List[dict]:
        return [
            {"name": f.file_name, "size": f.size}
            for f in self.bucket.list_file_names(prefix)
        ]

    def get_file_url(self, filename: str, expires_in: int = 3600) -> str:
        return self.bucket.get_download_authorization(
            filename, valid_duration_in_seconds=expires_in
        )

    def create_folder(self, folder_name: str) -> None:
        """Create a folder in Backblaze B2.
        B2 doesn't have a concept of folders, so we create a 0-byte file with a trailing slash.
        """
        if not folder_name.endswith("/"):
            folder_name += "/"
        self.bucket.upload_stream(io.BytesIO(b""), folder_name)

    def delete_folder(self, folder_name: str) -> None:
        """Delete a folder and its contents in Backblaze B2."""
        if not folder_name.endswith("/"):
            folder_name += "/"
        for f in self.bucket.list_file_names(folder_name):
            if f.file_name.startswith(folder_name):
                # Delete all versions of the file
                for version in self.bucket.list_file_versions(f.file_name):
                    self.bucket.delete_file_version(version.id_, version.file_name)


class WasabiProvider(S3CompatibleProvider):
    """Wasabi storage provider (S3 compatible) using s3fs
    Authentication:
    - Access Key
    - Secret Key
    - Bucket Name
    - Region (Wasabi specific regions)
    """

    def __init__(
        self, access_key: str, secret_key: str, bucket: str, region: str, **kwargs
    ):
        endpoint_url = f"https://s3.{region}.wasabisys.com"

        # Initialize s3fs filesystem for all operations
        fs = s3fs.S3FileSystem(
            key=access_key,
            secret=secret_key,
            endpoint_url=endpoint_url,
        )

        # Initialize base class with configured filesystem
        super().__init__(fs, bucket)


class GoogleCloudStorageProvider(StorageProvider):
    """Google Cloud Storage provider
    Authentication:
    - Project ID
    - Service Account JSON (contains all auth info)
    - Bucket Name
    No region needed - handled by GCS
    """

    def __init__(
        self, project_id: str, bucket_name: str, credentials_json: str, **kwargs
    ):
        try:
            # Parse the credentials JSON string into a dictionary
            if isinstance(credentials_json, str):
                try:
                    credentials_dict = json.loads(credentials_json)
                    print(
                        f"Successfully parsed credentials JSON for project: {credentials_dict.get('project_id')}"
                    )
                except json.JSONDecodeError as e:
                    print(f"JSON parsing error: {str(e)}")
                    raise ValueError(f"Invalid service account JSON format: {str(e)}")
            else:
                credentials_dict = credentials_json

            try:
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict
                )
                print(
                    f"Successfully created credentials for service account: {credentials_dict.get('client_email')}"
                )
            except Exception as e:
                print(f"Error creating credentials: {str(e)}")
                raise ValueError(
                    f"Error creating service account credentials: {str(e)}"
                )

            try:
                self.client = storage.Client(
                    project=project_id, credentials=credentials
                )
                print(f"Successfully created storage client for project: {project_id}")
            except Exception as e:
                print(f"Error creating storage client: {str(e)}")
                raise ValueError(f"Error creating storage client: {str(e)}")

            try:
                self.bucket = self.client.bucket(bucket_name)
                print(f"Successfully got bucket reference: {bucket_name}")
            except Exception as e:
                print(f"Error getting bucket: {str(e)}")
                raise ValueError(f"Error accessing bucket {bucket_name}: {str(e)}")

        except Exception as e:
            print(f"Unexpected error in GCS initialization: {str(e)}")
            raise ValueError(f"Error initializing Google Cloud Storage: {str(e)}")

    def list_files(self, prefix: str = "") -> List[dict]:
        try:
            # Use delimiter='/' to only get objects in the current level
            # This makes it non-recursive, matching S3 behavior.
            blobs = self.bucket.list_blobs(prefix=prefix, delimiter="/")

            # 1. Collect files (blobs) at this level
            result = [
                {"name": blob.name, "size": blob.size, "type": "file"} for blob in blobs
            ]

            # 2. Collect sub-directories (prefixes)
            # The list_blobs call with delimiter populates blobs.prefixes
            for folder in blobs.prefixes:
                result.append({"name": folder, "size": 0, "type": "directory"})

            return result
        except Exception as e:
            print(f"Error listing files: {str(e)}")
            raise ValueError(f"Error listing files: {str(e)}")

    def upload_file(self, file_obj: BinaryIO, filename: str) -> None:
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_file(file_obj)
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            raise ValueError(f"Error uploading file: {str(e)}")

    def download_file(self, filename: str) -> BinaryIO:
        try:
            blob = self.bucket.blob(filename)
            file_obj = io.BytesIO()
            blob.download_to_file(file_obj)
            file_obj.seek(0)
            return file_obj
        except Exception as e:
            print(f"Error downloading file: {str(e)}")
            raise ValueError(f"Error downloading file: {str(e)}")

    def delete_file(self, filename: str) -> None:
        try:
            blob = self.bucket.blob(filename)
            blob.delete()
        except Exception as e:
            print(f"Error deleting file: {str(e)}")
            raise ValueError(f"Error deleting file: {str(e)}")

    def get_file_url(self, filename: str, expires_in: int = 3600) -> str:
        try:
            blob = self.bucket.blob(filename)
            return blob.generate_signed_url(
                expiration=datetime.timedelta(seconds=expires_in)
            )
        except Exception as e:
            print(f"Error generating signed URL: {str(e)}")
            raise ValueError(f"Error generating signed URL: {str(e)}")

    def create_folder(self, folder_name: str) -> None:
        """Create a folder in GCS by creating a 0-byte blob with a trailing slash."""
        try:
            if not folder_name.endswith("/"):
                folder_name += "/"
            blob = self.bucket.blob(folder_name)
            blob.upload_from_string("", content_type="application/x-directory")
        except Exception as e:
            print(f"Error creating folder: {str(e)}")
            raise ValueError(f"Error creating folder: {str(e)}")

    def delete_folder(self, folder_name: str) -> None:
        """Delete a folder and its contents in GCS."""
        try:
            if not folder_name.endswith("/"):
                folder_name += "/"
            blobs = self.bucket.list_blobs(prefix=folder_name)
            self.bucket.delete_blobs(blobs)
        except Exception as e:
            print(f"Error deleting folder: {str(e)}")
            raise ValueError(f"Error deleting folder: {str(e)}")


class DigitalOceanSpacesProvider(S3CompatibleProvider):
    """DigitalOcean Spaces provider (S3 compatible) using s3fs
    Authentication:
    - Spaces Access Key
    - Spaces Secret Key
    - Bucket Name
    - Region (DO specific: nyc3, ams3, sgp1, etc.)
    """

    def __init__(
        self, access_key: str, secret_key: str, bucket: str, region: str, **kwargs
    ):
        try:
            logger.debug(
                f"Initializing DigitalOcean Spaces provider with bucket: {bucket}, region: {region}"
            )
            endpoint_url = f"https://{region}.digitaloceanspaces.com"

            # Initialize s3fs filesystem for all operations
            fs = s3fs.S3FileSystem(
                key=access_key,
                secret=secret_key,
                endpoint_url=endpoint_url,
                client_kwargs={
                    "config": boto3.session.Config(
                        signature_version="s3v4", s3={"addressing_style": "virtual"}
                    ),
                },
            )

            logger.debug(
                "Successfully initialized DigitalOcean Spaces client with s3fs"
            )

            # Initialize base class with configured filesystem
            super().__init__(fs, bucket)
            self.region = region

        except Exception as e:
            logger.error(f"Error initializing DigitalOcean Spaces client: {str(e)}")
            raise ValueError(
                f"Failed to initialize DigitalOcean Spaces client: {str(e)}"
            )


class CloudflareR2Provider(S3CompatibleProvider):
    """Cloudflare R2 provider (S3 compatible) using s3fs.
    Authentication:
    - Account ID (Cloudflare specific)
    - Access Key ID
    - Secret Access Key
    - Bucket Name
    Region is optional and ignored (R2 uses 'auto')
    """

    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: Optional[str] = None,
        **kwargs,
    ):
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

        if region and region != "auto":
            logger.debug(
                "Cloudflare R2 ignores region '%s'; using 'auto' instead",
                region,
            )

        # Initialize s3fs filesystem for all operations
        fs = s3fs.S3FileSystem(
            key=access_key,
            secret=secret_key,
            endpoint_url=endpoint_url,
            client_kwargs={"region_name": "auto"},
        )

        # Initialize base class with configured filesystem
        super().__init__(fs, bucket)
        self.account_id = account_id


class HetznerStorageProvider(S3CompatibleProvider):
    """Hetzner Storage Box provider (S3 compatible) using s3fs
    Authentication:
    - Access Key
    - Secret Key
    - Bucket Name
    - Region (eu-central: fsn1/nbg1, eu-north: hel1, us-east: ash, us-west: hil, ap-southeast: sin)
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "nbg1",
        **kwargs,
    ):
        try:
            logger.debug(
                f"Initializing Hetzner Storage provider with bucket: {bucket}, region: {region}"
            )
            # Map region codes to endpoints
            region_endpoints = {
                "fsn1": "eu-central",
                "nbg1": "eu-central",
                "hel1": "eu-north",
                "ash": "us-east",
                "hil": "us-west",
                "sin": "ap-southeast",
            }
            region_endpoints.get(region, "eu-central")
            endpoint_url = f"https://{region}.your-objectstorage.com"

            # Initialize s3fs filesystem for all operations
            fs = s3fs.S3FileSystem(
                key=access_key,
                secret=secret_key,
                endpoint_url=endpoint_url,
                client_kwargs={
                    "region_name": region,
                    "config": boto3.session.Config(
                        signature_version="s3v4", s3={"addressing_style": "path"}
                    ),
                },
            )

            logger.debug("Successfully initialized Hetzner Storage client with s3fs")

            # Initialize base class with configured filesystem
            super().__init__(fs, bucket)
            self.region = region

        except Exception as e:
            logger.error(f"Error initializing Hetzner Storage client: {str(e)}")
            raise ValueError(f"Failed to initialize Hetzner Storage client: {str(e)}")


def get_storage_provider(provider_type: str, **credentials) -> StorageProvider:
    """Factory function to create storage provider instances

    Each provider has different authentication requirements:
    - AWS S3: access_key, secret_key, bucket, region
    - Backblaze B2: application_key_id, application_key, bucket_name
    - Google Cloud: project_id, bucket_name, credentials_json
    - Cloudflare R2: account_id, access_key, secret_key, bucket
    - DigitalOcean: access_key, secret_key, bucket, region
    - Wasabi: access_key, secret_key, bucket, region
    - Hetzner: access_key, secret_key, bucket, region
    """
    providers = {
        "aws": AWSS3Provider,
        "backblaze": BackblazeB2Provider,
        "wasabi": WasabiProvider,
        "gcs": GoogleCloudStorageProvider,
        "digitalocean": DigitalOceanSpacesProvider,
        "cloudflare": CloudflareR2Provider,
        "hetzner": HetznerStorageProvider,
    }

    if provider_type not in providers:
        raise ValueError(f"Unsupported storage provider: {provider_type}")

    return providers[provider_type](**credentials)
