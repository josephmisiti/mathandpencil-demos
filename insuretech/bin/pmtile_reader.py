import argparse
import json
import math
from pmtiles.reader import Reader, MmapSource

def deg2num(lat_deg, lon_deg, zoom):
    """Convert lat/lng to tile coordinates"""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (x, y)

def num2deg(x, y, zoom):
    """Convert tile coordinates to lat/lng"""
    n = 2.0 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

def tile_bounds(x, y, zoom):
    """Get the lat/lng bounds of a tile"""
    # Top-left corner
    north, west = num2deg(x, y, zoom)
    # Bottom-right corner  
    south, east = num2deg(x + 1, y + 1, zoom)
    return {
        'north': north,
        'south': south,
        'east': east,
        'west': west,
        'center_lat': (north + south) / 2,
        'center_lng': (east + west) / 2
    }

def get_pmtiles_metadata(file_path):
    """Reads and prints the header and metadata from a PMTiles file."""
    try:
        with open(file_path, "rb") as f:
            reader = Reader(MmapSource(f))
            header = reader.header()
            metadata = reader.metadata()

            print(f"Reading PMTiles file: {file_path}")
            print("\n--- PMTiles Header ---")
            
            # Convert any non-serializable objects to strings
            serializable_header = {}
            for key, value in header.items():
                if hasattr(value, 'name'):  # Enum objects have a 'name' attribute
                    serializable_header[key] = value.name
                else:
                    serializable_header[key] = value
            
            print(json.dumps(serializable_header, indent=4))
            print("\n--- PMTiles Metadata ---")
            print(json.dumps(metadata, indent=4))

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")

def get_pmtiles_tile(file_path, z, x, y, output_file=None):
    """Reads a specific tile from a PMTiles file."""
    try:
        with open(file_path, "rb") as f:
            reader = Reader(MmapSource(f))
            
            print(f"Reading tile {z}/{x}/{y} from PMTiles file: {file_path}")
            
            # Show tile bounds
            bounds = tile_bounds(x, y, z)
            print(f"\nTile {z}/{x}/{y} geographic bounds:")
            print(f"  North: {bounds['north']:.6f}")
            print(f"  South: {bounds['south']:.6f}")
            print(f"  East: {bounds['east']:.6f}")
            print(f"  West: {bounds['west']:.6f}")
            print(f"  Center: {bounds['center_lat']:.6f}, {bounds['center_lng']:.6f}")
            
            # Get the tile data
            tile_data = reader.get(z, x, y)
            
            if tile_data is None:
                print(f"\n✗ Tile {z}/{x}/{y} not found in the PMTiles file.")
                return None
            
            print(f"\n✓ Successfully retrieved tile {z}/{x}/{y}")
            print(f"Tile size: {len(tile_data)} bytes")
            
            # Determine tile format based on magic bytes
            tile_format = "unknown"
            if tile_data.startswith(b'\x1f\x8b'):
                tile_format = "gzipped (likely MVT)"
            elif tile_data.startswith(b'\x08') or tile_data.startswith(b'\x12'):
                tile_format = "MVT (Mapbox Vector Tile)"
            elif tile_data.startswith(b'\x89PNG'):
                tile_format = "PNG"
            elif tile_data.startswith(b'\xff\xd8'):
                tile_format = "JPEG"
            elif tile_data.startswith(b'<'):
                tile_format = "SVG"
            
            print(f"Tile format: {tile_format}")
            
            # Show first few bytes
            hex_preview = ' '.join(f'{b:02x}' for b in tile_data[:16])
            print(f"First 16 bytes: {hex_preview}")
            
            # Save tile to file if output path provided
            if output_file:
                with open(output_file, 'wb') as out_f:
                    out_f.write(tile_data)
                print(f"Tile saved to: {output_file}")
            
            return tile_data

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except Exception as e:
        print(f"An error occurred while reading the tile: {e}")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read PMTiles metadata or extract specific tiles.",
        epilog="""
Examples:
  # Show metadata
  python script.py file.pmtiles
  python script.py file.pmtiles --metadata
  
  # Get specific tile
  python script.py file.pmtiles --tile 8 0 0
  python script.py file.pmtiles 8 0 0
  
  # Save tile to file  
  python script.py file.pmtiles --tile 8 0 0 --output tile.mvt
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "file_path",
        help="The path to the PMTiles file."
    )
    
    # Positional arguments for tile coordinates (optional)
    parser.add_argument(
        "z", 
        nargs='?', 
        type=int,
        help="Zoom level (if providing tile coordinates directly)"
    )
    parser.add_argument(
        "x", 
        nargs='?', 
        type=int,
        help="Tile X coordinate"
    )
    parser.add_argument(
        "y", 
        nargs='?', 
        type=int,
        help="Tile Y coordinate"
    )
    
    # Named arguments
    parser.add_argument(
        "--metadata", "-m",
        action="store_true",
        help="Show metadata and header information"
    )
    parser.add_argument(
        "--tile", "-t",
        nargs=3,
        type=int,
        metavar=("Z", "X", "Y"),
        help="Get specific tile by zoom, x, y coordinates"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path to save the tile data"
    )
    
    args = parser.parse_args()
    
    # Determine what action to take
    if args.tile:
        # Using --tile flag
        z, x, y = args.tile
        get_pmtiles_tile(args.file_path, z, x, y, args.output)
    elif args.z is not None and args.x is not None and args.y is not None:
        # Using positional arguments
        get_pmtiles_tile(args.file_path, args.z, args.x, args.y, args.output)
    else:
        # Default to showing metadata
        get_pmtiles_metadata(args.file_path)