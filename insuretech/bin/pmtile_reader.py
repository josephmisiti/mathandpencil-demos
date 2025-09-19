import argparse
import json
from pmtiles.reader import Reader, MmapSource  # Import MmapSource

def get_pmtiles_metadata(file_path):
    """Reads and prints the header and metadata from a PMTiles file."""
    try:
        # Open the file and create a Reader with MmapSource
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

if __name__ == "__main__":
    # Set up the command-line argument parser
    parser = argparse.ArgumentParser(
        description="Read header and metadata from a PMTiles file."
    )
    parser.add_argument(
        "file_path",
        help="The path to the PMTiles file (local path or remote URL).",
    )
    
    # Parse the command-line arguments
    args = parser.parse_args()

    # Call the function with the provided file path
    get_pmtiles_metadata(args.file_path)