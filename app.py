import os
import logging
from flask import Flask, render_template, request, jsonify, send_file, Response, abort, redirect, url_for, session, g, make_response
from werkzeug.utils import secure_filename
from storage_providers import get_storage_provider
import mimetypes
import boto3
from botocore.exceptions import ClientError
from functools import wraps
import secrets
import json
from flask_wtf.csrf import CSRFProtect, generate_csrf
import re
from ingestion.routers import ingestion_bp

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024 * 1024  # 1 TB
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens
app.config['WTF_CSRF_SSL_STRICT'] = False  # Disable SSL-only for CSRF cookies
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_METHODS'] = ['POST', 'PUT', 'PATCH', 'DELETE']
app.config['WTF_CSRF_CHECK_DEFAULT'] = False  # Disable default CSRF checking

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Register blueprints
app.register_blueprint(ingestion_bp)
csrf.exempt(ingestion_bp)

@app.before_request
def before_request():
    if not request.is_secure and not app.debug:
        url = request.url.replace('http://', 'https://', 1)
        code = 301
        return redirect(url, code=code)

@app.after_request
def after_request(response):
    # Ensure CSRF token is set in cookie and header
    if not request.path.startswith('/static/'):
        csrf_token = generate_csrf()
        response.set_cookie('csrf_token', csrf_token, samesite='Strict')
        response.headers['X-CSRF-Token'] = csrf_token
    return response

@app.route('/get-csrf-token')
def get_csrf_token():
    token = generate_csrf()
    response = make_response(jsonify({'csrf_token': token}))
    response.set_cookie('csrf_token', token, samesite='Strict')
    return response

# Set up logging
logger = logging.getLogger(__name__)

CHUNK_SIZE = 100 * 1024 * 1024  # 100 MB chunks

# Update MIME type detection
mimetypes.init()
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/heic', '.heic')
mimetypes.add_type('image/heif', '.heif')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('configure_storage'))
        return f(*args, **kwargs)
    return decorated_function

def get_current_provider():
    """Get the current storage provider based on session configuration"""
    if 'provider_type' not in session:
        return None
        
    try:
        return get_storage_provider(
            session['provider_type'],
            **session['provider_config']
        )
    except Exception as e:
        logger.error(f"Error creating storage provider: {str(e)}")
        return None

@app.route('/')
@login_required
def index():
    provider = get_current_provider()
    if not provider:
        return redirect(url_for('configure_storage'))
    return render_template('index.html')

@csrf.exempt
@app.route('/configure', methods=['GET', 'POST'])
def configure_storage():
    if request.method == 'POST':
        # Verify CSRF token manually
        token = request.form.get('csrf_token')
        if not token or token != request.cookies.get('csrf_token'):
            logger.error(f"CSRF token mismatch. Form token: {token}, Cookie token: {request.cookies.get('csrf_token')}")
            return jsonify({'error': 'Invalid CSRF token'}), 400
            
        provider_type = request.form.get('provider_type')
        logger.debug(f"Received configuration request for provider: {provider_type}")
        logger.debug(f"Form data: {request.form}")
        
        try:
            if provider_type == 'cloudflare':
                account_id = request.form.get('account_id', '').strip()
                access_key = request.form.get('access_key', '').strip()
                secret_key = request.form.get('secret_key', '').strip()
                bucket = request.form.get('bucket', '').strip()

                logger.debug(f"Cloudflare configuration - Account ID: {account_id}, Bucket: {bucket}")

                if not account_id:
                    return jsonify({'error': 'Account ID is required'}), 400
                if not access_key:
                    return jsonify({'error': 'Access Key ID is required'}), 400
                if not secret_key:
                    return jsonify({'error': 'Secret Access Key is required'}), 400
                if not bucket:
                    return jsonify({'error': 'Bucket name is required'}), 400
                if not re.match(r'^[a-zA-Z0-9.\-_]{3,63}$', bucket):
                    return jsonify({'error': 'Invalid bucket name format'}), 400

                credentials = {
                    'account_id': account_id,
                    'access_key': access_key,
                    'secret_key': secret_key,
                    'bucket': bucket
                }
            elif provider_type in ['aws', 'wasabi']:
                credentials = {
                    'access_key': request.form.get('access_key'),
                    'secret_key': request.form.get('secret_key'),
                    'bucket': request.form.get('bucket'),
                    'region': request.form.get('region', 'us-east-1')
                }
            elif provider_type == 'backblaze':
                key_id = request.form.get('key_id', '').strip()
                application_key = request.form.get('application_key', '').strip()
                bucket_name = request.form.get('bucket_name', '').strip()

                if not key_id:
                    return jsonify({'error': 'Application Key ID is required'}), 400
                if not application_key:
                    return jsonify({'error': 'Application Key is required'}), 400
                if not bucket_name:
                    return jsonify({'error': 'Bucket name is required'}), 400
                if not re.match(r'^[a-z0-9-]{6,50}$', bucket_name):
                    return jsonify({'error': 'Invalid bucket name format for Backblaze B2'}), 400

                credentials = {
                    'application_key_id': key_id,
                    'application_key': application_key,
                    'bucket_name': bucket_name
                }
            elif provider_type == 'wasabi':
                access_key = request.form.get('access_key', '').strip()
                secret_key = request.form.get('secret_key', '').strip()
                bucket = request.form.get('bucket', '').strip()
                region = request.form.get('region', '').strip()

                if not access_key:
                    return jsonify({'error': 'Access Key is required'}), 400
                if not secret_key:
                    return jsonify({'error': 'Secret Key is required'}), 400
                if not bucket:
                    return jsonify({'error': 'Bucket name is required'}), 400
                if not region:
                    return jsonify({'error': 'Region is required'}), 400
                if not re.match(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$', bucket):
                    return jsonify({'error': 'Invalid bucket name format for Wasabi'}), 400

                credentials = {
                    'access_key': access_key,
                    'secret_key': secret_key,
                    'bucket': bucket,
                    'region': region
                }
            elif provider_type == 'gcs':
                credentials_json = request.form.get('credentials_json', '').strip()
                if not credentials_json:
                    return jsonify({'error': 'Service account JSON is required'}), 400
                
                try:
                    # Validate JSON format
                    json.loads(credentials_json)
                    project_id = request.form.get('project_id', '').strip()
                    bucket_name = request.form.get('bucket_name', '').strip()
                    
                    if not project_id:
                        return jsonify({'error': 'Project ID is required'}), 400
                    if not bucket_name:
                        return jsonify({'error': 'Bucket name is required'}), 400
                        
                    credentials = {
                        'project_id': project_id,
                        'bucket_name': bucket_name,
                        'credentials_json': credentials_json
                    }
                except json.JSONDecodeError as e:
                    return jsonify({'error': f'Invalid service account JSON format: {str(e)}'}), 400
            elif provider_type == 'digitalocean':
                access_key = request.form.get('access_key', '').strip()
                secret_key = request.form.get('secret_key', '').strip()
                bucket = request.form.get('bucket', '').strip()
                region = request.form.get('region', '').strip()

                if not access_key:
                    return jsonify({'error': 'Access Key is required'}), 400
                if not secret_key:
                    return jsonify({'error': 'Secret Key is required'}), 400
                if not bucket:
                    return jsonify({'error': 'Bucket name is required'}), 400
                if not region:
                    return jsonify({'error': 'Region is required'}), 400
                if not re.match(r'^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$', bucket):
                    return jsonify({'error': 'Invalid bucket name format for DigitalOcean Spaces'}), 400
                if region not in ['nyc3', 'ams3', 'sgp1', 'fra1', 'sfo3']:
                    return jsonify({'error': 'Invalid region for DigitalOcean Spaces'}), 400

                credentials = {
                    'access_key': access_key,
                    'secret_key': secret_key,
                    'bucket': bucket,
                    'region': region
                }
            elif provider_type == 'hetzner':
                access_key = request.form.get('access_key', '').strip()
                secret_key = request.form.get('secret_key', '').strip()
                bucket = request.form.get('bucket', '').strip()
                region = request.form.get('region', '').strip()

                if not access_key:
                    return jsonify({'error': 'Access Key is required'}), 400
                if not secret_key:
                    return jsonify({'error': 'Secret Key is required'}), 400
                if not bucket:
                    return jsonify({'error': 'Bucket name is required'}), 400
                if not region:
                    return jsonify({'error': 'Region is required'}), 400
                if not re.match(r'^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$', bucket):
                    return jsonify({'error': 'Invalid bucket name format for Hetzner Storage'}), 400
                if region not in ['nbg1', 'fsn1', 'hel1', 'ash', 'hil', 'sin']:
                    return jsonify({'error': 'Invalid region for Hetzner Storage'}), 400

                credentials = {
                    'access_key': access_key,
                    'secret_key': secret_key,
                    'bucket': bucket,
                    'region': region
                }
            else:
                return jsonify({'error': 'Invalid storage provider selected'}), 400

            # Validate credentials by creating a provider instance
            logger.debug(f"Attempting to create provider instance for {provider_type}")
            provider = get_storage_provider(provider_type, **credentials)
            
            # Test provider by listing files
            logger.debug("Testing provider connection by listing files")
            provider.list_files()
            
            # Store configuration in session
            session['authenticated'] = True
            session['provider_type'] = provider_type
            session['provider_config'] = credentials
            
            # Set bucket name based on provider type
            if provider_type == 'gcs':
                session['bucket'] = credentials.get('bucket_name')
            else:
                session['bucket'] = credentials.get('bucket')
            
            logger.info(f"Successfully configured {provider_type} provider with bucket: {session['bucket']}")
            return jsonify({'message': 'Configuration updated successfully'}), 200
            
        except Exception as e:
            logger.error(f"Error configuring storage: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 400
            
    return render_template('configure.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400
        
    if file:
        filename = secure_filename(file.filename)
        folder = request.form.get('folder', '')
        if folder:
            filename = f"{folder.rstrip('/')}/{filename}"
        try:
            provider.upload_file(file, filename)
            return jsonify({'message': 'File uploaded successfully'}), 200
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>')
@login_required
def download(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400

    # Prevent downloading folders
    if filename.endswith('/'):
        return jsonify({'error': 'Cannot download a folder'}), 400

    try:
        file_obj = provider.download_file(filename)
        return send_file(
            file_obj,
            download_name=os.path.basename(filename),
            as_attachment=True
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/list')
@login_required
def list_files():
    provider = get_current_provider()
    if not provider:
        return jsonify({
            'files': [],
            'message': 'Storage not configured'
        }), 200
        
    try:
        prefix = request.args.get('prefix', '')
        files = provider.list_files(prefix)

        file_data = []
        folders_seen = set()

        for file in files:
            try:
                file_name = file['name']
                file_size = file.get('size', 0)

                # Detect if this is a folder:
                # 1. Size is 0 and mime_type is None/null
                # 2. Name ends with '/'
                is_folder_marker = (file_size == 0 and file.get('mime_type') is None) or file_name.endswith('/')

                # Remove prefix from the path to get relative path
                if prefix and file_name.startswith(prefix):
                    relative_path = file_name[len(prefix):]
                else:
                    relative_path = file_name

                # Skip empty paths
                if not relative_path:
                    continue

                # Check if this is a direct child or a nested item
                if '/' in relative_path:
                    # This contains a slash, so it's either:
                    # 1. A folder marker (e.g., "hello/")
                    # 2. A nested file (e.g., "hello/file.txt")
                    # 3. A deeper nested item (e.g., "hello/world/file.txt")

                    # Extract the immediate folder name
                    folder_name = relative_path.split('/')[0]
                    full_folder_path = prefix + folder_name + '/'

                    # Add folder if not already seen
                    if full_folder_path not in folders_seen:
                        folders_seen.add(full_folder_path)
                        file_data.append({
                            'name': full_folder_path,
                            'size': 0,
                            'preview_url': None,
                            'mime_type': 'folder',
                            'type': 'folder'
                        })

                    # Skip this entry - it's nested, not a direct child
                    # We've already added the folder, no need to process the file
                    continue

                # This is a direct child (no slashes in relative_path)
                # Check if it's a folder or a file
                if is_folder_marker:
                    # This is a folder in the current directory
                    folder_path = file_name if file_name.endswith('/') else file_name + '/'
                    if folder_path not in folders_seen:
                        folders_seen.add(folder_path)
                        file_data.append({
                            'name': folder_path,
                            'size': 0,
                            'preview_url': None,
                            'mime_type': 'folder',
                            'type': 'folder'
                        })
                else:
                    # This is a regular file
                    mime_type, _ = mimetypes.guess_type(file_name)
                    preview_url = None
                    if mime_type and (mime_type.startswith('image/') or
                                    mime_type == 'application/pdf' or
                                    mime_type.startswith('video/')):
                        preview_url = provider.get_file_url(file_name)
                    file_data.append({
                        'name': file_name,
                        'size': file_size,
                        'preview_url': preview_url,
                        'mime_type': mime_type,
                        'type': 'file'
                    })
            except Exception as e:
                logger.warning(f"Error processing file {file['name']}: {str(e)}")
                continue

        return jsonify({'files': file_data}), 200
        
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred',
            'details': str(e)
        }), 500

@app.route('/delete/<path:filename>', methods=['DELETE'])
@login_required
def delete(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400

    try:
        provider.delete_file(filename)
        return jsonify({'message': 'File deleted successfully'}), 200
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400

    try:
        data = request.get_json()
        folder_name = data.get('folder_name')

        if not folder_name:
            return jsonify({'error': 'Folder name is required'}), 400

        # Check if provider has create_folder method
        if not hasattr(provider, 'create_folder'):
            return jsonify({'error': 'Folder creation not supported by this storage provider'}), 400

        provider.create_folder(folder_name)
        return jsonify({'message': 'Folder created successfully', 'folder_name': folder_name}), 200
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_folder', methods=['DELETE'])
@login_required
def delete_folder():
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400

    try:
        data = request.get_json()
        folder_name = data.get('folder_name')

        if not folder_name:
            return jsonify({'error': 'Folder name is required'}), 400

        # For s3_utils-based providers, use the module function
        # For storage_providers-based providers, they don't have delete_folder yet
        # So we'll use s3_utils.delete_folder if available
        from s3_utils import delete_folder as delete_folder_util
        delete_folder_util(folder_name)

        return jsonify({'message': 'Folder deleted successfully', 'folder_name': folder_name}), 200
    except Exception as e:
        logger.error(f"Error deleting folder: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('configure_storage'))

@app.route('/share/<path:filename>')
@login_required
def share_file(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({'error': 'Storage not configured'}), 400

    # Prevent sharing folders
    if filename.endswith('/'):
        return jsonify({'error': 'Cannot share a folder'}), 400

    try:
        # Generate a URL that expires in 7 days (604800 seconds)
        url = provider.get_file_url(filename, expires_in=604800)
        # Also get mime type for preview
        mime_type, _ = mimetypes.guess_type(filename)
        return jsonify({'url': url, 'preview_url': url, 'mime_type': mime_type}), 200
    except Exception as e:
        logger.error(f"Error generating share link: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
