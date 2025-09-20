#!/usr/bin/env python3
"""
Simple Working PMTiles Server (Single File Version)
No TiTiler dependencies, just FastAPI + PMTiles.
This version is refactored to serve a single, consolidated PMTiles file
and uses the modern 'lifespan' event handler.

Install dependencies: pip install fastapi uvicorn pmtiles jinja2
Run with: uvicorn pmtiles_server:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
import os
import traceback
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple

import jinja2
from fastapi import FastAPI, HTTPException, Request
from pmtiles.reader import Reader, MmapSource
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PMTILES_FILE_PATH = os.path.join(BASE_DIR, "source", "NFHL_02_20250811_z10_16.pmtiles")

PMTILES_FILES = {
    "flood_zones": PMTILES_FILE_PATH,
}

# Global PMTiles readers and file handles
pmtiles_readers: Dict[str, Reader] = {}
pmtiles_file_handles: Dict[str, object] = {}

def initialize_pmtiles() -> bool:
    """Initialize all PMTiles readers from the configuration."""
    global pmtiles_readers, pmtiles_file_handles
    
    key, file_path = next(iter(PMTILES_FILES.items()))

    if not os.path.exists(file_path):
        print("="*80)
        print(f"❌ FATAL ERROR: PMTiles file not found at the configured path.")
        print(f"   Checked Path: {file_path}")
        print("   Please ensure the file exists and the path is correct.")
        print("="*80)
        raise FileNotFoundError(f"PMTiles file not found: {file_path}")
    
    try:
        file_handle = open(file_path, "rb")
        reader = Reader(MmapSource(file_handle))
        
        pmtiles_file_handles[key] = file_handle
        pmtiles_readers[key] = reader
        
        print(f"✓ Successfully loaded: {key} -> {os.path.basename(file_path)}")
        return True
        
    except Exception as e:
        print(f"✗ Error loading {file_path}: {e}")
        if key in pmtiles_file_handles:
            pmtiles_file_handles[key].close()
            del pmtiles_file_handles[key]
        return False

def cleanup_pmtiles():
    """Clean up PMTiles resources on shutdown."""
    print("Shutting down and closing PMTiles file handles...")
    global pmtiles_file_handles
    for key, file_handle in pmtiles_file_handles.items():
        if file_handle:
            file_handle.close()
    pmtiles_file_handles.clear()
    pmtiles_readers.clear()
    print("Cleanup complete.")

def get_tile_data(z: int, x: int, y: int) -> Tuple[Optional[bytes], Optional[str]]:
    """Get tile data from the loaded PMTiles file."""
    if not pmtiles_readers:
        return None, None
    
    reader = next(iter(pmtiles_readers.values()))
    tile_data = reader.get(z, x, y)
    
    if tile_data is None:
        return None, None
    
    content_type = "application/vnd.mapbox-vector-tile"
    return tile_data, content_type

# --- TEMPLATES ---

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
        <p class="subtitle">High-performance tile server for a single PMTiles file using FastAPI.</p>
        <div class="status">
            <strong>✅ Server Status:</strong> Running with {{ loaded_count }} PMTiles file(s) loaded.
        </div>
        <div class="file-list">
            <h3>📁 Loaded PMTiles File:</h3>
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
                <strong>Tiles:</strong> <a href="{{ api_root }}/tiles/8/82/97">{{ api_root }}/tiles/{z}/{x}/{y}</a>
                <div class="endpoint-desc">Get individual map tiles by zoom/x/y coordinates.</div>
            </div>
             <div class="endpoint">
                <strong>Info / TileJSON:</strong> <a href="{{ api_root }}/info">{{ api_root }}/info</a>
                <div class="endpoint-desc">Combined bounds, zoom levels, and TileJSON metadata.</div>
            </div>
            <div class="endpoint">
                <strong>Health Check:</strong> <a href="{{ api_root }}/health">{{ api_root }}/health</a>
                <div class="endpoint-desc">Server health and file status.</div>
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
    <title>PMTiles Vector Map Viewer</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { margin: 0; padding: 0; font-family: sans-serif; }
        #map { height: 100vh; background: #f0f0f0; }
    </style>
</head>
<body>
    <div id="map"></div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/protomaps-leaflet@latest/dist/protomaps-leaflet.min.js"></script>

    <script>
        window.onload = function () {
            const map = L.map('map');
  
            // Light base map
            L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            }).addTo(map);

            // --- VECTOR TILE LAYER ---
            const floodZoneUrl = '{{ api_root }}/tiles/{z}/{x}/{y}';

            // Using the correct function call for this library version
            const floodZoneLayer = protomaps.leafletLayer({
                url: floodZoneUrl,
                paint: (feature) => {
                    const zone = feature.props.FLD_ZONE;
                    if (zone === 'A' || zone === 'AE' || zone === 'AH' || zone === 'AO') {
                        return { color: "#3b82f6", opacity: 0.5 };
                    } else if (zone === 'V' || zone === 'VE') {
                        return { color: "#ef4444", opacity: 0.6 };
                    } else if (zone === 'X') {
                        const subty = feature.props.ZONE_SUBTY;
                        if (subty && subty.includes("0.2")) {
                           return { color: "#f97316", opacity: 0.4 };
                        }
                    }
                    return { color: "#a8a29e", opacity: 0.3 };
                }
            });

            floodZoneLayer.addTo(map);

            // Fetch info and zoom to data bounds
            fetch('{{ api_root }}/info')
                .then(response => response.json())
                .then(data => {
                    if (data && data.bounds) {
                        const bounds = [[data.bounds[1], data.bounds[0]], [data.bounds[3], data.bounds[2]]];
                        map.fitBounds(bounds);
                    } else {
                        // Centered on Alaska
                        map.setView([64, -150], 4);
                    }
                })
                .catch(err => {
                    console.error('Could not load PMTiles info:', err);
                    // Centered on Alaska
                    map.setView([64, -150], 4);
                });
        };
    </script>
</body>
</html>
        """
    })
)
templates = Jinja2Templates(env=jinja2_env)

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for the application."""
    print("🚀 Starting PMTiles Server...")
    initialize_pmtiles()
    yield
    cleanup_pmtiles()

# --- APP SETUP ---
app = FastAPI(
    title="PMTiles Tile Server",
    description="High-performance tile server for a single PMTiles file.",
    version="1.5.2", # Incremented version
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["GET"], allow_headers=["*"],
)

# --- API ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
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
        {"request": request, "api_root": str(request.base_url).rstrip("/"), "files": files_info, "loaded_count": len(pmtiles_readers)},
    )

@app.get("/map", response_class=HTMLResponse)
async def map_viewer(request: Request):
    return templates.TemplateResponse("map.html", {"request": request, "api_root": str(request.base_url).rstrip("/")})

@app.get("/tiles/{z}/{x}/{y}", response_class=Response)
async def get_tile(z: int, x: int, y: int):
    try:
        tile_data, content_type = get_tile_data(z, x, y)
        if tile_data is None:
            return Response(status_code=204)
        
        headers = {
            "Cache-Control": "public, max-age=86400",
            "Content-Type": "application/vnd.mapbox-vector-tile",
        }

        # PMTiles stores all vector tiles gzip-compressed; advertise that so
        # browsers transparently decompress them before deck.gl parses bytes.
        if tile_data.startswith(b"\x1f\x8b"):
            headers["Content-Encoding"] = "gzip"

        return Response(content=tile_data, headers=headers)
    except Exception as e:
        print(f"Error serving tile {z}/{x}/{y}: {e}")
        traceback.print_exc()
        return Response(status_code=500, content=f"Error serving tile: {e}")

@app.get("/info")
async def get_info(request: Request):
    if not pmtiles_readers:
        raise HTTPException(status_code=404, detail="PMTiles file not loaded")
    
    try:
        reader = next(iter(pmtiles_readers.values()))
        metadata = reader.metadata() or {}
        header = reader.header()

        bounds = [
            header.get("min_lon_e7", 0) / 1e7,
            header.get("min_lat_e7", 0) / 1e7,
            header.get("max_lon_e7", 0) / 1e7,
            header.get("max_lat_e7", 0) / 1e7,
        ]
        center = [
            header.get("center_lon_e7", 0) / 1e7,
            header.get("center_lat_e7", 0) / 1e7,
            header.get("center_zoom", 0),
        ]

        tilejson = {
            "tilejson": "2.2.0",
            "name": metadata.get("name", "Flood Zones"),
            "tiles": [f"{str(request.base_url).rstrip('/')}/tiles/{{z}}/{{x}}/{{y}}"],
            "minzoom": header.get("min_zoom", 0),
            "maxzoom": header.get("max_zoom", 18),
            "bounds": bounds,
            "center": center,
            "vector_layers": metadata.get("vector_layers", [])
        }
        return tilejson
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading metadata: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pmtiles_server:app", host="0.0.0.0", port=8000, reload=True)
