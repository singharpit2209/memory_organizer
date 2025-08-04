"""
Logging module for the media organizer application.

This module provides centralized logging functionality with configurable
log levels and output formats.
"""

import logging
import sys
from typing import Optional

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logging.warning("tqdm not available. Progress bars will be disabled.")


class Logger:
    """
    Centralized logging configuration for the media organizer application.
    
    Provides consistent logging across all modules with configurable
    log levels and output formats.
    """
    
    def __init__(self, log_level: str = "INFO", log_file: Optional[str] = None):
        """
        Initialize the logger.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
        """
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_file = log_file
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging configuration."""
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler (if specified)
        if self.log_file:
            try:
                file_handler = logging.FileHandler(self.log_file, mode='w')
                file_handler.setLevel(self.log_level)
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                logging.info(f"Logging to file: {self.log_file}")
            except Exception as e:
                logging.error(f"Failed to set up file logging: {e}")
        
        # Set specific logger levels
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        logging.info("Logging system initialized")
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance for a specific module.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def log_operation_summary(self, total_files: int, processed_files: int, 
                            successful_operations: int, failed_operations: int):
        """
        Log a summary of file operations.
        
        Args:
            total_files: Total number of files found
            processed_files: Number of files processed
            successful_operations: Number of successful operations
            failed_operations: Number of failed operations
        """
        logger = logging.getLogger(__name__)
        
        logger.info("=" * 50)
        logger.info("OPERATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total files found: {total_files}")
        logger.info(f"Files processed: {processed_files}")
        logger.info(f"Successful operations: {successful_operations}")
        logger.info(f"Failed operations: {failed_operations}")
        
        if processed_files > 0:
            success_rate = (successful_operations / processed_files) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
        
        logger.info("=" * 50)
    
    def log_file_operation(self, operation: str, source: str, destination: str, 
                          success: bool, error: Optional[str] = None):
        """
        Log a file operation with details.
        
        Args:
            operation: Type of operation (copy/move)
            source: Source file path
            destination: Destination file path
            success: Whether the operation was successful
            error: Error message if operation failed
        """
        logger = logging.getLogger(__name__)
        
        if success:
            logger.info(f"{operation.upper()}: {source} -> {destination}")
        else:
            logger.error(f"{operation.upper()} FAILED: {source} -> {destination}")
            if error:
                logger.error(f"Error: {error}")
    
    def log_gps_extraction(self, file_path: str, coordinates: Optional[tuple], 
                          location: Optional[tuple]):
        """
        Log GPS extraction results.
        
        Args:
            file_path: Path to the file
            coordinates: GPS coordinates (lat, lon) if found
            location: Location (country, state) if geocoded
        """
        logger = logging.getLogger(__name__)
        
        if coordinates:
            lat, lon = coordinates
            logger.info(f"GPS found in {file_path}: ({lat:.6f}, {lon:.6f})")
            
            if location:
                country, state, city = location
                logger.info(f"Location: {country}, {state}, {city}")
            else:
                logger.warning(f"Could not geocode coordinates for {file_path}")
        else:
            logger.debug(f"No GPS data found in {file_path}")
    
    def log_progress(self, current: int, total: int, operation: str = "Processing"):
        """
        Log progress information.
        
        Args:
            current: Current item number
            total: Total number of items
            operation: Description of the operation
        """
        logger = logging.getLogger(__name__)
        
        if total > 0:
            percentage = (current / total) * 100
            logger.info(f"{operation}: {current}/{total} ({percentage:.1f}%)")
        else:
            logger.info(f"{operation}: {current} items")
    
    def create_progress_bar(self, total: int, desc: str = "Processing") -> Optional['tqdm']:
        """
        Create a progress bar for tracking operations.
        
        Args:
            total: Total number of items to process
            desc: Description for the progress bar
            
        Returns:
            tqdm progress bar instance or None if tqdm is not available
        """
        if TQDM_AVAILABLE and total > 0:
            return tqdm(total=total, desc=desc, unit="files", ncols=80)
        return None 