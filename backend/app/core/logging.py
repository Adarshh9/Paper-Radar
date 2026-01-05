"""
Centralized logging configuration using Loguru.
Provides structured, colored, and rotated logging for the application.
"""
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """
    Configure Loguru for the application.
    
    Features:
    - Colored console output for development
    - JSON structured logs for production
    - File rotation with compression
    - Request correlation IDs
    """
    # Remove default handler
    logger.remove()
    
    # Console handler with colors (always enabled)
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    if settings.environment == "development":
        # Pretty console output for development
        logger.add(
            sys.stderr,
            format=log_format,
            level="DEBUG",
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # JSON format for production (easier to parse in log aggregators)
        logger.add(
            sys.stderr,
            format="{message}",
            level="INFO",
            serialize=True,  # JSON output
            backtrace=False,
            diagnose=False,
        )
    
    # File handler with rotation
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "paper_radar_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # New file at midnight
        retention="30 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG" if settings.environment == "development" else "INFO",
        enqueue=True,  # Thread-safe async logging
    )
    
    # Separate error log
    logger.add(
        log_dir / "paper_radar_errors_{time:YYYY-MM-DD}.log",
        rotation="00:00",
        retention="90 days",
        compression="gz",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="ERROR",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )


def get_logger(name: str) -> Any:
    """
    Get a logger instance bound with the module name.
    
    Usage:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logger.bind(name=name)


# Initialize on import
setup_logging()
