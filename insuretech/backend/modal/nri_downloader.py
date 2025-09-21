import os
import logging
import modal
import requests


STORAGE_ROOT = "/cache"
TARGET_URL = (
    "https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/"
    "NRI_Shapefile_CensusTracts/NRI_Shapefile_CensusTracts.zip"
)
TARGET_FILENAME = "NRI_Shapefile_CensusTracts.zip"


volume = modal.Volume.from_name("nri-data")


app = modal.App(
    "nri-downloader",
    image=modal.Image.debian_slim().pip_install("requests"),
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.function(volumes={STORAGE_ROOT: volume}, timeout=600)
def download_nri_zip():
    """Download the NRI census tract shapefile archive into nri-data/raw."""

    raw_dir = os.path.join(STORAGE_ROOT, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    target_path = os.path.join(raw_dir, TARGET_FILENAME)

    if os.path.exists(target_path):
        logger.info("File already exists at %s; skipping download.", target_path)
        return {"status": "skipped", "path": target_path}

    logger.info("Downloading %s", TARGET_URL)
    response = requests.get(TARGET_URL, stream=True, timeout=60)
    response.raise_for_status()

    with open(target_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    volume.commit()

    size_mb = os.path.getsize(target_path) / (1024 * 1024)
    logger.info("Downloaded %s (%.1f MB)", target_path, size_mb)

    return {"status": "downloaded", "path": target_path, "size_mb": round(size_mb, 1)}


@app.local_entrypoint()
def main():
    result = download_nri_zip.remote()
    print(result)
