"""
File organization module for media files.

This module handles file operations including copying, moving, and
organizing files into directory structures based on location data.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict


class FileOrganizer:
    """
    Handles file organization operations including copying, moving,
    and creating directory structures for media files.
    """
    
    def __init__(self, destination_root: str, folder_structure: str = "city"):
        """
        Initialize the file organizer.
        
        Args:
            destination_root: Root directory for organized files
            folder_structure: "state" for Country/State or "city" for Country/State/City
        """
        self.logger = logging.getLogger(__name__)
        self.destination_root = Path(destination_root)
        self.folder_structure = folder_structure
        
        # Cache for created directories to avoid repeated mkdir calls
        self._directory_cache = {}
        
        # Counter for skipped files
        self.skipped_files_count = 0
        
        # Ensure destination root exists
        self.destination_root.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Destination root: {self.destination_root}")
    
    def create_location_directory(self, country: str, state: str, city: str) -> Path:
        """
        Create directory structure for a specific location.
        
        Args:
            country: Country name
            state: State/province name
            city: City name
            
        Returns:
            Path to the created directory
        """
        # Clean directory names for filesystem compatibility
        safe_country = self._sanitize_filename(country)
        safe_state = self._sanitize_filename(state)
        safe_city = self._sanitize_filename(city)
        
        # Create cache key based on folder structure
        if self.folder_structure == "state":
            cache_key = f"{safe_country}:{safe_state}"
        else:
            cache_key = f"{safe_country}:{safe_state}:{safe_city}"
        
        # Check cache first
        if cache_key in self._directory_cache:
            return self._directory_cache[cache_key]
        
        # Special handling for Unknown location - create single Unknown folder
        if safe_country == "Unknown" and safe_state == "Unknown" and safe_city == "Unknown":
            location_path = self.destination_root / "Unknown"
        else:
            # Create directory structure based on user preference
            if self.folder_structure == "state":
                # Country/State structure
                location_path = self.destination_root / safe_country / safe_state
            else:
                # Country/State/City structure (default)
                location_path = self.destination_root / safe_country / safe_state / safe_city
        
        try:
            location_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {location_path}")
            # Cache the result
            self._directory_cache[cache_key] = location_path
            return location_path
        except Exception as e:
            self.logger.error(f"Failed to create directory {location_path}: {e}")
            # Fallback to Unknown directory
            return self.create_location_directory("Unknown", "Unknown", "Unknown")
    
    def get_directory_cache_stats(self) -> Dict[str, int]:
        """
        Get directory cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'cached_directories': len(self._directory_cache),
            'cache_keys': list(self._directory_cache.keys())
        }
    
    def get_skipped_files_count(self) -> int:
        """
        Get the total number of files that were skipped during operations.
        
        Returns:
            Number of skipped files
        """
        return self.skipped_files_count
    
    def log_skipped_files_summary(self):
        """
        Log a summary of skipped files.
        """
        if self.skipped_files_count > 0:
            self.logger.info(f"Total files skipped during copy/move operations: {self.skipped_files_count}")
        else:
            self.logger.info("No files were skipped during copy/move operations")
    
    def copy_file(self, source_path: str, destination_path: Path) -> bool:
        """
        Copy a file to the destination.
        
        Args:
            source_path: Source file path
            destination_path: Destination directory path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            source_file = Path(source_path)
            if not source_file.exists():
                self.logger.error(f"Source file does not exist: {source_path}")
                return False
            
            # Create destination filename
            dest_file = destination_path / source_file.name
            
            # Check if file already exists in destination
            if dest_file.exists():
                # Check if files are identical
                if self._files_are_identical(source_file, dest_file):
                    self.logger.info(f"Skipped (identical file): {source_path} -> {dest_file}")
                    self.skipped_files_count += 1
                else:
                    self.logger.info(f"Skipped (file exists with different content): {source_path} -> {dest_file}")
                    self.skipped_files_count += 1
                return True  # Return True since we're skipping intentionally
            
            # Copy the file
            shutil.copy2(source_file, dest_file)
            self.logger.info(f"Copied: {source_path} -> {dest_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to copy {source_path}: {e}")
            return False
    
    def move_file(self, source_path: str, destination_path: Path) -> bool:
        """
        Move a file to the destination.
        
        Args:
            source_path: Source file path
            destination_path: Destination directory path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            source_file = Path(source_path)
            if not source_file.exists():
                self.logger.error(f"Source file does not exist: {source_path}")
                return False
            
            # Create destination filename
            dest_file = destination_path / source_file.name
            
            # Check if file already exists in destination
            if dest_file.exists():
                # Check if files are identical
                if self._files_are_identical(source_file, dest_file):
                    self.logger.info(f"Skipped (identical file): {source_path} -> {dest_file}")
                    self.skipped_files_count += 1
                else:
                    self.logger.info(f"Skipped (file exists with different content): {source_path} -> {dest_file}")
                    self.skipped_files_count += 1
                return True  # Return True since we're skipping intentionally
            
            # Move the file
            shutil.move(str(source_file), str(dest_file))
            self.logger.info(f"Moved: {source_path} -> {dest_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move {source_path}: {e}")
            return False
    
    def organize_file(self, source_path: str, country: str, state: str, city: str,
                     operation: str = "copy") -> bool:
        """
        Organize a file into the appropriate location directory.
        
        Args:
            source_path: Source file path
            country: Country name
            state: State/province name
            city: City name
            operation: "copy" or "move"
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create the location directory
            location_dir = self.create_location_directory(country, state, city)
            
            # Perform the file operation
            if operation.lower() == "move":
                return self.move_file(source_path, location_dir)
            else:
                return self.copy_file(source_path, location_dir)
                
        except Exception as e:
            self.logger.error(f"Failed to organize file {source_path}: {e}")
            return False
    
    def scan_directory(self, source_dir: str) -> List[str]:
        """
        Recursively scan a directory for media files.
        
        Args:
            source_dir: Source directory to scan
            
        Returns:
            List of media file paths found
        """
        media_files = []
        source_path = Path(source_dir)
        
        if not source_path.exists():
            self.logger.error(f"Source directory does not exist: {source_dir}")
            return media_files
        
        try:
            # Supported media extensions
            media_extensions = {
                '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp',
                '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'
            }
            
            for file_path in source_path.rglob('*'):
                if file_path.is_file() and file_path.suffix.lower() in media_extensions:
                    media_files.append(str(file_path))
            
            self.logger.info(f"Found {len(media_files)} media files in {source_dir}")
            return media_files
            
        except Exception as e:
            self.logger.error(f"Error scanning directory {source_dir}: {e}")
            return media_files
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename for filesystem compatibility.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # For common Hindi names, provide English equivalents
        hindi_mappings = {
            'नई दिल्ली': 'New Delhi',
            'मुंबई': 'Mumbai',
            'कोलकाता': 'Kolkata',
            'चेन्नई': 'Chennai',
            'बैंगलोर': 'Bangalore',
            'हैदराबाद': 'Hyderabad',
            'अहमदाबाद': 'Ahmedabad',
            'पुणे': 'Pune',
            'जयपुर': 'Jaipur',
            'लखनऊ': 'Lucknow',
            'कानपुर': 'Kanpur',
            'नागपुर': 'Nagpur',
            'इंदौर': 'Indore',
            'थाणे': 'Thane',
            'भोपाल': 'Bhopal',
            'विशाखापत्तनम': 'Visakhapatnam',
            'पटना': 'Patna',
            'वडोदरा': 'Vadodara',
            'घाटकोपर': 'Ghatkopar',
            'लुधियाना': 'Ludhiana',
            'आगरा': 'Agra',
            'नाशिक': 'Nashik',
            'फरीदाबाद': 'Faridabad',
            'मेरठ': 'Meerut',
            'राजकोट': 'Rajkot',
            'कलकत्ता': 'Kolkata',
            'मद्रास': 'Chennai',
            'बॉम्बे': 'Mumbai',
            'दिल्ली': 'Delhi',
            'महाराष्ट्र': 'Maharashtra',
            'पश्चिम बंगाल': 'West Bengal',
            'तमिलनाडु': 'Tamil Nadu',
            'कर्नाटक': 'Karnataka',
            'उत्तर प्रदेश': 'Uttar Pradesh',
            'मध्य प्रदेश': 'Madhya Pradesh',
            'गुजरात': 'Gujarat',
            'राजस्थान': 'Rajasthan',
            'पंजाब': 'Punjab',
            'हरियाणा': 'Haryana',
            'बिहार': 'Bihar',
            'झारखंड': 'Jharkhand',
            'ओडिशा': 'Odisha',
            'छत्तीसगढ़': 'Chhattisgarh',
            'तेलंगाना': 'Telangana',
            'आंध्र प्रदेश': 'Andhra Pradesh',
            'केरल': 'Kerala',
            'गोवा': 'Goa',
        }
        
        # For common Arabic names, provide English equivalents
        arabic_mappings = {
            # Qatar cities and country
            'الدوحة': 'Doha',
            'الوكرة': 'Al Wakrah',
            'الخور': 'Al Khor',
            'الريان': 'Al Rayyan',
            'أم صلال': 'Umm Salal',
            'الظعاين': 'Al Daayen',
            'الشحانية': 'Al Shamal',
            'قطر': 'Qatar',
            # UAE cities and country
            'دبي': 'Dubai',
            'أبو ظبي': 'Abu Dhabi',
            'الشارقة': 'Sharjah',
            'العين': 'Al Ain',
            'أم القيوين': 'Umm Al Quwain',
            'رأس الخيمة': 'Ras Al Khaimah',
            'الفجيرة': 'Fujairah',
            'عجمان': 'Ajman',
            'الإمارات': 'United Arab Emirates',
            # Kuwait cities and country
            'الكويت': 'Kuwait City',
            'حولي': 'Hawally',
            'الجهراء': 'Al Jahra',
            'مبارك الكبير': 'Mubarak Al Kabeer',
            'الأحمدي': 'Al Ahmadi',
            'الفروانية': 'Al Farwaniyah',
            # Bahrain cities and country
            'المنامة': 'Manama',
            'المحرق': 'Muharraq',
            'الرفاع': 'Riffa',
            'مدينة عيسى': 'Isa Town',
            'مدينة حمد': 'Hamad Town',
            'الدراز': 'Dar Kulaib',
            'البحرين': 'Bahrain',
            # Oman cities and country
            'مسقط': 'Muscat',
            'صلالة': 'Salalah',
            'صحار': 'Sohar',
            'نزوى': 'Nizwa',
            'البريمي': 'Al Buraimi',
            'صور': 'Sur',
            'عمان': 'Oman',
            # Jordan cities and country
            'عمان': 'Amman',
            'إربد': 'Irbid',
            'الزرقاء': 'Zarqa',
            'العقبة': 'Aqaba',
            'السلط': 'Salt',
            'الكرك': 'Karak',
            'الأردن': 'Jordan',
            # Lebanon cities and country
            'بيروت': 'Beirut',
            'طرابلس': 'Tripoli',
            'صيدا': 'Sidon',
            'بعلبك': 'Baalbek',
            'جبيل': 'Byblos',
            'زحلة': 'Zahle',
            'لبنان': 'Lebanon',
            # Syria cities and country
            'دمشق': 'Damascus',
            'حلب': 'Aleppo',
            'حمص': 'Homs',
            'حماة': 'Hama',
            'اللاذقية': 'Latakia',
            'دير الزور': 'Deir ez-Zor',
            'سوريا': 'Syria',
            # Iraq cities and country
            'بغداد': 'Baghdad',
            'البصرة': 'Basra',
            'الموصل': 'Mosul',
            'أربيل': 'Erbil',
            'السليمانية': 'Sulaymaniyah',
            'النجف': 'Najaf',
            'العراق': 'Iraq',
            # Yemen cities and country
            'صنعاء': 'Sanaa',
            'عدن': 'Aden',
            'تعز': 'Taiz',
            'الحديدة': 'Al Hudaydah',
            'إب': 'Ibb',
            'ذمار': 'Dhamar',
            'اليمن': 'Yemen',
            # Saudi cities and country
            'الرياض': 'Riyadh',
            'جدة': 'Jeddah',
            'مكة': 'Makkah',
            'المدينة': 'Madinah',
            'الدمام': 'Dammam',
            'الخبر': 'Khobar',
            'الظهران': 'Dhahran',
            'تبوك': 'Tabuk',
            'حائل': 'Hail',
            'بريدة': 'Buraidah',
            'الطائف': 'Taif',
            'أبها': 'Abha',
            'جازان': 'Jazan',
            'نجران': 'Najran',
            'الجوف': 'Jouf',
            'السعودية': 'Saudi Arabia',
            # Egypt
            'مصر': 'Egypt',
            'القاهرة': 'Cairo',
            'الإسكندرية': 'Alexandria',
            'الأقصر': 'Luxor',
            'أسوان': 'Aswan',
            'شرم الشيخ': 'Sharm El Sheikh',
        }
        
        # First, try to find a mapping for the original name (trim whitespace first)
        trimmed_filename = filename.strip()
        if trimmed_filename in hindi_mappings:
            filename = hindi_mappings[trimmed_filename]
        elif trimmed_filename in arabic_mappings:
            filename = arabic_mappings[trimmed_filename]
        else:
            # Handle non-ASCII characters by transliterating to ASCII
            original_filename = filename  # Keep original for fallback
            try:
                import unicodedata
                # Normalize unicode characters and try to convert to ASCII
                filename = unicodedata.normalize('NFKD', filename)
                # Try to encode as ASCII, replace non-ASCII with closest ASCII equivalent
                filename = filename.encode('ascii', 'ignore').decode('ascii')
            except ImportError:
                # If unicodedata is not available, just remove non-ASCII characters
                filename = ''.join(char for char in filename if ord(char) < 128)
            
            # If the result is empty after ASCII conversion, try to preserve the original meaning
            if not filename.strip():
                # Try to find a mapping for the original name (trim whitespace first)
                trimmed_original = original_filename.strip()
                if trimmed_original in hindi_mappings:
                    filename = hindi_mappings[trimmed_original]
                elif trimmed_original in arabic_mappings:
                    filename = arabic_mappings[trimmed_original]
                else:
                    filename = "Location"
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')
        
        # Replace multiple spaces with single space
        import re
        filename = re.sub(r'\s+', ' ', filename)
        
        # Limit length
        if len(filename) > 100:
            filename = filename[:100]
        
        # Ensure it's not empty
        if not filename:
            filename = "Unknown"
        
        return filename
    
    def _get_unique_filename(self, file_path: Path) -> Path:
        """
        Get a unique filename if the original already exists.
        
        Args:
            file_path: Original file path
            
        Returns:
            Unique file path
        """
        if not file_path.exists():
            return file_path
        
        # Try adding a number suffix
        counter = 1
        while True:
            stem = file_path.stem
            suffix = file_path.suffix
            new_path = file_path.parent / f"{stem}_{counter}{suffix}"
            
            if not new_path.exists():
                return new_path
            
            counter += 1
    
    def _files_are_identical(self, file1: Path, file2: Path) -> bool:
        """
        Check if two files are identical by comparing their content.
        
        Args:
            file1: First file path
            file2: Second file path
            
        Returns:
            True if files are identical, False otherwise
        """
        try:
            if not file1.exists() or not file2.exists():
                return False
            
            # Compare file sizes first (fast check)
            if file1.stat().st_size != file2.stat().st_size:
                return False
            
            # Compare file content (slower but more accurate)
            with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
                while True:
                    chunk1 = f1.read(8192)
                    chunk2 = f2.read(8192)
                    if chunk1 != chunk2:
                        return False
                    if not chunk1:  # End of file
                        break
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Error comparing files {file1} and {file2}: {e}")
            return False 