import modal
import os
import json
import logging
from datetime import UTC, datetime

STORAGE_ROOT = "/cache"
FEMA_BASE_URL = 'https://hazards.fema.gov/nfhlv2/output/State/'
STFIPS = [
    '01', '02', '04', '05', '06', '08', '09', '10', '11', '12', '13', '15', '16',
    '17', '18', '19', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29',
    '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '40', '41', '42',
    '44', '45', '46', '47', '48', '49', '50', '51', '53', '54', '55', '56', '60',
    '66', '69', '72', '78',
]


storage = modal.Volume.from_name("fema-flood-zone-storage")

app = modal.App(
    "fema-flood-zone-pipeline-v2",
    image=modal.Image.debian_slim().pip_install("requests"),
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.function(retries=3)
def get_manifest_for_fips(fips: str) -> dict:
    import requests
    logger.info(f"Fetching manifest data for FIPS {fips}...")
    try:
        url = (
            f'https://msc.fema.gov/portal/advanceSearch?affiliate=fema&query&'
            f'selstate={fips}&selcounty={fips}001&selcommunity={fips}001C&'
            f'searchedCid={fips}001C&method=search'
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        state_data_list = response.json().get("EFFECTIVE", {}).get("NFHL_STATE_DATA")
        if not state_data_list or not isinstance(state_data_list, list):
            raise ValueError(f"Unexpected or missing data for FIPS {fips}")

        state_data = state_data_list[0]
        manifest_item = {
            "fips": fips,
            "effective": state_data.get("product_EFFECTIVE_DATE_STRING"),
            "file_name": state_data.get("product_FILE_PATH"),
            "file_size": state_data.get("product_FILE_SIZE"),
        }
        
        for key in ["effective", "file_name", "file_size"]:
            if not manifest_item[key]:
                raise ValueError(f"Missing '{key}' in manifest for FIPS {fips}")
                
        return manifest_item

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error for FIPS {fips}: {e}")
        raise
    except (ValueError, KeyError, IndexError) as e:
        logger.error(f"Data parsing error for FIPS {fips}: {e}")
        raise

@app.function(
    timeout=1200,
    memory=2048,
    volumes={STORAGE_ROOT: storage},
)
def stream_zip_to_storage(manifest_item: dict):
    import requests

    file_name = manifest_item["file_name"]
    storage_path = os.path.join(STORAGE_ROOT, "state_raw", file_name)

    os.makedirs(os.path.dirname(storage_path), exist_ok=True)

    if os.path.exists(storage_path):
        logger.warning(f"SKIP: {storage_path} already exists.")
        return {"fips": manifest_item["fips"], "status": "skipped"}

    download_url = f"{FEMA_BASE_URL}{file_name}"
    logger.info(f"Downloading {download_url} to {storage_path}")

    try:
        with requests.get(download_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(storage_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info(f"SUCCESS: Downloaded {storage_path}")
        return {"fips": manifest_item["fips"], "status": "success"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {download_url}: {e}")
        if os.path.exists(storage_path):
            os.remove(storage_path)
        return {"fips": manifest_item["fips"], "status": "failed", "error": str(e)}

@app.function(volumes={STORAGE_ROOT: storage})
def manage_manifest(action: str, path: str, data: dict = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if action == "read":
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return None
    elif action == "write":
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return data

@app.local_entrypoint()
def main():
    now = datetime.now(UTC)
    vintage_name = f"mainfest-{now.strftime('%Y%m%d')}"
    manifest_dir = os.path.join(STORAGE_ROOT, "manifest")
    manifest_path = os.path.join(manifest_dir, f"{vintage_name}.json")
    manifest = {}

    logger.info("--- Step 1: Building or Getting Manifest ---")

    result = manage_manifest.remote("delete", manifest_path)
    print(result)

    existing_manifest = manage_manifest.remote("read", manifest_path)

    if existing_manifest:
        logger.info(f"Manifest '{manifest_path}' already exists. Using it.")
        manifest = existing_manifest
    else:
        logger.info(f"Manifest not found. Generating a new one for {vintage_name}...")
        results = list(get_manifest_for_fips.map(STFIPS))
        
        manifest = {item.pop("fips"): item for item in results if item}

        logger.info(f"Uploading new manifest to '{manifest_path}'")
        manage_manifest.remote("write", manifest_path, data=manifest)

    logger.info(f"\n--- Step 2: Processing {len(manifest)} Files in Parallel ---")
    
    manifest_items_to_process = [
        {"fips": fips, **data} for fips, data in manifest.items()
    ]
    
    successful_uploads = 0
    for result in stream_zip_to_storage.map(manifest_items_to_process, order_outputs=False):
        if result.get("status") == "success":
            successful_uploads += 1

    logger.info(f"\n--- Pipeline Complete ---")
    logger.info(f"Successfully downloaded {successful_uploads} new files to Modal Volume.")