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
        
        # Cache for reverse geocoding results
        self._geocoding_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self._last_request_time = 0
        
        if GEOPY_AVAILABLE:
            try:
                # Configure Nominatim with better timeout and retry settings
                self.geolocator = Nominatim(
                    user_agent=user_agent,
                    timeout=10,  # Increased timeout
                    proxies=None
                )
                self.logger.info("Geocoder initialized with Nominatim (optimized settings)")
            except Exception as e:
                self.logger.error(f"Failed to initialize geocoder: {e}")
        else:
            self.logger.error("No geocoding libraries available!")
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Tuple[str, str, str]]:
        """
        Reverse geocode GPS coordinates to country, state, and city.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Tuple of (country, state, city) if successful, None otherwise
        """
        if not self.geolocator:
            self.logger.error("Geocoder not available")
            return None
        
        # Check cache first
        cache_key = f"{latitude:.6f},{longitude:.6f}"
        if cache_key in self._geocoding_cache:
            self._cache_hits += 1
            self.logger.debug(f"Cache hit for coordinates ({latitude}, {longitude})")
            return self._geocoding_cache[cache_key]
        
        self._cache_misses += 1
        
        # Rate limiting with exponential backoff
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        min_delay = 1.0  # Minimum 1 second between requests
        
        if time_since_last_request < min_delay:
            sleep_time = min_delay - time_since_last_request
            time.sleep(sleep_time)
        
        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self._last_request_time = time.time()
                location = self.geolocator.reverse((latitude, longitude))
                
                if location and location.raw:
                    result = self._extract_country_state_city(location.raw)
                    # Cache the result
                    self._geocoding_cache[cache_key] = result
                    return result
                else:
                    self.logger.debug(f"No location data returned for coordinates ({latitude}, {longitude})")
                    break
                    
            except GeocoderTimedOut:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                self.logger.warning(f"Geocoding timed out for coordinates ({latitude}, {longitude}), attempt {attempt + 1}/{max_retries}, retrying in {delay}s")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                else:
                    self.logger.error(f"Geocoding failed after {max_retries} attempts for coordinates ({latitude}, {longitude})")
                    
            except GeocoderUnavailable:
                self.logger.warning(f"Geocoding service unavailable for coordinates ({latitude}, {longitude})")
                break
                
            except Exception as e:
                self.logger.error(f"Geocoding failed for coordinates ({latitude}, {longitude}): {e}")
                break
        
        return None
    
    def batch_reverse_geocode(self, coordinates: list) -> Dict[tuple, Optional[Tuple[str, str, str]]]:
        """
        Batch reverse geocode multiple GPS coordinates.
        
        Args:
            coordinates: List of (latitude, longitude) tuples
            
        Returns:
            Dictionary mapping coordinates to (country, state, city) tuples
        """
        results = {}
        
        # Group similar coordinates to reduce API calls
        coordinate_groups = self._group_similar_coordinates(coordinates)
        
        self.logger.info(f"Processing {len(coordinate_groups)} unique coordinate groups from {len(coordinates)} total coordinates")
        
        # Add progress reporting
        from tqdm import tqdm
        progress_bar = tqdm(total=len(coordinate_groups), desc="Geocoding coordinates", unit="groups")
        
        for i, group in enumerate(coordinate_groups):
            try:
                # Use the first coordinate in the group as representative
                representative = group[0]
                result = self.reverse_geocode(*representative)
                
                # Apply the same result to all coordinates in the group
                for coord in group:
                    results[coord] = result
                
                # Update progress
                progress_bar.update(1)
                progress_bar.set_postfix({
                    'processed': i + 1,
                    'total': len(coordinate_groups),
                    'cache_hits': self._cache_hits,
                    'cache_misses': self._cache_misses
                })
                
            except Exception as e:
                self.logger.error(f"Error processing coordinate group {i}: {e}")
                # Apply None result to all coordinates in the group
                for coord in group:
                    results[coord] = None
        
        progress_bar.close()
        return results
    
    def _group_similar_coordinates(self, coordinates: list, tolerance: float = 0.005) -> list:
        """
        Group coordinates that are very close to each other.
        
        Args:
            coordinates: List of (latitude, longitude) tuples
            tolerance: Distance tolerance in degrees
            
        Returns:
            List of coordinate groups
        """
        groups = []
        used = set()
        
        for i, coord1 in enumerate(coordinates):
            if i in used:
                continue
                
            group = [coord1]
            used.add(i)
            
            for j, coord2 in enumerate(coordinates[i+1:], i+1):
                if j in used:
                    continue
                    
                # Calculate distance between coordinates
                lat1, lon1 = coord1
                lat2, lon2 = coord2
                distance = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5
                
                if distance <= tolerance:
                    group.append(coord2)
                    used.add(j)
            
            groups.append(group)
        
        return groups
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache hit/miss statistics
        """
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'cache_size': len(self._geocoding_cache)
        }
    
    def _extract_country_state_city(self, location_data: Dict[str, Any]) -> Optional[Tuple[str, str, str]]:
        """
        Extract country, state, and city from location data.
        
        Args:
            location_data: Raw location data from geocoding service
            
        Returns:
            Tuple of (country, state, city) if found, None otherwise
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
            
            # Try different possible keys for city
            city = (
                address.get('city') or
                address.get('town') or
                address.get('village') or
                address.get('municipality') or
                address.get('suburb') or
                address.get('district') or
                'Unknown'
            )
            
            # Clean up the values
            country = self._clean_location_name(country)
            state = self._clean_location_name(state)
            city = self._clean_location_name(city)
            
            # Normalize country names to English
            country = self._normalize_country_name(country)
            
            # Normalize state names to English
            state = self._normalize_state_name(state)
            
            # Normalize city names to English
            city = self._normalize_city_name(city)
            
            if country and state and city:
                return (country, state, city)
                
        except Exception as e:
            self.logger.error(f"Error extracting country/state/city from location data: {e}")
        
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
    
    def _normalize_country_name(self, country: str) -> str:
        """
        Normalize country names to English equivalents.
        
        Args:
            country: Country name (potentially in native language)
            
        Returns:
            Normalized country name in English
        """
        # Dictionary of common country name mappings
        country_mappings = {
            # Thai
            'ประเทศไทย': 'Thailand',
            'ไทย': 'Thailand',
            
            # Chinese
            '中国': 'China',
            '中華人民共和國': 'China',
            
            # Japanese
            '日本': 'Japan',
            
            # Korean
            '대한민국': 'South Korea',
            '한국': 'South Korea',
            
            # Arabic
            'مصر': 'Egypt',
            'السعودية': 'Saudi Arabia',
            'قطر': 'Qatar',
            'الإمارات': 'United Arab Emirates',
            'الكويت': 'Kuwait',
            'البحرين': 'Bahrain',
            'عمان': 'Oman',
            'الأردن': 'Jordan',
            'لبنان': 'Lebanon',
            'سوريا': 'Syria',
            'العراق': 'Iraq',
            'اليمن': 'Yemen',
            
            # Russian
            'Россия': 'Russia',
            'Российская Федерация': 'Russia',
            
            # German
            'Deutschland': 'Germany',
            
            # French
            'France': 'France',  # Already in English
            'Espagne': 'Spain',
            'Italie': 'Italy',
            
            # Spanish
            'España': 'Spain',
            'México': 'Mexico',
            'Argentina': 'Argentina',
            
            # Portuguese
            'Brasil': 'Brazil',
            'Portugal': 'Portugal',
            
            # Other common variations
            'USA': 'United States',
            'US': 'United States',
            'United States of America': 'United States',
            'UK': 'United Kingdom',
            'Great Britain': 'United Kingdom',
            'England': 'United Kingdom',
            'UAE': 'United Arab Emirates',
            'U.A.E.': 'United Arab Emirates',
            'U.A.E': 'United Arab Emirates',
        }
        
        # Return normalized name if found, otherwise return original
        return country_mappings.get(country, country)
    
    def _normalize_state_name(self, state: str) -> str:
        """
        Normalize state/province names to English equivalents.
        
        Args:
            state: State name (potentially in native language)
            
        Returns:
            Normalized state name in English
        """
        # Dictionary of common state name mappings
        state_mappings = {
            # Thai provinces
            'จังหวัดชลบุรี': 'Chonburi',
            'จังหวัดกรุงเทพมหานคร': 'Bangkok',
            'จังหวัดเชียงใหม่': 'Chiang Mai',
            'จังหวัดภูเก็ต': 'Phuket',
            'จังหวัดพัทยา': 'Pattaya',
            'จังหวัดกระบี่': 'Krabi',
            'จังหวัดสุราษฎร์ธานี': 'Surat Thani',
            'จังหวัดนครศรีธรรมราช': 'Nakhon Si Thammarat',
            'จังหวัดสงขลา': 'Songkhla',
            'จังหวัดปัตตานี': 'Pattani',
            'จังหวัดยะลา': 'Yala',
            'จังหวัดนราธิวาส': 'Narathiwat',
            'จังหวัดตรัง': 'Trang',
            'จังหวัดพังงา': 'Phang Nga',
            'จังหวัดระนอง': 'Ranong',
            'จังหวัดชุมพร': 'Chumphon',
            'จังหวัดนครปฐม': 'Nakhon Pathom',
            'จังหวัดสมุทรปราการ': 'Samut Prakan',
            'จังหวัดสมุทรสาคร': 'Samut Sakhon',
            'จังหวัดสมุทรสงคราม': 'Samut Songkhram',
            'จังหวัดนครนายก': 'Nakhon Nayok',
            'จังหวัดปราจีนบุรี': 'Prachinburi',
            'จังหวัดฉะเชิงเทรา': 'Chachoengsao',
            'จังหวัดชัยนาท': 'Chainat',
            'จังหวัดลพบุรี': 'Lopburi',
            'จังหวัดสิงห์บุรี': 'Singburi',
            'จังหวัดอ่างทอง': 'Ang Thong',
            'จังหวัดพระนครศรีอยุธยา': 'Phra Nakhon Si Ayutthaya',
            'จังหวัดสุพรรณบุรี': 'Suphanburi',
            'จังหวัดนครนายก': 'Nakhon Nayok',
            'จังหวัดกาญจนบุรี': 'Kanchanaburi',
            'จังหวัดราชบุรี': 'Ratchaburi',
            'จังหวัดเพชรบุรี': 'Phetchaburi',
            'จังหวัดประจวบคีรีขันธ์': 'Prachuap Khiri Khan',
            'จังหวัดนครสวรรค์': 'Nakhon Sawan',
            'จังหวัดอุทัยธานี': 'Uthai Thani',
            'จังหวัดกำแพงเพชร': 'Kamphaeng Phet',
            'จังหวัดตาก': 'Tak',
            'จังหวัดสุโขทัย': 'Sukhothai',
            'จังหวัดพิษณุโลก': 'Phitsanulok',
            'จังหวัดเพชรบูรณ์': 'Phetchabun',
            'จังหวัดพิจิตร': 'Phichit',
            'จังหวัดนครราชสีมา': 'Nakhon Ratchasima',
            'จังหวัดบุรีรัมย์': 'Buriram',
            'จังหวัดสุรินทร์': 'Surin',
            'จังหวัดศรีสะเกษ': 'Sisaket',
            'จังหวัดอุบลราชธานี': 'Ubon Ratchathani',
            'จังหวัดยโสธร': 'Yasothon',
            'จังหวัดชัยภูมิ': 'Chaiyaphum',
            'จังหวัดอำนาจเจริญ': 'Amnat Charoen',
            'จังหวัดหนองบัวลำภู': 'Nong Bua Lamphu',
            'จังหวัดขอนแก่น': 'Khon Kaen',
            'จังหวัดอุดรธานี': 'Udon Thani',
            'จังหวัดเลย': 'Loei',
            'จังหวัดหนองคาย': 'Nong Khai',
            'จังหวัดมหาสารคาม': 'Maha Sarakham',
            'จังหวัดร้อยเอ็ด': 'Roi Et',
            'จังหวัดกาฬสินธุ์': 'Kalasin',
            'จังหวัดสกลนคร': 'Sakon Nakhon',
            'จังหวัดนครพนม': 'Nakhon Phanom',
            'จังหวัดมุกดาหาร': 'Mukdahan',
            'จังหวัดบึงกาฬ': 'Bueng Kan',
            'จังหวัดเชียงราย': 'Chiang Rai',
            'จังหวัดพะเยา': 'Phayao',
            'จังหวัดน่าน': 'Nan',
            'จังหวัดแพร่': 'Phrae',
            'จังหวัดลำปาง': 'Lampang',
            'จังหวัดอุตรดิตถ์': 'Uttaradit',
            'จังหวัดตาก': 'Tak',
            'จังหวัดแม่ฮ่องสอน': 'Mae Hong Son',
            'จังหวัดลำพูน': 'Lamphun',
            'จังหวัดเชียงใหม่': 'Chiang Mai',
            
            # Chinese provinces/states
            '广东省': 'Guangdong',
            '北京市': 'Beijing',
            '上海市': 'Shanghai',
            '天津市': 'Tianjin',
            '重庆市': 'Chongqing',
            '河北省': 'Hebei',
            '山西省': 'Shanxi',
            '辽宁省': 'Liaoning',
            '吉林省': 'Jilin',
            '黑龙江省': 'Heilongjiang',
            '江苏省': 'Jiangsu',
            '浙江省': 'Zhejiang',
            '安徽省': 'Anhui',
            '福建省': 'Fujian',
            '江西省': 'Jiangxi',
            '山东省': 'Shandong',
            '河南省': 'Henan',
            '湖北省': 'Hubei',
            '湖南省': 'Hunan',
            '四川省': 'Sichuan',
            '贵州省': 'Guizhou',
            '云南省': 'Yunnan',
            '陕西省': 'Shaanxi',
            '甘肃省': 'Gansu',
            '青海省': 'Qinghai',
            '台湾省': 'Taiwan',
            '内蒙古自治区': 'Inner Mongolia',
            '广西壮族自治区': 'Guangxi',
            '西藏自治区': 'Tibet',
            '宁夏回族自治区': 'Ningxia',
            '新疆维吾尔自治区': 'Xinjiang',
            '香港特别行政区': 'Hong Kong',
            '澳门特别行政区': 'Macau',
            
            # Japanese prefectures
            '東京都': 'Tokyo',
            '大阪府': 'Osaka',
            '京都府': 'Kyoto',
            '北海道': 'Hokkaido',
            '神奈川県': 'Kanagawa',
            '愛知県': 'Aichi',
            '埼玉県': 'Saitama',
            '千葉県': 'Chiba',
            '兵庫県': 'Hyogo',
            '福岡県': 'Fukuoka',
            '静岡県': 'Shizuoka',
            '茨城県': 'Ibaraki',
            '広島県': 'Hiroshima',
            '群馬県': 'Gunma',
            '栃木県': 'Tochigi',
            '岐阜県': 'Gifu',
            '新潟県': 'Niigata',
            '長野県': 'Nagano',
            '三重県': 'Mie',
            '福島県': 'Fukushima',
            '山梨県': 'Yamanashi',
            '滋賀県': 'Shiga',
            '岡山県': 'Okayama',
            '山口県': 'Yamaguchi',
            '愛媛県': 'Ehime',
            '奈良県': 'Nara',
            '和歌山県': 'Wakayama',
            '鳥取県': 'Tottori',
            '島根県': 'Shimane',
            '高知県': 'Kochi',
            '徳島県': 'Tokushima',
            '香川県': 'Kagawa',
            '富山県': 'Toyama',
            '石川県': 'Ishikawa',
            '福井県': 'Fukui',
            '山形県': 'Yamagata',
            '秋田県': 'Akita',
            '青森県': 'Aomori',
            '岩手県': 'Iwate',
            '宮城県': 'Miyagi',
            '山形県': 'Yamagata',
            '福島県': 'Fukushima',
            '茨城県': 'Ibaraki',
            '栃木県': 'Tochigi',
            '群馬県': 'Gunma',
            '埼玉県': 'Saitama',
            '千葉県': 'Chiba',
            '東京都': 'Tokyo',
            '神奈川県': 'Kanagawa',
            '新潟県': 'Niigata',
            '富山県': 'Toyama',
            '石川県': 'Ishikawa',
            '福井県': 'Fukui',
            '山梨県': 'Yamanashi',
            '長野県': 'Nagano',
            '岐阜県': 'Gifu',
            '静岡県': 'Shizuoka',
            '愛知県': 'Aichi',
            '三重県': 'Mie',
            '滋賀県': 'Shiga',
            '京都府': 'Kyoto',
            '大阪府': 'Osaka',
            '兵庫県': 'Hyogo',
            '奈良県': 'Nara',
            '和歌山県': 'Wakayama',
            '鳥取県': 'Tottori',
            '島根県': 'Shimane',
            '岡山県': 'Okayama',
            '広島県': 'Hiroshima',
            '山口県': 'Yamaguchi',
            '徳島県': 'Tokushima',
            '香川県': 'Kagawa',
            '愛媛県': 'Ehime',
            '高知県': 'Kochi',
            '福岡県': 'Fukuoka',
            '佐賀県': 'Saga',
            '長崎県': 'Nagasaki',
            '熊本県': 'Kumamoto',
            '大分県': 'Oita',
            '宮崎県': 'Miyazaki',
            '鹿児島県': 'Kagoshima',
            '沖縄県': 'Okinawa',
            
            # Korean provinces
            '서울특별시': 'Seoul',
            '부산광역시': 'Busan',
            '대구광역시': 'Daegu',
            '인천광역시': 'Incheon',
            '광주광역시': 'Gwangju',
            '대전광역시': 'Daejeon',
            '울산광역시': 'Ulsan',
            '세종특별자치시': 'Sejong',
            '경기도': 'Gyeonggi',
            '강원도': 'Gangwon',
            '충청북도': 'Chungcheongbuk',
            '충청남도': 'Chungcheongnam',
            '전라북도': 'Jeollabuk',
            '전라남도': 'Jeollanam',
            '경상북도': 'Gyeongsangbuk',
            '경상남도': 'Gyeongsangnam',
            '제주특별자치도': 'Jeju',
            
            # Arabic states/provinces
            'الرياض': 'Riyadh',
            'جدة': 'Jeddah',
            'مكة المكرمة': 'Makkah',
            'المدينة المنورة': 'Madinah',
            'الشرقية': 'Eastern Province',
            'القصيم': 'Qassim',
            'حائل': 'Hail',
            'تبوك': 'Tabuk',
            'الجوف': 'Jouf',
            'الباحة': 'Baha',
            'نجران': 'Najran',
            'جازان': 'Jazan',
            'عسير': 'Asir',
            'الحدود الشمالية': 'Northern Borders',
        }
        
        # Return normalized name if found, otherwise return original
        return state_mappings.get(state, state)
    
    def _normalize_city_name(self, city: str) -> str:
        """
        Normalize city names to English equivalents.
        
        Args:
            city: City name (potentially in native language)
            
        Returns:
            Normalized city name in English
        """
        # Dictionary of common city name mappings
        city_mappings = {
            # Thai cities
            'กรุงเทพมหานคร': 'Bangkok',
            'เชียงใหม่': 'Chiang Mai',
            'ภูเก็ต': 'Phuket',
            'พัทยา': 'Pattaya',
            'หาดใหญ่': 'Hat Yai',
            'นครราชสีมา': 'Nakhon Ratchasima',
            'ขอนแก่น': 'Khon Kaen',
            'อุบลราชธานี': 'Ubon Ratchathani',
            'นครศรีธรรมราช': 'Nakhon Si Thammarat',
            'สงขลา': 'Songkhla',
            
            # Chinese cities
            '北京': 'Beijing',
            '上海': 'Shanghai',
            '广州': 'Guangzhou',
            '深圳': 'Shenzhen',
            '天津': 'Tianjin',
            '重庆': 'Chongqing',
            '成都': 'Chengdu',
            '杭州': 'Hangzhou',
            '南京': 'Nanjing',
            '武汉': 'Wuhan',
            '西安': 'Xian',
            '青岛': 'Qingdao',
            '大连': 'Dalian',
            '厦门': 'Xiamen',
            '苏州': 'Suzhou',
            '无锡': 'Wuxi',
            '宁波': 'Ningbo',
            '长沙': 'Changsha',
            '郑州': 'Zhengzhou',
            '济南': 'Jinan',
            
            # Japanese cities
            '東京': 'Tokyo',
            '大阪': 'Osaka',
            '京都': 'Kyoto',
            '横浜': 'Yokohama',
            '名古屋': 'Nagoya',
            '神戸': 'Kobe',
            '福岡': 'Fukuoka',
            '札幌': 'Sapporo',
            '仙台': 'Sendai',
            '広島': 'Hiroshima',
            '岡山': 'Okayama',
            '金沢': 'Kanazawa',
            '奈良': 'Nara',
            '鎌倉': 'Kamakura',
            '箱根': 'Hakone',
            
            # Korean cities
            '서울': 'Seoul',
            '부산': 'Busan',
            '대구': 'Daegu',
            '인천': 'Incheon',
            '광주': 'Gwangju',
            '대전': 'Daejeon',
            '울산': 'Ulsan',
            '수원': 'Suwon',
            '창원': 'Changwon',
            '고양': 'Goyang',
            '용인': 'Yongin',
            '성남': 'Seongnam',
            '부천': 'Bucheon',
            '안산': 'Ansan',
            '전주': 'Jeonju',
            '청주': 'Cheongju',
            '포항': 'Pohang',
            '춘천': 'Chuncheon',
            '강릉': 'Gangneung',
            '여수': 'Yeosu',
            
            # Arabic cities
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
        }
        
        # Return normalized name if found, otherwise return original
        return city_mappings.get(city, city) 