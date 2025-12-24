"""Temporal workflow integration for ingestion pipeline.

This module provides Temporal workflow orchestration for the data ingestion pipeline,
enabling distributed execution and integration with other services like catalog.
"""

from src.modules.ingestion.temporal.activities import run_ingestion_pipeline_activity
from src.modules.ingestion.temporal.models import IngestionJobParams, IngestionResult
from src.modules.ingestion.temporal.workflows import IngestionPipelineWorkflow

__all__ = [
    "IngestionJobParams",
    "IngestionResult",
    "run_ingestion_pipeline_activity",
    "IngestionPipelineWorkflow",
]
