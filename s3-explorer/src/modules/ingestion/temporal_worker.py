"""
Temporal Worker for Ingestion Pipeline

Run this script in a separate terminal to process ingestion workflows.

Usage:
    poetry run python -m src.modules.ingestion.temporal_worker
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
# File is at src/modules/ingestion/temporal_worker.py
# Root is at ../../../../
_project_root = Path(__file__).resolve().parents[3]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from temporalio.client import Client
from temporalio.worker import Worker

from src.shared._logging import get_logger
from src.modules.ingestion.temporal.workflows import IngestionPipelineWorkflow, INGESTION_TASK_QUEUE
from src.modules.ingestion.temporal.activities import run_ingestion_pipeline_activity

logger = get_logger(__name__)

# Environment config
TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")


async def main():
    """Run the Temporal worker for ingestion pipelines."""
    logger.info("=" * 60)
    logger.info("Starting Ingestion Pipeline Temporal Worker")
    logger.info(f"Temporal Host: {TEMPORAL_SERVER_URL}")
    logger.info(f"Namespace: {TEMPORAL_NAMESPACE}")
    logger.info(f"Task Queue: {INGESTION_TASK_QUEUE}")
    logger.info("=" * 60)
    
    try:
        # Connect to Temporal
        client = await Client.connect(
            TEMPORAL_SERVER_URL,
            namespace=TEMPORAL_NAMESPACE,
        )
        logger.info("✅ Connected to Temporal server")
        
        # Create worker with workflows and activities
        worker = Worker(
            client,
            task_queue=INGESTION_TASK_QUEUE,
            workflows=[IngestionPipelineWorkflow],
            activities=[run_ingestion_pipeline_activity],
        )
        
        logger.info("🚀 Worker is running. Press Ctrl+C to stop.")
        await worker.run()
        
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
