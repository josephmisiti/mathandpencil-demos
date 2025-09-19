#!/usr/bin/env python3
"""
PMTiles FastAPI Server
Install dependencies: pip install fastapi uvicorn pmtiles
Run with: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import traceback
from fastapi import FastAPI, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pmtiles.reader import Reader, MmapSource

# Configuration - Multiple PMTiles files for different zoom levels
PMTILES_FILES = {
    "z0_10": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z0_10.pmtiles",
    "z10_16": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z10_16.pmtiles", 
    "z18": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z18.pmtiles"
}
PORT = 8000

# Global PMTiles readers and file handles
pmtiles_readers = {}
pmtiles_file_handles = {}

def get_pmtiles_file_for_zoom(zoom_level):
    """Determine which PMTiles file to use based on zoom level"""
    if zoom_level <= 10:
        return "z0_10"
    elif zoom_level <= 16:
        return "z10_16"
    else:
        return "z18"

def initialize_pmtiles():
    """Initialize all PMTiles readers"""
    global pmtiles_readers, pmtiles_file_handles
    
    success_count = 0
    
    for key, file_path in PMTILES_FILES.items():
        if not os.path.exists(file_path):
            print(f"Warning: PMTiles file not found: {file_path}")
            continue
        
        try:
            # Open the file and create a Reader with MmapSource
            file_handle = open(file_path, "rb")
            reader = Reader(MmapSource(file_handle))
            
            pmtiles_file_handles[key] = file_handle
            pmtiles_readers[key] = reader
            
            print(f"Successfully loaded PMTiles file: {key} -> {os.path.basename(file_path)}")
            success_count += 1
            
        except Exception as e:
            print(f"Error loading PMTiles file {file_path}: {e}")
            print("Full traceback:")
            traceback.print_exc()
            if key in pmtiles_file_handles:
                pmtiles_file_handles[key].close()
                del pmtiles_file_handles[key]
    
    if success_count == 0:
        print("No PMTiles files could be loaded!")
        return False
        
    print(f"Successfully loaded {success_count} PMTiles files")
    return True

def cleanup_pmtiles():
    """Clean up PMTiles resources"""
    global pmtiles_file_handles
    for key, file_handle in pmtiles_file_handles.items():
        if file_handle:
            file_handle.close()
    pmtiles_file_handles.clear()
    pmtiles_readers.clear()

# Initialize PMTiles on startup
print("Starting PMTiles FastAPI Server...")
print(f"Looking for PMTiles files:")
for key, path in PMTILES_FILES.items():
    print(f"  {key}: {path}")

if not initialize_pmtiles():
    print("Failed to initialize any PMTiles files. Please check your file paths.")
    print(f"Current working directory: {os.getcwd()}")
    exit(1)

# Create FastAPI app
app = FastAPI(
    title="PMTiles Tile Server",
    description="A high-performance tile server for PMTiles using FastAPI",
    version="1.0.0",
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint with information about available services"""
    return {
        "title": "PMTiles Tile Server",
        "description": "Serving PMTiles using FastAPI",
        "pmtiles_files": {key: os.path.basename(path) for key, path in PMTILES_FILES.items()},
        "loaded_files": list(pmtiles_readers.keys()),
        "endpoints": {
            "tiles": "/tiles/{z}/{x}/{y}",
            "metadata": "/metadata",
            "info": "/info",
            "map": "/map",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.get("/tiles/{z}/{x}/{y}")
async def get_tile(z: int, x: int, y: int):
    """Serve individual tiles from appropriate PMTiles file based on zoom level"""
    if not pmtiles_readers:
        raise HTTPException(status_code=500, detail="No PMTiles files initialized")
    
    try:
        # Determine which PMTiles file to use
        file_key = get_pmtiles_file_for_zoom(z)
        
        if file_key not in pmtiles_readers:
            # Try to find an available reader as fallback
            available_keys = list(pmtiles_readers.keys())
            if not available_keys:
                raise HTTPException(status_code=500, detail="No PMTiles readers available")
            file_key = available_keys[0]
            print(f"Warning: Using fallback reader {file_key} for zoom {z}")
        
        reader = pmtiles_readers[file_key]
        
        # Get tile data from PMTiles
        tile_data = reader.get(z, x, y)
        
        if tile_data is None:
            # Try other readers as fallback
            for fallback_key, fallback_reader in pmtiles_readers.items():
                if fallback_key != file_key:
                    tile_data = fallback_reader.get(z, x, y)
                    if tile_data is not None:
                        print(f"Found tile {z}/{x}/{y} in fallback reader {fallback_key}")
                        reader = fallback_reader
                        break
            
            if tile_data is None:
                # Return 204 No Content instead of 404 to avoid errors in map viewers
                return Response(status_code=204)
        
        # Determine content type based on tile format
        content_type = "application/octet-stream"
        
        # Check if it's a vector tile (MVT)
        if tile_data.startswith(b'\x1f\x8b'):  # Gzipped
            content_type = "application/x-protobuf"
        elif tile_data.startswith(b'\x08') or tile_data.startswith(b'\x12'):  # MVT magic bytes
            content_type = "application/x-protobuf"
        elif tile_data.startswith(b'\x89PNG'):  # PNG
            content_type = "image/png"
        elif tile_data.startswith(b'\xff\xd8'):  # JPEG
            content_type = "image/jpeg"
        elif tile_data.startswith(b'<'):  # Might be SVG
            content_type = "image/svg+xml"
        
        headers = {
            'Cache-Control': 'public, max-age=3600'
        }
        
        if content_type == "application/x-protobuf":
            headers['Content-Encoding'] = 'gzip'
        
        return Response(
            content=tile_data,
            media_type=content_type,
            headers=headers
        )
        
    except Exception as e:
        error_msg = f"Error serving tile {z}/{x}/{y}: {e}"
        print(error_msg)
        print("Full traceback:")
        traceback.print_exc()
        # Return 204 No Content instead of 500 to avoid flooding logs
        return Response(status_code=204)

@app.get("/metadata")
async def get_metadata():
    """Get PMTiles metadata from all files"""
    if not pmtiles_readers:
        raise HTTPException(status_code=500, detail="No PMTiles files initialized")
    
    try:
        all_metadata = {}
        
        for key, reader in pmtiles_readers.items():
            header = reader.header()
            metadata = reader.metadata()
            
            # Convert any non-serializable objects to strings (like enums)
            serializable_header = {}
            for hkey, value in header.items():
                if hasattr(value, 'name'):  # Enum objects have a 'name' attribute
                    serializable_header[hkey] = value.name
                else:
                    serializable_header[hkey] = value
            
            all_metadata[key] = {
                "header": serializable_header,
                "metadata": metadata
            }
        
        return all_metadata
    except Exception as e:
        error_msg = f"Error getting metadata: {e}"
        print(error_msg)
        print("Full traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting metadata: {str(e)}")

@app.get("/info")
async def get_info():
    """Get PMTiles info (bounds, zoom levels, etc.) from all files"""
    if not pmtiles_readers:
        raise HTTPException(status_code=500, detail="No PMTiles files initialized")
    
    try:
        combined_info = {
            "files": {},
            "overall_bounds": None,
            "overall_minzoom": None,
            "overall_maxzoom": None
        }
        
        all_bounds = []
        all_minzooms = []
        all_maxzooms = []
        
        for key, reader in pmtiles_readers.items():
            header = reader.header()
            metadata = reader.metadata()
            
            # Convert any non-serializable objects to strings (like enums)
            serializable_header = {}
            for hkey, value in header.items():
                if hasattr(value, 'name'):  # Enum objects have a 'name' attribute
                    serializable_header[hkey] = value.name
                else:
                    serializable_header[hkey] = value
            
            # Extract bounds and zoom info
            bounds = serializable_header.get('bounds')
            minzoom = serializable_header.get('min_zoom', 0)
            maxzoom = serializable_header.get('max_zoom', 18)
            
            file_info = {
                "minzoom": minzoom,
                "maxzoom": maxzoom,
                "header": serializable_header,
                "metadata": metadata
            }
            
            if bounds:
                file_info["bounds"] = bounds
                all_bounds.append(bounds)
            
            all_minzooms.append(minzoom)
            all_maxzooms.append(maxzoom)
            
            combined_info["files"][key] = file_info
        
        # Calculate overall bounds and zoom levels
        if all_bounds:
            # Combine all bounds to get overall extent
            # bounds format: [west, south, east, north]
            west = min(b[0] for b in all_bounds)
            south = min(b[1] for b in all_bounds)
            east = max(b[2] for b in all_bounds)
            north = max(b[3] for b in all_bounds)
            combined_info["overall_bounds"] = [west, south, east, north]
        
        combined_info["overall_minzoom"] = min(all_minzooms) if all_minzooms else 0
        combined_info["overall_maxzoom"] = max(all_maxzooms) if all_maxzooms else 18
        
        return combined_info
    except Exception as e:
        error_msg = f"Error getting info: {e}"
        print(error_msg)
        print("Full traceback:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting info: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    loaded_files = list(pmtiles_readers.keys())
    status = "healthy" if loaded_files else "unhealthy"
    
    file_status = {}
    for key, path in PMTILES_FILES.items():
        file_status[key] = {
            "path": path,
            "exists": os.path.exists(path),
            "loaded": key in pmtiles_readers
        }
    
    return {
        "status": status,
        "loaded_files": loaded_files,
        "file_status": file_status
    }

@app.get("/map", response_class=HTMLResponse)
async def map_viewer():
    """Simple map viewer"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PMTiles Viewer</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
        <style>
            body {{ margin: 0; padding: 0; }}
            #map {{ height: 100vh; }}
            .info {{ 
                position: absolute; 
                top: 10px; 
                right: 10px; 
                background: rgba(255,255,255,0.9); 
                padding: 10px; 
                border-radius: 5px;
                z-index: 1000;
                font-family: Arial, sans-serif;
                max-width: 300px;
            }}
            .loading {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(255,255,255,0.9);
                padding: 20px;
                border-radius: 5px;
                font-family: Arial, sans-serif;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div id="loading" class="loading">Loading map...</div>
        <div class="info">
            <strong>PMTiles Viewer</strong><br>
            <small>Powered by FastAPI</small><br><br>
            <strong>Files:</strong><br>
            {' • '.join([f"{key}: z{info.get('minzoom', '?')}-{info.get('maxzoom', '?')}" for key, info in [('z0_10', {'minzoom': 0, 'maxzoom': 10}), ('z10_16', {'minzoom': 10, 'maxzoom': 16}), ('z18', {'minzoom': 18, 'maxzoom': 18})]])}<br><br>
            <strong>Server:</strong> http://localhost:{PORT}<br><br>
            <strong>Endpoints:</strong><br>
            <a href="/docs" target="_blank">API Docs</a><br>
            <a href="/info" target="_blank">Info</a><br>
            <a href="/metadata" target="_blank">Metadata</a><br>
            <a href="/health" target="_blank">Health</a>
        </div>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
        <script>
            document.getElementById('loading').style.display = 'block';
            
            // Initialize map
            var map = L.map('map').setView([39.8283, -98.5795], 4); // Center of USA
            
            // Add OpenStreetMap base layer
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '© OpenStreetMap contributors'
            }}).addTo(map);
            
            // Add PMTiles overlay
            var pmtilesLayer = L.tileLayer('/tiles/{{z}}/{{x}}/{{y}}', {{
                attribution: 'PMTiles',
                opacity: 0.7
            }}).addTo(map);
            
            // Hide loading indicator when map is ready
            map.whenReady(function() {{
                document.getElementById('loading').style.display = 'none';
            }});
            
            // Try to get bounds and zoom to them
            fetch('/info')
                .then(response => response.json())
                .then(data => {{
                    console.log('PMTiles info:', data);
                    if (data.overall_bounds) {{
                        var bounds = data.overall_bounds;
                        console.log('Setting overall bounds:', bounds);
                        map.fitBounds([
                            [bounds[1], bounds[0]], // SW corner [lat, lng]
                            [bounds[3], bounds[2]]  // NE corner [lat, lng]
                        ]);
                    }}
                    document.getElementById('loading').style.display = 'none';
                }})
                .catch(err => {{
                    console.log('Could not load PMTiles info:', err);
                    // Fallback for NFHL (flood data) - likely covers USA
                    map.setView([39.8283, -98.5795], 4);
                    document.getElementById('loading').style.display = 'none';
                }});
                
            // Add error handling for tile loading
            pmtilesLayer.on('tileerror', function(error) {{
                console.log('Tile error:', error);
            }});
            
            pmtilesLayer.on('tileload', function() {{
                console.log('Tile loaded successfully');
            }});
        </script>
    </body>
    </html>
    """

# Cleanup on shutdown
@app.on_event("shutdown")
def shutdown_event():
    cleanup_pmtiles()

if __name__ == "__main__":
    import uvicorn
    print(f"Server starting on http://localhost:{PORT}")
    print(f"Tile endpoint: http://localhost:{PORT}/tiles/{{z}}/{{x}}/{{y}}")
    print(f"Map viewer: http://localhost:{PORT}/map")
    print(f"API docs: http://localhost:{PORT}/docs")
    print(f"Health check: http://localhost:{PORT}/health")
    uvicorn.run(app, host="0.0.0.0", port=PORT, reload=True)