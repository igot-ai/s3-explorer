"""
Unit tests for s3_utils.py
Testing S3 utility functions for AWS S3
"""
import pytest
import io
from unittest.mock import Mock, patch, MagicMock
import s3_utils


# Test data
TEST_FILE_CONTENT = b"test file content for s3_utils"
TEST_FILENAME = "test_file.txt"
TEST_BUCKET = "test-s3-bucket"
TEST_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
TEST_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
TEST_REGION = "us-east-1"


class TestValidateCredentials:
    """Test validate_credentials function"""

    @patch('s3_utils.boto3.client')
    def test_validate_credentials_success(self, mock_boto_client):
        """Test successful credential validation"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock successful head_bucket and list_objects_v2 calls
        mock_s3.head_bucket.return_value = {}
        mock_s3.list_objects_v2.return_value = {'Contents': []}

        result, message = s3_utils.validate_credentials(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)

        assert result is True
        assert "successfully" in message.lower()
        mock_s3.head_bucket.assert_called_once_with(Bucket=TEST_BUCKET)
        mock_s3.list_objects_v2.assert_called_once_with(Bucket=TEST_BUCKET, MaxKeys=1)

    @patch('s3_utils.boto3.client')
    def test_validate_credentials_bucket_not_found(self, mock_boto_client):
        """Test credential validation with non-existent bucket"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        # Mock 404 error for bucket not found
        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': '404'}}
        mock_s3.head_bucket.side_effect = ClientError(error_response, 'HeadBucket')

        result, message = s3_utils.validate_credentials(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)

        assert result is False
        assert "does not exist" in message

    @patch('s3_utils.boto3.client')
    def test_validate_credentials_access_denied(self, mock_boto_client):
        """Test credential validation with access denied"""
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3

        from botocore.exceptions import ClientError
        error_response = {'Error': {'Code': '403'}}
        mock_s3.head_bucket.side_effect = ClientError(error_response, 'HeadBucket')

        result, message = s3_utils.validate_credentials(TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_BUCKET, TEST_REGION)

        assert result is False
        assert "Access denied" in message


class TestUploadFile:
    """Test upload_file function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_upload_file_success(self, mock_config, mock_get_client):
        """Test successful file upload"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET

        file_obj = io.BytesIO(TEST_FILE_CONTENT)
        s3_utils.upload_file(file_obj, TEST_FILENAME)

        mock_s3.upload_fileobj.assert_called_once_with(file_obj, TEST_BUCKET, TEST_FILENAME)

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_upload_file_error(self, mock_config, mock_get_client):
        """Test upload file with error"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_s3.upload_fileobj.side_effect = Exception("Upload failed")

        file_obj = io.BytesIO(TEST_FILE_CONTENT)
        with pytest.raises(Exception, match="Error uploading file"):
            s3_utils.upload_file(file_obj, TEST_FILENAME)


class TestDownloadFile:
    """Test download_file function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_download_file_success(self, mock_config, mock_get_client):
        """Test successful file download"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET

        # Mock the response
        mock_body = io.BytesIO(TEST_FILE_CONTENT)
        mock_s3.get_object.return_value = {'Body': mock_body}

        result = s3_utils.download_file(TEST_FILENAME)

        assert result == mock_body
        mock_s3.get_object.assert_called_once_with(Bucket=TEST_BUCKET, Key=TEST_FILENAME)

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_download_file_error(self, mock_config, mock_get_client):
        """Test download file with error"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_s3.get_object.side_effect = Exception("Download failed")

        with pytest.raises(Exception, match="Error downloading file"):
            s3_utils.download_file(TEST_FILENAME)


class TestDeleteFile:
    """Test delete_file function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_delete_file_success(self, mock_config, mock_get_client):
        """Test successful file deletion"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET

        s3_utils.delete_file(TEST_FILENAME)

        mock_s3.delete_object.assert_called_once_with(Bucket=TEST_BUCKET, Key=TEST_FILENAME)

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_delete_file_error(self, mock_config, mock_get_client):
        """Test delete file with error"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_s3.delete_object.side_effect = Exception("Delete failed")

        with pytest.raises(Exception, match="Error deleting file"):
            s3_utils.delete_file(TEST_FILENAME)


class TestListFilesAndFolders:
    """Test list_files_and_folders function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_list_files_and_folders_success(self, mock_config, mock_get_client):
        """Test successful listing of files and folders"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_config.is_configured.return_value = True

        # Mock paginator
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'file1.txt', 'Size': 100},
                    {'Key': 'file2.pdf', 'Size': 200},
                    {'Key': 'folder/', 'Size': 0}
                ],
                'CommonPrefixes': [
                    {'Prefix': 'documents/'}
                ]
            }
        ]

        files, folders = s3_utils.list_files_and_folders()

        assert len(files) == 2  # Only non-folders
        assert files[0]['name'] == 'file1.txt'
        assert files[0]['size'] == 100
        assert 'folder/' in folders
        assert 'documents/' in folders

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_list_files_with_prefix(self, mock_config, mock_get_client):
        """Test listing files with prefix filter"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_config.is_configured.return_value = True

        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{'Contents': [{'Key': 'docs/file.txt', 'Size': 100}]}]

        files, folders = s3_utils.list_files_and_folders(prefix='docs/')

        mock_paginator.paginate.assert_called_once_with(Bucket=TEST_BUCKET, Prefix='docs/')

    @patch('s3_utils.s3_config')
    def test_list_files_not_configured(self, mock_config):
        """Test listing files when S3 is not configured"""
        mock_config.is_configured.return_value = False

        files, folders = s3_utils.list_files_and_folders()

        assert files == []
        assert folders == []

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_list_files_with_min_size_filter(self, mock_config, mock_get_client):
        """Test listing files with minimum size filter"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_config.is_configured.return_value = True

        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'small.txt', 'Size': 50},
                    {'Key': 'large.txt', 'Size': 1000}
                ]
            }
        ]

        files, folders = s3_utils.list_files_and_folders(min_file_size=100)

        assert len(files) == 1
        assert files[0]['name'] == 'large.txt'


class TestGetFileUrl:
    """Test get_file_url function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_get_file_url_success(self, mock_config, mock_get_client):
        """Test successful presigned URL generation"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET
        mock_s3.generate_presigned_url.return_value = 'https://test-url.com/file'

        url = s3_utils.get_file_url(TEST_FILENAME)

        assert url == 'https://test-url.com/file'
        mock_s3.generate_presigned_url.assert_called_once()


class TestCreateFolder:
    """Test create_folder function"""

    @patch('s3_utils.get_s3_client')
    @patch('s3_utils.s3_config')
    def test_create_folder_success(self, mock_config, mock_get_client):
        """Test successful folder creation"""
        mock_s3 = Mock()
        mock_get_client.return_value = mock_s3
        mock_config.s3_bucket = TEST_BUCKET

        folder_name = "my-folder"
        s3_utils.create_folder(folder_name)

        # S3 folders are created by uploading an empty object with trailing slash
        call_args = mock_s3.put_object.call_args
        assert call_args[1]['Bucket'] == TEST_BUCKET
        assert call_args[1]['Key'].endswith('/')


class TestIsS3Configured:
    """Test is_s3_configured function"""

    @patch('s3_utils.s3_config')
    def test_is_configured_true(self, mock_config):
        """Test when S3 is configured"""
        mock_config.is_configured.return_value = True

        result = s3_utils.is_s3_configured()

        assert result is True

    @patch('s3_utils.s3_config')
    def test_is_configured_false(self, mock_config):
        """Test when S3 is not configured"""
        mock_config.is_configured.return_value = False

        result = s3_utils.is_s3_configured()

        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
