from flask import Blueprint, jsonify, request
from marshmallow import ValidationError
from src.modules.ingestion.schemas.ingestion import ingestion_request_schema
from src.shared._logging import get_logger
from src.modules.ingestion.core.connectors import get_storage_provider
from src.modules.ingestion.core.connectors.s3_connector import S3SourceConnector

logger = get_logger(__name__)

ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/v1/ingestion")



@ingestion_bp.route("/run", methods=["POST"])
def run_ingestion():
    """Run the ingestion pipeline by delegating to the Temporal wrapper via AgentService."""
    try:
        data = request.get_json()
        if not data:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Request body is required",
                        "errors": ["No JSON data provided"],
                    }
                ),
                400,
            )

        try:
            req = ingestion_request_schema.load(data)
        except ValidationError as e:
            errors = [
                f"{field}: {', '.join(msgs)}" for field, msgs in e.messages.items()
            ]
            return (
                jsonify(
                    {"success": False, "message": "Validation error", "errors": errors}
                ),
                400,
            )

        config_data = req["config"]
        storage_creds = {k: v for k, v in config_data.get("storage_credentials", {}).items() if v is not None}
        source_path = config_data["source_path"][:-1] if config_data["source_path"] and config_data["source_path"].endswith("/") else config_data["source_path"]

        workspace_id = config_data.get("workspace_id")
        project_id = config_data.get("project_id")
        auth_token = config_data.get("auth_token")
        if not workspace_id or not project_id or not auth_token:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Missing required API handler settings",
                        "errors": [
                            "workspace_id, project_id, and auth_token are required"
                        ],
                    }
                ),
                400,
            )

        catalogs = [
            {
                "id": cat["id"],
                "instruction": cat["instruction"],
                "fetch_all_metadata": cat.get("fetch_all_metadata", False),
            }
            for cat in req["catalogs"]
        ]

        from dataroutine.modules.ingestion.wrapper import get_ingestion_wrapper
        wrapper = get_ingestion_wrapper()
        
        # Convert catalogs to list of dicts if needed, though wrapper expects list of dicts
        # The schema validation in ingestion.py returns dicts for catalogs already?
        # req["catalogs"] is a list of dicts.
        
        response = wrapper.trigger_ingestion(
            source_path=source_path,
            workspace_id=workspace_id,
            project_id=project_id,
            auth_token=auth_token,
            catalogs=catalogs,
            task_id=config_data.get("task_id") or "",
            storage_provider=config_data.get("storage_provider", "aws"),
            storage_credentials=storage_creds,
            recursive=config_data.get("recursive", True),
            pages_to_read=config_data.get("pages_to_read", 3),
            reader_type=config_data.get("reader_type") or "pymupdf",
            temp_dir=config_data.get("temp_dir"),
            api_base_url=config_data.get("api_base_url"),
            user_id=config_data.get("user_id"),
            callback_workflow=config_data.get("callback_workflow"),
            callback_params=config_data.get("callback_params"),
        )

        return (
            jsonify(
                {
                    "success": bool(response.success),
                    "message": "Ingestion pipeline started via Temporal",
                    "status": response.status,
                    "task_id": response.task_id,
                    "error": response.error,
                }
            ),
            200 if response.success else 500,
        )

    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return (
            jsonify(
                {"success": False, "message": "Configuration error", "errors": [str(e)]}
            ),
            400,
        )

    except Exception as e:
        logger.error(f"Pipeline dispatch failed with error: {str(e)}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Pipeline dispatch failed",
                    "errors": [str(e)],
                }
            ),
            500,
        )


@ingestion_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for the ingestion API."""
    return jsonify({"status": "healthy", "service": "ingestion-pipeline"}), 200


@ingestion_bp.route("/list-prefixes", methods=["POST"])
def list_prefixes():
    """List available prefixes/folders in an S3 bucket.

    Request Body:
        {
            "storage_provider": "cloudflare",  # Required
            "storage_credentials": {  # Required
                "account_id": "...",  # For Cloudflare R2
                "access_key": "...",
                "secret_key": "...",
                "bucket": "...",
                "region": "..."  # Optional for some providers
            },
            "prefix": "optional/current/path/"  # Optional, defaults to root
        }

    Returns:
        JSON response with list of prefixes:
        {
            "prefixes": ["folder1/", "folder2/", "nested/path/"]
        }
    """
    try:
        data = request.get_json()
        if not data:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Request body is required",
                        "errors": ["No JSON data provided"],
                    }
                ),
                400,
            )

        storage_provider_type = data.get("storage_provider", "aws")
        storage_credentials = data.get("storage_credentials", {})
        prefix = data.get("prefix", "")

        if not storage_credentials:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Storage credentials required",
                        "errors": ["storage_credentials is required"],
                    }
                ),
                400,
            )

        # Filter out None values from storage credentials
        storage_creds = {k: v for k, v in storage_credentials.items() if v is not None}

        # Create storage provider
        try:
            storage_provider = get_storage_provider(
                storage_provider_type, **storage_creds
            )
        except Exception as e:
            logger.error(f"Error creating storage provider: {str(e)}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Failed to connect to storage",
                        "errors": [str(e)],
                    }
                ),
                400,
            )

        # Create source connector
        source_connector = S3SourceConnector(storage_provider)

        # List folders/prefixes
        try:
            prefixes = source_connector.list_folders(prefix)
            return jsonify({"success": True, "prefixes": prefixes}), 200
        except Exception as e:
            logger.error(f"Error listing prefixes: {str(e)}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Failed to list prefixes",
                        "errors": [str(e)],
                    }
                ),
                500,
            )

    except Exception as e:
        logger.error(f"Unexpected error in list_prefixes: {str(e)}", exc_info=True)
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Unexpected error",
                    "errors": [str(e)],
                }
            ),
            500,
        )
