"""
Temporal Client Singleton Module

Provides a single, reusable Temporal client connection across the application.
Following the flowgpt pattern for consistency.

Usage:
    from dataroutine.shared.temporal_client import get_temporal_client

    # In async context
    client = await get_temporal_client()
    await client.start_workflow(...)
"""

import asyncio
import os
import threading
from typing import Optional

from temporalio.client import Client

from dataroutine.shared._logging import get_logger

logger = get_logger(__name__)

# Environment config
TEMPORAL_SERVER_URL = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")

# Global singleton client
_temporal_client: Optional[Client] = None
# Use threading.Lock instead of asyncio.Lock to avoid event loop binding issues
_client_lock = threading.Lock()


async def get_temporal_client() -> Client:
    """
    Get or create singleton Temporal client.
    
    Thread-safe singleton pattern that creates only one Temporal client connection
    for the entire application lifetime. Subsequent calls return the cached client.
    
    Uses threading.Lock instead of asyncio.Lock to avoid event loop binding issues
    when called from different threads.
    
    Returns:
        Client: Temporal client instance
        
    Raises:
        asyncio.TimeoutError: If connection takes longer than 30 seconds
        Exception: If connection to Temporal server fails
    """
    global _temporal_client
    
    with _client_lock:
        if _temporal_client is None:
            try:
                logger.info(f"🔌 Creating Temporal client connection to {TEMPORAL_SERVER_URL}")
                
                _temporal_client = await asyncio.wait_for(
                    Client.connect(
                        TEMPORAL_SERVER_URL,
                        namespace=TEMPORAL_NAMESPACE,
                    ),
                    timeout=30.0
                )
                
                logger.info("✅ Temporal client connection established successfully")
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Timeout: Could not connect to Temporal server at {TEMPORAL_SERVER_URL}")
                raise
            except Exception as e:
                logger.error(f"❌ Failed to connect to Temporal server: {e}")
                raise
        
        return _temporal_client


def run_async(coro, timeout: float = 300.0):
    """
    Safely run async code in synchronous context.

    This helper is specifically designed for sync contexts where you need to call 
    async Temporal operations. It properly handles event loop detection.

    Args:
        coro: Coroutine to execute
        timeout: Maximum seconds to wait for execution (default: 300)

    Returns:
        Result of the coroutine execution

    Raises:
        asyncio.TimeoutError: If execution exceeds timeout
        Exception: Any exception raised by the coroutine
    """
    try:
        # Try to get the running event loop
        loop = asyncio.get_running_loop()
        # If we get here, we're in an async context with a running loop
        logger.warning("run_async called from async context with running loop")
        raise RuntimeError("Cannot use run_async from async context")
    except RuntimeError:
        # No running loop - expected case
        pass
    
    # Create a new event loop for this thread
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        # Run the coroutine with timeout
        task = new_loop.create_task(coro)
        return new_loop.run_until_complete(
            asyncio.wait_for(task, timeout=timeout)
        )
    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout: Operation exceeded {timeout} seconds")
        raise
    finally:
        try:
            # Cancel any remaining tasks
            pending = asyncio.all_tasks(new_loop)
            for task in pending:
                task.cancel()
            # Run the loop one more time to process cancellations
            if pending:
                new_loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)


async def close_temporal_client():
    """Close the Temporal client connection gracefully."""
    global _temporal_client
    
    if _temporal_client is not None:
        try:
            logger.info("🔌 Closing Temporal client connection")
            await _temporal_client.close()
            _temporal_client = None
            logger.info("✅ Temporal client connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing Temporal client: {e}")
            raise


def reset_temporal_client():
    """Reset the client singleton (for testing only)."""
    global _temporal_client
    with _client_lock:
        _temporal_client = None
    logger.warning("⚠️ Temporal client singleton has been reset")
