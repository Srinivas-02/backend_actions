"""
Custom Logger Module for POS Backend
Provides colored logging with different log levels and formatting
"""

import logging
import os
from typing import Optional

import coloredlogs

# Default log levels
LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG
}

# Get log level from environment or default to INFO
LOG_LEVEL = os.environ.get("POS_LOG_LEVEL", "INFO")

# Custom colored formatter configuration
COLORED_FORMATTER = coloredlogs.ColoredFormatter(
    fmt="[%(asctime)s] [%(hostname)s] [%(name)s] [%(levelname)s] %(message)s",
    level_styles={
        'debug': {'color': 'white'},
        'info': {'color': 'green'},
        'warning': {'color': 'yellow', 'bright': True},
        'error': {'color': 'red', 'bold': True, 'bright': True},
        'critical': {'color': 'black', 'bold': True, 'background': 'red'}
    },
    field_styles={
        'asctime': {'color': 'white'},
        'hostname': {'color': 'magenta'},
        'name': {'color': 'blue', 'bright': True},
        'levelname': {'color': 'white', 'bold': True},
        'message': {'color': 'white'}
    },
    datefmt="%Y-%m-%d %H:%M:%S"
)


class POSLogger:
    """
    Custom logger class for POS Backend application
    Provides colored logging with different severity levels
    """
    
    def __init__(self, module_name: str = "", level: Optional[str] = None) -> None:
        """
        Initialize logger with module name and log level
        
        Args:
            module_name (str): Name of the module using the logger
            level (Optional[str]): Log level, defaults to LOG_LEVEL from env
        """
        self.logger = logging.getLogger(module_name)
        
        if not self.logger.handlers:
            # Install colored logs
            coloredlogs.install(logger=self.logger)
            
            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(COLORED_FORMATTER)
            console_handler.addFilter(coloredlogs.HostNameFilter())
            
            # Add handler to logger
            self.logger.addHandler(console_handler)
            
            # Set log level
            log_level = level if level else LOG_LEVEL
            self.logger.setLevel(LOG_LEVELS.get(log_level, LOG_LEVELS["INFO"]))
            
            # Prevent duplicate logs
            self.logger.propagate = False
    
    def debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False) -> None:
        """
        Log error message
        
        Args:
            message (str): Error message
            exc_info (bool): Include exception traceback if True
        """
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False) -> None:
        """
        Log critical message
        
        Args:
            message (str): Critical error message
            exc_info (bool): Include exception traceback if True
        """
        self.logger.critical(message, exc_info=exc_info)


# Example usage:
# logger = POSLogger(__name__)
# logger.info("Server started successfully")
# logger.error("Database connection failed", exc_info=True) 