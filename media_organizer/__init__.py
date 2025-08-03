"""
Media Organizer Package

A Python package for organizing media files by GPS location.
Extracts GPS metadata from images and videos, reverse geocodes coordinates,
and organizes files into country/state folders.
"""

__version__ = "1.0.0"
__author__ = "Media Organizer Team"

from .metadata_extractor import MetadataExtractor
from .geocoder import Geocoder
from .file_organizer import FileOrganizer
from .logger import Logger

__all__ = [
    "MetadataExtractor",
    "Geocoder", 
    "FileOrganizer",
    "Logger"
] 