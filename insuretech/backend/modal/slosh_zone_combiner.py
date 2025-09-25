"""
Combine processed SLOSH COGs into global PMTiles archives by zoom range.

This creates 3 global files:
- SLOSH_GLOBAL_z0_10.pmtiles   (all geographies, all categories, zoom 0-10)
- SLOSH_GLOBAL_z10_16.pmtiles  (all geographies, all categories, zoom 10-16)  
- SLOSH_GLOBAL_z16_20.pmtiles  (all geographies, all categories, zoom 16-20)

Usage: modal run slosh_zone_combiner.py global_zoom run_tag=20250924
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import modal

# Hurricane categories to process
SLOSH_CATEGORY_NAMES: List[str] = [
    "Category1",
    "Category2", 
    "Category3",
    "Category4",
    "Category5",
]

ZOOM_RANGES = ["z0_10", "z10_16", "z16_20"]

STORAGE_ROOT = Path("/cache")
PROCESSED_ROOT = STORAGE_ROOT / "processed"
OUTPUT_ROOT = STORAGE_ROOT / "outputs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

volume = modal.Volume.from_name("national-hurricane-center-slosh")

geo_image = (
    modal.Image.debian_slim()
    .apt_install("gdal-bin", "python3-gdal", "curl", "unzip", "wget")
    .run_commands([
        "curl -L https://github.com/protomaps/go-pmtiles/releases/download/v1.11.1/go-pmtiles_1.11.1_Linux_x86_64.tar.gz -o /tmp/pmtiles.tar.gz",
        "cd /tmp && tar -xzf pmtiles.tar.gz", 
        "mv /tmp/pmtiles /usr/local/bin/",
        "chmod +x /usr/local/bin/pmtiles",
        "rm /tmp/pmtiles.tar.gz",
    ])
)

app = modal.App("slosh-combiner", image=geo_image)

def discover_all_datasets() -> List[Dict[str, str]]:
    """Discover all available datasets by scanning the processed directory."""
    discovered_datasets = []

    if not PROCESSED_ROOT.exists():
        logger.warning("Processed root directory does not exist: %s", PROCESSED_ROOT)
        return discovered_datasets

    for subdir in PROCESSED_ROOT.iterdir():
        if not subdir.is_dir():
            continue

        cog_files = list(subdir.glob("*.cog.tif"))
        if not cog_files:
            continue

        first_cog = cog_files[0]
        name_parts = first_cog.stem.split("_")
        if len(name_parts) >= 2:
            output_prefix = "_".join(name_parts[:2])
        else:
            output_prefix = f"SLOSH_{subdir.name.upper()}"

        dataset = {
            "key": subdir.name,
            "description": subdir.name.replace("_", " ").title(),
            "output_prefix": output_prefix,
            "processed_subdir": subdir.name,
        }

        discovered_datasets.append(dataset)
        logger.info("Discovered dataset: %s (%s)", dataset["description"], output_prefix)

    return discovered_datasets

def find_cog_files_for_zoom_range(zoom_range: str, run_tag: Optional[str]) -> List[str]:
    """Find all COG files for a specific zoom range across all geographies and categories."""
    all_datasets = discover_all_datasets()
    cog_files = []
    
    for dataset in all_datasets:
        processed_dir = PROCESSED_ROOT / dataset["processed_subdir"]
        if not processed_dir.exists():
            continue
            
        for category in SLOSH_CATEGORY_NAMES:
            if run_tag:
                pattern = f"{dataset['output_prefix']}_{category}_{zoom_range}_{run_tag}.cog.tif"
            else:
                pattern = f"{dataset['output_prefix']}_{category}_{zoom_range}*.cog.tif"
            
            candidates = sorted(processed_dir.glob(pattern))
            if candidates:
                # Take the most recent file
                latest = max(candidates, key=lambda p: (p.name, p.stat().st_mtime))
                cog_files.append(str(latest))
                logger.info(f"Adding {latest.name} to {zoom_range}")
    
    return cog_files

def create_global_pmtiles_for_zoom_range(zoom_range: str, run_tag: Optional[str]) -> bool:
    """Create a single global PMTiles file for all geographies and categories at a zoom range."""
    
    cog_files = find_cog_files_for_zoom_range(zoom_range, run_tag)
    
    if not cog_files:
        logger.warning(f"No COG files found for {zoom_range}")
        return False
        
    logger.info(f"Creating global {zoom_range} PMTiles from {len(cog_files)} COG files")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        
        # Create VRT mosaic combining all COGs for this zoom range
        vrt_path = tmp_dir_path / f"global_{zoom_range}.vrt"
        
        run_command([
            "gdalbuildvrt",
            "-resolution", "highest",    # Use highest resolution where files overlap
            "-srcnodata", "0",          # Treat 0 as nodata  
            "-vrtnodata", "0",
            str(vrt_path),
            *cog_files
        ], f"gdalbuildvrt {zoom_range}")
        
        # Output path
        tag_suffix = f"_{run_tag}" if run_tag else ""
        output_name = f"SLOSH_GLOBAL_{zoom_range}{tag_suffix}.pmtiles"
        destination = OUTPUT_ROOT / "global" / output_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert VRT to PMTiles
        convert_cog_to_pmtiles(vrt_path, destination)
        logger.info(f"Created global PMTiles: {destination}")
        
    return True

def convert_cog_to_pmtiles(source: Path, destination: Path) -> None:
    """Reproject a COG to WebMercator and convert it into PMTiles."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        warped = tmp_dir_path / f"{destination.stem}_3857.tif"
        mbtiles = tmp_dir_path / f"{destination.stem}.mbtiles"
        pmtiles = tmp_dir_path / destination.name

        run_command([
            "gdalwarp",
            "-t_srs", "EPSG:3857",
            "-r", "bilinear", 
            "-of", "COG",
            "-co", "COMPRESS=LZW",
            "-co", "PREDICTOR=2",
            str(source),
            str(warped),
        ], "gdalwarp")

        run_command([
            "gdal_translate",
            "-of", "MBTILES",
            "-co", "TILE_FORMAT=PNG", 
            str(warped),
            str(mbtiles),
        ], "gdal_translate")

        run_command([
            "gdaladdo",
            "-r", "average",
            str(mbtiles),
            "2", "4", "8", "16", "32", "64",
        ], "gdaladdo")

        run_command(["pmtiles", "convert", str(mbtiles), str(pmtiles)], "pmtiles convert")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pmtiles, destination)

def run_command(command: Sequence[str], label: str) -> None:
    """Execute a shell command and raise if it fails."""
    logger.info("Running command (%s): %s", label, " ".join(command))
    env = os.environ.copy()
    env.setdefault("PROJ_NETWORK", "YES")
    env.setdefault("OSR_USE_ESTIMATED_COORD_OPS", "YES")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        logger.error("%s failed: %s", label, result.stderr.strip())
        raise RuntimeError(f"{label} failed: {result.stderr.strip()}")

@app.function(
    volumes={str(STORAGE_ROOT): volume},
    timeout=12*3600,  # Longer timeout for global processing
    memory=8*4096,    # More memory for large VRTs
)
def combine_global_zoom_ranges(run_tag: Optional[str] = None) -> None:
    """Create 3 global PMTiles files organized by zoom range."""
    
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    
    produced_any = False
    
    for zoom_range in ZOOM_RANGES:
        logger.info(f"Processing global {zoom_range}...")
        if create_global_pmtiles_for_zoom_range(zoom_range, run_tag):
            produced_any = True
    
    if produced_any:
        volume.commit()
        logger.info("Global zoom-range PMTiles creation complete")
    else:
        logger.warning("No global PMTiles were created")

@app.local_entrypoint()
def main(*args: str) -> None:
    run_tag: Optional[str] = None
    mode = "global_zoom"
    
    for arg in args:
        if arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        elif arg == "global_zoom":
            mode = "global_zoom"
    
    if mode == "global_zoom":
        combine_global_zoom_ranges.remote(run_tag=run_tag)
    else:
        logger.error("Only global_zoom mode is supported in this version")