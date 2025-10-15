import modal
import os
import logging
import subprocess
import tempfile

STORAGE_ROOT = "/vol"
RAW_DIR = os.path.join(STORAGE_ROOT, "noaa-shoreline", "raw")
GEOJSON_DIR = os.path.join(STORAGE_ROOT, "geojson")

storage = modal.Volume.from_name("noaa-shoreline")

geo_image = (
    modal.Image.debian_slim()
    .apt_install(
        "gdal-bin",
        "unzip",
    )
)

app = modal.App(
    "noaa-coastline-processor",
    image=geo_image,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, check=True):
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
    timeout=3600,
    memory=4096,
    cpu=2,
    volumes={"/vol": storage},
)
def process_coastline_zip(zip_filename: str):
    zip_path = os.path.join(RAW_DIR, zip_filename)
    base_name = zip_filename.replace('.zip', '')
    geojson_output_path = os.path.join(GEOJSON_DIR, f"{base_name}_coastline.geojson")

    if os.path.exists(geojson_output_path):
        logger.info(f"SKIP: {geojson_output_path} already exists")
        return {"file": zip_filename, "status": "skipped", "geojson": geojson_output_path}

    if not os.path.exists(zip_path):
        logger.error(f"Source file not found: {zip_path}")
        return {"file": zip_filename, "status": "failed", "error": "Source file not found"}

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            logger.info(f"Extracting {zip_path}")
            run_command(f"cd {temp_dir} && unzip -q '{zip_path}'")

            result = run_command(f"find {temp_dir} -name '*.shp' | head -1")
            shp_file = result.stdout.strip()

            if not shp_file:
                raise ValueError(f"No .shp file found in {zip_filename}")

            logger.info(f"Found shapefile: {shp_file}")

            temp_geojson = os.path.join(temp_dir, f"{base_name}_coastline.geojson")

            filter_where = (
                "ATTRIBUTE IN ('Natural.Mean High Water', "
                "'Natural.Mean High Water.Approximate', "
                "'Natural.Apparent.Mangrove Or Cypress', "
                "'Natural.Apparent.Marsh Or Swamp')"
            )

            cmd = (
                f'ogr2ogr -f GeoJSON '
                f'-where "{filter_where}" '
                f'"{temp_geojson}" "{shp_file}"'
            )
            run_command(cmd)

            os.makedirs(GEOJSON_DIR, exist_ok=True)
            run_command(f"cp '{temp_geojson}' '{geojson_output_path}'")

            storage.commit()

            if os.path.exists(geojson_output_path):
                size_mb = os.path.getsize(geojson_output_path) / (1024*1024)
                logger.info(f"SUCCESS: Created {geojson_output_path} ({size_mb:.1f}MB)")
            else:
                raise Exception("GeoJSON file was not written to storage successfully")

            return {
                "file": zip_filename,
                "status": "success",
                "geojson": geojson_output_path
            }

        except Exception as e:
            logger.error(f"Error processing {zip_filename}: {e}")
            return {"file": zip_filename, "status": "failed", "error": str(e)}


@app.function(
    volumes={"/vol": storage},
)
def list_zip_files():
    if not os.path.exists(RAW_DIR):
        raise ValueError(f"Raw directory not found: {RAW_DIR}")

    zip_files = [f for f in os.listdir(RAW_DIR) if f.endswith('.zip')]
    logger.info(f"Found {len(zip_files)} zip files in {RAW_DIR}")

    return sorted(zip_files)


@app.local_entrypoint()
def main():
    logger.info("--- NOAA Coastline Processor ---")

    logger.info("Listing zip files...")
    zip_files = list_zip_files.remote()

    if not zip_files:
        logger.error("No zip files found in /noaa-shoreline/raw/")
        return

    logger.info(f"Processing {len(zip_files)} files...")

    results = []
    for zip_file in zip_files:
        logger.info(f"Processing {zip_file}...")
        result = process_coastline_zip.remote(zip_file)
        results.append(result)
        logger.info(f"Result: {result['status']}")

    success_count = sum(1 for r in results if r['status'] == 'success')
    skipped_count = sum(1 for r in results if r['status'] == 'skipped')
    failed_count = sum(1 for r in results if r['status'] == 'failed')

    logger.info("--- Processing Complete ---")
    logger.info(f"Success: {success_count}, Skipped: {skipped_count}, Failed: {failed_count}")

    if failed_count > 0:
        logger.error("Failed files:")
        for r in results:
            if r['status'] == 'failed':
                logger.error(f"  {r['file']}: {r.get('error', 'Unknown error')}")
