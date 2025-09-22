"""Combine per-category SLOSH COGs into category PMTiles (no execution)."""

import logging
import os
import tempfile
from pathlib import Path

import modal


STORAGE_ROOT = "/cache"
PROCESSED_DIR = "processed/puerto_rico"
OUTPUT_DIR = "outputs"
CATEGORY_NAMES = [
    "Category1",
    "Category2",
    "Category3",
    "Category4",
    "Category5",
]


volume = modal.Volume.from_name("national-hurricane-center-slosh")

geo_image = (
    modal.Image.debian_slim()
    .apt_install(
        "gdal-bin",
        "python3-gdal",
        "curl",
        "unzip",
        "wget",
    )
    .run_commands(
        [
            "curl -L https://github.com/protomaps/go-pmtiles/releases/download/v1.11.1/go-pmtiles_1.11.1_Linux_x86_64.tar.gz -o /tmp/pmtiles.tar.gz",
            "cd /tmp && tar -xzf pmtiles.tar.gz",
            "mv /tmp/pmtiles /usr/local/bin/",
            "chmod +x /usr/local/bin/pmtiles",
            "rm /tmp/pmtiles.tar.gz",
            "pmtiles --help || echo 'pmtiles CLI installed'",
        ]
    )
)


app = modal.App("slosh-combiner", image=geo_image)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.function(volumes={STORAGE_ROOT: volume}, timeout=3600, memory=4096)
def combine_categories():
    """Take z16_20 COGs and write PMTiles into outputs/ (no execution)."""

    processed_path = Path(STORAGE_ROOT) / PROCESSED_DIR
    output_path = Path(STORAGE_ROOT) / OUTPUT_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Combining SLOSH categories from %s", processed_path)

    for category in CATEGORY_NAMES:
        src = processed_path / f"SLOSH_PR_{category}_z16_20.cog.tif"
        if not src.exists():
            logger.warning("Skipping %s (missing)", src)
            continue

        dst = output_path / f"SLOSH_PR_{category}.pmtiles"

        logger.info("Creating %s from %s", dst, src)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_warped = Path(tmp) / f"{dst.stem}_3857.tif"
            tmp_mbtiles = Path(tmp) / f"{dst.stem}.mbtiles"
            tmp_pmtiles = Path(tmp) / dst.name

            # Reproject to WebMercator for compatibility with Google tiles
            warp_cmd = (
                "gdalwarp"
                " -t_srs EPSG:3857"
                " -r bilinear"
                " -of COG"
                " -co COMPRESS=LZW"
                " -co PREDICTOR=2"
                f" {src} {tmp_warped}"
            )
            os.system(warp_cmd)

            # Convert raster to MBTiles with GoogleMapsCompatible scheme
            gdal_cmd = (
                "gdal_translate"
                " -of MBTILES"
                " -co TILE_FORMAT=PNG"
                f" {tmp_warped} {tmp_mbtiles}"
            )
            os.system(gdal_cmd)

            # Build pyramid overviews for smoother low zooms
            os.system(f"gdaladdo -r average {tmp_mbtiles} 2 4 8 16 32 64")

            # Convert MBTiles to PMTiles
            os.system(f"pmtiles convert {tmp_mbtiles} {tmp_pmtiles}")

            # Copy back into volume
            os.system(f"cp {tmp_pmtiles} {dst}")

    volume.commit()
    logger.info("SLOSH category PMTiles ready in %s", output_path)


@app.local_entrypoint()
def main():
    combine_categories.remote()
