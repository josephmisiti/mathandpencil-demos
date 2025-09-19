#!/usr/bin/env python3
"""
PMTiles Tile Server in Python
Install dependencies: pip install flask pmtiles flask-cors
Run with: python tile_server.py
"""

import os
import json
from flask import Flask, Response, send_from_directory, jsonify, request
from flask_cors import CORS
from pmtiles.reader import Reader
import gzip

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Configuration
PMTILES_FILE = "/Users/josephmisiti/mathandpencil/projects/mathandpencil-demos/insuretech/data/source/NFHL_02_20250811_z0_10.pmtiles"
PORT = 3000

# Global PMTiles reader
pmtiles_reader = None

def initialize_pmtiles():
    """Initialize the PMTiles reader"""
    global pmtiles_reader
    if not os.path.exists(PMTILES_FILE):
        print(f"Error: PMTiles file not found: {PMTILES_FILE}")
        return False
    
    try:
        pmtiles_reader = Reader(PMTILES_FILE)
        print(f"Successfully loaded PMTiles file: {PMTILES_FILE}")
        return True
    except Exception as e:
        print(f"Error loading PMTiles file: {e}")
        return False

@app.route('/')
def index():
    """Serve a simple map viewer"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>PMTiles Tile Server</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
        <style>
            body { margin: 0; padding: 0; }
            #map { height: 100vh; }
            .info { 
                position: absolute; 
                top: 10px; 
                right: 10px; 
                background: rgba(255,255,255,0.9); 
                padding: 10px; 
                border-radius: 5px;
                z-index: 1000;
                font-family: Arial, sans-serif;
            }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="info">
            <strong>PMTiles Tile Server</strong><br>
            Serving: ''' + PMTILES_FILE + '''<br>
            Tile URL: /tiles/{z}/{x}/{y}
        </div>
        
        <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
        <script>
            // Initialize map
            var map = L.map('map').setView([0, 0], 2);
            
            // Add OpenStreetMap base layer
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            // Add PMTiles overlay
            var pmtilesLayer = L.tileLayer('http://localhost:''' + str(PORT) + '''/tiles/{z}/{x}/{y}', {
                attribution: 'PMTiles',
                opacity: 0.7
            }).addTo(map);
        </script>
    </body>
    </html>
    '''

@app.route('/tiles/<int:z>/<int:x>/<int:y>')
def get_tile(z, x, y):
    """Serve individual tiles"""
    if pmtiles_reader is None:
        return Response("PMTiles not initialized", status=500)
    
    try:
        # Get tile data from PMTiles
        tile_data = pmtiles_reader.get(z, x, y)
        
        if tile_data is None:
            return Response("Tile not found", status=404)
        
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
        
        response = Response(tile_data, content_type=content_type)
        
        # Add appropriate headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        
        if content_type == "application/x-protobuf":
            response.headers['Content-Encoding'] = 'gzip'
        
        return response
        
    except Exception as e:
        print(f"Error serving tile {z}/{x}/{y}: {e}")
        return Response(f"Error: {str(e)}", status=500)

@app.route('/metadata')
def get_metadata():
    """Get PMTiles metadata"""
    if pmtiles_reader is None:
        return jsonify({"error": "PMTiles not initialized"}), 500
    
    try:
        header = pmtiles_reader.header()
        metadata = pmtiles_reader.metadata()
        
        return jsonify({
            "header": {
                "tile_type": header.get("tile_type"),
                "tile_compression": header.get("tile_compression"),
                "min_zoom": header.get("min_zoom"),
                "max_zoom": header.get("max_zoom"),
                "bounds": header.get("bounds")
            },
            "metadata": metadata
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    status = "healthy" if pmtiles_reader is not None else "unhealthy"
    return jsonify({
        "status": status,
        "pmtiles_file": PMTILES_FILE,
        "file_exists": os.path.exists(PMTILES_FILE)
    })

if __name__ == '__main__':
    print("Starting PMTiles Tile Server...")
    print(f"Looking for PMTiles file: {PMTILES_FILE}")
    
    if initialize_pmtiles():
        print(f"Server starting on http://localhost:{PORT}")
        print(f"Tile endpoint: http://localhost:{PORT}/tiles/{{z}}/{{x}}/{{y}}")
        print(f"Metadata: http://localhost:{PORT}/metadata")
        print(f"Health check: http://localhost:{PORT}/health")
        app.run(host='0.0.0.0', port=PORT, debug=True)
    else:
        print("Failed to initialize PMTiles. Please check your file path.")
        print(f"Current working directory: {os.getcwd()}")
        print("Available files:", os.listdir('.'))