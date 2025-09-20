import modal
import os
import json
import logging
from datetime import UTC, datetime
import subprocess
import tempfile

STORAGE_ROOT = "/cache"
TARGET_FIPS = "02"  # Florida
REQUIRED_SHAPE_FILE_NAME = "S_FLD_HAZ_AR"

storage = modal.Volume.from_name("fema-flood-zone-storage")

# Create image with all required geospatial tools
geo_image = (
    modal.Image.debian_slim()
    .apt_install(
        "gdal-bin",
        "curl",
        "unzip",
        "jq",
        "build-essential",
        "libsqlite3-dev",
        "zlib1g-dev",
        "git"
    )
    .pip_install("requests")
    .run_commands([
        # Build and install tippecanoe from source (more reliable than binary)
        "git clone https://github.com/felt/tippecanoe.git /tmp/tippecanoe",
        "cd /tmp/tippecanoe && make && make install",
        "rm -rf /tmp/tippecanoe",
        # Install pmtiles
        "curl -L https://github.com/protomaps/go-pmtiles/releases/download/v1.11.1/go-pmtiles_1.11.1_Linux_x86_64.tar.gz -o /tmp/pmtiles.tar.gz",
        "cd /tmp && tar -xzf pmtiles.tar.gz",
        "mv /tmp/pmtiles /usr/local/bin/",
        "chmod +x /usr/local/bin/pmtiles",
        "rm /tmp/pmtiles.tar.gz",
        # Verify installations
        "tippecanoe --version || echo 'tippecanoe installation check'",
        "tile-join --version || echo 'tile-join installation check'", 
        "pmtiles --help || echo 'pmtiles installation check'"
    ])
)

app = modal.App(
    "fema-pmtiles-converter",
    image=geo_image,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, check=True):
    """Run shell command and log output"""
    logger.info(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        logger.info(f"STDOUT: {result.stdout}")
    if result.stderr:
        logger.warning(f"STDERR: {result.stderr}")
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result

@app.function(
    timeout=7200,  # Allow long-running conversions (2 hours)
    memory=8192,   # 8GB
    cpu=4,
    volumes={STORAGE_ROOT: storage},
)
def convert_gdb_to_fgb(fips: str, file_name: str):
    """Convert GDB to FlatGeobuf format with filtering"""
    
    # Paths
    zip_path = os.path.join(STORAGE_ROOT, "state_raw", file_name)
    state_name = file_name.replace('.zip', '')
    output_dir = os.path.join(STORAGE_ROOT, "processed")
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if already processed
    fgb_path = os.path.join(output_dir, f"{state_name}.fgb")
    
    if os.path.exists(fgb_path):
        logger.info(f"SKIP: {fgb_path} already exists")
        return {"fips": fips, "status": "skipped", "fgb_path": fgb_path}
    
    if not os.path.exists(zip_path):
        logger.error(f"Source file not found: {zip_path}")
        return {"fips": fips, "status": "failed", "error": "Source file not found"}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Extract zip file
            logger.info(f"Extracting {zip_path}")
            run_command(f"cd {temp_dir} && unzip -q '{zip_path}'")
            
            # Find GDB directory
            result = run_command(f"find {temp_dir} -name '*.gdb' -type d | head -1")
            gdb_dir = result.stdout.strip()
            
            if not gdb_dir:
                raise ValueError("No .gdb directory found in zip file")
            
            logger.info(f"Found GDB: {gdb_dir}")
            
            # Convert to raw FlatGeobuf (all data)
            temp_raw_fgb = os.path.join(temp_dir, f"{state_name}_raw.fgb")
            cmd = (
                f'ogr2ogr -f FlatGeobuf '
                f'-s_srs EPSG:4269 -t_srs EPSG:4326 '
                f'-skipfailures '
                f'-select "FLD_ZONE,ZONE_SUBTY,SOURCE_CIT" '
                f'"{temp_raw_fgb}" "{gdb_dir}" "{REQUIRED_SHAPE_FILE_NAME}"'
            )
            run_command(cmd)
            
            # Filter to create cleaned version (removing low-risk zones)
            temp_filtered_fgb = os.path.join(temp_dir, f"{state_name}.fgb")
            filter_cmd = (
                f'ogr2ogr -f FlatGeobuf -skipfailures '
                f'-where "FLD_ZONE NOT IN (\'OPEN WATER\',\'D\') AND NOT (FLD_ZONE=\'X\' AND ZONE_SUBTY=\'AREA OF MINIMAL FLOOD HAZARD\')" '
                f'"{temp_filtered_fgb}" "{temp_raw_fgb}"'
            )
            run_command(filter_cmd)
            
            # Copy filtered version to storage (we'll use this for the PMTiles)
            run_command(f"cp '{temp_filtered_fgb}' '{fgb_path}'")
            
            # Commit changes to Modal volume
            storage.commit()
            
            # Verify files were written
            if os.path.exists(fgb_path):
                fgb_size = os.path.getsize(fgb_path) / (1024*1024)  # MB
                logger.info(f"SUCCESS: Created {fgb_path} ({fgb_size:.1f}MB)")
            else:
                raise Exception("Files were not written to storage successfully")
            
            return {"fips": fips, "status": "success", "fgb_path": fgb_path}
            
        except Exception as e:
            logger.error(f"Error processing {file_name}: {e}")
            return {"fips": fips, "status": "failed", "error": str(e)}

@app.function(
    timeout=7200,  # Allow heavy tile builds to finish
    memory=8192,   # 8GB  
    cpu=4,
    volumes={STORAGE_ROOT: storage},
)
def create_pmtiles(fips: str, fgb_path: str):
    """Create single PMTiles file from FlatGeobuf"""
    
    state_name = os.path.basename(fgb_path).replace('.fgb', '')
    tiles_dir = os.path.join(STORAGE_ROOT, "tiles")
    os.makedirs(tiles_dir, exist_ok=True)
    
    # Single output file
    pmtiles_path = os.path.join(tiles_dir, f"{state_name}.pmtiles")
    
    # Check if already exists
    if os.path.exists(pmtiles_path):
        logger.info(f"SKIP: PMTiles already exist for {state_name}")
        return {"fips": fips, "status": "skipped", "pmtiles_path": pmtiles_path}
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Copy input file to temp directory
            temp_fgb = os.path.join(temp_dir, f"{state_name}.fgb")
            run_command(f"cp '{fgb_path}' '{temp_fgb}'")
            
            # Create single PMTiles file covering all zoom levels
            temp_pmtiles = os.path.join(temp_dir, f"{state_name}.pmtiles")
            cmd = (
                f'tippecanoe -z18 '  # Max zoom 18, min zoom 0 (default)
                f'--maximum-tile-bytes=1000000 '
                f'--progress-interval=30 '
                f'--read-parallel '
                f'--hilbert '
                f'--coalesce-densest-as-needed '
                f'--force '
                f'--output="{temp_pmtiles}" '
                f'-l floodzones '
                f'"{temp_fgb}"'
            )
            run_command(cmd)
            
            # Copy to storage
            run_command(f"cp '{temp_pmtiles}' '{pmtiles_path}'")
            
            # Commit changes to Modal volume
            storage.commit()
            
            # Verify file was written and get size
            if os.path.exists(pmtiles_path):
                size_mb = os.path.getsize(pmtiles_path) / (1024*1024)
                logger.info(f"Created: {pmtiles_path} ({size_mb:.1f}MB)")
            else:
                raise Exception("PMTiles file was not created successfully")
            
            logger.info(f"SUCCESS: Created PMTiles for {state_name}")
            return {
                "fips": fips, 
                "status": "success",
                "pmtiles_path": pmtiles_path
            }
            
        except Exception as e:
            logger.error(f"Error creating PMTiles for {fips}: {e}")
            return {"fips": fips, "status": "failed", "error": str(e)}

@app.function(volumes={STORAGE_ROOT: storage})
def get_manifest():
    """Get the latest manifest file"""
    manifest_dir = os.path.join(STORAGE_ROOT, "manifest")
    if not os.path.exists(manifest_dir):
        raise ValueError("No manifest directory found. Run the download script first.")
    
    # Find the most recent manifest file
    manifest_files = [f for f in os.listdir(manifest_dir) if f.endswith('.json')]
    if not manifest_files:
        raise ValueError("No manifest files found")
    
    latest_manifest = "mainfest-20250918.json"
    manifest_path = os.path.join(manifest_dir, latest_manifest)
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    return manifest

@app.local_entrypoint()
def main():
    """Process FIPS 12 (Florida) data"""
    logger.info("--- FEMA PMTiles Conversion Pipeline ---")
    
    # Get manifest
    logger.info("Loading manifest...")
    manifest = get_manifest.remote()
    
    # Find Florida data
    if TARGET_FIPS not in manifest:
        logger.error(f"FIPS {TARGET_FIPS} not found in manifest")
        return
    
    florida_data = manifest[TARGET_FIPS]
    file_name = florida_data["file_name"]
    
    logger.info(f"Processing Florida (FIPS {TARGET_FIPS}): {file_name}")
    
    # Step 1: Convert GDB to FlatGeobuf
    logger.info("--- Step 1: Converting GDB to FlatGeobuf ---")
    conversion_result = convert_gdb_to_fgb.remote(TARGET_FIPS, file_name)
    
    if conversion_result["status"] != "success" and conversion_result["status"] != "skipped":
        logger.error(f"GDB conversion failed: {conversion_result.get('error')}")
        return
    
    # Step 2: Create PMTiles
    logger.info("--- Step 2: Creating PMTiles ---")
    pmtiles_result = create_pmtiles.remote(
        TARGET_FIPS,
        conversion_result["fgb_path"]
    )
    
    if pmtiles_result["status"] == "success":
        logger.info("--- Pipeline Complete ---")
        logger.info(f"PMTiles created successfully for Florida (FIPS {TARGET_FIPS})")
        logger.info(f"Created: {pmtiles_result['pmtiles_path']}")
    else:
        logger.error(f"PMTiles creation failed: {pmtiles_result.get('error')}")