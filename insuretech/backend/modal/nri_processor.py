import json
import logging
import os
import subprocess
import tempfile
from datetime import UTC, datetime

import modal


STORAGE_ROOT = "/cache"
RAW_ZIP_NAME = "NRI_Shapefile_CensusTracts.zip"
DATASET_STEM = "NRI_Shapefile_CensusTracts"


storage = modal.Volume.from_name("nri-data")


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
        "git",
    )
    .pip_install("requests")
    .run_commands(
        [
            "git clone https://github.com/felt/tippecanoe.git /tmp/tippecanoe",
            "cd /tmp/tippecanoe && make && make install",
            "rm -rf /tmp/tippecanoe",
            "curl -L https://github.com/protomaps/go-pmtiles/releases/download/v1.11.1/go-pmtiles_1.11.1_Linux_x86_64.tar.gz -o /tmp/pmtiles.tar.gz",
            "cd /tmp && tar -xzf pmtiles.tar.gz",
            "mv /tmp/pmtiles /usr/local/bin/",
            "chmod +x /usr/local/bin/pmtiles",
            "rm /tmp/pmtiles.tar.gz",
            "tippecanoe --version || echo 'tippecanoe installation check'",
            "tile-join --version || echo 'tile-join installation check'",
            "pmtiles --help || echo 'pmtiles installation check'",
        ]
    )
)


app = modal.App("nri-pmtiles-processor", image=geo_image)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    logger.info("Running: %s", cmd)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        logger.info("STDOUT: %s", result.stdout)
    if result.stderr:
        logger.warning("STDERR: %s", result.stderr)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


@app.function(timeout=7200, memory=8192, cpu=4, volumes={STORAGE_ROOT: storage})
def convert_shapefile_to_fgb():
    """Convert the downloaded NRI shapefile archive into FlatGeobuf."""

    raw_dir = os.path.join(STORAGE_ROOT, "raw")
    processed_dir = os.path.join(STORAGE_ROOT, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    zip_path = os.path.join(raw_dir, RAW_ZIP_NAME)
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Expected archive not found at {zip_path}")

    fgb_path = os.path.join(processed_dir, f"{DATASET_STEM}.fgb")
    if os.path.exists(fgb_path):
        logger.info("FlatGeobuf already exists at %s; skipping conversion.", fgb_path)
        return {"status": "skipped", "fgb_path": fgb_path}

    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info("Extracting %s", zip_path)
        run_command(f"cd '{temp_dir}' && unzip -q '{zip_path}'")

        # Locate the shapefile (.shp)
        result = run_command(f"find '{temp_dir}' -name '*.shp' -type f | head -1")
        shp_path = result.stdout.strip()

        if not shp_path:
            raise ValueError("Shapefile (.shp) not found in archive")

        logger.info("Found shapefile: %s", shp_path)

        temp_fgb = os.path.join(temp_dir, f"{DATASET_STEM}.fgb")
        cmd = (
            f"ogr2ogr -f FlatGeobuf "
            f"-t_srs EPSG:4326 "
            f"-skipfailures "
            f"-dim XY "
            f"-nlt PROMOTE_TO_MULTI "
            f"'{temp_fgb}' '{shp_path}'"
        )
        run_command(cmd)

        run_command(f"cp '{temp_fgb}' '{fgb_path}'")
        storage.commit()

        if os.path.exists(fgb_path):
            size_mb = os.path.getsize(fgb_path) / (1024 * 1024)
            logger.info("Created FlatGeobuf at %s (%.1f MB)", fgb_path, size_mb)
        else:
            raise RuntimeError("FlatGeobuf conversion failed: output not found")

    return {"status": "success", "fgb_path": fgb_path}


@app.function(timeout=7200, memory=8192, cpu=4, volumes={STORAGE_ROOT: storage})
def create_pmtiles():
    """Generate PMTiles for the NRI dataset at multiple zoom ranges."""

    processed_dir = os.path.join(STORAGE_ROOT, "processed")
    tiles_dir = os.path.join(STORAGE_ROOT, "tiles")
    os.makedirs(tiles_dir, exist_ok=True)

    fgb_path = os.path.join(processed_dir, f"{DATASET_STEM}.fgb")
    if not os.path.exists(fgb_path):
        raise FileNotFoundError("FlatGeobuf not available; run convert_shapefile_to_fgb first.")

    output_paths = {
        "z0_10": os.path.join(tiles_dir, f"{DATASET_STEM}_z0_10.pmtiles"),
        "z10_16": os.path.join(tiles_dir, f"{DATASET_STEM}_z10_16.pmtiles"),
        "z17": os.path.join(tiles_dir, f"{DATASET_STEM}_z17.pmtiles"),
        "z18": os.path.join(tiles_dir, f"{DATASET_STEM}_z18.pmtiles"),
    }

    if all(os.path.exists(path) for path in output_paths.values()):
        logger.info("All PMTiles already exist; skipping generation.")
        return {"status": "skipped", "tiles": output_paths}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_files = {
            key: os.path.join(temp_dir, os.path.basename(path))
            for key, path in output_paths.items()
        }

        commands = [
            (
                temp_files["z0_10"],
                f"tippecanoe -z10 -D10 --maximum-tile-bytes=1000000 "
                f"--progress-interval=30 --read-parallel --hilbert "
                f"--coalesce-densest-as-needed --force "
                f"--output='{temp_files['z0_10']}' -l nri '{fgb_path}'",
            ),
            (
                temp_files["z10_16"],
                f"tippecanoe -Z10 -z16 --maximum-tile-bytes=1000000 "
                f"--progress-interval=30 --read-parallel --hilbert "
                f"--coalesce-densest-as-needed --force "
                f"--output='{temp_files['z10_16']}' -l nri '{fgb_path}'",
            ),
            (
                temp_files["z17"],
                f"tippecanoe -Z17 -z17 --maximum-tile-bytes=1000000 "
                f"--progress-interval=30 --read-parallel --hilbert "
                f"--coalesce-densest-as-needed --force "
                f"--output='{temp_files['z17']}' -l nri '{fgb_path}'",
            ),
            (
                temp_files["z18"],
                f"tippecanoe -Z18 -z18 --maximum-tile-bytes=1000000 "
                f"--progress-interval=30 --read-parallel --hilbert "
                f"--coalesce-densest-as-needed --force "
                f"--output='{temp_files['z18']}' -l nri '{fgb_path}'",
            ),
        ]

        for _, cmd in commands:
            run_command(cmd)

        for key, temp_path in temp_files.items():
            run_command(f"cp '{temp_path}' '{output_paths[key]}'")

        storage.commit()

    tiles_created = []
    for key, path in output_paths.items():
        if os.path.exists(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info("Created %s (%.1f MB)", path, size_mb)
            tiles_created.append(path)
        else:
            raise RuntimeError(f"PMTiles creation failed for {path}")

    return {"status": "success", "tiles": tiles_created}


@app.local_entrypoint()
def main():
    logger.info("--- NRI PMTiles Processing Pipeline ---")

    convert_result = convert_shapefile_to_fgb.remote()
    logger.info("Conversion result: %s", json.dumps(convert_result, indent=2))

    pmtiles_result = create_pmtiles.remote()
    logger.info("PMTiles result: %s", json.dumps(pmtiles_result, indent=2))

    logger.info("--- Pipeline complete ---")
