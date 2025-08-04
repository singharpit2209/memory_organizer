"""
Main entry point for the Media Organizer application.

This module handles user interaction and orchestrates the media organization
process, including file scanning, GPS extraction, geocoding, and file organization.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .metadata_extractor import MetadataExtractor
from .geocoder import Geocoder
from .file_organizer import FileOrganizer
from .logger import Logger


class MediaOrganizer:
    """
    Main application class that orchestrates the media organization process.
    
    Handles user interaction, coordinates between different modules,
    and manages the overall workflow.
    """
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize the media organizer application.
        
        Args:
            max_workers: Maximum number of worker threads for concurrent processing
        """
        self.logger = Logger()
        self.log = self.logger.get_logger(__name__)
        
        self.metadata_extractor = MetadataExtractor()
        self.geocoder = Geocoder()
        self.file_organizer = None
        self.max_workers = max_workers
        
        self.log.info("Media Organizer initialized")
    
    def get_user_input(self) -> tuple:
        """
        Get user input for source directory, destination directory, operation type, and mode.
        
        Returns:
            Tuple of (source_dir, dest_dir, operation, mode)
        """
        print("\n" + "="*60)
        print("MEDIA ORGANIZER")
        print("="*60)
        print("This tool organizes media files by GPS location.")
        print("Files will be organized into Country/State/City folders based on GPS data.")
        print("Files without GPS data will be placed in Unknown folder.")
        print("="*60)
        
        # Get source directory
        while True:
            source_dir = input("\nEnter source directory path: ").strip()
            if os.path.exists(source_dir):
                break
            else:
                print(f"Error: Directory '{source_dir}' does not exist. Please try again.")
        
        # Get destination directory
        while True:
            dest_dir = input("Enter destination directory path: ").strip()
            if not dest_dir:
                print("Error: Destination directory cannot be empty. Please try again.")
                continue
            
            # Create destination directory if it doesn't exist
            try:
                Path(dest_dir).mkdir(parents=True, exist_ok=True)
                break
            except Exception as e:
                print(f"Error creating destination directory: {e}. Please try again.")
        
        # Get operation type
        while True:
            operation = input("Operation type (copy/move): ").strip().lower()
            if operation in ['copy', 'move']:
                break
            else:
                print("Error: Please enter 'copy' or 'move'.")
        
        # Get mode (plan or execute)
        while True:
            mode = input("Mode (plan/execute): ").strip().lower()
            if mode in ['plan', 'execute']:
                break
            else:
                print("Error: Please enter 'plan' or 'execute'.")
        
        # Get concurrent processing option (only for execute mode)
        max_workers = 16  # Increased default for better performance
        if mode == "execute":
            while True:
                try:
                    workers_input = input("Number of concurrent workers (1-32, default 16): ").strip()
                    if not workers_input:
                        break
                    max_workers = int(workers_input)
                    if 1 <= max_workers <= 32:
                        break
                    else:
                        print("Error: Please enter a number between 1 and 32.")
                except ValueError:
                    print("Error: Please enter a valid number.")
        
        return source_dir, dest_dir, operation, mode, max_workers
    
    def plan_organization(self, source_dir: str, dest_dir: str) -> bool:
        """
        Plan the organization of media files without actually moving/copying them.
        
        Args:
            source_dir: Source directory path
            dest_dir: Destination directory path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize file organizer
            self.file_organizer = FileOrganizer(dest_dir)
            
            # Scan for media files
            self.log.info(f"Scanning directory: {source_dir}")
            media_files = self.file_organizer.scan_directory(source_dir)
            
            if not media_files:
                self.log.warning("No media files found in the source directory.")
                return True
            
            self.log.info(f"Found {len(media_files)} media files to analyze")
            
            # Pre-filter files that likely have GPS data
            self.log.info("Pre-filtering files for GPS data...")
            files_with_gps = []
            files_without_gps = []
            
            progress_bar = self.logger.create_progress_bar(len(media_files), "Pre-filtering files")
            
            for file_path in media_files:
                if self.metadata_extractor.has_gps_data(file_path):
                    files_with_gps.append(file_path)
                else:
                    files_without_gps.append(file_path)
                if progress_bar:
                    progress_bar.update(1)
            
            if progress_bar:
                progress_bar.close()
            
            self.log.info(f"Files likely with GPS data: {len(files_with_gps)}")
            self.log.info(f"Files likely without GPS data: {len(files_without_gps)}")
            
            # Dictionary to track folder structure and file counts
            folder_structure = {}
            total_files = 0
            
            print("\n" + "="*60)
            print("ORGANIZATION PLAN")
            print("="*60)
            
            # Extract all GPS coordinates first for batch processing
            self.log.info("Extracting GPS coordinates for batch geocoding...")
            coordinates_data = []
            
            progress_bar = self.logger.create_progress_bar(len(files_with_gps), "Extracting GPS coordinates")
            
            for file_path in files_with_gps:
                try:
                    coordinates = self.metadata_extractor.extract_gps_coordinates(file_path)
                    if coordinates:
                        coordinates_data.append((file_path, coordinates))
                    else:
                        # File without GPS data goes to Unknown
                        if "Unknown" not in folder_structure:
                            folder_structure["Unknown"] = []
                        folder_structure["Unknown"].append(file_path)
                        total_files += 1
                except Exception as e:
                    self.log.error(f"Error extracting GPS from {file_path}: {e}")
                    # Add to Unknown folder
                    if "Unknown" not in folder_structure:
                        folder_structure["Unknown"] = []
                    folder_structure["Unknown"].append(file_path)
                    total_files += 1
                
                if progress_bar:
                    progress_bar.update(1)
            
            if progress_bar:
                progress_bar.close()
            
            # Batch geocode all coordinates with timeout
            if coordinates_data:
                self.log.info(f"Batch geocoding {len(coordinates_data)} coordinates...")
                all_coordinates = [coords for _, coords in coordinates_data]
                
                # For large datasets, offer a fast mode that skips geocoding
                if len(coordinates_data) > 1000:
                    print(f"\n⚠️  Large dataset detected ({len(coordinates_data)} files with GPS data)")
                    print("Geocoding may take a very long time due to API rate limits.")
                    fast_mode = input("Use fast mode (skip geocoding, all files go to Unknown)? (y/n): ").strip().lower()
                    
                    if fast_mode in ['y', 'yes']:
                        self.log.info("Using fast mode - skipping geocoding for large dataset")
                        geocoding_results = {}
                        # All files will go to Unknown folder
                        for file_path, coordinates in coordinates_data:
                            if "Unknown" not in folder_structure:
                                folder_structure["Unknown"] = []
                            folder_structure["Unknown"].append(file_path)
                            total_files += 1
                    else:
                            # Try geocoding with timeout (cross-platform)
                            try:
                                import threading
                                import time
                                
                                geocoding_results = {}
                                geocoding_completed = threading.Event()
                                geocoding_error = None
                                
                                def geocoding_worker():
                                    nonlocal geocoding_results, geocoding_error
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(all_coordinates)
                                        geocoding_completed.set()
                                    except Exception as e:
                                        geocoding_error = e
                                        geocoding_completed.set()
                                
                                # Start geocoding in a separate thread
                                geocoding_thread = threading.Thread(target=geocoding_worker)
                                geocoding_thread.daemon = True
                                geocoding_thread.start()
                                
                                # Wait for completion or timeout (15 minutes - increased for better coverage)
                                if not geocoding_completed.wait(timeout=900):
                                    self.log.warning("Geocoding timed out - trying with larger batch")
                                    # Try with a much larger sample of coordinates for better coverage
                                    sample_size = min(5000, len(all_coordinates))  # Try up to 2000 coordinates
                                    if len(all_coordinates) > sample_size:
                                        # Take samples from beginning, middle, and end for better coverage
                                        step = len(all_coordinates) // sample_size
                                        sample_coordinates = all_coordinates[::step][:sample_size]
                                    else:
                                        sample_coordinates = all_coordinates
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(sample_coordinates)
                                        # For coordinates not in the sample, use Unknown
                                        for file_path, coordinates in coordinates_data:
                                            if coordinates in geocoding_results:
                                                location = geocoding_results.get(coordinates)
                                                if location:
                                                    country, state, city = location
                                                    folder_key = f"{country}/{state}/{city}"
                                                else:
                                                    folder_key = "Unknown"
                                            else:
                                                folder_key = "Unknown"
                                            
                                            if folder_key not in folder_structure:
                                                folder_structure[folder_key] = []
                                            folder_structure[folder_key].append(file_path)
                                            total_files += 1
                                    except Exception as e:
                                        self.log.error(f"Even sample geocoding failed: {e} - using fast mode")
                                        # All files will go to Unknown folder
                                        for file_path, coordinates in coordinates_data:
                                            if "Unknown" not in folder_structure:
                                                folder_structure["Unknown"] = []
                                            folder_structure["Unknown"].append(file_path)
                                            total_files += 1
                                elif geocoding_error:
                                    self.log.error(f"Geocoding failed: {geocoding_error} - trying with larger batch")
                                    # Try with a much larger sample of coordinates for better coverage
                                    sample_size = min(5000, len(all_coordinates))  # Try up to 2000 coordinates
                                    if len(all_coordinates) > sample_size:
                                        # Take samples from beginning, middle, and end for better coverage
                                        step = len(all_coordinates) // sample_size
                                        sample_coordinates = all_coordinates[::step][:sample_size]
                                    else:
                                        sample_coordinates = all_coordinates
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(sample_coordinates)
                                        # For coordinates not in the sample, use Unknown
                                        for file_path, coordinates in coordinates_data:
                                            if coordinates in geocoding_results:
                                                location = geocoding_results.get(coordinates)
                                                if location:
                                                    country, state, city = location
                                                    folder_key = f"{country}/{state}/{city}"
                                                else:
                                                    folder_key = "Unknown"
                                            else:
                                                folder_key = "Unknown"
                                            
                                            if folder_key not in folder_structure:
                                                folder_structure[folder_key] = []
                                            folder_structure[folder_key].append(file_path)
                                            total_files += 1
                                    except Exception as e:
                                        self.log.error(f"Even sample geocoding failed: {e} - using fast mode")
                                        # All files will go to Unknown folder
                                        for file_path, coordinates in coordinates_data:
                                            if "Unknown" not in folder_structure:
                                                folder_structure["Unknown"] = []
                                            folder_structure["Unknown"].append(file_path)
                                            total_files += 1
                                
                            except Exception as e:
                                self.log.error(f"Geocoding failed: {e} - using fast mode")
                                geocoding_results = {}
                                # All files will go to Unknown folder
                                for file_path, coordinates in coordinates_data:
                                    if "Unknown" not in folder_structure:
                                        folder_structure["Unknown"] = []
                                    folder_structure["Unknown"].append(file_path)
                                    total_files += 1
                else:
                    # For smaller datasets, proceed normally
                    geocoding_results = self.geocoder.batch_reverse_geocode(all_coordinates)
                
                # Process results
                progress_bar = self.logger.create_progress_bar(len(coordinates_data), "Processing geocoding results")
                
                for file_path, coordinates in coordinates_data:
                    location = geocoding_results.get(coordinates)
                    
                    if location:
                        country, state, city = location
                        folder_key = f"{country}/{state}/{city}"
                    else:
                        country, state, city = "Unknown", "Unknown", "Unknown"
                        folder_key = "Unknown"
                    
                    # Update folder structure
                    if folder_key not in folder_structure:
                        folder_structure[folder_key] = []
                    folder_structure[folder_key].append(file_path)
                    total_files += 1
                    
                    if progress_bar:
                        progress_bar.update(1)
                
                if progress_bar:
                    progress_bar.close()
            
            # Add files without GPS data to Unknown folder
            if files_without_gps:
                if "Unknown" not in folder_structure:
                    folder_structure["Unknown"] = []
                folder_structure["Unknown"].extend(files_without_gps)
                total_files += len(files_without_gps)
            
            # Display the plan
            print(f"\nTotal files to process: {total_files}")
            print(f"Folders that will be created: {len(folder_structure)}")
            print("\nFolder Structure:")
            print("-" * 40)
            
            for folder, files in sorted(folder_structure.items()):
                print(f"{folder}/ ({len(files)} files)")
                for file_path in files[:3]:  # Show first 3 files as examples
                    filename = Path(file_path).name
                    print(f"  - {filename}")
                if len(files) > 3:
                    print(f"  ... and {len(files) - 3} more files")
                print()
            
            # Show cache statistics
            cache_stats = self.geocoder.get_cache_stats()
            print(f"Geocoding cache: {cache_stats['cache_hits']} hits, {cache_stats['cache_misses']} misses ({cache_stats['hit_rate_percent']}% hit rate)")
            
            # Note about skipped files (during planning, we can't know exact count)
            print("\nNote: During execution, files that already exist in the destination")
            print("with identical content will be skipped to avoid duplicates.")
            
            print("="*60)
            return True
            
        except Exception as e:
            self.log.error(f"Error during planning: {e}")
            return False
    
    def process_files(self, source_dir: str, dest_dir: str, operation: str) -> bool:
        """
        Process all media files in the source directory.
        
        Args:
            source_dir: Source directory path
            dest_dir: Destination directory path
            operation: Operation type ('copy' or 'move')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize file organizer
            self.file_organizer = FileOrganizer(dest_dir)
            
            # Scan for media files
            self.log.info(f"Scanning directory: {source_dir}")
            media_files = self.file_organizer.scan_directory(source_dir)
            
            if not media_files:
                self.log.warning("No media files found in the source directory.")
                return True
            
            self.log.info(f"Found {len(media_files)} media files to process")
            
            # Pre-filter files that likely have GPS data
            self.log.info("Pre-filtering files for GPS data...")
            files_with_gps = []
            files_without_gps = []
            
            progress_bar = self.logger.create_progress_bar(len(media_files), "Pre-filtering files")
            
            for file_path in media_files:
                if self.metadata_extractor.has_gps_data(file_path):
                    files_with_gps.append(file_path)
                else:
                    files_without_gps.append(file_path)
                if progress_bar:
                    progress_bar.update(1)
            
            if progress_bar:
                progress_bar.close()
            
            self.log.info(f"Files likely with GPS data: {len(files_with_gps)}")
            self.log.info(f"Files likely without GPS data: {len(files_without_gps)}")
            
            # Process files with likely GPS data using concurrent processing
            successful_operations = 0
            failed_operations = 0
            no_gps_files = 0
            geocoding_failed_files = 0
            
            if files_with_gps:
                self.log.info(f"Processing {len(files_with_gps)} files with GPS data using batch geocoding")
                
                # Extract all GPS coordinates first for batch processing
                self.log.info("Extracting GPS coordinates for batch geocoding...")
                coordinates_data = []
                
                progress_bar = self.logger.create_progress_bar(len(files_with_gps), "Extracting GPS coordinates")
                
                for file_path in files_with_gps:
                    try:
                        coordinates = self.metadata_extractor.extract_gps_coordinates(file_path)
                        if coordinates:
                            coordinates_data.append((file_path, coordinates))
                        else:
                            # File without GPS data - will be handled after geocoding
                            coordinates_data.append((file_path, None))
                    except Exception as e:
                        self.log.error(f"Error extracting GPS from {file_path}: {e}")
                        # File with error - will be handled after geocoding
                        coordinates_data.append((file_path, None))
                    
                    if progress_bar:
                        progress_bar.update(1)
                
                if progress_bar:
                    progress_bar.close()
                
                # Batch geocode all coordinates with timeout
                if coordinates_data:
                    # Filter out None coordinates for geocoding
                    valid_coordinates_data = [(file_path, coords) for file_path, coords in coordinates_data if coords is not None]
                    all_coordinates = [coords for _, coords in valid_coordinates_data]
                    
                    self.log.info(f"Batch geocoding {len(valid_coordinates_data)} coordinates...")
                    
                    # For large datasets, offer a fast mode that skips geocoding
                    if len(coordinates_data) > 1000:
                        print(f"\n⚠️  Large dataset detected ({len(coordinates_data)} files with GPS data)")
                        print("Geocoding may take a very long time due to API rate limits.")
                        fast_mode = input("Use fast mode (skip geocoding, all files go to Unknown)? (y/n): ").strip().lower()
                        
                        if fast_mode in ['y', 'yes']:
                            self.log.info("Using fast mode - skipping geocoding for large dataset")
                            geocoding_results = {}
                            # All files will go to Unknown folder
                            for file_path, coordinates in coordinates_data:
                                success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                if success:
                                    successful_operations += 1
                                    no_gps_files += 1
                                else:
                                    failed_operations += 1
                        else:
                            # Try geocoding with timeout (cross-platform)
                            try:
                                import threading
                                import time
                                
                                geocoding_results = {}
                                geocoding_completed = threading.Event()
                                geocoding_error = None
                                
                                def geocoding_worker():
                                    nonlocal geocoding_results, geocoding_error
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(all_coordinates)
                                        geocoding_completed.set()
                                    except Exception as e:
                                        geocoding_error = e
                                        geocoding_completed.set()
                                
                                # Start geocoding in a separate thread
                                geocoding_thread = threading.Thread(target=geocoding_worker)
                                geocoding_thread.daemon = True
                                geocoding_thread.start()
                                
                                # Wait for completion or timeout (15 minutes - increased for better coverage)
                                if not geocoding_completed.wait(timeout=900):
                                    self.log.warning("Geocoding timed out - trying with larger batch")
                                    # Try with a much larger sample of coordinates for better coverage
                                    sample_size = min(5000, len(all_coordinates))  # Try up to 2000 coordinates
                                    if len(all_coordinates) > sample_size:
                                        # Take samples from beginning, middle, and end for better coverage
                                        step = len(all_coordinates) // sample_size
                                        sample_coordinates = all_coordinates[::step][:sample_size]
                                    else:
                                        sample_coordinates = all_coordinates
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(sample_coordinates)
                                        # Process files with available geocoding results
                                        for file_path, coordinates in coordinates_data:
                                            if coordinates in geocoding_results:
                                                location = geocoding_results.get(coordinates)
                                                if location:
                                                    country, state, city = location
                                                    success = self.file_organizer.organize_file(file_path, country, state, city, operation)
                                                else:
                                                    success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            else:
                                                # Coordinate not in sample, go to Unknown
                                                success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            
                                            if success:
                                                successful_operations += 1
                                                if location:
                                                    pass  # Successfully geocoded
                                                else:
                                                    no_gps_files += 1
                                            else:
                                                failed_operations += 1
                                    except Exception as e:
                                        self.log.error(f"Even sample geocoding failed: {e} - using fast mode")
                                        # All files will go to Unknown folder
                                        for file_path, coordinates in coordinates_data:
                                            success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            if success:
                                                successful_operations += 1
                                                no_gps_files += 1
                                            else:
                                                failed_operations += 1
                                elif geocoding_error:
                                    self.log.error(f"Geocoding failed: {geocoding_error} - trying with larger batch")
                                    # Try with a much larger sample of coordinates for better coverage
                                    sample_size = min(5000, len(all_coordinates))  # Try up to 2000 coordinates
                                    if len(all_coordinates) > sample_size:
                                        # Take samples from beginning, middle, and end for better coverage
                                        step = len(all_coordinates) // sample_size
                                        sample_coordinates = all_coordinates[::step][:sample_size]
                                    else:
                                        sample_coordinates = all_coordinates
                                    try:
                                        geocoding_results = self.geocoder.batch_reverse_geocode(sample_coordinates)
                                        # Process files with available geocoding results
                                        for file_path, coordinates in coordinates_data:
                                            if coordinates in geocoding_results:
                                                location = geocoding_results.get(coordinates)
                                                if location:
                                                    country, state, city = location
                                                    success = self.file_organizer.organize_file(file_path, country, state, city, operation)
                                                else:
                                                    success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            else:
                                                # Coordinate not in sample, go to Unknown
                                                success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            
                                            if success:
                                                successful_operations += 1
                                                if location:
                                                    pass  # Successfully geocoded
                                                else:
                                                    no_gps_files += 1
                                            else:
                                                failed_operations += 1
                                    except Exception as e:
                                        self.log.error(f"Even sample geocoding failed: {e} - using fast mode")
                                        # All files will go to Unknown folder
                                        for file_path, coordinates in coordinates_data:
                                            success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                            if success:
                                                successful_operations += 1
                                                no_gps_files += 1
                                            else:
                                                failed_operations += 1
                                
                            except Exception as e:
                                self.log.error(f"Geocoding failed: {e} - using fast mode")
                                geocoding_results = {}
                                # All files will go to Unknown folder
                                for file_path, coordinates in coordinates_data:
                                    success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                                    if success:
                                        successful_operations += 1
                                        no_gps_files += 1
                                    else:
                                        failed_operations += 1
                    else:
                        # For smaller datasets, proceed normally
                        geocoding_results = self.geocoder.batch_reverse_geocode(all_coordinates)
                    
                    # Process results with concurrent file operations
                    self.log.info(f"Processing {len(coordinates_data)} files with geocoded results")
                    
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        # Submit all file operations
                        future_to_file = {}
                        for file_path, coordinates in coordinates_data:
                            if coordinates is None:
                                # File without GPS data - process directly
                                future = executor.submit(self._process_file_without_gps, file_path, operation)
                                future_to_file[future] = file_path
                            else:
                                # File with GPS data - process with geocoding results
                                future = executor.submit(self._process_file_with_location, file_path, coordinates, geocoding_results, operation)
                                future_to_file[future] = file_path
                        
                        # Process completed tasks with progress bar
                        progress_bar = self.logger.create_progress_bar(len(coordinates_data), "Processing files with GPS data")
                        
                        for future in as_completed(future_to_file):
                            file_path = future_to_file[future]
                            try:
                                success, gps_status = future.result()
                                if success:
                                    successful_operations += 1
                                    if gps_status == "geocoding_failed":
                                        geocoding_failed_files += 1
                                    elif gps_status == "no_gps":
                                        no_gps_files += 1
                                else:
                                    failed_operations += 1
                            except Exception as e:
                                self.log.error(f"Error processing {file_path}: {e}")
                                failed_operations += 1
                            
                            if progress_bar:
                                progress_bar.update(1)
                        
                        if progress_bar:
                            progress_bar.close()
            
            # Process files without GPS data (fast path)
            if files_without_gps:
                self.log.info(f"Processing {len(files_without_gps)} files without GPS data")
                
                progress_bar = self.logger.create_progress_bar(len(files_without_gps), "Processing non-GPS files")
                
                for file_path in files_without_gps:
                    try:
                        success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
                        if success:
                            successful_operations += 1
                            no_gps_files += 1
                        else:
                            failed_operations += 1
                    except Exception as e:
                        self.log.error(f"Error processing {file_path}: {e}")
                        failed_operations += 1
                    
                    if progress_bar:
                        progress_bar.update(1)
                
                if progress_bar:
                    progress_bar.close()
            
            # Get skipped files count
            skipped_files_count = self.file_organizer.get_skipped_files_count()
            
            # Log summary
            self.logger.log_operation_summary(
                len(media_files), len(media_files), 
                successful_operations, failed_operations,
                skipped_files_count
            )
            
            # Log GPS-related summary
            if no_gps_files > 0:
                self.log.info(f"Files without GPS data (moved to Unknown): {no_gps_files}")
            if geocoding_failed_files > 0:
                self.log.info(f"Files with GPS data but geocoding failed (moved to Unknown): {geocoding_failed_files}")
            
            # Show cache statistics
            cache_stats = self.geocoder.get_cache_stats()
            self.log.info(f"Geocoding cache: {cache_stats['cache_hits']} hits, {cache_stats['cache_misses']} misses ({cache_stats['hit_rate_percent']}% hit rate)")
            
            dir_cache_stats = self.file_organizer.get_directory_cache_stats()
            self.log.info(f"Directory cache: {dir_cache_stats['cached_directories']} directories cached")
            
            return failed_operations == 0
            
        except Exception as e:
            self.log.error(f"Error during file processing: {e}")
            return False
    
    def _process_file_without_gps(self, file_path: str, operation: str) -> tuple:
        """
        Process a single media file without GPS data.
        
        Args:
            file_path: Path to the media file
            operation: Operation type ('copy' or 'move')
            
        Returns:
            Tuple of (success, gps_status) where gps_status is "no_gps"
        """
        try:
            # File without GPS data goes to Unknown
            success = self.file_organizer.organize_file(file_path, "Unknown", "Unknown", "Unknown", operation)
            return success, "no_gps"
        except Exception as e:
            self.log.error(f"Error processing {file_path}: {e}")
            return False, "error"
    
    def _process_file_with_location(self, file_path: str, coordinates: tuple, geocoding_results: dict, operation: str) -> tuple:
        """
        Process a single media file with pre-geocoded location data.
        
        Args:
            file_path: Path to the media file
            coordinates: GPS coordinates (lat, lon)
            geocoding_results: Dictionary of geocoding results
            operation: Operation type ('copy' or 'move')
            
        Returns:
            Tuple of (success, gps_status) where gps_status is:
            - "success" if GPS data found and geocoded successfully
            - "geocoding_failed" if GPS data found but geocoding failed
        """
        try:
            # Get location from batch geocoding results
            location = geocoding_results.get(coordinates)
            
            if location:
                country, state, city = location
                self.logger.log_gps_extraction(file_path, coordinates, location)
                gps_status = "success"
            else:
                country, state, city = "Unknown", "Unknown", "Unknown"
                self.logger.log_gps_extraction(file_path, coordinates, None)
                self.log.info(f"File not moved - Geocoding failed: {file_path}")
                gps_status = "geocoding_failed"
            
            # Organize the file
            success = self.file_organizer.organize_file(
                file_path, country, state, city, operation
            )
            
            return success, gps_status
            
        except Exception as e:
            self.log.error(f"Error processing {file_path}: {e}")
            return False, "error"
    
    def _smart_sample_coordinates(self, coordinates: list, sample_size: int) -> list:
        """
        Create a smart sample of coordinates for better geocoding coverage.
        
        Args:
            coordinates: List of all coordinates
            sample_size: Target sample size
            
        Returns:
            Smartly sampled coordinates
        """
        if len(coordinates) <= sample_size:
            return coordinates
        
        import random
        
        # Take systematic samples (beginning, middle, end)
        systematic_count = sample_size // 2
        step = len(coordinates) // systematic_count
        systematic_samples = coordinates[::step][:systematic_count]
        
        # Take random samples for better distribution
        remaining_count = sample_size - len(systematic_samples)
        remaining_coords = [coord for coord in coordinates if coord not in systematic_samples]
        random_samples = random.sample(remaining_coords, min(remaining_count, len(remaining_coords)))
        
        # Combine and deduplicate
        all_samples = systematic_samples + random_samples
        return list(dict.fromkeys(all_samples))  # Remove duplicates while preserving order
    
    def _process_single_file(self, file_path: str, operation: str) -> tuple:
        """
        Process a single media file.
        
        Args:
            file_path: Path to the media file
            operation: Operation type ('copy' or 'move')
            
        Returns:
            Tuple of (success, gps_status) where gps_status is:
            - "success" if GPS data found and geocoded successfully
            - "no_gps" if no GPS data found
            - "geocoding_failed" if GPS data found but geocoding failed
        """
        try:
            # Extract GPS coordinates
            coordinates = self.metadata_extractor.extract_gps_coordinates(file_path)
            
            if coordinates:
                # Reverse geocode coordinates
                location = self.geocoder.reverse_geocode(*coordinates)
                
                if location:
                    country, state, city = location
                    self.logger.log_gps_extraction(file_path, coordinates, location)
                    gps_status = "success"
                else:
                    country, state, city = "Unknown", "Unknown", "Unknown"
                    self.logger.log_gps_extraction(file_path, coordinates, None)
                    self.log.info(f"File not moved - Geocoding failed: {file_path}")
                    gps_status = "geocoding_failed"
            else:
                country, state, city = "Unknown", "Unknown", "Unknown"
                self.logger.log_gps_extraction(file_path, None, None)
                self.log.info(f"File not moved - No GPS data found: {file_path}")
                gps_status = "no_gps"
            
            # Organize the file
            success = self.file_organizer.organize_file(
                file_path, country, state, city, operation
            )
            
            return success, gps_status
            
        except Exception as e:
            self.log.error(f"Error processing {file_path}: {e}")
            return False, "error"
    
    def run(self) -> bool:
        """
        Run the media organizer application.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get user input
            source_dir, dest_dir, operation, mode, max_workers = self.get_user_input()
            
            # Update max_workers for this session
            self.max_workers = max_workers
            
            # Confirm operation
            print(f"\nSummary:")
            print(f"Source: {source_dir}")
            print(f"Destination: {dest_dir}")
            print(f"Operation: {operation}")
            print(f"Mode: {mode}")
            if mode == "execute":
                print(f"Concurrent workers: {max_workers}")
            
            confirm = input("\nProceed? (y/n): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Operation cancelled.")
                return True
            
            # Execute based on mode
            if mode == "plan":
                success = self.plan_organization(source_dir, dest_dir)
                if success:
                    print("\nPlanning completed successfully!")
                else:
                    print("\nPlanning completed with some errors. Check the log for details.")
            else:  # execute mode
                success = self.process_files(source_dir, dest_dir, operation)
                if success:
                    print("\nOperation completed successfully!")
                else:
                    print("\nOperation completed with some errors. Check the log for details.")
            
            return success
            
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return False
        except Exception as e:
            self.log.error(f"Unexpected error: {e}")
            print(f"\nAn unexpected error occurred: {e}")
            return False


def main():
    """Main entry point for the application."""
    try:
        organizer = MediaOrganizer()
        success = organizer.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 