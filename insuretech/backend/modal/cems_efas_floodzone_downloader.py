#!/usr/bin/env python3
"""Download CEMS-EFAS flood hazard GeoTIFFs into a Modal volume."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import modal


TIF_URLS: List[str] = [
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP10_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP20_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP30_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP40_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP50_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP75_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP100_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP200_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_RP500_filled_depth.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_permanent_water_bodies.tif",
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-EFAS/flood_hazard/Europe_spurious_depth_areas.tif",
]


app = modal.App("cems-efas-downloader")
volume = modal.Volume.from_name("cems-efas", create_if_missing=True)


def download_file(url: str, destination: Path) -> bool:
    if destination.exists():
        logging.info("Skipping existing file %s", destination.name)
        return False

    try:
        with urlopen(url, timeout=60) as response, destination.open("wb") as out_file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
        logging.info("Downloaded %s", destination.name)
        return True
    except (HTTPError, URLError, TimeoutError) as exc:
        logging.error("Failed to download %s: %s", url, exc)
        if destination.exists():
            destination.unlink(missing_ok=True)
        raise


@app.function(volumes={"/data": volume}, timeout=3600, memory=4096)
def fetch_cems_efas_files() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    target_dir = Path("/data/raw")
    os.makedirs(target_dir, exist_ok=True)

    new_downloads = 0
    for url in TIF_URLS:
        filename = url.split("/")[-1]
        if download_file(url, target_dir / filename):
            new_downloads += 1

    volume.commit()
    logging.info("Completed CEMS-EFAS download run; %d new file(s) saved.", new_downloads)


@app.local_entrypoint()
def main() -> None:
    fetch_cems_efas_files.remote()
