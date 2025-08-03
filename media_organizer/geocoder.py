"""
Geocoding module for reverse geocoding GPS coordinates.

This module handles reverse geocoding of GPS coordinates to obtain
country and state information using various geocoding services.
"""

import logging
import time
from typing import Optional, Tuple, Dict, Any
import requests

try:
    import geopy
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    logging.warning("geopy not available. Geocoding will be limited.")


class Geocoder:
    """
    Handles reverse geocoding of GPS coordinates to location information.
    
    Uses multiple geocoding services with fallback mechanisms to ensure
    reliable location data extraction.
    """
    
    def __init__(self, user_agent: str = "MediaOrganizer/1.0"):
        """
        Initialize the geocoder.
        
        Args:
            user_agent: User agent string for geocoding requests
        """
        self.logger = logging.getLogger(__name__)
        self.user_agent = user_agent
        self.geolocator = None
        
        if GEOPY_AVAILABLE:
            try:
                self.geolocator = Nominatim(user_agent=user_agent)
                self.logger.info("Geocoder initialized with Nominatim")
            except Exception as e:
                self.logger.error(f"Failed to initialize geocoder: {e}")
        else:
            self.logger.error("No geocoding libraries available!")
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Tuple[str, str]]:
        """
        Reverse geocode GPS coordinates to country and state.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Tuple of (country, state) if successful, None otherwise
        """
        if not self.geolocator:
            self.logger.error("Geocoder not available")
            return None
        
        try:
            # Add delay to respect rate limits
            time.sleep(1)
            
            location = self.geolocator.reverse((latitude, longitude))
            if location and location.raw:
                return self._extract_country_state(location.raw)
                
        except GeocoderTimedOut:
            self.logger.warning(f"Geocoding timed out for coordinates ({latitude}, {longitude})")
        except GeocoderUnavailable:
            self.logger.warning(f"Geocoding service unavailable for coordinates ({latitude}, {longitude})")
        except Exception as e:
            self.logger.error(f"Geocoding failed for coordinates ({latitude}, {longitude}): {e}")
        
        return None
    
    def _extract_country_state(self, location_data: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """
        Extract country and state from location data.
        
        Args:
            location_data: Raw location data from geocoding service
            
        Returns:
            Tuple of (country, state) if found, None otherwise
        """
        try:
            address = location_data.get('address', {})
            
            # Try different possible keys for country
            country = (
                address.get('country') or
                address.get('country_code') or
                address.get('state') or  # Fallback for some regions
                'Unknown'
            )
            
            # Try different possible keys for state
            state = (
                address.get('state') or
                address.get('province') or
                address.get('region') or
                address.get('county') or
                'Unknown'
            )
            
            # Clean up the values
            country = self._clean_location_name(country)
            state = self._clean_location_name(state)
            
            if country and state:
                return (country, state)
                
        except Exception as e:
            self.logger.error(f"Error extracting country/state from location data: {e}")
        
        return None
    
    def _clean_location_name(self, name: str) -> str:
        """
        Clean and normalize location names.
        
        Args:
            name: Raw location name
            
        Returns:
            Cleaned location name
        """
        if not name or name == 'Unknown':
            return 'Unknown'
        
        # Remove common prefixes/suffixes and normalize
        name = name.strip()
        name = name.replace('_', ' ')
        name = name.title()
        
        # Handle special cases
        if name.lower() in ['unknown', 'none', 'null', '']:
            return 'Unknown'
        
        return name 