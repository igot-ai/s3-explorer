import json
import mimetypes
import os
import re
from functools import wraps

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from src.shared._logging import get_logger
from src.shared.storage import get_storage_provider
from werkzeug.utils import secure_filename

logger = get_logger(__name__)

# Blueprint for the S3 Explorer web UI.
# `main.py` is responsible for creating the Flask app and registering this blueprint.
s3_explore_bp = Blueprint("s3_explore", __name__)

CHUNK_SIZE = 100 * 1024 * 1024  # 100 MB chunks

# Update MIME type detection
mimetypes.init()
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/heif", ".heif")


def _url_for(endpoint, **values):
    generated_url = url_for(endpoint, _external=False, **values)
    if request.script_root and request.script_root != "/":
        script_root = request.script_root.rstrip("/")
        if not (
            generated_url.startswith(script_root)
            or generated_url.startswith(script_root + "/")
        ):
            generated_url = script_root + generated_url
    return generated_url


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "authenticated" not in session:
            return redirect(_url_for("s3_explore.configure_storage"))
        return f(*args, **kwargs)

    return decorated_function


def get_current_provider():
    """Get the current storage provider based on session configuration."""
    if "provider_type" not in session:
        return None

    try:
        return get_storage_provider(
            session["provider_type"], **session["provider_config"]
        )
    except Exception as e:
        logger.error(f"Error creating storage provider: {str(e)}")
        return None


@s3_explore_bp.route("/")
@login_required
def index():
    provider = get_current_provider()
    if not provider:
        return redirect(_url_for("s3_explore.configure_storage"))
    return render_template("index.html")


@s3_explore_bp.route("/configure", methods=["GET", "POST"])
def configure_storage():
    if request.method == "POST":
        # Verify CSRF token manually (cookie set by main.py after_request hook)
        token = request.form.get("csrf_token")
        if not token or token != request.cookies.get("csrf_token"):
            logger.error(
                f"CSRF token mismatch. Form token: {token}, Cookie token: {request.cookies.get('csrf_token')}"
            )
            return jsonify({"error": "Invalid CSRF token"}), 400

        provider_type = request.form.get("provider_type")
        logger.debug(f"Received configuration request for provider: {provider_type}")
        logger.debug(f"Form data: {request.form}")

        try:
            if provider_type == "cloudflare":
                account_id = request.form.get("account_id", "").strip()
                access_key = request.form.get("access_key", "").strip()
                secret_key = request.form.get("secret_key", "").strip()
                bucket = request.form.get("bucket", "").strip()

                logger.debug(
                    f"Cloudflare configuration - Account ID: {account_id}, Bucket: {bucket}"
                )

                if not account_id:
                    return jsonify({"error": "Account ID is required"}), 400
                if not access_key:
                    return jsonify({"error": "Access Key ID is required"}), 400
                if not secret_key:
                    return jsonify({"error": "Secret Access Key is required"}), 400
                if not bucket:
                    return jsonify({"error": "Bucket name is required"}), 400
                if not re.match(r"^[a-zA-Z0-9.\-_]{3,63}$", bucket):
                    return jsonify({"error": "Invalid bucket name format"}), 400

                credentials = {
                    "account_id": account_id,
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "bucket": bucket,
                }
            elif provider_type in ["aws", "wasabi"]:
                credentials = {
                    "access_key": request.form.get("access_key"),
                    "secret_key": request.form.get("secret_key"),
                    "bucket": request.form.get("bucket"),
                    "region": request.form.get("region", "us-east-1"),
                }
            elif provider_type == "backblaze":
                key_id = request.form.get("key_id", "").strip()
                application_key = request.form.get("application_key", "").strip()
                bucket_name = request.form.get("bucket_name", "").strip()

                if not key_id:
                    return jsonify({"error": "Application Key ID is required"}), 400
                if not application_key:
                    return jsonify({"error": "Application Key is required"}), 400
                if not bucket_name:
                    return jsonify({"error": "Bucket name is required"}), 400
                if not re.match(r"^[a-z0-9-]{6,50}$", bucket_name):
                    return (
                        jsonify(
                            {"error": "Invalid bucket name format for Backblaze B2"}
                        ),
                        400,
                    )

                credentials = {
                    "application_key_id": key_id,
                    "application_key": application_key,
                    "bucket_name": bucket_name,
                }
            elif provider_type == "wasabi":
                access_key = request.form.get("access_key", "").strip()
                secret_key = request.form.get("secret_key", "").strip()
                bucket = request.form.get("bucket", "").strip()
                region = request.form.get("region", "").strip()

                if not access_key:
                    return jsonify({"error": "Access Key is required"}), 400
                if not secret_key:
                    return jsonify({"error": "Secret Key is required"}), 400
                if not bucket:
                    return jsonify({"error": "Bucket name is required"}), 400
                if not region:
                    return jsonify({"error": "Region is required"}), 400
                if not re.match(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", bucket):
                    return (
                        jsonify({"error": "Invalid bucket name format for Wasabi"}),
                        400,
                    )

                credentials = {
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "bucket": bucket,
                    "region": region,
                }
            elif provider_type == "gcs":
                credentials_json = request.form.get("credentials_json", "").strip()
                if not credentials_json:
                    return jsonify({"error": "Service account JSON is required"}), 400

                try:
                    json.loads(credentials_json)
                    project_id = request.form.get("project_id", "").strip()
                    bucket_name = request.form.get("bucket_name", "").strip()

                    if not project_id:
                        return jsonify({"error": "Project ID is required"}), 400
                    if not bucket_name:
                        return jsonify({"error": "Bucket name is required"}), 400

                    credentials = {
                        "project_id": project_id,
                        "bucket_name": bucket_name,
                        "credentials_json": credentials_json,
                    }
                except json.JSONDecodeError as e:
                    return (
                        jsonify(
                            {"error": f"Invalid service account JSON format: {str(e)}"}
                        ),
                        400,
                    )
            elif provider_type == "digitalocean":
                access_key = request.form.get("access_key", "").strip()
                secret_key = request.form.get("secret_key", "").strip()
                bucket = request.form.get("bucket", "").strip()
                region = request.form.get("region", "").strip()

                if not access_key:
                    return jsonify({"error": "Access Key is required"}), 400
                if not secret_key:
                    return jsonify({"error": "Secret Key is required"}), 400
                if not bucket:
                    return jsonify({"error": "Bucket name is required"}), 400
                if not region:
                    return jsonify({"error": "Region is required"}), 400
                if not re.match(r"^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$", bucket):
                    return (
                        jsonify(
                            {
                                "error": "Invalid bucket name format for DigitalOcean Spaces"
                            }
                        ),
                        400,
                    )
                if region not in ["nyc3", "ams3", "sgp1", "fra1", "sfo3"]:
                    return (
                        jsonify({"error": "Invalid region for DigitalOcean Spaces"}),
                        400,
                    )

                credentials = {
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "bucket": bucket,
                    "region": region,
                }
            elif provider_type == "hetzner":
                access_key = request.form.get("access_key", "").strip()
                secret_key = request.form.get("secret_key", "").strip()
                bucket = request.form.get("bucket", "").strip()
                region = request.form.get("region", "").strip()

                if not access_key:
                    return jsonify({"error": "Access Key is required"}), 400
                if not secret_key:
                    return jsonify({"error": "Secret Key is required"}), 400
                if not bucket:
                    return jsonify({"error": "Bucket name is required"}), 400
                if not region:
                    return jsonify({"error": "Region is required"}), 400
                if not re.match(r"^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$", bucket):
                    return (
                        jsonify(
                            {"error": "Invalid bucket name format for Hetzner Storage"}
                        ),
                        400,
                    )
                if region not in ["nbg1", "fsn1", "hel1", "ash", "hil", "sin"]:
                    return jsonify({"error": "Invalid region for Hetzner Storage"}), 400

                credentials = {
                    "access_key": access_key,
                    "secret_key": secret_key,
                    "bucket": bucket,
                    "region": region,
                }
            else:
                return jsonify({"error": "Invalid storage provider selected"}), 400

            logger.debug(f"Attempting to create provider instance for {provider_type}")
            provider = get_storage_provider(provider_type, **credentials)

            logger.debug("Testing provider connection by listing files")
            provider.list_files()

            session["authenticated"] = True
            session["provider_type"] = provider_type
            session["provider_config"] = credentials

            if provider_type == "gcs":
                session["bucket"] = credentials.get("bucket_name")
            else:
                session["bucket"] = credentials.get("bucket")

            logger.info(
                f"Successfully configured {provider_type} provider with bucket: {session['bucket']}"
            )
            return jsonify({"message": "Configuration updated successfully"}), 200

        except Exception as e:
            logger.error(f"Error configuring storage: {str(e)}", exc_info=True)
            return jsonify({"error": str(e)}), 400

    return render_template("configure.html")


@s3_explore_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    filename = secure_filename(file.filename)
    folder = request.form.get("folder", "")
    if folder:
        filename = f"{folder.rstrip('/')}/{filename}"

    try:
        provider.upload_file(file, filename)
        return jsonify({"message": "File uploaded successfully"}), 200
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@s3_explore_bp.route("/download/<path:filename>")
@login_required
def download(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    if filename.endswith("/"):
        return jsonify({"error": "Cannot download a folder"}), 400

    try:
        file_obj = provider.download_file(filename)
        return send_file(
            file_obj, download_name=os.path.basename(filename), as_attachment=True
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@s3_explore_bp.route("/list")
@login_required
def list_files():
    provider = get_current_provider()
    if not provider:
        return jsonify({"files": [], "message": "Storage not configured"}), 200

    try:
        prefix = request.args.get("prefix", "")
        files = provider.list_files(prefix)

        file_data = []
        folders_seen = set()

        for file in files:
            try:
                file_name = file["name"]
                file_size = file.get("size", 0)
                is_folder_marker = (
                    file_size == 0 and file.get("mime_type") is None
                ) or file_name.endswith("/")

                if prefix and file_name.startswith(prefix):
                    relative_path = file_name[len(prefix) :]
                else:
                    relative_path = file_name

                if not relative_path:
                    continue

                if "/" in relative_path:
                    folder_name = relative_path.split("/")[0]
                    full_folder_path = prefix + folder_name + "/"

                    if full_folder_path not in folders_seen:
                        folders_seen.add(full_folder_path)
                        file_data.append(
                            {
                                "name": full_folder_path,
                                "size": 0,
                                "preview_url": None,
                                "mime_type": "folder",
                                "type": "folder",
                            }
                        )
                    continue

                if is_folder_marker:
                    folder_path = (
                        file_name if file_name.endswith("/") else file_name + "/"
                    )
                    if folder_path not in folders_seen:
                        folders_seen.add(folder_path)
                        file_data.append(
                            {
                                "name": folder_path,
                                "size": 0,
                                "preview_url": None,
                                "mime_type": "folder",
                                "type": "folder",
                            }
                        )
                else:
                    mime_type, _ = mimetypes.guess_type(file_name)
                    preview_url = None
                    if mime_type and (
                        mime_type.startswith("image/")
                        or mime_type == "application/pdf"
                        or mime_type.startswith("video/")
                    ):
                        preview_url = provider.get_file_url(file_name)

                    file_data.append(
                        {
                            "name": file_name,
                            "size": file_size,
                            "preview_url": preview_url,
                            "mime_type": mime_type,
                            "type": "file",
                        }
                    )
            except Exception as e:
                logger.warning(f"Error processing file {file.get('name')}: {str(e)}")
                continue

        return jsonify({"files": file_data}), 200

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return (
            jsonify({"error": "An unexpected error occurred", "details": str(e)}),
            500,
        )


@s3_explore_bp.route("/delete/<path:filename>", methods=["DELETE"])
@login_required
def delete(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    try:
        provider.delete_file(filename)
        return jsonify({"message": "File deleted successfully"}), 200
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return jsonify({"error": str(e)}), 500


@s3_explore_bp.route("/create_folder", methods=["POST"])
@login_required
def create_folder():
    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    try:
        data = request.get_json()
        folder_name = data.get("folder_name") if isinstance(data, dict) else None

        if not folder_name:
            return jsonify({"error": "Folder name is required"}), 400

        if not hasattr(provider, "create_folder"):
            return (
                jsonify(
                    {"error": "Folder creation not supported by this storage provider"}
                ),
                400,
            )

        provider.create_folder(folder_name)
        return (
            jsonify(
                {"message": "Folder created successfully", "folder_name": folder_name}
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return jsonify({"error": str(e)}), 500


@s3_explore_bp.route("/delete_folder", methods=["DELETE"])
@login_required
def delete_folder():
    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    try:
        data = request.get_json()
        folder_name = data.get("folder_name") if isinstance(data, dict) else None

        if not folder_name:
            return jsonify({"error": "Folder name is required"}), 400

        if not hasattr(provider, "delete_folder"):
            return (
                jsonify(
                    {"error": "Folder deletion not supported by this storage provider"}
                ),
                400,
            )

        provider.delete_folder(folder_name)
        return (
            jsonify(
                {"message": "Folder deleted successfully", "folder_name": folder_name}
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error deleting folder: {str(e)}")
        return jsonify({"error": str(e)}), 500


@s3_explore_bp.route("/logout")
def logout():
    session.clear()
    return redirect(_url_for("s3_explore.configure_storage"))


@s3_explore_bp.route("/share/<path:filename>")
@login_required
def share_file(filename):
    provider = get_current_provider()
    if not provider:
        return jsonify({"error": "Storage not configured"}), 400

    if filename.endswith("/"):
        return jsonify({"error": "Cannot share a folder"}), 400

    try:
        url = provider.get_file_url(filename, expires_in=604800)
        mime_type, _ = mimetypes.guess_type(filename)
        return jsonify({"url": url, "preview_url": url, "mime_type": mime_type}), 200
    except Exception as e:
        logger.error(f"Error generating share link: {str(e)}")
        return jsonify({"error": str(e)}), 500


__all__ = ["s3_explore_bp"]
