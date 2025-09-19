import logging
import os
from urllib.parse import urlparse

import modal

STORAGE_ROOT = "/cache"
SLOSH_URLS = [
    "https://www.nhc.noaa.gov/gis/hazardmaps/US_SLOSH_MOM_Inundation_v3.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/PR_SLOSH_MOM_Inundation.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/USVI_SLOSH_MOM_Inundation.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/Hawaii_SLOSH_MOM_Inundation.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/Southern_California_SLOSH_MOM_Inundation_v3.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/Guam_SLOSH_MOM_Inundation_v3.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/American_Samoa_SLOSH_MOM_Inundation_v3.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/Hispaniola_SLOSH_MOM_Inundation.zip",
    "https://www.nhc.noaa.gov/gis/hazardmaps/Yucatan_SLOSH_MOM_Inundation_v3.zip",
]


storage = modal.Volume.from_name("national-hurricane-center-slosh")

app = modal.App(
    "slosh-zone-downloader",
    image=modal.Image.debian_slim().pip_install("requests"),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.function(
    timeout=1800,
    memory=2048,
    volumes={STORAGE_ROOT: storage},
)
def stream_zip_to_storage(download_url: str) -> dict:
    import requests

    parsed = urlparse(download_url)
    file_name = os.path.basename(parsed.path)
    storage_path = os.path.join(STORAGE_ROOT, "raw", file_name)

    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    if os.path.exists(storage_path):
        logger.warning("SKIP: %s already exists.", storage_path)
        return {"file": file_name, "status": "skipped"}

    logger.info("Downloading %s to %s", download_url, storage_path)

    try:
        with requests.get(download_url, stream=True, timeout=30) as response:
            response.raise_for_status()
            with open(storage_path, "wb") as destination:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        destination.write(chunk)
        logger.info("SUCCESS: Downloaded %s", storage_path)
        return {"file": file_name, "status": "success"}
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download %s: %s", download_url, exc)
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return {"file": file_name, "status": "failed", "error": str(exc)}


@app.local_entrypoint()
def main():
    logger.info("--- SLOSH Download Pipeline Starting ---")
    successes = 0

    for result in stream_zip_to_storage.map(SLOSH_URLS, order_outputs=False):
        if result.get("status") == "success":
            successes += 1

    logger.info("--- Pipeline Complete ---")
    logger.info("Successfully downloaded %d new files to Modal volume.", successes)
