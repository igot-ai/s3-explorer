import boto3
import s3fs
import io
from botocore.exceptions import ClientError, NoCredentialsError
import logging
from dataclasses import dataclass
from typing import Optional, BinaryIO

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class S3Config:
    """Configuration for S3 connection"""
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str
    s3_bucket: str

    def is_configured(self) -> bool:
        return all([
            self.aws_access_key_id,
            self.aws_secret_access_key,
            self.aws_region,
            self.s3_bucket
        ])


def validate_credentials(access_key: str, secret_key: str, bucket: str, region: str) -> tuple[bool, str]:
    """Validate AWS credentials and bucket access"""
    try:
        temp_client = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Test bucket access
        try:
            temp_client.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '403':
                return False, "Access denied. Please check if you have sufficient permissions for this bucket."
            elif error_code == '404':
                return False, f"Bucket '{bucket}' does not exist."
            else:
                return False, f"Error accessing bucket: {str(e)}"
                
        # Test list objects permission
        try:
            temp_client.list_objects_v2(Bucket=bucket, MaxKeys=1)
        except ClientError:
            return False, "The provided credentials don't have permission to list bucket contents."
            
        return True, "Credentials validated successfully"
        
    except NoCredentialsError:
        return False, "Invalid AWS credentials"
    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return False, f"Error validating credentials: {str(e)}"


class S3Client:
    """Reusable S3 client with injected configuration"""
    
    def __init__(self, config: S3Config):
        self.config = config
        self._fs: Optional[s3fs.S3FileSystem] = None
        self._client = None
    
    def _get_filesystem(self) -> s3fs.S3FileSystem:
        """Get or create an s3fs filesystem"""
        if self._fs is None:
            try:
                self._fs = s3fs.S3FileSystem(
                    key=self.config.aws_access_key_id,
                    secret=self.config.aws_secret_access_key,
                    client_kwargs={'region_name': self.config.aws_region}
                )
            except Exception as e:
                logger.error(f"Error creating S3 filesystem: {str(e)}")
                raise Exception(f"Error creating S3 filesystem: {str(e)}")
        return self._fs
    
    def _get_boto_client(self):
        """Get or create a boto3 S3 client"""
        if self._client is None:
            try:
                self._client = boto3.client(
                    's3',
                    aws_access_key_id=self.config.aws_access_key_id,
                    aws_secret_access_key=self.config.aws_secret_access_key,
                    region_name=self.config.aws_region
                )
            except Exception as e:
                logger.error(f"Error creating S3 client: {str(e)}")
                raise Exception(f"Error creating S3 client: {str(e)}")
        return self._client
    
    def is_configured(self) -> bool:
        """Check if S3 is properly configured"""
        return self.config.is_configured()
    
    def upload_file(self, file_obj: BinaryIO, filename: str) -> None:
        """Upload a file to S3 using s3fs"""
        try:
            fs = self._get_filesystem()
            s3_path = f'{self.config.s3_bucket}/{filename}'
            with fs.open(s3_path, 'wb') as f:
                f.write(file_obj.read())
            logger.info(f"Successfully uploaded file {filename}")
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise Exception(f"Error uploading file: {str(e)}")
    
    def download_file(self, filename: str) -> io.BytesIO:
        """Download a file from S3 using s3fs"""
        try:
            fs = self._get_filesystem()
            s3_path = f'{self.config.s3_bucket}/{filename}'
            with fs.open(s3_path, 'rb') as f:
                return io.BytesIO(f.read())
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            raise Exception(f"Error downloading file: {str(e)}")
    
    def delete_file(self, filename: str) -> None:
        """Delete a file from S3 using s3fs"""
        try:
            fs = self._get_filesystem()
            s3_path = f'{self.config.s3_bucket}/{filename}'
            fs.rm(s3_path)
            logger.info(f"File {filename} deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            raise Exception(f"Error deleting file: {str(e)}")
    
    def list_files_and_folders(self, prefix: str = '', min_file_size: int = 0) -> tuple[list, list]:
        """List files and folders in the S3 bucket using s3fs"""
        if not self.is_configured():
            logger.warning("Attempted to list files but S3 is not configured")
            return [], []

        if not self.config.s3_bucket:
            logger.error("S3 bucket name is empty")
            raise ValueError("S3 bucket name is not configured")

        try:
            fs = self._get_filesystem()
            s3_prefix = f'{self.config.s3_bucket}/{prefix}' if prefix else self.config.s3_bucket
            files = []
            folders = set()

            try:
                for item in fs.ls(s3_prefix, detail=True):
                    size = item.get('Size', item.get('size', 0))
                    key = item.get('Key', item.get('name', ''))

                    # Remove bucket prefix from key
                    if key.startswith(f'{self.config.s3_bucket}/'):
                        key = key[len(f'{self.config.s3_bucket}/'):]

                    # Check if it's a folder or file
                    if item.get('type') == 'directory' or key.endswith('/'):
                        folders.add(key)
                    elif size >= min_file_size:
                        files.append({
                            'name': key,
                            'size': size
                        })
            except FileNotFoundError:
                # Prefix doesn't exist, return empty lists
                pass

            logger.info(f"Successfully listed files and folders from the S3 bucket with prefix: {prefix}")
            return files, sorted(list(folders))
        except Exception as e:
            logger.error(f"Error listing files and folders: {str(e)}")
            raise
    
    def get_file_url(self, filename: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for file preview"""
        try:
            s3_client = self._get_boto_client()
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.config.s3_bucket,
                    'Key': filename
                },
                ExpiresIn=expires_in
            )
            logger.info(f"Preview URL generated for file {filename}.")
            return url
        except Exception as e:
            logger.error(f"Error generating preview URL: {str(e)}")
            raise Exception(f"Error generating preview URL: {str(e)}")
    
    def create_folder(self, folder_name: str) -> None:
        """Create a new folder in S3 using s3fs"""
        if not folder_name.endswith('/'):
            folder_name += '/'
        try:
            fs = self._get_filesystem()
            s3_path = f'{self.config.s3_bucket}/{folder_name}'
            # Use touch to create an empty object representing the folder
            fs.touch(s3_path)
            logger.info(f"Folder {folder_name} created successfully.")
        except Exception as e:
            logger.error(f"Error creating folder: {str(e)}")
            raise Exception(f"Error creating folder: {str(e)}")
    
    def delete_folder(self, folder_name: str) -> None:
        """Delete a folder and its contents from S3 using s3fs"""
        if not folder_name.endswith('/'):
            folder_name += '/'
        try:
            fs = self._get_filesystem()
            s3_path = f'{self.config.s3_bucket}/{folder_name}'

            # List and delete all objects within the folder
            try:
                files_to_delete = fs.glob(f'{s3_path}**')
                if files_to_delete:
                    fs.rm(files_to_delete, recursive=True)
            except FileNotFoundError:
                pass

            # Delete the folder itself
            try:
                fs.rm(s3_path)
            except FileNotFoundError:
                pass

            logger.info(f"Folder {folder_name} deleted successfully.")
        except Exception as e:
            logger.error(f"Error deleting folder: {str(e)}")
            raise Exception(f"Error deleting folder: {str(e)}")