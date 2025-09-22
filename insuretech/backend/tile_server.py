#!/usr/bin/env python3
"""
Simple PMTiles Server with FastAPI.

This variant supports serving multiple PMTiles archives that cover different
zoom ranges (and optionally different geographic footprints) for the same
logical dataset. It automatically selects the best archive to satisfy a tile
request based on zoom level and tile bounds.

Install dependencies: pip install fastapi uvicorn pmtiles jinja2
Run with: uvicorn tile_server:app --host 0.0.0.0 --port 8000 --reload
"""

import gzip
import io
import logging
import math
import os
import traceback
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Tuple

import jinja2
from fastapi import FastAPI, HTTPException, Query, Request
from pmtiles.reader import Reader, MmapSource
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

from mapbox_vector_tile import decode as decode_mvt
# from PIL import Image
from shapely.geometry import Point, shape

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Describe the PMTiles archives that should be loaded. Each entry should point
# to a PMTiles file on disk; if it is missing it will simply be skipped.
SLOSH_CATEGORIES = [
    "Category1",
    "Category2",
    "Category3",
    "Category4",
    "Category5",
]

SLOSH_CATEGORY_LOOKUP = {
    category.lower(): category for category in SLOSH_CATEGORIES
}

for category in SLOSH_CATEGORIES:
    short = category.replace("Category", "cat").lower()
    digit = category[-1]
    SLOSH_CATEGORY_LOOKUP[short] = category
    SLOSH_CATEGORY_LOOKUP[digit] = category

PMTILES_VARIANTS: List[Dict[str, str]] = [
    {
        "key": "nfhl_combined",
        "dataset": "flood_zones",
        "path": os.path.join(BASE_DIR, "source", "NFHL_combined.pmtiles"),
    },
]

for category in SLOSH_CATEGORIES:
    PMTILES_VARIANTS.append(
        {
            "key": f"slosh_{category.lower()}",
            "dataset": "slosh",
            "category": category,
            "path": os.path.join(BASE_DIR, "source", f"SLOSH_PR_{category}.pmtiles"),
        }
    )

# Global catalogue of loaded PMTiles variants indexed by their key.
CatalogEntry = Dict[str, object]
pmtiles_catalog: Dict[str, CatalogEntry] = {}
# Map dataset name -> list of variant keys for quick lookup.
pmtiles_datasets: Dict[str, List[str]] = {}

TILE_TYPE_TO_MIME = {
    1: "application/vnd.mapbox-vector-tile",
    2: "image/png",
    3: "image/jpeg",
    4: "image/webp",
}


def _lon_lat_bounds_from_header(header: Dict[str, int]) -> Tuple[float, float, float, float]:
    """Convert fixed-point header bounds to floats."""
    return (
        header.get("min_lon_e7", 0) / 1e7,
        header.get("min_lat_e7", 0) / 1e7,
        header.get("max_lon_e7", 0) / 1e7,
        header.get("max_lat_e7", 0) / 1e7,
    )


def _tile_xyz_to_lon_lat_bounds(z: int, x: int, y: int) -> Tuple[float, float, float, float]:
    """Return lon/lat bounds for a WebMercator tile."""
    n = 2 ** z
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0

    def mercator_to_lat(tile_y: int) -> float:
        exp = math.pi * (1 - 2 * tile_y / n)
        return math.degrees(math.atan(math.sinh(exp)))

    lat_max = mercator_to_lat(y)
    lat_min = mercator_to_lat(y + 1)
    return (lon_min, lat_min, lon_max, lat_max)


def _bbox_intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    """Check if two [min_lon, min_lat, max_lon, max_lat] boxes intersect."""
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _latlng_to_slippy(lat: float, lon: float, z: int) -> Tuple[int, int, int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    lon = (lon + 180.0) % 360.0 - 180.0

    lat_rad = math.radians(lat)
    n = 2 ** z
    x_float = (lon + 180.0) / 360.0 * n
    y_float = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n

    x_tile = int(math.floor(x_float))
    y_tile = int(math.floor(y_float))

    x_pixel = int(round((x_float - x_tile) * 256))
    y_pixel = int(round((y_float - y_tile) * 256))

    x_pixel = min(max(x_pixel, 0), 255)
    y_pixel = min(max(y_pixel, 0), 255)

    return x_tile, y_tile, x_pixel, y_pixel


def _lon_lat_to_tile(z: int, lon: float, lat: float) -> Tuple[int, int]:
    """Convert geographic coordinates to XYZ tile indices for a zoom level."""
    # Clamp latitude to WebMercator valid range to avoid math overflow.
    lat = max(min(lat, 85.05112878), -85.05112878)
    lon = (lon + 180.0) % 360.0 - 180.0

    lat_rad = math.radians(lat)
    n = 2 ** z
    x_float = (lon + 180.0) / 360.0 * n
    y_float = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n

    x = int(min(max(x_float, 0), n - 1))
    y = int(min(max(y_float, 0), n - 1))
    return x, y


def _decompress_tile(tile_data: bytes) -> bytes:
    """Return decompressed tile bytes, handling gzip-compressed payloads."""
    if tile_data.startswith(b"\x1f\x8b"):
        return gzip.decompress(tile_data)
    return tile_data


def _project_point_to_lonlat(x: float, y: float, bbox: Tuple[float, float, float, float], extent: int) -> Tuple[float, float]:
    lon_min, lat_min, lon_max, lat_max = bbox
    lon_span = lon_max - lon_min
    lat_span = lat_max - lat_min

    lon = lon_min + (x / extent) * lon_span
    lat = lat_max - (y / extent) * lat_span
    return lon, lat


def _transform_geometry_coordinates(coords, bbox, extent):
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        return _project_point_to_lonlat(coords[0], coords[1], bbox, extent)
    if isinstance(coords, (list, tuple)):
        return [
            _transform_geometry_coordinates(child, bbox, extent)
            for child in coords
        ]
    return coords


def _iter_tile_features(tile_bytes: bytes, z: int, x: int, y: int):
    """Yield (layer_name, feature_dict) pairs for decoded MVT features."""
    bbox = _tile_xyz_to_lon_lat_bounds(z, x, y)
    decoded = decode_mvt(tile_bytes)

    for layer_name, layer in decoded.items():
        if not isinstance(layer, dict):
            continue

        features = layer.get("features", [])
        extent = layer.get("extent", 4096) or 4096

        for feature in features:
            geometry = feature.get("geometry")
            if geometry and "coordinates" in geometry:
                transformed = {
                    "type": geometry.get("type"),
                    "coordinates": _transform_geometry_coordinates(geometry.get("coordinates"), bbox, extent),
                }
                feature = {**feature, "geometry": transformed}

            yield layer_name, feature


def initialize_pmtiles() -> bool:
    """Initialize all configured PMTiles archives."""
    global pmtiles_catalog, pmtiles_datasets

    if pmtiles_catalog:
        # Already initialized (useful in reload scenarios)
        return True

    loaded_count = 0
    for entry in PMTILES_VARIANTS:
        key = entry["key"]
        dataset = entry["dataset"]
        path = entry["path"]

        if not os.path.exists(path):
            logging.warning("PMTiles file missing, skipping: %s", path)
            continue

        try:
            file_handle = open(path, "rb")
            reader = Reader(MmapSource(file_handle))
            header = reader.header()
            metadata = reader.metadata() or {}

            tile_type = header.get("tile_type")
            catalog_entry: CatalogEntry = {
                "key": key,
                "dataset": dataset,
                "path": path,
                "file_handle": file_handle,
                "reader": reader,
                "header": header,
                "metadata": metadata,
                "min_zoom": header.get("min_zoom", 0),
                "max_zoom": header.get("max_zoom", 0),
                "bounds": _lon_lat_bounds_from_header(header),
                "tile_type": tile_type,
                "content_type": TILE_TYPE_TO_MIME.get(tile_type, "application/octet-stream"),
            }

            if "category" in entry:
                catalog_entry["category"] = entry["category"]

            pmtiles_catalog[key] = catalog_entry
            pmtiles_datasets.setdefault(dataset, []).append(key)
            loaded_count += 1
            print(f"✓ Loaded {dataset}: {os.path.basename(path)} (key={key})")
        except Exception as exc:  # pragma: no cover - initialization should succeed, log otherwise
            logging.exception("Failed to load PMTiles archive %s: %s", path, exc)

    if loaded_count == 0:
        raise FileNotFoundError("No PMTiles archives could be loaded; check configuration paths.")

    # Sort dataset variants so that higher-resolution archives appear last.
    for dataset, keys in pmtiles_datasets.items():
        pmtiles_datasets[dataset] = sorted(
            keys,
            key=lambda k: (pmtiles_catalog[k]["min_zoom"], pmtiles_catalog[k]["max_zoom"]),
        )

    return True


def cleanup_pmtiles():
    """Clean up PMTiles resources on shutdown."""
    print("Shutting down and closing PMTiles file handles...")
    global pmtiles_catalog, pmtiles_datasets

    for entry in pmtiles_catalog.values():
        file_handle = entry.get("file_handle")
        if file_handle:
            file_handle.close()

    pmtiles_catalog.clear()
    pmtiles_datasets.clear()
    print("Cleanup complete.")


def _select_catalog_entry(
    z: int,
    x: int,
    y: int,
    dataset: str = "flood_zones",
    category: Optional[str] = None,
) -> Optional[CatalogEntry]:
    """Find the best PMTiles archive for the requested tile."""
    if dataset not in pmtiles_datasets:
        return None

    bbox = _tile_xyz_to_lon_lat_bounds(z, x, y)
    candidates = []

    for key in pmtiles_datasets[dataset]:
        entry = pmtiles_catalog[key]
        if category and entry.get("category") != category:
            continue
        if not _bbox_intersects(bbox, entry["bounds"]):
            continue

        min_zoom = entry["min_zoom"]
        max_zoom = entry["max_zoom"]

        if min_zoom <= z <= max_zoom:
            zoom_penalty = 0
        elif z < min_zoom:
            zoom_penalty = min_zoom - z
        else:
            zoom_penalty = z - max_zoom

        # Prefer smaller penalty (exact zoom match wins) and higher max zoom.
        candidates.append((zoom_penalty, -max_zoom, entry))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _dataset_entries(dataset: str) -> List[CatalogEntry]:
    return [pmtiles_catalog[key] for key in pmtiles_datasets.get(dataset, [])]


def find_floodzone_feature(lat: float, lng: float) -> Optional[Dict[str, object]]:
    """Locate the flood-zone feature covering the provided coordinate."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        raise ValueError("Latitude must be between -90 and 90 and longitude between -180 and 180.")

    entries = _dataset_entries("flood_zones")
    if not entries:
        raise RuntimeError("Flood zone dataset is not loaded.")

    min_zoom = int(min(entry["min_zoom"] for entry in entries))
    max_zoom = int(max(entry["max_zoom"] for entry in entries))

    point = Point(lng, lat)

    for z in range(max_zoom, min_zoom - 1, -1):
        tile_x, tile_y = _lon_lat_to_tile(z, lng, lat)
        entry = _select_catalog_entry(z, tile_x, tile_y, dataset="flood_zones")
        if entry is None:
            continue

        reader: Reader = entry["reader"]  # type: ignore[index]
        tile_data = reader.get(z, tile_x, tile_y)
        if tile_data is None:
            continue

        tile_bytes = _decompress_tile(tile_data)

        try:
            feature_iter = _iter_tile_features(tile_bytes, z, tile_x, tile_y)
        except Exception as exc:  # pragma: no cover - guard against corrupt tiles
            logging.exception("Failed to decode tile %s/%s/%s: %s", z, tile_x, tile_y, exc)
            continue

    for layer_name, feature in feature_iter:
        geometry = feature.get("geometry")
        if not geometry:
            continue

            try:
                geom = shape(geometry)
            except Exception as exc:  # pragma: no cover - invalid geometry
                logging.debug("Invalid geometry in tile %s/%s/%s: %s", z, tile_x, tile_y, exc)
                continue

            if geom.is_empty:
                continue

            if geom.covers(point):
                return {
                    "layer": layer_name,
                    "properties": feature.get("properties", {}),
                    "geometry": geometry,
                    "tile": {"z": z, "x": tile_x, "y": tile_y},
                    "variant": entry["key"],
                }

    return None


# def find_slosh_values(
#     lat: float,
#     lng: float,
#     categories: List[str],
#     zoom: int = 14,
# ) -> List[Dict[str, object]]:
#     results: List[Dict[str, object]] = []

#     if not categories:
#         return results

#     x_tile, y_tile, x_pixel, y_pixel = _latlng_to_slippy(lat, lng, zoom)

#     for category in categories:
#         tile_data, _ = get_tile_data(
#             zoom,
#             x_tile,
#             y_tile,
#             dataset="slosh",
#             category=category,
#         )

#         value: Optional[int] = None
#         if tile_data:
#             try:
#                 with Image.open(io.BytesIO(tile_data)) as img:
#                     pixel = img.getpixel((x_pixel, y_pixel))
#                     if isinstance(pixel, tuple):
#                         value = int(pixel[0])
#                     else:
#                         value = int(pixel)
#             except Exception:
#                 traceback.print_exc()

#         results.append(
#             {
#                 "category": category,
#                 "value": value,
#                 "tile": {"z": zoom, "x": x_tile, "y": y_tile},
#             }
#         )

#     return results


def get_tile_data(
    z: int,
    x: int,
    y: int,
    dataset: str = "flood_zones",
    category: Optional[str] = None,
) -> Tuple[Optional[bytes], Optional[str]]:
    """Get tile data from the loaded PMTiles archives."""
    entry = _select_catalog_entry(z, x, y, dataset=dataset, category=category)
    if entry is None:
        return None, None

    reader: Reader = entry["reader"]  # type: ignore[index]
    source_y = y
    if dataset == "slosh":
        source_y = (1 << z) - 1 - y

    tile_data = reader.get(z, x, source_y)

    if tile_data is None:
        return None, None

    content_type = entry.get("content_type", "application/octet-stream")
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
        <p class="subtitle">High-performance tile server for serving PMTiles archives with FastAPI.</p>
        <div class="status">
            <strong>✅ Server Status:</strong> Running with {{ loaded_count }} PMTiles file(s) loaded.
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
                <strong>Tiles:</strong> <a href="{{ api_root }}/tiles/floodzone/8/82/97">{{ api_root }}/tiles/floodzone/{z}/{x}/{y}</a>
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
            const floodZoneUrl = '{{ api_root }}/tiles/floodzone/{z}/{x}/{y}';

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
    description="High-performance tile server for PMTiles archives.",
    version="1.6.0",
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
    for key, entry in pmtiles_catalog.items():
        files_info[key] = {
            "filename": os.path.basename(entry["path"]),
            "minzoom": entry["min_zoom"],
            "maxzoom": entry["max_zoom"],
        }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "api_root": str(request.base_url).rstrip("/"),
            "files": files_info,
            "loaded_count": len(pmtiles_catalog),
        },
    )

@app.get("/map", response_class=HTMLResponse)
async def map_viewer(request: Request):
    return templates.TemplateResponse("map.html", {"request": request, "api_root": str(request.base_url).rstrip("/")})

@app.get("/tiles/floodzone/{z}/{x}/{y}", response_class=Response)
async def get_tile(z: int, x: int, y: int):
    try:
        tile_data, content_type = get_tile_data(z, x, y, dataset="flood_zones")
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


@app.get("/tiles/slosh/{z}/{x}/{y}", response_class=Response)
async def get_slosh_tile(
    z: int,
    x: int,
    y: int,
    category: str = Query(
        ..., description="SLOSH category (Category1–Category5)."
    ),
):
    normalized = category.strip().lower()
    canonical = SLOSH_CATEGORY_LOOKUP.get(normalized)
    if canonical is None:
        raise HTTPException(status_code=400, detail="Unknown SLOSH category")

    try:
        tile_data, content_type = get_tile_data(
            z,
            x,
            y,
            dataset="slosh",
            category=canonical,
        )
        if tile_data is None:
            return Response(status_code=204)

        headers = {
            "Cache-Control": "public, max-age=86400",
            "Content-Type": content_type or "application/octet-stream",
        }

        if tile_data.startswith(b"\x1f\x8b"):
            headers["Content-Encoding"] = "gzip"

        return Response(content=tile_data, headers=headers)
    except Exception as e:
        print(f"Error serving SLOSH tile {category} {z}/{x}/{y}: {e}")
        traceback.print_exc()
        return Response(status_code=500, content=f"Error serving tile: {e}")

@app.get("/info")
async def get_info(request: Request):
    if not pmtiles_catalog:
        raise HTTPException(status_code=404, detail="PMTiles archives not loaded")

    dataset_keys = pmtiles_datasets.get("flood_zones")
    if not dataset_keys:
        raise HTTPException(status_code=404, detail="Requested dataset not available")

    try:
        entries = [pmtiles_catalog[key] for key in dataset_keys]
        min_zoom = min(entry["min_zoom"] for entry in entries)
        max_zoom = max(entry["max_zoom"] for entry in entries)

        bounds = (
            min(entry["bounds"][0] for entry in entries),
            min(entry["bounds"][1] for entry in entries),
            max(entry["bounds"][2] for entry in entries),
            max(entry["bounds"][3] for entry in entries),
        )

        # Use the highest-resolution archive for name/center metadata.
        reference_entry = max(entries, key=lambda entry: entry["max_zoom"])
        header = reference_entry["header"]
        metadata = reference_entry["metadata"]

        center = [
            header.get("center_lon_e7", 0) / 1e7,
            header.get("center_lat_e7", 0) / 1e7,
            header.get("center_zoom", max_zoom),
        ]

        tilejson = {
            "tilejson": "2.2.0",
            "name": metadata.get("name", "Flood Zones"),
            "tiles": [f"{str(request.base_url).rstrip('/')}/tiles/floodzone/{{z}}/{{x}}/{{y}}"],
            "minzoom": min_zoom,
            "maxzoom": max_zoom,
            "bounds": bounds,
            "center": center,
            "vector_layers": metadata.get("vector_layers", []),
            "variants": [
                {
                    "key": entry["key"],
                    "filename": os.path.basename(entry["path"]),
                    "minzoom": entry["min_zoom"],
                    "maxzoom": entry["max_zoom"],
                    "bounds": entry["bounds"],
                }
                for entry in entries
            ],
        }
        return tilejson
    except Exception as e:  # pragma: no cover - surfaces in API response
        raise HTTPException(status_code=500, detail=f"Error reading metadata: {e}")


@app.get("/api/v1/floodzone")
async def get_floodzone(
    lat: float = Query(..., description="Latitude in decimal degrees"),
    lng: float = Query(..., description="Longitude in decimal degrees"),
):
    try:
        match = find_floodzone_feature(lat, lng)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if match is None:
        raise HTTPException(status_code=404, detail="No flood zone covers the provided location.")

    return {
        "location": {"lat": lat, "lng": lng},
        # "layer": match["layer"],
        # "variant": match["variant"],
        "tile": match["tile"],
        "properties": match["properties"],
        # "geometry": match["geometry"],
    }


# @app.get("/api/v1/slosh")
# async def get_slosh(
#     lat: float = Query(..., description="Latitude in decimal degrees"),
#     lng: float = Query(..., description="Longitude in decimal degrees"),
#     category: Optional[str] = Query(
#         None, description="Specific SLOSH category (e.g., Category1, cat1, 1)."
#     ),
#     zoom: int = Query(14, ge=0, le=22, description="Zoom level used for sampling"),
# ):
#     categories: List[str]
#     if category:
#         normalized = category.strip().lower()
#         canonical = SLOSH_CATEGORY_LOOKUP.get(normalized)
#         if canonical is None:
#             raise HTTPException(status_code=400, detail="Unknown SLOSH category")
#         categories = [canonical]
#     else:
#         categories = list(SLOSH_CATEGORIES)

#     values = find_slosh_values(lat, lng, categories, zoom=zoom)

#     if not any(result["value"] is not None for result in values):
#         raise HTTPException(status_code=404, detail="No SLOSH data available at this location.")

#     max_category = None
#     for result in values:
#         val = result["value"]
#         if val is not None and val > 0:
#             max_category = result["category"]

#     return {
#         "location": {"lat": lat, "lng": lng},
#         "zoom": zoom,
#         "categories": values,
#         "max_category": max_category,
#     }


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tile_server:app", host="0.0.0.0", port=8000, reload=True)
