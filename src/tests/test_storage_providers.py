"""
Unit tests for storage_providers.py
Testing all S3-compatible providers: AWS, Wasabi, Cloudflare R2, DigitalOcean, Hetzner
"""
import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from s3_explore.services.storage_providers import (
    AWSS3Provider,
    WasabiProvider,
    CloudflareR2Provider,
    DigitalOceanSpacesProvider,
    HetznerStorageProvider,
    BackblazeB2Provider,
    GoogleCloudStorageProvider,
    get_storage_provider
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

    @patch('shared.storage.boto3.client')
    def test_init(self, mock_boto_client):
        """Test AWS provider initialization"""
        provider = AWSS3Provider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION
        )

        assert provider.bucket == TEST_BUCKET
        mock_boto_client.assert_called_once_with(
            's3',
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY,
            region_name=TEST_REGION
        )

    @patch('shared.storage.boto3.client')
    def test_upload_file(self, mock_boto_client):
        """Test file upload"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        file_obj = io.BytesIO(TEST_FILE_CONTENT)

        provider.upload_file(file_obj, TEST_FILENAME)

        mock_s3.upload_fileobj.assert_called_once()
        call_args = mock_s3.upload_fileobj.call_args
        assert call_args[0][1] == TEST_BUCKET
        assert call_args[0][2] == TEST_FILENAME

    @patch('shared.storage.boto3.client')
    def test_download_file(self, mock_boto_client):
        """Test file download"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock the download_fileobj to write test content
        def mock_download(bucket, key, file_obj):
            file_obj.write(TEST_FILE_CONTENT)

        mock_s3.download_fileobj.side_effect = mock_download

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        result = provider.download_file(TEST_FILENAME)

        assert isinstance(result, io.BytesIO)
        assert result.read() == TEST_FILE_CONTENT
        mock_s3.download_fileobj.assert_called_once_with(TEST_BUCKET, TEST_FILENAME, result)

    @patch('shared.storage.boto3.client')
    def test_list_files(self, mock_boto_client):
        """Test listing files"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock paginator
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'file1.txt', 'Size': 100},
                    {'Key': 'file2.txt', 'Size': 200},
                ]
            }
        ]

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        files = provider.list_files()

        assert len(files) == 2
        assert files[0]['name'] == 'file1.txt'
        assert files[0]['size'] == 100
        assert files[1]['name'] == 'file2.txt'
        assert files[1]['size'] == 200

    @patch('shared.storage.boto3.client')
    def test_list_files_with_prefix(self, mock_boto_client):
        """Test listing files with prefix"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{'Contents': []}]

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        provider.list_files(prefix='folder/')

        mock_paginator.paginate.assert_called_once_with(Bucket=TEST_BUCKET, Prefix='folder/')

    @patch('shared.storage.boto3.client')
    def test_delete_file(self, mock_boto_client):
        """Test file deletion"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        provider.delete_file(TEST_FILENAME)

        mock_s3.delete_object.assert_called_once_with(Bucket=TEST_BUCKET, Key=TEST_FILENAME)

    @patch('shared.storage.boto3.client')
    def test_get_file_url(self, mock_boto_client):
        """Test presigned URL generation"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = 'https://test-url.com/file'

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        url = provider.get_file_url(TEST_FILENAME, expires_in=3600)

        assert url == 'https://test-url.com/file'
        mock_s3.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': TEST_BUCKET, 'Key': TEST_FILENAME},
            ExpiresIn=3600
        )


class TestWasabiProvider:
    """Test Wasabi Provider"""

    @patch('shared.storage.boto3.client')
    def test_init_with_correct_endpoint(self, mock_boto_client):
        """Test Wasabi provider initialization with correct endpoint"""
        provider = WasabiProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region='us-west-1'
        )

        assert provider.bucket == TEST_BUCKET
        mock_boto_client.assert_called_once_with(
            's3',
            endpoint_url='https://s3.us-west-1.wasabisys.com',
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY
        )

    @patch('shared.storage.boto3.client')
    def test_upload_file(self, mock_boto_client):
        """Test Wasabi file upload"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = WasabiProvider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        file_obj = io.BytesIO(TEST_FILE_CONTENT)

        provider.upload_file(file_obj, TEST_FILENAME)

        mock_s3.upload_fileobj.assert_called_once()


class TestCloudflareR2Provider:
    """Test Cloudflare R2 Provider"""

    @patch('shared.storage.boto3.client')
    def test_init_with_account_id(self, mock_boto_client):
        """Test Cloudflare R2 provider initialization"""
        provider = CloudflareR2Provider(
            account_id=TEST_ACCOUNT_ID,
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET
        )

        assert provider.bucket == TEST_BUCKET
        assert provider.account_id == TEST_ACCOUNT_ID
        mock_boto_client.assert_called_once_with(
            's3',
            endpoint_url=f'https://{TEST_ACCOUNT_ID}.r2.cloudflarestorage.com',
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY
        )

    @patch('shared.storage.boto3.client')
    def test_upload_and_download(self, mock_boto_client):
        """Test Cloudflare R2 upload and download"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = CloudflareR2Provider(TEST_ACCOUNT_ID, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET)

        # Test upload
        file_obj = io.BytesIO(TEST_FILE_CONTENT)
        provider.upload_file(file_obj, TEST_FILENAME)
        mock_s3.upload_fileobj.assert_called_once()

        # Test download
        def mock_download(bucket, key, file_obj):
            file_obj.write(TEST_FILE_CONTENT)

        mock_s3.download_fileobj.side_effect = mock_download
        result = provider.download_file(TEST_FILENAME)
        assert result.read() == TEST_FILE_CONTENT


class TestDigitalOceanProvider:
    """Test DigitalOcean Spaces Provider"""

    @patch('shared.storage.boto3.client')
    def test_init_with_correct_endpoint(self, mock_boto_client):
        """Test DigitalOcean provider initialization"""
        provider = DigitalOceanSpacesProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region='nyc3'
        )

        assert provider.bucket == TEST_BUCKET
        mock_boto_client.assert_called_once_with(
            's3',
            endpoint_url='https://nyc3.digitaloceanspaces.com',
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY
        )

    @patch('shared.storage.boto3.client')
    def test_all_operations(self, mock_boto_client):
        """Test all DigitalOcean operations"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{'Contents': [{'Key': 'file.txt', 'Size': 100}]}]

        provider = DigitalOceanSpacesProvider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, 'nyc3')

        # Upload
        provider.upload_file(io.BytesIO(TEST_FILE_CONTENT), TEST_FILENAME)
        mock_s3.upload_fileobj.assert_called_once()

        # List
        files = provider.list_files()
        assert len(files) == 1

        # Delete
        provider.delete_file(TEST_FILENAME)
        mock_s3.delete_object.assert_called_once()


class TestHetznerProvider:
    """Test Hetzner Storage Provider"""

    @patch('shared.storage.boto3.client')
    def test_init_with_correct_endpoint(self, mock_boto_client):
        """Test Hetzner provider initialization"""
        provider = HetznerStorageProvider(
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region='nbg1'
        )

        assert provider.bucket == TEST_BUCKET
        mock_boto_client.assert_called_once_with(
            's3',
            endpoint_url='https://nbg1.your-objectstorage.com',
            aws_access_key_id=TEST_ACCESS_KEY,
            aws_secret_access_key=TEST_SECRET_KEY
        )

    @patch('shared.storage.boto3.client')
    def test_presigned_url(self, mock_boto_client):
        """Test Hetzner presigned URL generation"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        mock_s3.generate_presigned_url.return_value = 'https://hetzner-url.com/file'

        provider = HetznerStorageProvider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, 'nbg1')
        url = provider.get_file_url(TEST_FILENAME, expires_in=7200)

        assert url == 'https://hetzner-url.com/file'
        mock_s3.generate_presigned_url.assert_called_once()


class TestProviderFactory:
    """Test get_storage_provider factory function"""

    @patch('shared.storage.boto3.client')
    def test_get_aws_provider(self, mock_boto_client):
        """Test factory creates AWS provider"""
        provider = get_storage_provider(
            'aws',
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION
        )
        assert isinstance(provider, AWSS3Provider)

    @patch('shared.storage.boto3.client')
    def test_get_wasabi_provider(self, mock_boto_client):
        """Test factory creates Wasabi provider"""
        provider = get_storage_provider(
            'wasabi',
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION
        )
        assert isinstance(provider, WasabiProvider)

    @patch('shared.storage.boto3.client')
    def test_get_cloudflare_provider(self, mock_boto_client):
        """Test factory creates Cloudflare R2 provider"""
        provider = get_storage_provider(
            'cloudflare',
            account_id=TEST_ACCOUNT_ID,
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET
        )
        assert isinstance(provider, CloudflareR2Provider)

    @patch('shared.storage.boto3.client')
    def test_get_digitalocean_provider(self, mock_boto_client):
        """Test factory creates DigitalOcean provider"""
        provider = get_storage_provider(
            'digitalocean',
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION
        )
        assert isinstance(provider, DigitalOceanSpacesProvider)

    @patch('shared.storage.boto3.client')
    def test_get_hetzner_provider(self, mock_boto_client):
        """Test factory creates Hetzner provider"""
        provider = get_storage_provider(
            'hetzner',
            access_key=TEST_ACCESS_KEY,
            secret_key=TEST_SECRET_KEY,
            bucket=TEST_BUCKET,
            region=TEST_REGION
        )
        assert isinstance(provider, HetznerStorageProvider)

    def test_invalid_provider_type(self):
        """Test factory raises error for invalid provider"""
        with pytest.raises(ValueError, match="Unknown storage provider"):
            get_storage_provider('invalid_provider')


class TestEdgeCases:
    """Test edge cases and error handling"""

    @patch('shared.storage.boto3.client')
    def test_empty_file_upload(self, mock_boto_client):
        """Test uploading empty file"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        empty_file = io.BytesIO(b"")

        provider.upload_file(empty_file, "empty.txt")
        mock_s3.upload_fileobj.assert_called_once()

    @patch('shared.storage.boto3.client')
    def test_list_files_empty_bucket(self, mock_boto_client):
        """Test listing files in empty bucket"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No Contents key

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        files = provider.list_files()

        assert files == []

    @patch('shared.storage.boto3.client')
    def test_large_file_handling(self, mock_boto_client):
        """Test handling large files"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        provider = AWSS3Provider(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        large_file = io.BytesIO(large_content)

        provider.upload_file(large_file, "large_file.bin")
        mock_s3.upload_fileobj.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
