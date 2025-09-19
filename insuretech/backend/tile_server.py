#!/usr/bin/env python3
"""
Simple Working PMTiles Server
No TiTiler dependencies, just FastAPI + PMTiles
Install dependencies: pip install fastapi uvicorn pmtiles jinja2
Run with: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import os
import traceback
from typing import Dict, Optional, Tuple

import jinja2
from fastapi import FastAPI, HTTPException, Request
from pmtiles.reader import Reader, MmapSource
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

# PMTiles file configuration
PMTILES_FILES = {
    "z0_10": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z0_10.pmtiles",
    "z10_16": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z10_16.pmtiles", 
    "z18": "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/backend/source/NFHL_02_20250811_z18.pmtiles"
}

# Global PMTiles readers and file handles
pmtiles_readers: Dict[str, Reader] = {}
pmtiles_file_handles: Dict[str, object] = {}

def get_pmtiles_file_for_zoom(zoom_level: int) -> str:
    """Determine which PMTiles file to use based on zoom level"""
    if zoom_level <= 10:
        return "z0_10"
    elif zoom_level <= 16:
        return "z10_16"
    else:
        return "z18"

def initialize_pmtiles() -> bool:
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
            
            print(f"✓ Successfully loaded: {key} -> {os.path.basename(file_path)}")
            success_count += 1
            
        except Exception as e:
            print(f"✗ Error loading {file_path}: {e}")
            if key in pmtiles_file_handles:
                pmtiles_file_handles[key].close()
                del pmtiles_file_handles[key]
    
    if success_count == 0:
        print("❌ No PMTiles files could be loaded!")
        return False
        
    print(f"🎉 Successfully loaded {success_count} PMTiles files")
    return True

def cleanup_pmtiles():
    """Clean up PMTiles resources"""
    global pmtiles_file_handles, pmtiles_readers
    for key, file_handle in pmtiles_file_handles.items():
        if file_handle:
            file_handle.close()
    pmtiles_file_handles.clear()
    pmtiles_readers.clear()

def get_tile_data(z: int, x: int, y: int) -> Tuple[Optional[bytes], Optional[str]]:
    """Get tile data from appropriate PMTiles file"""
    if not pmtiles_readers:
        return None, None
    
    # Determine which PMTiles file to use
    file_key = get_pmtiles_file_for_zoom(z)
    
    if file_key not in pmtiles_readers:
        # Try to find an available reader as fallback
        available_keys = list(pmtiles_readers.keys())
        if not available_keys:
            return None, None
        file_key = available_keys[0]
    
    reader = pmtiles_readers[file_key]
    
    # Get tile data from PMTiles
    tile_data = reader.get(z, x, y)
    
    if tile_data is None:
        # Try other readers as fallback
        for fallback_key, fallback_reader in pmtiles_readers.items():
            if fallback_key != file_key:
                tile_data = fallback_reader.get(z, x, y)
                if tile_data is not None:
                    break
        
        if tile_data is None:
            return None, None
    
    # Determine content type based on tile format
    content_type = "application/octet-stream"
    
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
    
    return tile_data, content_type

# Setup Jinja2 templates
jinja2_env = jinja2.Environment(
    autoescape=True, 
    loader=jinja2.DictLoader({
        "index.html": """
<!DOCTYPE html>
<html>
<head>
    <title>PMTiles Server</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 40px; background: #f8f9fa; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 2px 20px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .subtitle { color: #7f8c8d; margin-bottom: 30px; }
        .status { background: #d4edda; color: #155724; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745; }
        .file-list { background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .file-item { margin: 8px 0; padding: 8px; background: white; border-radius: 4px; }
        .endpoints { background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 20px 0; }
        .endpoint { margin: 12px 0; padding: 12px; background: white; border-radius: 6px; border-left: 4px solid #007bff; }
        .endpoint a { text-decoration: none; color: #007bff; font-weight: 500; }
        .endpoint a:hover { text-decoration: underline; }
        .endpoint-desc { color: #6c757d; font-size: 14px; margin-top: 4px; }
        .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 6px; margin: 8px 8px 8px 0; font-weight: 500; transition: background 0.2s; }
        .btn:hover { background: #0056b3; color: white; text-decoration: none; }
        .btn-success { background: #28a745; }
        .btn-success:hover { background: #1e7e34; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗺️ PMTiles Tile Server</h1>
        <p class="subtitle">High-performance tile server for PMTiles using FastAPI</p>
        
        <div class="status">
            <strong>✅ Server Status:</strong> Running with {{ loaded_count }} PMTiles files loaded
        </div>
        
        <div class="file-list">
            <h3>📁 Loaded PMTiles Files:</h3>
            {% for key, info in files.items() %}
            <div class="file-item">
                <strong>{{ key }}</strong>: {{ info.filename }} 
                <span style="color: #6c757d;">(zoom {{ info.minzoom }}-{{ info.maxzoom }})</span>
            </div>
            {% endfor %}
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <a href="{{ api_root }}/map" class="btn btn-success">🌍 Open Map Viewer</a>
            <a href="{{ api_root }}/docs" class="btn">📚 API Documentation</a>
        </div>
        
        <div class="endpoints">
            <h3>🔗 Available Endpoints:</h3>
            <div class="endpoint">
                <strong>Tiles:</strong> <a href="{{ api_root }}/tiles/8/123/345">{{ api_root }}/tiles/{z}/{x}/{y}</a>
                <div class="endpoint-desc">Get individual map tiles by zoom/x/y coordinates</div>
            </div>
            <div class="endpoint">
                <strong>Map Viewer:</strong> <a href="{{ api_root }}/map">{{ api_root }}/map</a>
                <div class="endpoint-desc">Interactive map viewer with your PMTiles data</div>
            </div>
            <div class="endpoint">
                <strong>Metadata:</strong> <a href="{{ api_root }}/metadata">{{ api_root }}/metadata</a>
                <div class="endpoint-desc">PMTiles metadata from all loaded files</div>
            </div>
            <div class="endpoint">
                <strong>Info:</strong> <a href="{{ api_root }}/info">{{ api_root }}/info</a>
                <div class="endpoint-desc">Combined bounds and zoom level information</div>
            </div>
            <div class="endpoint">
                <strong>Health Check:</strong> <a href="{{ api_root }}/health">{{ api_root }}/health</a>
                <div class="endpoint-desc">Server health and file status</div>
            </div>
        </div>
    </div>
</body>
</html>
        """,
        "map.html": """
<!DOCTYPE html>
<html>
<head>
    <title>PMTiles Map Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <style>
        body { margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; }
        #map { height: 100vh; }
        .info { 
            position: absolute; 
            top: 15px; 
            right: 15px; 
            background: rgba(255,255,255,0.95); 
            padding: 20px; 
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            max-width: 320px;
            backdrop-filter: blur(10px);
        }
        .info h3 { margin: 0 0 15px 0; color: #2c3e50; font-size: 18px; }
        .info-section { margin: 15px 0; }
        .info-section h4 { margin: 0 0 8px 0; color: #34495e; font-size: 14px; font-weight: 600; }
        .file-item { font-size: 12px; color: #7f8c8d; margin: 4px 0; }
        .links a { display: inline-block; margin: 4px 8px 4px 0; padding: 6px 12px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 12px; }
        .links a:hover { background: #0056b3; }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(255,255,255,0.95);
            padding: 30px 40px;
            border-radius: 10px;
            font-size: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 2000;
        }
        .coordinates {
            position: absolute;
            bottom: 10px;
            left: 10px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 1000;
        }
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="loading" class="loading">🗺️ Loading map...</div>
    <div class="coordinates" id="coordinates">Click on map to see coordinates</div>
    <div class="info">
        <h3>🗺️ PMTiles Viewer</h3>
        
        <div class="info-section">
            <h4>📁 Files Loaded:</h4>
            {% for key, info in files.items() %}
            <div class="file-item">• {{ key }}: z{{ info.minzoom }}-{{ info.maxzoom }}</div>
            {% endfor %}
        </div>
        
        <div class="info-section">
            <h4>🔗 Links:</h4>
            <div class="links">
                <a href="{{ api_root }}/docs" target="_blank">API Docs</a>
                <a href="{{ api_root }}/info" target="_blank">Info</a>
                <a href="{{ api_root }}/health" target="_blank">Health</a>
                <a href="{{ api_root }}/" target="_blank">Home</a>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script>
        document.getElementById('loading').style.display = 'block';
        
        // Initialize map
        var map = L.map('map').setView([39.8283, -98.5795], 4);
        
        // Add OpenStreetMap base layer
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Add PMTiles overlay
        var pmtilesLayer = L.tileLayer('{{ api_root }}/tiles/{z}/{x}/{y}', {
            attribution: 'PMTiles Data',
            opacity: 0.8
        }).addTo(map);
        
        // Show coordinates on click
        map.on('click', function(e) {
            var lat = e.latlng.lat.toFixed(6);
            var lng = e.latlng.lng.toFixed(6);
            var zoom = map.getZoom();
            document.getElementById('coordinates').innerHTML = 
                `Lat: ${lat}, Lng: ${lng}, Zoom: ${zoom}`;
        });
        
        // Hide loading indicator when map is ready
        map.whenReady(function() {
            document.getElementById('loading').style.display = 'none';
        });
        
        // Try to get bounds and zoom to them
        fetch('{{ api_root }}/info')
            .then(response => response.json())
            .then(data => {
                console.log('PMTiles info:', data);
                if (data.overall_bounds) {
                    var bounds = data.overall_bounds;
                    console.log('Setting overall bounds:', bounds);
                    map.fitBounds([
                        [bounds[1], bounds[0]], // SW corner [lat, lng]
                        [bounds[3], bounds[2]]  // NE corner [lat, lng]
                    ]);
                }
                document.getElementById('loading').style.display = 'none';
            })
            .catch(err => {
                console.log('Could not load PMTiles info:', err);
                map.setView([39.8283, -98.5795], 4);
                document.getElementById('loading').style.display = 'none';
            });
            
        // Add tile loading feedback
        var tileCount = 0;
        pmtilesLayer.on('tileloadstart', function() {
            tileCount++;
        });
        
        pmtilesLayer.on('tileload', function() {
            tileCount--;
            if (tileCount === 0) {
                document.getElementById('loading').style.display = 'none';
            }
        });
        
        pmtilesLayer.on('tileerror', function(error) {
            console.log('Tile error:', error);
            tileCount--;
        });
    </script>
</body>
</html>
        """
    })
)
templates = Jinja2Templates(env=jinja2_env)

# Initialize PMTiles on startup
print("🚀 Starting PMTiles Server...")
print("📂 Looking for PMTiles files:")
for key, path in PMTILES_FILES.items():
    print(f"   {key}: {path}")

if not initialize_pmtiles():
    print("❌ Failed to initialize any PMTiles files. Exiting.")
    exit(1)

# Create FastAPI app
app = FastAPI(
    title="PMTiles Tile Server",
    description="High-performance tile server for PMTiles",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Routes
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """PMTiles server landing page"""
    # Get file info for template
    files_info = {}
    for key, reader in pmtiles_readers.items():
        header = reader.header()
        files_info[key] = {
            "filename": os.path.basename(PMTILES_FILES[key]),
            "minzoom": header.get('min_zoom', 0),
            "maxzoom": header.get('max_zoom', 18)
        }
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "api_root": str(request.base_url).rstrip("/"),
            "files": files_info,
            "loaded_count": len(pmtiles_readers),
        },
    )

@app.get("/map", response_class=HTMLResponse)
async def map_viewer(request: Request):
    """Map viewer page"""
    # Get file info for template
    files_info = {}
    for key, reader in pmtiles_readers.items():
        header = reader.header()
        files_info[key] = {
            "filename": os.path.basename(PMTILES_FILES[key]),
            "minzoom": header.get('min_zoom', 0),
            "maxzoom": header.get('max_zoom', 18)
        }
    
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "api_root": str(request.base_url).rstrip("/"),
            "files": files_info,
        },
    )

@app.get("/tiles/{z}/{x}/{y}")
async def get_tile(z: int, x: int, y: int):
    """Serve individual tiles from appropriate PMTiles file"""
    try:
        tile_data, content_type = get_tile_data(z, x, y)
        
        if tile_data is None:
            # Return 204 No Content for missing tiles
            return Response(status_code=204)
        
        headers = {"Cache-Control": "public, max-age=3600"}
        if content_type == "application/x-protobuf":
            headers['Content-Encoding'] = 'gzip'
        
        return Response(
            content=tile_data,
            media_type=content_type,
            headers=headers
        )
        
    except Exception as e:
        print(f"Error serving tile {z}/{x}/{y}: {e}")
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
        raise HTTPException(status_code=500, detail="Error getting metadata")

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
            west = min(b[0] for b in all_bounds)
            south = min(b[1] for b in all_bounds)
            east = max(b[2] for b in all_bounds)
            north = max(b[3] for b in all_bounds)
            combined_info["overall_bounds"] = [west, south, east, north]
        
        combined_info["overall_minzoom"] = min(all_minzooms) if all_minzooms else 0
        combined_info["overall_maxzoom"] = max(all_maxzooms) if all_maxzooms else 18
        
        return combined_info
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error getting info")

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

# Cleanup on shutdown
@app.on_event("shutdown")
def shutdown_event():
    cleanup_pmtiles()

if __name__ == "__main__":
    import uvicorn
    print("🌍 Server starting on http://localhost:8000")
    print("📍 Endpoints:")
    print("   • Map viewer: http://localhost:8000/map")
    print("   • API docs: http://localhost:8000/docs") 
    print("   • Health: http://localhost:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)