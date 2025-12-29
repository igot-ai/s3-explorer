"""FastAPI router for S3 Explorer web UI.

This replaces the Flask Blueprint with FastAPI router, maintaining all
the same functionality: storage configuration, file browsing, upload/download.
"""

import json
import mimetypes
import os
import re
import secrets
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from src.shared._logging import get_logger
from src.shared.storage import get_storage_provider
from werkzeug.utils import secure_filename

logger = get_logger(__name__)

router = APIRouter(tags=["S3 Explorer"])

CHUNK_SIZE = 100 * 1024 * 1024  # 100 MB chunks

# Update MIME type detection
mimetypes.init()
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("image/heic", ".heic")
mimetypes.add_type("image/heif", ".heif")


def get_templates(request: Request):
    """Get Jinja2Templates from app state."""
    return request.app.state.templates


def is_authenticated(request: Request) -> bool:
    """Check if user is authenticated."""
    return request.session.get("authenticated", False)


def require_auth(request: Request):
    """Dependency to require authentication."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


def get_current_provider(request: Request):
    """Get the current storage provider based on session configuration."""
    if "provider_type" not in request.session:
        return None

    try:
        return get_storage_provider(
            request.session["provider_type"], **request.session["provider_config"]
        )
    except Exception as e:
        logger.error(f"Error creating storage provider: {str(e)}")
        return None


@router.get("/", name="s3_explore.index")
async def index(request: Request):
    """Index page - redirects to configure if not authenticated."""
    if not is_authenticated(request):
        return RedirectResponse(url="/configure", status_code=302)

    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_hex(32)
        request.session["csrf_token"] = csrf_token

    templates = get_templates(request)
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"session": request.session, "csrf_token": lambda: csrf_token},
    )
    response.set_cookie("csrf_token", csrf_token, httponly=False)
    return response


@router.get("/configure", name="s3_explore.configure_storage")
async def configure_storage_get(request: Request):
    """Storage configuration page."""
    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_hex(32)
        request.session["csrf_token"] = csrf_token

    templates = get_templates(request)
    response = templates.TemplateResponse(
        request=request,
        name="configure.html",
        context={"session": request.session, "csrf_token": lambda: csrf_token},
    )
    # Also set as cookie to satisfy the frontend's getCsrfToken()
    response.set_cookie("csrf_token", csrf_token, httponly=False)
    return response


@router.get("/get-csrf-token")
async def get_csrf_token(request: Request):
    """Get or generate CSRF token."""
    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_hex(32)
        request.session["csrf_token"] = csrf_token

    response = JSONResponse({"csrf_token": csrf_token})
    response.set_cookie("csrf_token", csrf_token, httponly=False)
    return response


@router.post("/configure", name="s3_explore.configure_storage")
async def configure_storage_post(request: Request):
    """Handle storage configuration form submission."""
    form = await request.form()
    provider_type = form.get("provider_type")
    logger.debug(f"Received configuration request for provider: {provider_type}")

    try:
        if provider_type == "cloudflare":
            account_id = str(form.get("account_id", "")).strip()
            access_key = str(form.get("access_key", "")).strip()
            secret_key = str(form.get("secret_key", "")).strip()
            bucket = str(form.get("bucket", "")).strip()

            if not account_id:
                return JSONResponse(
                    {"error": "Account ID is required"}, status_code=400
                )
            if not access_key:
                return JSONResponse(
                    {"error": "Access Key ID is required"}, status_code=400
                )
            if not secret_key:
                return JSONResponse(
                    {"error": "Secret Access Key is required"}, status_code=400
                )
            if not bucket:
                return JSONResponse(
                    {"error": "Bucket name is required"}, status_code=400
                )
            if not re.match(r"^[a-zA-Z0-9.\-_]{3,63}$", bucket):
                return JSONResponse(
                    {"error": "Invalid bucket name format"}, status_code=400
                )

            credentials = {
                "account_id": account_id,
                "access_key": access_key,
                "secret_key": secret_key,
                "bucket": bucket,
            }
        elif provider_type in ["aws", "wasabi"]:
            credentials = {
                "access_key": form.get("access_key"),
                "secret_key": form.get("secret_key"),
                "bucket": form.get("bucket"),
                "region": form.get("region", "us-east-1"),
            }
        elif provider_type == "backblaze":
            key_id = str(form.get("key_id", "")).strip()
            application_key = str(form.get("application_key", "")).strip()
            bucket_name = str(form.get("bucket_name", "")).strip()

            if not key_id:
                return JSONResponse(
                    {"error": "Application Key ID is required"}, status_code=400
                )
            if not application_key:
                return JSONResponse(
                    {"error": "Application Key is required"}, status_code=400
                )
            if not bucket_name:
                return JSONResponse(
                    {"error": "Bucket name is required"}, status_code=400
                )
            if not re.match(r"^[a-z0-9-]{6,50}$", bucket_name):
                return JSONResponse(
                    {"error": "Invalid bucket name format for Backblaze B2"},
                    status_code=400,
                )

            credentials = {
                "application_key_id": key_id,
                "application_key": application_key,
                "bucket_name": bucket_name,
            }
        elif provider_type == "gcs":
            credentials_json = str(form.get("credentials_json", "")).strip()
            if not credentials_json:
                return JSONResponse(
                    {"error": "Service account JSON is required"}, status_code=400
                )

            try:
                json.loads(credentials_json)
                project_id = str(form.get("project_id", "")).strip()
                bucket_name = str(form.get("bucket_name", "")).strip()

                if not project_id:
                    return JSONResponse(
                        {"error": "Project ID is required"}, status_code=400
                    )
                if not bucket_name:
                    return JSONResponse(
                        {"error": "Bucket name is required"}, status_code=400
                    )

                credentials = {
                    "project_id": project_id,
                    "bucket_name": bucket_name,
                    "credentials_json": credentials_json,
                }
            except json.JSONDecodeError as e:
                return JSONResponse(
                    {"error": f"Invalid service account JSON format: {str(e)}"},
                    status_code=400,
                )
        elif provider_type == "digitalocean":
            access_key = str(form.get("access_key", "")).strip()
            secret_key = str(form.get("secret_key", "")).strip()
            bucket = str(form.get("bucket", "")).strip()
            region = str(form.get("region", "")).strip()

            if not access_key:
                return JSONResponse(
                    {"error": "Access Key is required"}, status_code=400
                )
            if not secret_key:
                return JSONResponse(
                    {"error": "Secret Key is required"}, status_code=400
                )
            if not bucket:
                return JSONResponse(
                    {"error": "Bucket name is required"}, status_code=400
                )
            if not region:
                return JSONResponse({"error": "Region is required"}, status_code=400)
            if not re.match(r"^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$", bucket):
                return JSONResponse(
                    {"error": "Invalid bucket name format for DigitalOcean Spaces"},
                    status_code=400,
                )
            if region not in ["nyc3", "ams3", "sgp1", "fra1", "sfo3"]:
                return JSONResponse(
                    {"error": "Invalid region for DigitalOcean Spaces"}, status_code=400
                )

            credentials = {
                "access_key": access_key,
                "secret_key": secret_key,
                "bucket": bucket,
                "region": region,
            }
        elif provider_type == "hetzner":
            access_key = str(form.get("access_key", "")).strip()
            secret_key = str(form.get("secret_key", "")).strip()
            bucket = str(form.get("bucket", "")).strip()
            region = str(form.get("region", "")).strip()

            if not access_key:
                return JSONResponse(
                    {"error": "Access Key is required"}, status_code=400
                )
            if not secret_key:
                return JSONResponse(
                    {"error": "Secret Key is required"}, status_code=400
                )
            if not bucket:
                return JSONResponse(
                    {"error": "Bucket name is required"}, status_code=400
                )
            if not region:
                return JSONResponse({"error": "Region is required"}, status_code=400)
            if not re.match(r"^[a-z0-9][a-z0-9.-]{2,62}[a-z0-9]$", bucket):
                return JSONResponse(
                    {"error": "Invalid bucket name format for Hetzner Storage"},
                    status_code=400,
                )
            if region not in ["nbg1", "fsn1", "hel1", "ash", "hil", "sin"]:
                return JSONResponse(
                    {"error": "Invalid region for Hetzner Storage"}, status_code=400
                )

            credentials = {
                "access_key": access_key,
                "secret_key": secret_key,
                "bucket": bucket,
                "region": region,
            }
        else:
            return JSONResponse(
                {"error": "Invalid storage provider selected"}, status_code=400
            )

        logger.debug(f"Attempting to create provider instance for {provider_type}")
        provider = get_storage_provider(provider_type, **credentials)

        logger.debug("Testing provider connection by listing files")
        provider.list_files()

        request.session["authenticated"] = True
        request.session["provider_type"] = provider_type
        request.session["provider_config"] = credentials

        if provider_type == "gcs":
            request.session["bucket"] = credentials.get("bucket_name")
        else:
            request.session["bucket"] = credentials.get("bucket")

        logger.info(
            f"Successfully configured {provider_type} provider with bucket: {request.session['bucket']}"
        )
        return JSONResponse(
            {"message": "Configuration updated successfully"}, status_code=200
        )

    except Exception as e:
        logger.error(f"Error configuring storage: {str(e)}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/upload")
async def upload(
    request: Request, file: UploadFile = File(...), folder: str = Form("")
):
    """Upload a file to storage."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    filename = secure_filename(file.filename)
    if folder:
        filename = f"{folder.rstrip('/')}/{filename}"

    try:
        file_content = await file.read()
        file_obj = BytesIO(file_content)
        provider.upload_file(file_obj, filename)
        return JSONResponse({"message": "File uploaded successfully"}, status_code=200)
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/download/{filename:path}")
async def download(request: Request, filename: str):
    """Download a file from storage."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    if filename.endswith("/"):
        return JSONResponse({"error": "Cannot download a folder"}, status_code=400)

    try:
        file_obj = provider.download_file(filename)
        return StreamingResponse(
            file_obj,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            },
        )
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/list")
async def list_files(request: Request, prefix: str = ""):
    """List files in storage."""
    if not is_authenticated(request):
        return JSONResponse(
            {"files": [], "message": "Not authenticated"}, status_code=200
        )

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse(
            {"files": [], "message": "Storage not configured"}, status_code=200
        )

    try:
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

        return JSONResponse({"files": file_data}, status_code=200)

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return JSONResponse(
            {"error": "An unexpected error occurred", "details": str(e)},
            status_code=500,
        )


@router.delete("/delete/{filename:path}")
async def delete(request: Request, filename: str):
    """Delete a file from storage."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    try:
        provider.delete_file(filename)
        return JSONResponse({"message": "File deleted successfully"}, status_code=200)
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/create_folder")
async def create_folder(request: Request):
    """Create a folder in storage."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    try:
        data = await request.json()
        folder_name = data.get("folder_name") if isinstance(data, dict) else None

        if not folder_name:
            return JSONResponse({"error": "Folder name is required"}, status_code=400)

        if not hasattr(provider, "create_folder"):
            return JSONResponse(
                {"error": "Folder creation not supported by this storage provider"},
                status_code=400,
            )

        provider.create_folder(folder_name)
        return JSONResponse(
            {"message": "Folder created successfully", "folder_name": folder_name},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error creating folder: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/delete_folder")
async def delete_folder(request: Request):
    """Delete a folder from storage."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    try:
        data = await request.json()
        folder_name = data.get("folder_name") if isinstance(data, dict) else None

        if not folder_name:
            return JSONResponse({"error": "Folder name is required"}, status_code=400)

        if not hasattr(provider, "delete_folder"):
            return JSONResponse(
                {"error": "Folder deletion not supported by this storage provider"},
                status_code=400,
            )

        provider.delete_folder(folder_name)
        return JSONResponse(
            {"message": "Folder deleted successfully", "folder_name": folder_name},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Error deleting folder: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/logout", name="s3_explore.logout")
async def logout(request: Request):
    """Clear session and logout."""
    request.session.clear()
    return RedirectResponse(url="/configure", status_code=302)


@router.get("/share/{filename:path}")
async def share_file(request: Request, filename: str):
    """Generate a shareable link for a file."""
    if not is_authenticated(request):
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    provider = get_current_provider(request)
    if not provider:
        return JSONResponse({"error": "Storage not configured"}, status_code=400)

    if filename.endswith("/"):
        return JSONResponse({"error": "Cannot share a folder"}, status_code=400)

    try:
        url = provider.get_file_url(filename, expires_in=604800)
        mime_type, _ = mimetypes.guess_type(filename)
        return JSONResponse(
            {"url": url, "preview_url": url, "mime_type": mime_type}, status_code=200
        )
    except Exception as e:
        logger.error(f"Error generating share link: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


__all__ = ["router"]
