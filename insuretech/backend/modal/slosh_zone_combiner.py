"""
Combine processed SLOSH COGs into PMTiles archives by region and category.

This creates PMTiles for each category within a region:
- SLOSH_PR_Category1.pmtiles (Puerto Rico, Category 1, all zoom levels)
- SLOSH_PR_Category2.pmtiles (Puerto Rico, Category 2, all zoom levels)
- etc.

Usage:
  modal run slosh_zone_combiner.py --region pr run_tag=20250924 resume=false
  modal run slosh_zone_combiner.py --region us run_tag=20250924 resume=false
  modal run slosh_zone_combiner.py --region hawaii run_tag=20250924 resume=false
  modal run slosh_zone_combiner.py --region southern_california run_tag=20250924 resume=false
  modal run slosh_zone_combiner.py --region american_samoa run_tag=20250924 resume=false
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

# Region mapping: input name -> (folder name, output prefix)
REGION_MAP = {
    "pr": ("puerto_rico", "SLOSH_PR"),
    "puerto_rico": ("puerto_rico", "SLOSH_PR"),
    "us": ("us", "SLOSH_US"),
    "hawaii": ("hawaii", "SLOSH_HAWAII"),
    "hi": ("hawaii", "SLOSH_HAWAII"),
    "southern_california": ("southern_california", "SLOSH_SOUTHERN_CALIFORNIA"),
    "sc": ("southern_california", "SLOSH_SOUTHERN_CALIFORNIA"),
    "american_samoa": ("american_samoa", "SLOSH_AMERICAN_SAMOA"),
    "as": ("american_samoa", "SLOSH_AMERICAN_SAMOA"),
}

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

def find_cog_files_for_category(
    region_folder: str,
    category: str,
    run_tag: Optional[str]
) -> List[str]:
    """Find all COG files for a specific region and category across all zoom ranges."""
    processed_dir = PROCESSED_ROOT / region_folder
    if not processed_dir.exists():
        logger.warning(f"Processed directory does not exist: {processed_dir}")
        return []

    cog_files = []

    # Find all COG files for this category across all zoom ranges
    for zoom_range in ZOOM_RANGES:
        if run_tag:
            pattern = f"*_{category}_{zoom_range}_{run_tag}.cog.tif"
        else:
            pattern = f"*_{category}_{zoom_range}*.cog.tif"

        candidates = sorted(processed_dir.glob(pattern))
        if candidates:
            # Take the most recent file
            latest = max(candidates, key=lambda p: (p.name, p.stat().st_mtime))
            cog_files.append(str(latest))
            logger.info(f"Adding {latest.name} for {category}")

    return cog_files

def create_pmtiles_for_category(
    region_folder: str,
    output_prefix: str,
    category: str,
    run_tag: Optional[str],
    *,
    resume: bool = True,
) -> bool:
    """Create a single PMTiles file for a specific region and category, combining all zoom ranges."""

    output_name = f"{output_prefix}_{category}.pmtiles"
    destination = OUTPUT_ROOT / region_folder / output_name

    if resume and destination.exists():
        logger.info(
            "Skipping %s because it already exists. Use resume=false to rebuild.",
            destination,
        )
        return True

    cog_files = find_cog_files_for_category(region_folder, category, run_tag)

    if not cog_files:
        logger.warning(f"No COG files found for {region_folder}/{category}")
        return False

    logger.info(f"Creating {output_name} from {len(cog_files)} COG files")

    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        # Create a VRT combining all zoom ranges for this category
        vrt_file = tmp_dir_path / f"{output_prefix}_{category}.vrt"

        run_command([
            "gdalbuildvrt",
            "-resolution", "highest",    # Use highest resolution where files overlap
            "-srcnodata", "0",          # Treat 0 as nodata
            "-vrtnodata", "0",
            str(vrt_file),
            *cog_files
        ], f"gdalbuildvrt {category}")

        # Convert VRT to PMTiles
        convert_cog_to_pmtiles(vrt_file, destination)
        logger.info(f"Created PMTiles: {destination}")

    return True

def convert_cog_to_pmtiles(source: Path, destination: Path) -> None:
    """Reproject a COG to WebMercator and convert it into PMTiles."""

    logger.info(f"Starting conversion of {source.name} to PMTiles (size: {source.stat().st_size / (1024**3):.2f} GB)")

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
            "-co", "TILED=YES",
            "-co", "BLOCKXSIZE=512",
            "-co", "BLOCKYSIZE=512",
            "-wo", "NUM_THREADS=ALL_CPUS",
            "-multi",
            "--config", "GDAL_CACHEMAX", "4096",
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
    timeout=86400,      # Maximum 24 hours
    memory=32 * 1024,   # 32GB RAM for VRT processing
    cpu=16.0,          # 16 CPU cores for parallel processing
)
def combine_region_categories(
    region: str,
    run_tag: Optional[str] = None,
    *,
    resume: bool = True,
) -> None:
    """Create PMTiles files for each category in a specific region."""

    region_lower = region.lower()
    if region_lower not in REGION_MAP:
        logger.error(f"Unknown region: {region}. Valid regions: {', '.join(REGION_MAP.keys())}")
        raise ValueError(f"Unknown region: {region}")

    region_folder, output_prefix = REGION_MAP[region_lower]

    logger.info(f"Processing region: {region_folder} (output prefix: {output_prefix})")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    produced_any = False

    for category in SLOSH_CATEGORY_NAMES:
        logger.info(f"Processing {region_folder}/{category}...")
        if create_pmtiles_for_category(region_folder, output_prefix, category, run_tag, resume=resume):
            produced_any = True

    if produced_any:
        volume.commit()
        logger.info(f"PMTiles creation complete for region: {region_folder}")
    else:
        logger.warning(f"No PMTiles were created for region: {region_folder}")

@app.local_entrypoint()
def main(*args: str) -> None:
    run_tag: Optional[str] = None
    resume = True
    region: Optional[str] = None

    for arg in args:
        if arg.startswith("--region="):
            region = arg.split("=", 1)[1]
        elif arg.startswith("region="):
            region = arg.split("=", 1)[1]
        elif arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        elif arg.startswith("resume="):
            value = arg.split("=", 1)[1].lower()
            resume = value not in {"0", "false", "no"}

    if not region:
        logger.error("Region is required. Usage: modal run slosh_zone_combiner.py --region=pr run_tag=20250924")
        logger.error(f"Valid regions: {', '.join(sorted(set(REGION_MAP.keys())))}")
        return

    combine_region_categories.remote(region=region, run_tag=run_tag, resume=resume)