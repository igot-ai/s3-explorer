"""
Centralized logging configuration using loguru.

This module provides a centralized logging setup that overrides Python's standard logging
and provides structured, colored logging suitable for both development and production.

Usage:
    from app._logging import get_logger

    logger = get_logger(__name__)
    logger.info("This is an info message")
    logger.error("This is an error message")
"""

import logging as stdlib_logging
import os
import sys
from pathlib import Path
from typing import Optional

LOG_PATH = "logs"

# Global variable to hold the logger once initialized
_logger = None

# Environment detection
ENV = os.getenv("ENVIRONMENT", "development").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if ENV == "development" else "INFO").upper()


class InterceptHandler(stdlib_logging.Handler):
    """
    Logging handler that intercepts standard library logging calls
    and redirects them to loguru.
    """

    def emit(self, record):
        # Get the global logger instance
        global _logger
        if _logger is None:
            return  # Skip if logger not initialized yet

        # Get corresponding Loguru level if it exists
        try:
            level = _logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == stdlib_logging.__file__:
            frame = frame.f_back
            depth += 1

        _logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    """
    Setup centralized logging configuration.

    This function:
    1. Removes default loguru handler
    2. Configures environment-specific log handlers
    3. Intercepts standard library logging
    4. Sets up structured logging format
    """
    global _logger

    # Import loguru only when needed to avoid circular imports
    from loguru import logger

    _logger = logger

    # Get persistent log directory
    log_dir = Path(LOG_PATH)

    # Remove default loguru handler
    logger.remove()

    # Development configuration
    if ENV == "development":
        # Console handler with colors and detailed format
        logger.add(
            sys.__stderr__,
            level=LOG_LEVEL,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>",
            colorize=True,
            backtrace=True,
            diagnose=True,
            catch=True,
        )

        # File handler for errors
        logger.add(
            log_dir / "error.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            backtrace=True,
            diagnose=True,
            catch=True,
        )

    # Production configuration
    else:
        # Console handler with JSON format for structured logging
        logger.add(
            sys.__stderr__,
            level=LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            colorize=False,
            catch=True,
        )

        # Application logs
        logger.add(
            log_dir / "app.log",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            rotation="50 MB",
            retention="30 days",
            compression="zip",
            catch=True,
        )

        # Error logs
        logger.add(
            log_dir / "error.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message} | {extra}",
            rotation="50 MB",
            retention="90 days",
            compression="zip",
            backtrace=True,
            diagnose=False,  # Disable in production for security
            catch=True,
        )

    # Intercept standard library logging
    stdlib_logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Intercept specific loggers that might be used by dependencies
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "sqlalchemy",
        "alembic",
        "sentence_transformers",
        "transformers",
        "torch",
        "httpx",
        "kuzu",
        "llama_index",
    ]:
        stdlib_logging.getLogger(logger_name).handlers = [InterceptHandler()]
        stdlib_logging.getLogger(logger_name).propagate = False

    logger.info(f"Logging configured for {ENV} environment with level {LOG_LEVEL}")


def get_logger(name: Optional[str] = None):
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured loguru logger instance

    Example:
        logger = get_logger(__name__)
        logger.info("Application started")
    """
    # Ensure logging is set up before returning logger
    _ensure_logging_setup()

    global _logger
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call setup_logging() first.")

    if name:
        return _logger.bind(name=name)
    return _logger


# Global flag to track if logging has been initialized
_logging_initialized = False


def _ensure_logging_setup():
    """Ensure logging is set up (lazy initialization)."""
    global _logging_initialized
    if not _logging_initialized:
        setup_logging()
        _logging_initialized = True


def getLogger(name: str):
    return get_logger(name)


# Export the logger for direct use
__all__ = ["get_logger", "setup_logging", "getLogger"]
