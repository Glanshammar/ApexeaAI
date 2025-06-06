import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from typing import Optional
import json
from datetime import datetime
import warnings

def _remove_duplicate_handlers(logger: logging.Logger) -> None:
    """Remove duplicate handlers from a logger."""
    seen = set()
    unique_handlers = []
    for handler in logger.handlers:
        if id(handler) not in seen:
            unique_handlers.append(handler)
            seen.add(id(handler))
    logger.handlers = unique_handlers

class StructuredLogFormatter(logging.Formatter):
    """Custom formatter that outputs logs in a structured format"""
    def format(self, record: logging.LogRecord) -> str:
        # Create a dictionary with all the log information
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
            
        return json.dumps(log_data)

class LoggerManager:
    _loggers: dict[str, logging.Logger] = {}
    _default_level: int = logging.INFO
    _default_max_bytes: int = 10 * 1024 * 1024  # 10MB
    _default_backup_count: int = 5

    @classmethod
    def get_logger(
        cls,
        name: str = __name__,
        filename: Optional[str] = None,
        level: Optional[int] = None,
        log_to_console: bool = False,
        max_bytes: Optional[int] = None,
        backup_count: Optional[int] = None
    ) -> logging.Logger:
        """
        Get or create a logger with the specified configuration.
        Args:
            name: Logger name (typically component name like 'api', 'agent', 'manager')
            filename: Log file path. If None, will be generated based on component name
            level: Logging level
            log_to_console: Whether to also log to console
            max_bytes: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
        Returns:
            Configured logger instance
        """
        if name in cls._loggers:
            logger = cls._loggers[name]
            _remove_duplicate_handlers(logger)
            return logger

        level = level if level is not None else cls._default_level
        max_bytes = max_bytes if max_bytes is not None else cls._default_max_bytes
        backup_count = backup_count if backup_count is not None else cls._default_backup_count

        if filename is None:
            module_path = os.path.relpath(name).replace('.', '_') + '.log'
            filename = os.path.join('logs', module_path)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.handlers.clear()

        try:
            # Create log directory if it doesn't exist
            log_dir = os.path.dirname(filename)
            os.makedirs(log_dir, exist_ok=True)

            # Create and configure file handler
            file_handler = RotatingFileHandler(
                filename,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)

            # Create formatters
            json_formatter = StructuredLogFormatter()
            file_handler.setFormatter(json_formatter)

            # Add file handler
            logger.addHandler(file_handler)

            # Add console handler if requested
            if log_to_console:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(level)
                # Use a more readable format for console
                console_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                console_handler.setFormatter(console_formatter)
                logger.addHandler(console_handler)

            _remove_duplicate_handlers(logger)
            cls._loggers[name] = logger

            return logger

        except Exception as e:
            # If file logging fails, fall back to console logging
            fallback_logger = logging.getLogger(name)
            fallback_logger.setLevel(level)
            
            fallback_logger.handlers.clear()
            
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(level)
            console_handler.setFormatter(logging.Formatter(
                'ERROR: Could not set up file logging. %(message)s'
            ))
            fallback_logger.addHandler(console_handler)
            
            fallback_logger.error(f"Failed to set up logging to {filename}: {str(e)}")
            return fallback_logger

    @classmethod
    def set_default_level(cls, level: int) -> None:
        """Set the default logging level for new loggers"""
        cls._default_level = level

    @classmethod
    def set_default_rotation(cls, max_bytes: int, backup_count: int) -> None:
        """Set the default rotation parameters for new loggers"""
        cls._default_max_bytes = max_bytes
        cls._default_backup_count = backup_count

def get_logger(
    name: str = __name__,
    filename: Optional[str] = None,
    level: int = logging.INFO,
    log_to_console: bool = False
) -> logging.Logger:
    """
    Preferred function to get a logger instance.
    Args:
        name: Logger name
        filename: Log file path
        level: Logging level
        log_to_console: Whether to also log to console
    Returns:
        Configured logger instance
    """
    return LoggerManager.get_logger(name, filename, level, log_to_console)