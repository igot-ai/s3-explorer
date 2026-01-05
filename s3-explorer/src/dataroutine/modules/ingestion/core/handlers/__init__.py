"""Collection handlers for uploading files to destinations."""

from dataroutine.modules.ingestion.core.handlers.base import CollectionHandler
from dataroutine.modules.ingestion.core.handlers.collection_handler_manager import (
    CollectionHandlerManager,
)

__all__ = ["CollectionHandler", "CollectionHandlerManager"]
