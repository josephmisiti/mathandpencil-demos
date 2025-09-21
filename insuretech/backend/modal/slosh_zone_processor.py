#!/usr/bin/env python3
"""
SLOSH Data Processor for Modal
Processes Puerto Rico SLOSH MOM Inundation data with zoom-level splitting
"""

import modal
import zipfile
import tempfile
import os
from pathlib import Path
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modal app and volume setup
app = modal.App("slosh-processor")
volume = modal.Volume.from_name("national-hurricane-center-slosh")

# GDAL image with all geospatial tools
gdal_image = modal.Image.debian_slim(python_version="3.11").apt_install(
    "gdal-bin",
    "python3-gdal", 
    "unzip",
    "wget"
).pip_install(
    "rasterio",
    "numpy"
)

@app.function(
    image=gdal_image,
    volumes={"/data": volume},
    timeout=3600,  # 1 hour timeout
    memory=4096,   # 4GB memory
)
def process_pr_slosh():
    """
    Process Puerto Rico SLOSH data from the Modal volume
    Creates zoom-level specific COG files
    """
    
    # Input and output paths
    input_zip = "/data/raw/PR_SLOSH_MOM_Inundation.zip"
    output_dir = "/data/processed/puerto_rico"
    
    logger.info(f"Processing {input_zip}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract ZIP file to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Extracting to {temp_dir}")
        
        with zipfile.ZipFile(input_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find all .tif files (should be the 5 categories)
        tif_files = list(Path(temp_dir).rglob("*.tif"))
        logger.info(f"Found {len(tif_files)} TIF files: {[f.name for f in tif_files]}")
        
        for tif_file in tif_files:
            if "Category" in tif_file.name:
                process_single_category(tif_file, output_dir)
    
    volume.commit()

    logger.info("Processing complete!")
    for name in list_processed_files():
        logger.info("  %s", name)

def process_single_category(input_tif: Path, output_dir: str):
    """
    Process a single category TIF file into zoom-level specific COGs
    """
    category_name = extract_category_name(input_tif.name)
    logger.info(f"Processing {category_name}")
    
    # Define zoom ranges and their target resolutions
    zoom_configs = [
        {
            "suffix": "z0_10", 
            "resolution": 0.001,  # ~100m at equator
            "description": "Low zoom (0-10)"
        },
        {
            "suffix": "z10_16", 
            "resolution": 0.0001,  # ~10m at equator
            "description": "Medium zoom (10-16)"
        },
        {
            "suffix": "z16_20", 
            "resolution": None,  # Full resolution
            "description": "High zoom (16-20)"
        }
    ]
    
    for config in zoom_configs:
        output_file = os.path.join(output_dir, f"SLOSH_PR_{category_name}_{config['suffix']}.cog.tif")
        
        logger.info(f"Creating {config['description']}: {output_file}")
        
        if config['resolution']:
            # Resample to target resolution
            create_resampled_cog(input_tif, output_file, config['resolution'])
        else:
            # Full resolution COG
            create_full_resolution_cog(input_tif, output_file)

def extract_category_name(filename: str) -> str:
    """
    Extract category name from filename
    e.g., "PR_Category1_MOM_Inundation_HighTide.tif" -> "Category1"
    """
    if "Category1" in filename:
        return "Category1"
    elif "Category2" in filename:
        return "Category2"
    elif "Category3" in filename:
        return "Category3"
    elif "Category4" in filename:
        return "Category4"
    elif "Category5" in filename:
        return "Category5"
    else:
        return "Unknown"

def create_resampled_cog(input_file: Path, output_file: str, target_resolution: float):
    """
    Create a resampled COG with target resolution
    """
    cmd = [
        "gdalwarp",
        "-tr", str(target_resolution), str(target_resolution),  # Target resolution
        "-r", "average",  # Resampling method
        "-of", "COG",  # Cloud Optimized GeoTIFF
        "-co", "COMPRESS=LZW",  # LZW compression
        "-co", "PREDICTOR=2",  # Horizontal differencing
        "-co", "BLOCKSIZE=512",  # 512x512 blocks
        "-co", "OVERVIEW_RESAMPLING=AVERAGE",  # Overview resampling
        "-co", "NUM_THREADS=ALL_CPUS",  # Use all CPUs
        str(input_file),
        output_file
    ]
    
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"gdalwarp failed: {result.stderr}")
        raise RuntimeError(f"gdalwarp failed: {result.stderr}")
    
    logger.info(f"Successfully created: {output_file}")

def create_full_resolution_cog(input_file: Path, output_file: str):
    """
    Create a full resolution COG
    """
    cmd = [
        "gdal_translate",
        "-of", "COG",  # Cloud Optimized GeoTIFF
        "-co", "COMPRESS=LZW",  # LZW compression
        "-co", "PREDICTOR=2",  # Horizontal differencing
        "-co", "BLOCKSIZE=512",  # 512x512 blocks
        "-co", "OVERVIEW_RESAMPLING=NEAREST",  # Preserve exact values
        "-co", "OVERVIEW_COUNT=6",  # Create 6 overview levels
        "-co", "NUM_THREADS=ALL_CPUS",  # Use all CPUs
        str(input_file),
        output_file
    ]
    
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        logger.error(f"gdal_translate failed: {result.stderr}")
        raise RuntimeError(f"gdal_translate failed: {result.stderr}")
    
    logger.info(f"Successfully created: {output_file}")

def list_processed_files():
    """
    List all processed files in the output directory
    """
    output_dir = "/data/processed/puerto_rico"

    if not os.path.exists(output_dir):
        return []

    files = sorted(Path(output_dir).glob("*.tif"))
    return [f.name for f in files]

def inspect_file(filename: str):
    """
    Inspect a specific processed file using gdalinfo
    """
    file_path = f"/data/processed/puerto_rico/{filename}"
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    cmd = ["gdalinfo", "-stats", "-hist", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"Error inspecting file: {result.stderr}")

    return result.stdout

@app.local_entrypoint()
def main():
    process_pr_slosh.remote()
