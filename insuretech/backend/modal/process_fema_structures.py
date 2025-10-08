#!/usr/bin/env python3
"""Process FEMA USA Structures from GeoDatabase format into PMTiles."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import modal

TIMEOUT = 8 * 3600

# Extract state code from filename like "Deliverable20250606UT.zip" -> "UT"
STATE_PATTERN = re.compile(r"Deliverable\d{8}([A-Z]{2})\.zip")

RAW_ROOT = Path("/data/raw")
OUTPUT_ROOT = Path("/data/output")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("fema-structures-processor")
volume = modal.Volume.from_name("fema-usa-structures")

# Image with GDAL/OGR for GeoDatabase processing and tippecanoe for PMTiles
gdal_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "gdal-bin",
        "python3-gdal",
        "unzip",
        "wget",
        "build-essential",
        "libsqlite3-dev",
        "zlib1g-dev",
        "git",
    )
    .pip_install("rasterio", "numpy")
    .run_commands(
        # Install tippecanoe for PMTiles generation
        "git clone https://github.com/felt/tippecanoe.git /tmp/tippecanoe",
        "cd /tmp/tippecanoe && make -j && make install",
        "rm -rf /tmp/tippecanoe",
    )
)


def extract_state_code(zip_name: str) -> Optional[str]:
    """Extract state code from ZIP filename."""
    match = STATE_PATTERN.search(zip_name)
    if match:
        return match.group(1)
    return None


def find_gdb_in_directory(directory: Path) -> Optional[Path]:
    """Find the first .gdb directory in the given path."""
    gdb_dirs = list(directory.rglob("*.gdb"))
    if gdb_dirs:
        return gdb_dirs[0]
    return None


def extract_bounds_from_geojson(geojson_path: Path) -> Optional[List[float]]:
    """Extract bounding box from GeoJSON file."""
    try:
        with open(geojson_path, "r") as f:
            data = json.load(f)

        # Check if there's a bbox in the GeoJSON
        if "bbox" in data:
            return data["bbox"]

        # Otherwise calculate from features
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for feature in data.get("features", []):
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])

            if geom.get("type") == "Point":
                x, y = coords[0], coords[1]
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
            elif geom.get("type") in ["LineString", "MultiPoint"]:
                for coord in coords:
                    x, y = coord[0], coord[1]
                    min_x, max_x = min(min_x, x), max(max_x, x)
                    min_y, max_y = min(min_y, y), max(max_y, y)
            elif geom.get("type") in ["Polygon", "MultiLineString"]:
                for ring in coords:
                    for coord in ring:
                        x, y = coord[0], coord[1]
                        min_x, max_x = min(min_x, x), max(max_x, x)
                        min_y, max_y = min(min_y, y), max(max_y, y)
            elif geom.get("type") == "MultiPolygon":
                for polygon in coords:
                    for ring in polygon:
                        for coord in ring:
                            x, y = coord[0], coord[1]
                            min_x, max_x = min(min_x, x), max(max_x, x)
                            min_y, max_y = min(min_y, y), max(max_y, y)

        if min_x != float("inf"):
            return [min_x, min_y, max_x, max_y]

    except Exception as exc:
        logger.warning("Failed to extract bounds from GeoJSON: %s", exc)

    return None


def convert_gdb_to_geojson(gdb_path: Path, output_path: Path) -> bool:
    """Convert GeoDatabase to GeoJSON using ogr2ogr."""
    try:
        # List layers in the GDB
        list_cmd = ["ogrinfo", str(gdb_path)]
        result = subprocess.run(list_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("Failed to list layers in GDB: %s", result.stderr)
            return False

        # Find the structures layer (usually the one with "Structures" in the name)
        layers = []
        for line in result.stdout.split("\n"):
            if line.startswith("1:") or "Structures" in line:
                # Extract layer name
                parts = line.split(":")
                if len(parts) >= 2:
                    layer_name = parts[1].strip().split()[0]
                    layers.append(layer_name)

        if not layers:
            logger.error("No layers found in GDB")
            return False

        # Use the first layer (typically the structures layer)
        layer_name = layers[0]
        logger.info("Converting layer '%s' from GDB to GeoJSON", layer_name)

        # Convert to GeoJSON
        convert_cmd = [
            "ogr2ogr",
            "-f", "GeoJSON",
            "-t_srs", "EPSG:4326",  # Ensure WGS84
            str(output_path),
            str(gdb_path),
            layer_name,
        ]

        result = subprocess.run(convert_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("Failed to convert GDB to GeoJSON: %s", result.stderr)
            return False

        logger.info("Successfully converted GDB to GeoJSON: %s", output_path)
        return True

    except Exception as exc:
        logger.error("Error converting GDB to GeoJSON: %s", exc)
        return False


def create_pmtiles(geojson_path: Path, output_path: Path, state_code: str) -> bool:
    """Create PMTiles from GeoJSON using tippecanoe."""
    try:
        cmd = [
            "tippecanoe",
            "-o", str(output_path),
            "-Z", "0",  # Min zoom
            "-z", "16",  # Max zoom
            "-l", f"fema_structures_{state_code.lower()}",  # Layer name
            "--drop-densest-as-needed",  # Drop features to stay under tile size limit
            "--extend-zooms-if-still-dropping",
            "-f",  # Force overwrite
            str(geojson_path),
        ]

        logger.info("Running tippecanoe: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("tippecanoe failed: %s", result.stderr)
            return False

        logger.info("Successfully created PMTiles: %s", output_path)
        return True

    except Exception as exc:
        logger.error("Error creating PMTiles: %s", exc)
        return False


@app.function(
    image=gdal_image,
    volumes={"/data": volume},
    timeout=TIMEOUT,
    memory=16 * 1024,  # 16GB
)
def process_fema_structure_zip(
    zip_name: str,
    run_tag: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """Process a single FEMA structures ZIP file into PMTiles."""

    state_code = extract_state_code(zip_name)
    if not state_code:
        logger.error("Could not extract state code from ZIP name: %s", zip_name)
        return None

    effective_run_tag = (run_tag or datetime.utcnow().strftime("%Y%m%d")).strip()

    input_zip = RAW_ROOT / zip_name
    if not input_zip.exists():
        logger.error("ZIP file not found: %s", input_zip)
        return None

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    output_filename = f"fema_structures_{state_code.lower()}_{effective_run_tag}.pmtiles"
    output_path = OUTPUT_ROOT / output_filename

    # Check if already processed
    manifest_path = OUTPUT_ROOT / f"manifest_{state_code.lower()}.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("run_tag") == effective_run_tag and output_path.exists():
                logger.info(
                    "Skipping %s; already processed for run tag %s",
                    state_code,
                    effective_run_tag,
                )
                return manifest
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read manifest %s: %s", manifest_path, exc)

    logger.info(
        "Processing FEMA structures for %s from %s with run tag %s",
        state_code,
        input_zip,
        effective_run_tag,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Extract ZIP
        logger.info("Extracting archive to %s", temp_dir)
        try:
            with zipfile.ZipFile(input_zip, "r") as zip_ref:
                zip_ref.extractall(temp_path)
        except Exception as exc:
            logger.error("Failed to extract ZIP: %s", exc)
            return None

        # Find the .gdb directory
        gdb_path = find_gdb_in_directory(temp_path)
        if not gdb_path:
            logger.error("No .gdb directory found in ZIP: %s", input_zip)
            return None

        logger.info("Found GeoDatabase: %s", gdb_path)

        # Convert to GeoJSON
        geojson_path = temp_path / f"{state_code}_structures.geojson"
        if not convert_gdb_to_geojson(gdb_path, geojson_path):
            logger.error("Failed to convert GDB to GeoJSON")
            return None

        # Extract bounds
        bounds = extract_bounds_from_geojson(geojson_path)
        if not bounds:
            logger.warning("Could not extract bounds for %s", state_code)

        # Create PMTiles
        if not create_pmtiles(geojson_path, output_path, state_code):
            logger.error("Failed to create PMTiles")
            return None

    # Get file size
    file_size = output_path.stat().st_size if output_path.exists() else 0

    # Write manifest
    manifest = {
        "state_code": state_code,
        "run_tag": effective_run_tag,
        "zip_name": zip_name,
        "output_file": output_filename,
        "file_size_bytes": file_size,
        "bounds": bounds,
        "created_at": datetime.utcnow().isoformat(),
    }

    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Wrote manifest %s", manifest_path)
    except OSError as exc:
        logger.warning("Failed to write manifest %s: %s", manifest_path, exc)

    # Commit volume changes
    volume.commit()

    logger.info(
        "Completed processing %s; generated %s (%.2f MB)",
        state_code,
        output_filename,
        file_size / (1024 * 1024),
    )

    return manifest


@app.local_entrypoint()
def main(*args: str) -> None:
    """Process FEMA structure ZIP file(s)."""

    zip_name: Optional[str] = None
    run_tag: Optional[str] = None

    for arg in args:
        if arg.startswith("--zip="):
            zip_name = arg.split("=", 1)[1]
        elif arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            logger.warning("Unknown argument: %s", arg)
        else:
            # Assume it's a zip name if no flag
            if not zip_name:
                zip_name = arg

    if not zip_name:
        logger.error("No ZIP file specified. Usage: modal run process_fema_structures.py --zip=raw/Deliverable20250606UT.zip")
        return

    # Strip 'raw/' prefix if provided
    if zip_name.startswith("raw/"):
        zip_name = zip_name[4:]

    result = process_fema_structure_zip.remote(zip_name, run_tag=run_tag)

    if result:
        logger.info("Processing completed successfully")
        logger.info("Output: %s", result.get("output_file"))
    else:
        logger.error("Processing failed")
