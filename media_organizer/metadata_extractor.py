"""
Metadata extraction module for media files.

This module handles extraction of GPS metadata from image and video files.
Supports various image formats (JPEG, PNG, etc.) and video formats.
"""

import os
import logging
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/Pillow not available. Image metadata extraction will be limited.")

try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False
    logging.warning("exifread not available. Some image metadata extraction may be limited.")

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HACHOIR_AVAILABLE = True
except ImportError:
    HACHOIR_AVAILABLE = False
    logging.warning("hachoir not available. Video metadata extraction will be limited.")


class MetadataExtractor:
    """
    Extracts GPS metadata from media files.
    
    Supports various image and video formats, extracting GPS coordinates
    when available and providing fallback methods for different file types.
    """
    
    # Supported image extensions
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
    
    # Supported video extensions  
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp'}
    
    def __init__(self):
        """Initialize the metadata extractor."""
        self.logger = logging.getLogger(__name__)
        
        if not PIL_AVAILABLE and not EXIFREAD_AVAILABLE:
            self.logger.error("No image metadata extraction libraries available!")
        
        if not HACHOIR_AVAILABLE:
            self.logger.error("No video metadata extraction libraries available!")
    
    def is_supported_file(self, file_path: str) -> bool:
        """
        Check if the file is a supported media file.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if the file is a supported media file, False otherwise
        """
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.IMAGE_EXTENSIONS or file_ext in self.VIDEO_EXTENSIONS
    
    def extract_gps_coordinates(self, file_path: str) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from a media file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File does not exist: {file_path}")
            return None
        
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in self.IMAGE_EXTENSIONS:
            return self._extract_gps_from_image(file_path)
        elif file_ext in self.VIDEO_EXTENSIONS:
            return self._extract_gps_from_video(file_path)
        else:
            self.logger.warning(f"Unsupported file type: {file_path}")
            return None
    
    def _extract_gps_from_image(self, file_path: str) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from an image file using multiple methods.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        # Try PIL first (most reliable for common formats)
        if PIL_AVAILABLE:
            try:
                with Image.open(file_path) as img:
                    exif_data = img._getexif()
                    if exif_data:
                        gps_data = self._get_gps_data_from_exif(exif_data)
                        if gps_data:
                            return gps_data
            except Exception as e:
                self.logger.debug(f"PIL extraction failed for {file_path}: {e}")
        
        # Fallback to exifread
        if EXIFREAD_AVAILABLE:
            try:
                with open(file_path, 'rb') as f:
                    tags = exifread.process_file(f)
                    gps_data = self._get_gps_data_from_exifread(tags)
                    if gps_data:
                        return gps_data
            except Exception as e:
                self.logger.debug(f"exifread extraction failed for {file_path}: {e}")
        
        self.logger.debug(f"No GPS data found in image: {file_path}")
        return None
    
    def _extract_gps_from_video(self, file_path: str) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from a video file.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        if not HACHOIR_AVAILABLE:
            self.logger.debug(f"Video metadata extraction not available for: {file_path}")
            return None
        
        try:
            parser = createParser(file_path)
            if not parser:
                self.logger.debug(f"Could not create parser for video: {file_path}")
                return None
            
            with parser:
                metadata = extractMetadata(parser)
                if not metadata:
                    self.logger.debug(f"No metadata found in video: {file_path}")
                    return None
                
                # Try to extract GPS data from video metadata
                gps_data = self._get_gps_data_from_video_metadata(metadata)
                if gps_data:
                    return gps_data
                
                # If hachoir didn't find GPS data, try alternative methods
                gps_data = self._try_alternative_video_gps_extraction(file_path)
                if gps_data:
                    return gps_data
                
        except Exception as e:
            self.logger.debug(f"Video metadata extraction failed for {file_path}: {e}")
        
        self.logger.debug(f"No GPS data found in video: {file_path}")
        return None
    
    def _try_alternative_video_gps_extraction(self, file_path: str) -> Optional[Tuple[float, float]]:
        """
        Try alternative methods to extract GPS data from video files.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        try:
            # Try using ffprobe if available (for more detailed video metadata)
            return self._extract_gps_with_ffprobe(file_path)
        except Exception as e:
            self.logger.debug(f"Alternative video GPS extraction failed for {file_path}: {e}")
        
        return None
    
    def _extract_gps_with_ffprobe(self, file_path: str) -> Optional[Tuple[float, float]]:
        """
        Extract GPS data from video using ffprobe (if available).
        
        Args:
            file_path: Path to the video file
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        import subprocess
        import json
        
        try:
            # Try to run ffprobe to get detailed metadata
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Check format metadata
                if 'format' in data and 'tags' in data['format']:
                    tags = data['format']['tags']
                    coords = self._extract_gps_from_ffprobe_tags(tags)
                    if coords:
                        return coords
                
                # Check stream metadata
                if 'streams' in data:
                    for stream in data['streams']:
                        if 'tags' in stream:
                            coords = self._extract_gps_from_ffprobe_tags(stream['tags'])
                            if coords:
                                return coords
                                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, 
                FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.debug(f"ffprobe extraction failed for {file_path}: {e}")
        except Exception as e:
            self.logger.debug(f"Unexpected error in ffprobe extraction for {file_path}: {e}")
        
        return None
    
    def _extract_gps_from_ffprobe_tags(self, tags: dict) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from ffprobe tags.
        
        Args:
            tags: Dictionary of tags from ffprobe
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        # Common GPS tag names in video metadata
        gps_tags = [
            'location', 'gps', 'geo', 'coordinates',
            'latitude', 'longitude', 'lat', 'lon', 'lng',
            'gps_latitude', 'gps_longitude',
            'com.apple.quicktime.location.ISO6709',  # iOS location format
            'com.apple.quicktime.location',  # iOS location
        ]
        
        for tag_name in gps_tags:
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, str):
                    coords = self._parse_location_string(value)
                    if coords:
                        self.logger.debug(f"Found GPS data in ffprobe tag '{tag_name}': {value}")
                        return coords
        
        return None
    
    def _get_gps_data_from_exif(self, exif_data: Dict[int, Any]) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from EXIF data using PIL.
        
        Args:
            exif_data: EXIF data dictionary from PIL
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        gps_info = {}
        
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value
        
        return self._convert_gps_to_decimal(gps_info)
    
    def _get_gps_data_from_exifread(self, tags: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from EXIF data using exifread.
        
        Args:
            tags: Tags dictionary from exifread
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        gps_info = {}
        
        for tag, value in tags.items():
            if tag.startswith('GPS'):
                gps_info[tag] = str(value)
        
        return self._convert_gps_to_decimal(gps_info)
    
    def _get_gps_data_from_video_metadata(self, metadata) -> Optional[Tuple[float, float]]:
        """
        Extract GPS coordinates from video metadata.
        
        Args:
            metadata: Video metadata object from hachoir
            
        Returns:
            Tuple of (latitude, longitude) if GPS data is found, None otherwise
        """
        try:
            # Try to get GPS coordinates from various metadata fields
            gps_data = {}
            
            # Common GPS field names in video metadata
            gps_fields = [
                'latitude', 'longitude', 'lat', 'lon', 'lng',
                'gps_latitude', 'gps_longitude', 'gps_lat', 'gps_lon',
                'location_latitude', 'location_longitude',
                'geo_latitude', 'geo_longitude'
            ]
            
            # Check for direct GPS fields
            for field in gps_fields:
                try:
                    value = getattr(metadata, field, None)
                    if value is not None:
                        gps_data[field] = value
                        self.logger.debug(f"Found GPS field '{field}': {value}")
                except Exception:
                    continue
            
            # Try to extract from location fields
            location_fields = ['location', 'geo', 'gps', 'coordinates']
            for field in location_fields:
                try:
                    value = getattr(metadata, field, None)
                    if value is not None:
                        self.logger.debug(f"Found location field '{field}': {value}")
                        # Try to parse location string
                        coords = self._parse_location_string(str(value))
                        if coords:
                            return coords
                except Exception:
                    continue
            
            # Try to extract from comment or description fields
            comment_fields = ['comment', 'description', 'title', 'subject']
            for field in comment_fields:
                try:
                    value = getattr(metadata, field, None)
                    if value and isinstance(value, str):
                        self.logger.debug(f"Checking comment field '{field}': {value}")
                        coords = self._parse_location_string(value)
                        if coords:
                            return coords
                except Exception:
                    continue
            
            # If we have latitude and longitude fields, try to convert them
            if 'latitude' in gps_data and 'longitude' in gps_data:
                try:
                    lat = float(gps_data['latitude'])
                    lon = float(gps_data['longitude'])
                    return (lat, lon)
                except (ValueError, TypeError):
                    pass
            
            # Try alternative field combinations
            lat_fields = ['lat', 'gps_lat', 'gps_latitude', 'location_latitude', 'geo_latitude']
            lon_fields = ['lon', 'lng', 'gps_lon', 'gps_longitude', 'location_longitude', 'geo_longitude']
            
            lat = None
            lon = None
            
            for field in lat_fields:
                if field in gps_data:
                    try:
                        lat = float(gps_data[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            for field in lon_fields:
                if field in gps_data:
                    try:
                        lon = float(gps_data[field])
                        break
                    except (ValueError, TypeError):
                        continue
            
            if lat is not None and lon is not None:
                return (lat, lon)
            
            # Try to extract from all available metadata fields
            for key in dir(metadata):
                if not key.startswith('_'):  # Skip private attributes
                    try:
                        value = getattr(metadata, key, None)
                        if value and isinstance(value, str):
                            self.logger.debug(f"Checking metadata field '{key}': {value}")
                            coords = self._parse_location_string(value)
                            if coords:
                                return coords
                    except Exception:
                        continue
                        
        except Exception as e:
            self.logger.debug(f"Error extracting GPS from video metadata: {e}")
        
        return None
    
    def _parse_location_string(self, location_str: str) -> Optional[Tuple[float, float]]:
        """
        Parse location string to extract GPS coordinates.
        
        Args:
            location_str: String that might contain GPS coordinates
            
        Returns:
            Tuple of (latitude, longitude) if found, None otherwise
        """
        import re
        
        try:
            # Remove common prefixes and clean the string
            location_str = location_str.strip()
            
            # Pattern for decimal coordinates (e.g., "40.7128, -74.0060" or "40.7128,-74.0060")
            decimal_pattern = r'(-?\d+\.?\d*)\s*[,;]\s*(-?\d+\.?\d*)'
            match = re.search(decimal_pattern, location_str)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
            
            # Pattern for GPS coordinates with N/S/E/W indicators
            gps_pattern = r'(-?\d+\.?\d*)\s*([NSns])\s*[,;]\s*(-?\d+\.?\d*)\s*([EWew])'
            match = re.search(gps_pattern, location_str)
            if match:
                lat = float(match.group(1))
                lat_dir = match.group(2).upper()
                lon = float(match.group(3))
                lon_dir = match.group(4).upper()
                
                if lat_dir == 'S':
                    lat = -lat
                if lon_dir == 'W':
                    lon = -lon
                
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
            
            # Pattern for coordinates in parentheses
            paren_pattern = r'\((-?\d+\.?\d*)\s*[,;]\s*(-?\d+\.?\d*)\)'
            match = re.search(paren_pattern, location_str)
            if match:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
                    
        except Exception as e:
            self.logger.debug(f"Error parsing location string '{location_str}': {e}")
        
        return None
    
    def _convert_gps_to_decimal(self, gps_info: Dict[str, Any]) -> Optional[Tuple[float, float]]:
        """
        Convert GPS coordinates from degrees/minutes/seconds to decimal format.
        
        Args:
            gps_info: Dictionary containing GPS information
            
        Returns:
            Tuple of (latitude, longitude) in decimal format, None if conversion fails
        """
        try:
            lat = self._convert_dms_to_decimal(gps_info, 'GPSLatitude', 'GPSLatitudeRef')
            lon = self._convert_dms_to_decimal(gps_info, 'GPSLongitude', 'GPSLongitudeRef')
            
            if lat is not None and lon is not None:
                return (lat, lon)
        except Exception as e:
            self.logger.debug(f"Error converting GPS coordinates: {e}")
        
        return None
    
    def _convert_dms_to_decimal(self, gps_info: Dict[str, Any], 
                               coord_key: str, ref_key: str) -> Optional[float]:
        """
        Convert degrees/minutes/seconds to decimal coordinates.
        
        Args:
            gps_info: GPS information dictionary
            coord_key: Key for the coordinate value
            ref_key: Key for the coordinate reference (N/S, E/W)
            
        Returns:
            Decimal coordinate value, None if conversion fails
        """
        if coord_key not in gps_info:
            return None
        
        coord = gps_info[coord_key]
        ref = gps_info.get(ref_key, 'N')
        
        if isinstance(coord, (list, tuple)) and len(coord) >= 3:
            degrees = float(coord[0])
            minutes = float(coord[1])
            seconds = float(coord[2])
            
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            if ref in ['S', 'W']:
                decimal = -decimal
            
            return decimal
        elif isinstance(coord, str):
            # Handle string format coordinates
            try:
                # Simple decimal format
                decimal = float(coord)
                if ref in ['S', 'W']:
                    decimal = -decimal
                return decimal
            except ValueError:
                pass
        
        return None 