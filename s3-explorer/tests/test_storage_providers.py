"""Unit tests for shared storage providers.

These providers live in `dataroutine/shared/storage.py`.
"""

import io
from unittest.mock import Mock, patch

import pytest
from dataroutine.shared.storage import (
    AWSS3Provider,
    CloudflareR2Provider,
    DigitalOceanSpacesProvider,
    HetznerStorageProvider,
    WasabiProvider,
    get_storage_provider,
)

# Test data
TEST_FILE_CONTENT = b"test file content"
TEST_FILENAME = "test_file.txt"
TEST_BUCKET = "test-bucket"
TEST_ACCESS_KEY = "test-access-key"
TEST_SECRET_KEY = "test-secret-key"
TEST_REGION = "us-east-1"
TEST_ACCOUNT_ID = "test-account-123"


class TestAWSProvider:
    """Test AWS S3 Provider"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_init(self, mock_s3fs_cls):
        """Test AWS provider initialization"""
        provider = AWSS3Provider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION,
        )

        assert provider.bucket == TEST_BUCKET
        mock_s3fs_cls.assert_called_once_with(
            key=TEST_ACCESS_KEY,
            secret=TEST_SECRET_KEY,
            client_kwargs={"region_name": TEST_REGION},
        )

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_upload_file(self, mock_s3fs_cls):
        """Test file upload"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        file_obj = io.BytesIO(TEST_FILE_CONTENT)

        mock_writer = Mock()
        mock_cm = Mock()
        mock_cm.__enter__ = Mock(return_value=mock_writer)
        mock_cm.__exit__ = Mock(return_value=False)
        mock_fs.open.return_value = mock_cm

        provider.upload_file(file_obj, TEST_FILENAME)

        mock_fs.open.assert_called_once_with(f"{TEST_BUCKET}/{TEST_FILENAME}", "wb")
        mock_writer.write.assert_called_once_with(TEST_FILE_CONTENT)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_download_file(self, mock_s3fs_cls):
        """Test file download"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )

        mock_reader = Mock()
        mock_reader.read.return_value = TEST_FILE_CONTENT
        mock_cm = Mock()
        mock_cm.__enter__ = Mock(return_value=mock_reader)
        mock_cm.__exit__ = Mock(return_value=False)
        mock_fs.open.return_value = mock_cm

        result = provider.download_file(TEST_FILENAME)

        assert isinstance(result, io.BytesIO)
        assert result.read() == TEST_FILE_CONTENT
        mock_fs.open.assert_called_once_with(f"{TEST_BUCKET}/{TEST_FILENAME}", "rb")

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_list_files(self, mock_s3fs_cls):
        """Test listing files"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs
        mock_fs.ls.return_value = [
            {"type": "file", "Key": f"{TEST_BUCKET}/file1.txt", "Size": 100},
            {"type": "file", "Key": f"{TEST_BUCKET}/file2.txt", "Size": 200},
        ]

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        files = provider.list_files()

        assert len(files) == 2
        assert files[0]["name"] == "file1.txt"
        assert files[0]["size"] == 100
        assert files[1]["name"] == "file2.txt"
        assert files[1]["size"] == 200

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_list_files_with_prefix(self, mock_s3fs_cls):
        """Test listing files with prefix"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs
        mock_fs.ls.return_value = []

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        provider.list_files(prefix="folder/")

        mock_fs.ls.assert_called_once_with(f"{TEST_BUCKET}/folder/", detail=True)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_delete_file(self, mock_s3fs_cls):
        """Test file deletion"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        provider.delete_file(TEST_FILENAME)

        mock_fs.rm.assert_called_once_with(f"{TEST_BUCKET}/{TEST_FILENAME}")

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_file_url(self, mock_s3fs_cls):
        """Test presigned URL generation"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs
        mock_fs.sign.return_value = "https://test-url.com/file"

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        url = provider.get_file_url(TEST_FILENAME, expires_in=3600)

        assert url == "https://test-url.com/file"
        mock_fs.sign.assert_called_once_with(
            f"{TEST_BUCKET}/{TEST_FILENAME}", expiration=3600
        )


class TestWasabiProvider:
    """Test Wasabi Provider"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_init_with_correct_endpoint(self, mock_s3fs_cls):
        """Test Wasabi provider initialization with correct endpoint"""
        provider = WasabiProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region="us-west-1",
        )

        assert provider.bucket == TEST_BUCKET
        mock_s3fs_cls.assert_called_once()

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_upload_file(self, mock_s3fs_cls):
        """Test Wasabi file upload (delegates to base implementation)."""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = WasabiProvider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        file_obj = io.BytesIO(TEST_FILE_CONTENT)

        mock_writer = Mock()
        mock_cm = Mock()
        mock_cm.__enter__ = Mock(return_value=mock_writer)
        mock_cm.__exit__ = Mock(return_value=False)
        mock_fs.open.return_value = mock_cm

        provider.upload_file(file_obj, TEST_FILENAME)

        mock_fs.open.assert_called_once_with(f"{TEST_BUCKET}/{TEST_FILENAME}", "wb")


class TestCloudflareR2Provider:
    """Test Cloudflare R2 Provider"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_init_with_account_id(self, mock_s3fs_cls):
        """Test Cloudflare R2 provider initialization"""
        provider = CloudflareR2Provider(
            account_id=TEST_ACCOUNT_ID,
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
        )

        assert provider.bucket == TEST_BUCKET
        assert provider.account_id == TEST_ACCOUNT_ID
        mock_s3fs_cls.assert_called_once()


class TestDigitalOceanProvider:
    """Test DigitalOcean Spaces Provider"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_init_with_correct_endpoint(self, mock_s3fs_cls):
        """Test DigitalOcean provider initialization"""
        provider = DigitalOceanSpacesProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region="nyc3",
        )

        assert provider.bucket == TEST_BUCKET
        mock_s3fs_cls.assert_called_once()


class TestHetznerProvider:
    """Test Hetzner Storage Provider"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_init_with_correct_endpoint(self, mock_s3fs_cls):
        """Test Hetzner provider initialization"""
        provider = HetznerStorageProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region="nbg1",
        )

        assert provider.bucket == TEST_BUCKET
        mock_s3fs_cls.assert_called_once()


class TestProviderFactory:
    """Test get_storage_provider factory function"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_aws_provider(self, _mock_s3fs_cls):
        """Test factory creates AWS provider"""
        provider = get_storage_provider(
            "aws",
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION,
        )
        assert isinstance(provider, AWSS3Provider)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_wasabi_provider(self, _mock_s3fs_cls):
        """Test factory creates Wasabi provider"""
        provider = get_storage_provider(
            "wasabi",
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION,
        )
        assert isinstance(provider, WasabiProvider)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_cloudflare_provider(self, _mock_s3fs_cls):
        """Test factory creates Cloudflare R2 provider"""
        provider = get_storage_provider(
            "cloudflare",
            account_id=TEST_ACCOUNT_ID,
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
        )
        assert isinstance(provider, CloudflareR2Provider)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_digitalocean_provider(self, _mock_s3fs_cls):
        """Test factory creates DigitalOcean provider"""
        provider = get_storage_provider(
            "digitalocean",
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION,
        )
        assert isinstance(provider, DigitalOceanSpacesProvider)

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_get_hetzner_provider(self, _mock_s3fs_cls):
        """Test factory creates Hetzner provider"""
        provider = get_storage_provider(
            "hetzner",
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION,
        )
        assert isinstance(provider, HetznerStorageProvider)

    def test_invalid_provider_type(self):
        """Test factory raises error for invalid provider"""
        with pytest.raises(ValueError, match="Unsupported storage provider"):
            get_storage_provider("invalid_provider")


class TestEdgeCases:
    """Test edge cases and error handling"""

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_empty_file_upload(self, mock_s3fs_cls):
        """Test uploading empty file"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        empty_file = io.BytesIO(b"")

        mock_writer = Mock()
        mock_cm = Mock()
        mock_cm.__enter__ = Mock(return_value=mock_writer)
        mock_cm.__exit__ = Mock(return_value=False)
        mock_fs.open.return_value = mock_cm

        provider.upload_file(empty_file, "empty.txt")

        mock_fs.open.assert_called_once_with(f"{TEST_BUCKET}/empty.txt", "wb")
        mock_writer.write.assert_called_once_with(b"")

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_list_files_empty_bucket(self, mock_s3fs_cls):
        """Test listing files in empty bucket"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs
        mock_fs.ls.side_effect = FileNotFoundError()

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        files = provider.list_files()

        assert files == []

    @patch("dataroutine.shared.storage.s3fs.S3FileSystem")
    def test_large_file_handling(self, mock_s3fs_cls):
        """Test handling large files"""
        mock_fs = Mock()
        mock_s3fs_cls.return_value = mock_fs

        provider = AWSS3Provider(
            TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION
        )
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        large_file = io.BytesIO(large_content)

        mock_writer = Mock()
        mock_cm = Mock()
        mock_cm.__enter__ = Mock(return_value=mock_writer)
        mock_cm.__exit__ = Mock(return_value=False)
        mock_fs.open.return_value = mock_cm

        provider.upload_file(large_file, "large_file.bin")

        mock_fs.open.assert_called_once_with(f"{TEST_BUCKET}/large_file.bin", "wb")
        mock_writer.write.assert_called_once_with(large_content)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
