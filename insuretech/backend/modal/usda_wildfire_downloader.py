import logging
import os

import modal

STORAGE_ROOT = "/cache"
STATE_ZIP_URLS = {
    "RDS-2020-0060-2_Alabama.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Alabama.zip",
    "RDS-2020-0060-2_Alaska.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Alaska.zip",
    "RDS-2020-0060-2_Arizona.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Arizona.zip",
    "RDS-2020-0060-2_Arkansas.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Arkansas.zip",
    "RDS-2020-0060-2_California.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_California.zip",
    "RDS-2020-0060-2_Colorado.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Colorado.zip",
    "RDS-2020-0060-2_Connecticut.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Connecticut.zip",
    "RDS-2020-0060-2_Delaware.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Delaware.zip",
    "RDS-2020-0060-2_DistrictOfColumbia.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_DistrictOfColumbia.zip",
    "RDS-2020-0060-2_Florida.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Florida.zip",
    "RDS-2020-0060-2_Georgia.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Georgia.zip",
    "RDS-2020-0060-2_Hawaii.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Hawaii.zip",
    "RDS-2020-0060-2_Idaho.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Idaho.zip",
    "RDS-2020-0060-2_Illinois.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Illinois.zip",
    "RDS-2020-0060-2_Indiana.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Indiana.zip",
    "RDS-2020-0060-2_Iowa.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Iowa.zip",
    "RDS-2020-0060-2_Kansas.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Kansas.zip",
    "RDS-2020-0060-2_Kentucky.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Kentucky.zip",
    "RDS-2020-0060-2_Louisiana.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Louisiana.zip",
    "RDS-2020-0060-2_Maine.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Maine.zip",
    "RDS-2020-0060-2_Maryland.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Maryland.zip",
    "RDS-2020-0060-2_Massachusetts.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Massachusetts.zip",
    "RDS-2020-0060-2_Michigan.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Michigan.zip",
    "RDS-2020-0060-2_Minnesota.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Minnesota.zip",
    "RDS-2020-0060-2_Mississippi.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Mississippi.zip",
    "RDS-2020-0060-2_Missouri.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Missouri.zip",
    "RDS-2020-0060-2_Montana.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Montana.zip",
    "RDS-2020-0060-2_Nebraska.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Nebraska.zip",
    "RDS-2020-0060-2_Nevada.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Nevada.zip",
    "RDS-2020-0060-2_NewHampshire.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NewHampshire.zip",
    "RDS-2020-0060-2_NewJersey.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NewJersey.zip",
    "RDS-2020-0060-2_NewMexico.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NewMexico.zip",
    "RDS-2020-0060-2_NewYork.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NewYork.zip",
    "RDS-2020-0060-2_NorthCarolina.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NorthCarolina.zip",
    "RDS-2020-0060-2_NorthDakota.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_NorthDakota.zip",
    "RDS-2020-0060-2_Ohio.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Ohio.zip",
    "RDS-2020-0060-2_Oklahoma.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Oklahoma.zip",
    "RDS-2020-0060-2_Oregon.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Oregon.zip",
    "RDS-2020-0060-2_Pennsylvania.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Pennsylvania.zip",
    "RDS-2020-0060-2_RhodeIsland.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_RhodeIsland.zip",
    "RDS-2020-0060-2_SouthCarolina.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_SouthCarolina.zip",
    "RDS-2020-0060-2_SouthDakota.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_SouthDakota.zip",
    "RDS-2020-0060-2_Tennessee.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Tennessee.zip",
    "RDS-2020-0060-2_Texas.zip": "https://usfs-public.box.com/shared/static/4rb5ar8ym19n2mkyr49b9ms92h85t5yf.zip",
    "RDS-2020-0060-2_Utah.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Utah.zip",
    "RDS-2020-0060-2_Vermont.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Vermont.zip",
    "RDS-2020-0060-2_Virginia.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Virginia.zip",
    "RDS-2020-0060-2_Washington.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Washington.zip",
    "RDS-2020-0060-2_WestVirginia.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_WestVirginia.zip",
    "RDS-2020-0060-2_Wisconsin.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Wisconsin.zip",
    "RDS-2020-0060-2_Wyoming.zip": "https://www.fs.usda.gov/rds/archive/products/RDS-2020-0060-2/RDS-2020-0060-2_Wyoming.zip",
}


storage = modal.Volume.from_name("usda-wildfire")

app = modal.App(
    "usda-wildfire-downloader",
    image=modal.Image.debian_slim().pip_install("requests"),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.function(
    timeout=3600,
    memory=2048,
    volumes={STORAGE_ROOT: storage},
)
def stream_zip_to_storage(file_name: str, download_url: str) -> dict:
    import requests

    storage.reload()

    storage_path = os.path.join(STORAGE_ROOT, "raw", file_name)
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    if os.path.exists(storage_path):
        logger.warning("SKIP: %s already exists.", storage_path)
        return {"file": file_name, "status": "skipped"}

    logger.info("Downloading %s to %s", download_url, storage_path)

    try:
        with requests.get(download_url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(storage_path, "wb") as destination:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        destination.write(chunk)
        logger.info("SUCCESS: Downloaded %s", storage_path)
        storage.commit()
        return {"file": file_name, "status": "success"}
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download %s: %s", download_url, exc)
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return {"file": file_name, "status": "failed", "error": str(exc)}


@app.local_entrypoint()
def main():
    logger.info("--- USDA Wildfire Download Pipeline Starting ---")
    successes = 0

    for file_name, url in STATE_ZIP_URLS.items():
        result = stream_zip_to_storage.remote(file_name, url)
        if result.get("status") == "success":
            successes += 1

    logger.info("--- Pipeline Complete ---")
    logger.info("Successfully downloaded %d new files to Modal volume.", successes)
