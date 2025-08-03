# Media Organizer

A Python tool for organizing media files by GPS location. This application extracts GPS metadata from images and videos, reverse geocodes the coordinates to obtain country and state information, and organizes files into a structured directory hierarchy.

## Features

- **GPS Metadata Extraction**: Extracts GPS coordinates from various image formats (JPEG, PNG, TIFF, etc.) and video formats
- **Advanced Video GPS**: Enhanced GPS extraction from videos using hachoir and ffprobe for comprehensive metadata analysis
- **Reverse Geocoding**: Converts GPS coordinates to country and state information using OpenStreetMap's Nominatim service
- **File Organization**: Creates a Country/State directory structure and organizes files accordingly
- **Flexible Operations**: Supports both copy and move operations
- **Comprehensive Logging**: Detailed logging of all operations with progress tracking
- **Error Handling**: Robust error handling with fallback mechanisms
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Debug Tools**: Includes debug script for testing video GPS extraction capabilities
- **High Performance**: Optimized for large datasets with caching, concurrent processing, and early filtering
- **Progress Tracking**: Visual progress bars using tqdm for better user experience
- **Smart Caching**: In-memory caching for geocoding results and directory creation
- **Concurrent Processing**: Multi-threaded processing for faster execution of large datasets

## Supported File Formats

### Images
- JPEG (.jpg, .jpeg)
- PNG (.png)
- TIFF (.tiff, .tif)
- BMP (.bmp)
- GIF (.gif)
- WebP (.webp)

### Videos
- MP4 (.mp4)
- AVI (.avi)
- MOV (.mov)
- MKV (.mkv)
- WMV (.wmv)
- FLV (.flv)
- WebM (.webm)
- M4V (.m4v)
- 3GP (.3gp)

## Installation

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Install from Source

1. Clone or download this repository
2. Navigate to the project directory
3. Install the package:

```bash
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

Run the application:

```bash
python -m media_organizer.main
```

Or if installed with pip:

```bash
media-organizer
```

### Interactive Mode

The application will prompt you for:

1. **Source Directory**: Path to the directory containing your media files
2. **Destination Directory**: Path where organized files will be placed
3. **Operation Type**: Choose between 'copy' or 'move'
4. **Mode**: Choose between 'plan' or 'execute'
   - **Plan**: Shows the folder structure and file counts without performing any operations
   - **Execute**: Performs the actual copy/move operations

### Example Workflow

```
============================================================
MEDIA ORGANIZER
============================================================
This tool organizes media files by GPS location.
Files will be organized into Country/State folders based on GPS data.
Files without GPS data will be placed in Unknown folder.
============================================================

Enter source directory path: /path/to/photos
Enter destination directory path: /path/to/organized_photos
Operation type (copy/move): copy
Mode (plan/execute): plan

Summary:
Source: /path/to/photos
Destination: /path/to/organized_photos
Operation: copy
Mode: plan

Proceed? (y/n): y
```

### Plan Mode

When you choose "plan" mode, the application will:
- Scan all media files in the source directory
- Extract GPS metadata and perform reverse geocoding
- Display a detailed plan showing:
  - Total number of files to process
  - Number of folders that will be created
  - Folder structure with file counts
  - Sample filenames for each folder
- No files are actually moved or copied

This allows you to preview the organization structure before committing to the operation.

### Execute Mode

When you choose "execute" mode, the application will:
- Perform the same analysis as plan mode
- Actually copy or move files to their organized locations
- Provide detailed logging of all operations

### Output Structure

Files will be organized into the following structure:

```
destination_directory/
├── United States/
│   ├── California/
│   │   ├── photo1.jpg
│   │   └── video1.mp4
│   └── New York/
│       └── photo2.jpg
├── Canada/
│   └── Ontario/
│       └── photo3.jpg
└── Unknown/
    └── photo4.jpg
```

## Project Structure

```
media_organizer/
├── __init__.py              # Package initialization
├── main.py                  # Main application entry point
├── metadata_extractor.py    # GPS metadata extraction
├── geocoder.py             # Reverse geocoding functionality
├── file_organizer.py       # File operations and organization
└── logger.py               # Logging configuration

setup.py                    # Package setup configuration
requirements.txt            # Python dependencies
README.md                   # This file
.gitignore                  # Git ignore patterns
```

## Dependencies

### Core Dependencies
- **Pillow**: Image processing and EXIF extraction
- **exifread**: Alternative EXIF data extraction
- **hachoir**: Video metadata extraction
- **geopy**: Reverse geocoding functionality
- **tqdm**: Progress bars for better user experience

### Optional Dependencies
- **requests**: HTTP requests for geocoding services

## Configuration

### Logging
The application uses Python's built-in logging module with configurable levels:
- DEBUG: Detailed information for debugging
- INFO: General information about operations
- WARNING: Warning messages for non-critical issues
- ERROR: Error messages for failed operations

### Geocoding Service
The application uses OpenStreetMap's Nominatim service for reverse geocoding. This service has rate limits, so the application includes delays between requests.

## Error Handling

The application includes comprehensive error handling:

- **Missing GPS Data**: Files without GPS coordinates are placed in `Unknown`
- **Geocoding Failures**: Coordinates that can't be geocoded are placed in `Unknown`
- **File Operation Failures**: Failed operations are logged with detailed error messages
- **Network Issues**: Geocoding failures due to network issues are handled gracefully

## Limitations

- **Video GPS Extraction**: Video GPS extraction is limited and depends on the video format and metadata availability
- **Geocoding Rate Limits**: The free Nominatim service has rate limits (1 request per second)
- **Large File Sets**: Processing large numbers of files may take significant time due to geocoding delays

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Troubleshooting

### Common Issues

1. **"No GPS data found"**: The file may not contain GPS metadata, or the format is not supported
2. **"Geocoding failed"**: Network issues or rate limiting from the geocoding service
3. **"Permission denied"**: Check file and directory permissions
4. **"File not found"**: Verify the source directory path exists

### Debug Mode

For detailed logging, you can modify the logging level in the code or add debug output.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for detailed error messages
3. Create an issue in the project repository

## Changelog

### Version 1.0.0
- Initial release
- GPS metadata extraction from images and videos
- Reverse geocoding functionality
- File organization by country/state
- Comprehensive logging and error handling 