"""
Main entry point for the Media Organizer application.

This module handles user interaction and orchestrates the media organization
process, including file scanning, GPS extraction, geocoding, and file organization.
"""

import os
import sys
from pathlib import Path
from typing import Optional

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
    
    def __init__(self):
        """Initialize the media organizer application."""
        self.logger = Logger()
        self.log = self.logger.get_logger(__name__)
        
        self.metadata_extractor = MetadataExtractor()
        self.geocoder = Geocoder()
        self.file_organizer = None
        
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
        print("Files will be organized into Country/State folders based on GPS data.")
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
        
        return source_dir, dest_dir, operation, mode
    
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
            
            # Dictionary to track folder structure and file counts
            folder_structure = {}
            total_files = 0
            
            print("\n" + "="*60)
            print("ORGANIZATION PLAN")
            print("="*60)
            
            for i, file_path in enumerate(media_files, 1):
                self.logger.log_progress(i, len(media_files), "Analyzing files")
                
                try:
                    # Extract GPS coordinates
                    coordinates = self.metadata_extractor.extract_gps_coordinates(file_path)
                    
                    if coordinates:
                        # Reverse geocode coordinates
                        location = self.geocoder.reverse_geocode(*coordinates)
                        
                        if location:
                            country, state = location
                            folder_key = f"{country}/{state}"
                        else:
                            country, state = "Unknown", "Unknown"
                            folder_key = "Unknown"
                    else:
                        country, state = "Unknown", "Unknown"
                        folder_key = "Unknown"
                    
                    # Update folder structure
                    if folder_key not in folder_structure:
                        folder_structure[folder_key] = []
                    folder_structure[folder_key].append(file_path)
                    total_files += 1
                    
                except Exception as e:
                    self.log.error(f"Error analyzing {file_path}: {e}")
            
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
            
            # Process each file
            successful_operations = 0
            failed_operations = 0
            no_gps_files = 0
            geocoding_failed_files = 0
            
            for i, file_path in enumerate(media_files, 1):
                self.logger.log_progress(i, len(media_files), "Processing files")
                
                try:
                    success, gps_status = self._process_single_file(file_path, operation)
                    if success:
                        successful_operations += 1
                        if gps_status == "no_gps":
                            no_gps_files += 1
                        elif gps_status == "geocoding_failed":
                            geocoding_failed_files += 1
                    else:
                        failed_operations += 1
                        
                except Exception as e:
                    self.log.error(f"Error processing {file_path}: {e}")
                    failed_operations += 1
            
            # Log summary
            self.logger.log_operation_summary(
                len(media_files), len(media_files), 
                successful_operations, failed_operations
            )
            
            # Log GPS-related summary
            if no_gps_files > 0:
                self.log.info(f"Files without GPS data (moved to Unknown): {no_gps_files}")
            if geocoding_failed_files > 0:
                self.log.info(f"Files with GPS data but geocoding failed (moved to Unknown): {geocoding_failed_files}")
            
            return failed_operations == 0
            
        except Exception as e:
            self.log.error(f"Error during file processing: {e}")
            return False
    
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
                    country, state = location
                    self.logger.log_gps_extraction(file_path, coordinates, location)
                    gps_status = "success"
                else:
                    country, state = "Unknown", "Unknown"
                    self.logger.log_gps_extraction(file_path, coordinates, None)
                    self.log.info(f"File not moved - Geocoding failed: {file_path}")
                    gps_status = "geocoding_failed"
            else:
                country, state = "Unknown", "Unknown"
                self.logger.log_gps_extraction(file_path, None, None)
                self.log.info(f"File not moved - No GPS data found: {file_path}")
                gps_status = "no_gps"
            
            # Organize the file
            success = self.file_organizer.organize_file(
                file_path, country, state, operation
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
            source_dir, dest_dir, operation, mode = self.get_user_input()
            
            # Confirm operation
            print(f"\nSummary:")
            print(f"Source: {source_dir}")
            print(f"Destination: {dest_dir}")
            print(f"Operation: {operation}")
            print(f"Mode: {mode}")
            
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