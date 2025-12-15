from config import s3_config
import boto3
import s3fs
import io
from botocore.exceptions import ClientError, NoCredentialsError
from _logging import get_logger

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)

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

def get_s3_filesystem():
    """Get an s3fs filesystem using the current configuration"""
    from config import s3_config  # Import here to avoid circular import
    try:
        fs = s3fs.S3FileSystem(
            key=s3_config.aws_access_key_id,
            secret=s3_config.aws_secret_access_key,
            client_kwargs={'region_name': s3_config.aws_region}
        )
        return fs
    except Exception as e:
        logger.error(f"Error creating S3 filesystem: {str(e)}")
        raise Exception(f"Error creating S3 filesystem: {str(e)}")

def get_s3_client():
    """Get an S3 client using the current configuration (for presigned URLs)"""
    from config import s3_config  # Import here to avoid circular import
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=s3_config.aws_access_key_id,
            aws_secret_access_key=s3_config.aws_secret_access_key,
            region_name=s3_config.aws_region
        )
        return s3_client
    except Exception as e:
        logger.error(f"Error creating S3 client: {str(e)}")
        raise Exception(f"Error creating S3 client: {str(e)}")

def upload_file(file_obj, filename: str) -> None:
    """Upload a file to S3 using s3fs"""
    from config import s3_config  # Import here to avoid circular import
    try:
        fs = get_s3_filesystem()
        s3_path = f'{s3_config.s3_bucket}/{filename}'
        with fs.open(s3_path, 'wb') as f:
            f.write(file_obj.read())
        logger.info(f"Successfully uploaded file {filename}")
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise Exception(f"Error uploading file: {str(e)}")

def download_file(filename: str):
    """Download a file from S3 using s3fs"""
    from config import s3_config  # Import here to avoid circular import
    try:
        fs = get_s3_filesystem()
        s3_path = f'{s3_config.s3_bucket}/{filename}'
        with fs.open(s3_path, 'rb') as f:
            return io.BytesIO(f.read())
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise Exception(f"Error downloading file: {str(e)}")

def delete_file(filename: str) -> None:
    """Delete a file from S3 using s3fs"""
    from config import s3_config  # Import here to avoid circular import
    try:
        fs = get_s3_filesystem()
        s3_path = f'{s3_config.s3_bucket}/{filename}'
        fs.rm(s3_path)
        logger.info(f"File {filename} deleted successfully.")
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise Exception(f"Error deleting file: {str(e)}")

def is_s3_configured() -> bool:
    """Check if S3 is properly configured"""
    return s3_config.is_configured()

def list_files_and_folders(prefix: str = '', min_file_size: int = 0):
    """List files and folders in the S3 bucket using s3fs"""
    if not is_s3_configured():
        logger.warning("Attempted to list files but S3 is not configured")
        return [], []

    if not s3_config.s3_bucket:
        logger.error("S3 bucket name is empty")
        raise ValueError("S3 bucket name is not configured")

    try:
        fs = get_s3_filesystem()
        s3_prefix = f'{s3_config.s3_bucket}/{prefix}' if prefix else s3_config.s3_bucket
        files = []
        folders = set()

        try:
            for item in fs.ls(s3_prefix, detail=True):
                size = item.get('Size', item.get('size', 0))
                key = item.get('Key', item.get('name', ''))

                # Remove bucket prefix from key
                if key.startswith(f'{s3_config.s3_bucket}/'):
                    key = key[len(f'{s3_config.s3_bucket}/'):]

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

def get_file_url(filename: str) -> str:
    """Generate a pre-signed URL for file preview"""
    from config import s3_config  # Import here to avoid circular import
    try:
        s3_client = get_s3_client()
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': s3_config.s3_bucket,
                'Key': filename
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )
        logger.info(f"Preview URL generated for file {filename}.")
        return url
    except Exception as e:
        logger.error(f"Error generating preview URL: {str(e)}")
        raise Exception(f"Error generating preview URL: {str(e)}")

def create_folder(folder_name: str) -> None:
    """Create a new folder in S3 using s3fs"""
    from config import s3_config  # Import here to avoid circular import
    if not folder_name.endswith('/'):
        folder_name += '/'
    try:
        fs = get_s3_filesystem()
        s3_path = f'{s3_config.s3_bucket}/{folder_name}'
        # Use touch to create an empty object representing the folder
        fs.touch(s3_path)
        logger.info(f"Folder {folder_name} created successfully.")
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        raise Exception(f"Error creating folder: {str(e)}")

def delete_folder(folder_name: str) -> None:
    """Delete a folder and its contents from S3 using s3fs"""
    from config import s3_config  # Import here to avoid circular import
    if not folder_name.endswith('/'):
        folder_name += '/'
    try:
        fs = get_s3_filesystem()
        s3_path = f'{s3_config.s3_bucket}/{folder_name}'

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
