import logging
import os
from urllib.parse import urlparse

import modal

STORAGE_ROOT = "/cache"
FEMA_USA_STRUCTURES_LINKS = [
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Alabama/Deliverable20250606AL.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Alaska/Deliverable20250606AK.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/American+Samoa/Deliverable20250606AS.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Arizona/Deliverable20230502AZ.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Arkansas/Deliverable20230630AR.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/California/Deliverable20230728CA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Colorado/Deliverable20230630CO.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Connecticut/Deliverable20250606CT.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Delaware/Deliverable20250606DE.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/District+of+Columbia/Deliverable20250606DC.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Guam/Deliverable20250606GU.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Florida/Deliverable20250606FL.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Georgia/Deliverable20250606GA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Hawaii/Deliverable20250606HI.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Idaho/Deliverable20230526ID.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Illinois/Deliverable20230831IL.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Indiana/Deliverable20230502IN.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Iowa/Deliverable20250606IA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Kansas/Deliverable20250606KS.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Kentucky/Deliverable20250606KY.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Louisiana/Deliverable20250606LA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Maine/Deliverable20250606ME.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Maryland/Deliverable20230728MD.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Massachusetts/Deliverable20230502MA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Michigan/Deliverable20250606MI.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Minnesota/Deliverable20250606MN.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Missouri/Deliverable20230728MO.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Mississippi/Deliverable20250606MS.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Montana/Deliverable20250606MT.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Nebraska/Deliverable20250606NE.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Nevada/Deliverable20230526NV.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/New+Hampshire/Deliverable20250606NH.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/New+Jersey/Deliverable20230502NJ.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/New+Mexico/Deliverable20250606NM.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/New+York/Deliverable20250606NY.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/North+Carolina/Deliverable20250606NC.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/North+Dakota/Deliverable20250606ND.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Northern+Mariana+Islands/Deliverable20250606MP.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Ohio/Deliverable20230502OH.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Oklahoma/Deliverable20231003OK.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Oregon/Deliverable20250606OR.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Pennsylvania/Deliverable20230831PA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Puerto+Rico/Deliverable20250606PR.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Rhode+Island/Deliverable20250606RI.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/South+Carolina/Deliverable20250606SC.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/South+Dakota/Deliverable20250606SD.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Tennessee/Deliverable20250606TN.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Texas/Deliverable20250606TX.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Utah/Deliverable20250606UT.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Vermont/Deliverable20250606VT.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Virgin+Islands/Deliverable20250606VI.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Virginia/Deliverable20250606VA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Washington/Deliverable20250606WA.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/West+Virginia/Deliverable20250606WV.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Wisconsin/Deliverable20250606WI.zip",
    "https://fema-femadata.s3.amazonaws.com/Partners/ORNL/USA_Structures/Wyoming/Deliverable20250606WY.zip",
]


storage = modal.Volume.from_name("fema-usa-structures")

app = modal.App(
    "fema-usa-structures-downloader",
    image=modal.Image.debian_slim().pip_install("requests"),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.function(
    timeout=3600,
    memory=2048,
    volumes={STORAGE_ROOT: storage},
)
def stream_zip_to_storage(download_url: str) -> dict:
    import requests

    file_name = os.path.basename(urlparse(download_url).path)
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
        return {"file": file_name, "status": "success"}
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download %s: %s", download_url, exc)
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return {"file": file_name, "status": "failed", "error": str(exc)}


@app.local_entrypoint()
def main():
    logger.info("--- FEMA USA Structures Download Pipeline Starting ---")
    successes = 0

    for result in stream_zip_to_storage.map(FEMA_USA_STRUCTURES_LINKS, order_outputs=False):
        if result.get("status") == "success":
            successes += 1

    logger.info("--- Pipeline Complete ---")
    logger.info("Successfully downloaded %d new files to Modal volume.", successes)
