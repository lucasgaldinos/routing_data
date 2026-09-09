"""Logging configuration for converter operations."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str | None = None) -> logging.Logger:
  """
  Configure logging with file and console handlers.

  Args:
      level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
      log_file: Optional path to log file

  Returns:
      Configured logger instance
  """
  logger = logging.getLogger("converter")
  logger.setLevel(getattr(logging, level.upper()))

  # Disable propagation to prevent child loggers from duplicating messages
  logger.propagate = False

  # Remove existing handlers to avoid duplicates
  logger.handlers.clear()

  formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

  # Console handler
  console_handler = logging.StreamHandler(sys.stdout)
  console_handler.setFormatter(formatter)
  logger.addHandler(console_handler)

  # File handler if specified
  if log_file:
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

  return logger
