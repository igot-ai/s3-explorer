"""FastAPI routes for ingestion pipeline."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.modules.ingestion.env import AUTH_TOKEN
from src.modules.ingestion.schemas.fastapi_models import (
    IngestionRequestModel,
    IngestionResponseModel,
    ListPrefixesRequestModel,
    ListPrefixesResponseModel,
)
from src.modules.ingestion.wrapper import get_ingestion_wrapper
from src.modules.ingestion.core.connectors import get_storage_provider
from src.modules.ingestion.core.connectors.s3_connector import S3SourceConnector
from src.shared._logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion"])

security = HTTPBearer(auto_error=False)


def _normalize_token(value: Optional[str]) -> Optional[str]:
    """Normalize token strings so we can accept both 'Bearer <token>' and '<token>'."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    parts = value.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        return token or None
    return value


async def verify_ingestion_auth(
    authorization: Optional[str] = Header(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> None:
    """Dependency to verify ingestion API authentication.
    
    Compares incoming token against env AUTH_TOKEN.
    Accepts either:
    - Authorization: Bearer <token> (or raw token)
    - HTTPBearer token
    """
    # Get token from either source
    provided_token = None
    if authorization:
        provided_token = _normalize_token(authorization)
    elif credentials:
        provided_token = credentials.credentials
    
    if not AUTH_TOKEN:
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Server auth not configured",
                "errors": ["AUTH_TOKEN is not set on server"],
            }
        )
    
    if provided_token != AUTH_TOKEN:
        raise HTTPException(
            status_code=401,
            detail={
                "success": False,
                "message": "Unauthorized",
                "errors": ["Invalid or missing auth token. Use AUTH_TOKEN or Authorization header."],
            },
            headers={"WWW-Authenticate": 'Bearer realm="ingestion"'},
        )


@router.post("/run", response_model=IngestionResponseModel)
async def run_ingestion(
    request: IngestionRequestModel,
    _: None = Depends(verify_ingestion_auth),
):
    """Run the ingestion pipeline by delegating to the Temporal wrapper via AgentService.
    
    This endpoint validates the request, delegates to the ingestion wrapper,
    which calls gRPC AgentService to trigger a Temporal workflow.
    """
    try:
        config = request.config
        
        # Validate required fields
        if not config.workspace_id or not config.project_id or not config.auth_token:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Missing required API handler settings",
                    "errors": ["workspace_id, project_id, and auth_token are required"],
                }
            )
        
        # Normalize source path (remove trailing slash)
        source_path = config.source_path.rstrip("/") if config.source_path else ""
        
        # Filter out None values from storage credentials
        if isinstance(config.storage_credentials, dict):
            storage_creds_dict = {k: v for k, v in config.storage_credentials.items() if v is not None}
        elif config.storage_credentials:
            storage_creds_dict = config.storage_credentials.model_dump(exclude_none=True)
        else:
            storage_creds_dict = {}
        
        # Convert catalogs to dict format
        catalogs = [
            {
                "id": cat.id,
                "instruction": cat.instruction,
                "fetch_all_metadata": cat.fetch_all_metadata,
            }
            for cat in request.catalogs
        ]
        
        # Get wrapper and trigger ingestion
        wrapper = get_ingestion_wrapper()
        result = wrapper.trigger_ingestion(
            source_path=source_path,
            workspace_id=config.workspace_id,
            project_id=config.project_id,
            auth_token=config.auth_token,
            catalogs=catalogs,
            task_id=config.task_id,
            storage_provider=config.storage_provider,
            storage_credentials=storage_creds_dict,
            recursive=config.recursive,
            pages_to_read=config.pages_to_read,
            reader_type=config.reader_type or "pymupdf",
            temp_dir=config.temp_dir,
            api_base_url=config.api_base_url,
            user_id=config.user_id,
            callback_workflow=config.callback_workflow,
            callback_params=config.callback_params,
        )
        
        return IngestionResponseModel(
            success=result.success,
            message="Ingestion pipeline started via Temporal" if result.success else "Failed to start ingestion pipeline",
            task_id=result.task_id,
            status=result.status,
            error=result.error,
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": "Configuration error",
                "errors": [str(e)],
            }
        )
    except Exception as e:
        logger.error(f"Pipeline dispatch failed with error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Pipeline dispatch failed",
                "errors": [str(e)],
            }
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for the ingestion API."""
    return {"status": "healthy", "service": "ingestion-pipeline"}


@router.post("/list-prefixes", response_model=ListPrefixesResponseModel)
async def list_prefixes(
    request: ListPrefixesRequestModel,
    _: None = Depends(verify_ingestion_auth),
):
    """List available prefixes/folders in an S3 bucket.
    
    This endpoint allows clients to browse available folders/prefixes
    in their storage bucket before triggering ingestion.
    """
    try:
        # Filter out None values from storage credentials
        storage_creds = request.storage_credentials.model_dump(exclude_none=True) if request.storage_credentials else {}
        
        if not storage_creds:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Storage credentials required",
                    "errors": ["storage_credentials is required"],
                }
            )
        
        # Create storage provider
        try:
            storage_provider = get_storage_provider(
                request.storage_provider, **storage_creds
            )
        except Exception as e:
            logger.error(f"Error creating storage provider: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "message": "Failed to connect to storage",
                    "errors": [str(e)],
                }
            )
        
        # Create source connector
        source_connector = S3SourceConnector(storage_provider)
        
        # List folders/prefixes
        try:
            prefixes = source_connector.list_folders(request.prefix)
            return ListPrefixesResponseModel(
                success=True,
                prefixes=prefixes,
            )
        except Exception as e:
            logger.error(f"Error listing prefixes: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "message": "Failed to list prefixes",
                    "errors": [str(e)],
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in list_prefixes: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Unexpected error",
                "errors": [str(e)],
            }
        )

