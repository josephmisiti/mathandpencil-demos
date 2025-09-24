#!/usr/bin/env python3
"""Process SLOSH MOM inundation rasters into zoom-specific COGs."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set

import modal

TIMEOUT = 8 * 3600


SLOSH_DATASETS: List[Dict[str, str]] = [
    # {
    #     "key": "american_samoa",  
    #     "description": "American Samoa",
    #     "zip_name": "American_Samoa_SLOSH_MOM_Inundation_v3.zip",
    #     "output_prefix": "SLOSH_AMERICAN_SAMOA",
    #     "processed_subdir": "american_samoa",
    # },
    # {
    #     "key": "guam",
    #     "description": "Guam",
    #     "zip_name": "Guam_SLOSH_MOM_Inundation_v3.zip",
    #     "output_prefix": "SLOSH_GUAM",
    #     "processed_subdir": "guam",
    # },
    # {
    #     "key": "hispaniola",
    #     "description": "Hispaniola",
    #     "zip_name": "Hispaniola_SLOSH_MOM_Inundation.zip",
    #     "output_prefix": "SLOSH_HISPANIOLA",
    #     "processed_subdir": "hispaniola",
    # },
    {
        "key": "hawaii",
        "description": "Hawaii",
        "zip_name": "Hawaii_SLOSH_MOM_Inundation.zip",
        "output_prefix": "SLOSH_HAWAII",
        "processed_subdir": "hawaii",
    },
    {
        "key": "puerto_rico",
        "description": "Puerto Rico",
        "zip_name": "PR_SLOSH_MOM_Inundation.zip",
        "output_prefix": "SLOSH_PR",
        "processed_subdir": "puerto_rico",
    },
    {
        "key": "southern_california",
        "description": "Southern California",
        "zip_name": "Southern_California_SLOSH_MOM_Inundation_v3.zip",
        "output_prefix": "SLOSH_SOUTHERN_CALIFORNIA",
        "processed_subdir": "southern_california",
    },
    {
        "key": "us",
        "description": "Continental United States",
        "zip_name": "US_SLOSH_MOM_Inundation_v3.zip",
        "output_prefix": "SLOSH_US",
        "processed_subdir": "us",
    },
    # {
    #     "key": "usvi",
    #     "description": "U.S. Virgin Islands",
    #     "zip_name": "USVI_SLOSH_MOM_Inundation.zip",
    #     "output_prefix": "SLOSH_USVI",
    #     "processed_subdir": "usvi",
    # },
    # {
    #     "key": "yucatan",
    #     "description": "Yucatán Peninsula",
    #     "zip_name": "Yucatan_SLOSH_MOM_Inundation_v3.zip",
    #     "output_prefix": "SLOSH_YUCATAN",
    #     "processed_subdir": "yucatan",
    # },
]

SLOSH_DATASETS_BY_KEY: Dict[str, Dict[str, str]] = {
    dataset["key"]: dataset for dataset in SLOSH_DATASETS
}

SLOSH_CATEGORY_NAMES: List[str] = [
    "Category1",
    "Category2",
    "Category3",
    "Category4",
    "Category5",
]

SLOSH_ZOOM_CONFIGS: List[Dict[str, object]] = [
    {
        "suffix": "z0_10",
        "resolution": 0.001,
        "description": "Low zoom (0-10)",
    },
    {
        "suffix": "z10_16",
        "resolution": 0.0001,
        "description": "Medium zoom (10-16)",
    },
    {
        "suffix": "z16_20",
        "resolution": None,
        "description": "High zoom (16-20)",
    },
]


def select_datasets(keys: Optional[Iterable[str]]) -> List[Dict[str, str]]:
    if not keys:
        return SLOSH_DATASETS

    selected: List[Dict[str, str]] = []
    missing: List[str] = []
    for key in keys:
        dataset = SLOSH_DATASETS_BY_KEY.get(key)
        if dataset:
            selected.append(dataset)
        else:
            missing.append(key)

    if missing:
        raise KeyError(
            "Unknown SLOSH dataset key(s): " + ", ".join(sorted(set(missing)))
        )

    return selected


def build_output_filename(
    prefix: str,
    category: str,
    suffix: str,
    run_tag: str,
) -> str:
    sanitized_tag = run_tag.replace(" ", "_")
    return f"{prefix}_{category}_{suffix}_{sanitized_tag}.cog.tif"


def load_completed_manifest(
    dataset: Dict[str, str],
    run_tag: str,
) -> Optional[Dict[str, object]]:
    """Return the manifest if the dataset already has outputs for ``run_tag``."""

    output_dir = PROCESSED_ROOT / dataset["processed_subdir"]
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read manifest %s: %s", manifest_path, exc)
        return None

    if manifest.get("run_tag") != run_tag:
        return None

    categories = manifest.get("categories")
    if not isinstance(categories, dict) or not categories:
        return None

    expected_suffixes = {config["suffix"] for config in SLOSH_ZOOM_CONFIGS}

    for category, category_info in categories.items():
        if not isinstance(category_info, dict):
            return None
        cogs = category_info.get("cogs")
        if not isinstance(cogs, dict):
            return None
        missing_suffixes = expected_suffixes - set(cogs)
        if missing_suffixes:
            logger.info(
                "%s %s missing expected COGs for suffix(es) %s; reprocessing",
                dataset["description"],
                category,
                ", ".join(sorted(missing_suffixes)),
            )
            return None
        for suffix in expected_suffixes:
            filename = cogs.get(suffix)
            if not filename:
                return None
            expected_path = output_dir / filename
            if not expected_path.exists():
                logger.warning(
                    "Expected output missing for %s %s (%s)",
                    dataset["description"],
                    category,
                    expected_path,
                )
                return None

    return manifest


RAW_ROOT = Path("/data/raw")
PROCESSED_ROOT = Path("/data/processed")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = modal.App("slosh-processor")
volume = modal.Volume.from_name("national-hurricane-center-slosh")


gdal_image = modal.Image.debian_slim(python_version="3.11").apt_install(
    "gdal-bin",
    "python3-gdal",
    "unzip",
    "wget",
).pip_install("rasterio", "numpy")


@app.function(
    image=gdal_image,
    volumes={"/data": volume},
    timeout=TIMEOUT,
    memory=4 * 4096,
)
def process_slosh_datasets(
    dataset_keys: Optional[Sequence[str]] = None,
    run_tag: Optional[str] = None,
) -> None:
    """Process one or more configured SLOSH datasets."""

    try:
        datasets = select_datasets(dataset_keys)
    except KeyError as exc:
        logger.error("%s", exc)
        raise

    effective_run_tag = (run_tag or datetime.utcnow().strftime("%Y%m%d")).strip()
    logger.info(
        "Preparing to process %d dataset(s) with run tag %s: %s",
        len(datasets),
        effective_run_tag,
        ", ".join(dataset["description"] for dataset in datasets),
    )

    processed_any = False
    manifests: List[Dict[str, object]] = []

    for dataset in datasets:
        manifest = process_single_dataset(dataset, effective_run_tag)
        if manifest:
            processed_any = True
            manifests.append(manifest)

    if processed_any:
        write_global_manifest(manifests, effective_run_tag)
        volume.commit()
        logger.info("Processing complete.")
    else:
        logger.info("No datasets were processed (missing files or empty archives).")


def process_single_dataset(
    dataset: Dict[str, str],
    run_tag: str,
) -> Optional[Dict[str, object]]:
    """Extract and process every category raster for a specific dataset."""

    input_zip = RAW_ROOT / dataset["zip_name"]
    output_dir = PROCESSED_ROOT / dataset["processed_subdir"]

    if not input_zip.exists():
        logger.warning(
            "Skipping %s; ZIP archive missing: %s",
            dataset["description"],
            input_zip,
        )
        return None

    existing_manifest = load_completed_manifest(dataset, run_tag)
    if existing_manifest:
        logger.info(
            "Skipping %s; already processed for run tag %s",
            dataset["description"],
            run_tag,
        )
        return existing_manifest

    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Processing %s from %s with run tag %s",
        dataset["description"],
        input_zip,
        run_tag,
    )

    processed_categories: Set[str] = set()
    category_outputs: List[str] = []
    category_bounds: Dict[str, List[float]] = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info("Extracting archive to %s", temp_dir)

        with zipfile.ZipFile(input_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        tif_files = sorted(Path(temp_dir).rglob("*.tif"))
        if not tif_files:
            logger.warning("No GeoTIFF files found in %s", input_zip)
            return None

        for tif_file in tif_files:
            category = extract_category_name(tif_file.name)
            if not category:
                continue
            if category in processed_categories:
                logger.info(
                    "Already produced %s for %s; skipping %s",
                    category,
                    dataset["description"],
                    tif_file.name,
                )
                continue

            logger.info("Processing %s (%s)", category, tif_file.name)

            produced = process_category_raster(
                tif_file,
                output_dir,
                dataset["output_prefix"],
                category,
                run_tag,
            )

            if produced:
                processed_categories.add(category)
                category_outputs.extend(produced)

                high_res_path = output_dir / build_output_filename(
                    dataset["output_prefix"],
                    category,
                    "z16_20",
                    run_tag,
                )
                if high_res_path.exists():
                    bounds = extract_raster_bounds(high_res_path)
                    if bounds:
                        category_bounds[category] = bounds
                    else:
                        logger.warning(
                            "Could not determine bounds for %s %s (%s)",
                            dataset["description"],
                            category,
                            high_res_path.name,
                        )
                else:
                    logger.warning(
                        "High-resolution COG missing for %s %s at expected path %s",
                        dataset["description"],
                        category,
                        high_res_path,
                    )

    if not processed_categories:
        logger.warning("No SLOSH categories found for %s", dataset["description"])
        return None

    missing_categories = [
        category
        for category in SLOSH_CATEGORY_NAMES
        if category not in processed_categories
    ]

    if missing_categories:
        logger.warning(
            "%s missing categories: %s",
            dataset["description"],
            ", ".join(missing_categories),
        )

    dataset_bounds = merge_bounds(category_bounds.values())

    manifest = write_manifest(
        dataset=dataset,
        category_bounds=category_bounds,
        dataset_bounds=dataset_bounds,
        output_dir=output_dir,
        run_tag=run_tag,
    )

    logger.info(
        "Completed %s; generated %d file(s).",
        dataset["description"],
        len(category_outputs),
    )
    return manifest


CATEGORY_PATTERN = re.compile(r"Category\s*([1-5])", re.IGNORECASE)


def extract_category_name(filename: str) -> Optional[str]:
    """Return the canonical ``CategoryN`` label from a filename, if present."""

    match = CATEGORY_PATTERN.search(filename)
    if not match:
        return None
    number = match.group(1)
    return f"Category{number}"


def process_category_raster(
    input_tif: Path,
    output_dir: Path,
    output_prefix: str,
    category: str,
    run_tag: str,
) -> List[str]:
    """Generate the configured zoom-level COGs for a single category."""

    produced_files: List[str] = []

    for config in SLOSH_ZOOM_CONFIGS:
        suffix = config["suffix"]
        output_file = output_dir / build_output_filename(
            output_prefix,
            category,
            suffix,
            run_tag,
        )

        if output_file.exists():
            logger.info("Skipping existing COG %s", output_file)
            produced_files.append(str(output_file))
            continue

        logger.info("Creating %s", output_file)

        resolution = config.get("resolution")
        if resolution:
            create_resampled_cog(input_tif, output_file, float(resolution))
        else:
            create_full_resolution_cog(input_tif, output_file)

        produced_files.append(str(output_file))

    return produced_files


def create_resampled_cog(input_file: Path, output_file: Path, target_resolution: float) -> None:
    """Create a resampled COG at ``target_resolution`` degrees."""

    cmd = [
        "gdalwarp",
        "-tr",
        str(target_resolution),
        str(target_resolution),
        "-r",
        "average",
        "-of",
        "COG",
        "-co",
        "COMPRESS=LZW",
        "-co",
        "PREDICTOR=2",
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "OVERVIEW_RESAMPLING=AVERAGE",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        str(input_file),
        str(output_file),
    ]

    run_command(cmd, f"gdalwarp {input_file.name}")


def create_full_resolution_cog(input_file: Path, output_file: Path) -> None:
    """Create a full-resolution COG copy of ``input_file``."""

    cmd = [
        "gdal_translate",
        "-of",
        "COG",
        "-co",
        "COMPRESS=LZW",
        "-co",
        "PREDICTOR=2",
        "-co",
        "BLOCKSIZE=512",
        "-co",
        "OVERVIEW_RESAMPLING=NEAREST",
        "-co",
        "OVERVIEW_COUNT=6",
        "-co",
        "NUM_THREADS=ALL_CPUS",
        str(input_file),
        str(output_file),
    ]

    run_command(cmd, f"gdal_translate {input_file.name}")


def run_command(cmd: Sequence[str], label: str) -> None:
    """Run a subprocess command and raise an informative error on failure."""

    logger.info("Running command: %s", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("PROJ_NETWORK", "YES")
    env.setdefault("OSR_USE_ESTIMATED_COORD_OPS", "YES")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        logger.error("%s failed: %s", label, result.stderr.strip())
        raise RuntimeError(f"{label} failed: {result.stderr.strip()}")

def gdalinfo_json(path: Path) -> Optional[Dict[str, object]]:
    if not path.exists():
        return None

    result = subprocess.run(
        ["gdalinfo", "-json", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("gdalinfo failed for %s: %s", path, result.stderr.strip())
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse gdalinfo output for %s: %s", path, exc)
        return None


def extract_raster_bounds(path: Path) -> Optional[List[float]]:
    info = gdalinfo_json(path)
    if not info:
        return None

    corners = info.get("cornerCoordinates")
    if not isinstance(corners, dict):
        return None

    coords = [
        corners.get("upperLeft"),
        corners.get("upperRight"),
        corners.get("lowerLeft"),
        corners.get("lowerRight"),
    ]
    valid = [c for c in coords if isinstance(c, (list, tuple)) and len(c) >= 2]
    if not valid:
        return None

    min_x = min(point[0] for point in valid)
    max_x = max(point[0] for point in valid)
    min_y = min(point[1] for point in valid)
    max_y = max(point[1] for point in valid)
    return [min_x, min_y, max_x, max_y]


def merge_bounds(bounds_iterable: Iterable[List[float]]) -> Optional[List[float]]:
    mins_x: List[float] = []
    mins_y: List[float] = []
    maxs_x: List[float] = []
    maxs_y: List[float] = []

    for bounds in bounds_iterable:
        if not bounds:
            continue
        min_x, min_y, max_x, max_y = bounds
        mins_x.append(min_x)
        mins_y.append(min_y)
        maxs_x.append(max_x)
        maxs_y.append(max_y)

    if not mins_x:
        return None

    return [min(mins_x), min(mins_y), max(maxs_x), max(maxs_y)]


def write_manifest(
    *,
    dataset: Dict[str, str],
    category_bounds: Dict[str, List[float]],
    dataset_bounds: Optional[List[float]],
    output_dir: Path,
    run_tag: str,
) -> Dict[str, object]:
    manifest_path = output_dir / "manifest.json"

    manifest = {
        "key": dataset["key"],
        "description": dataset["description"],
        "output_prefix": dataset["output_prefix"],
        "processed_subdir": dataset["processed_subdir"],
        "run_tag": run_tag,
        "bounds": dataset_bounds,
        "categories": {},
    }

    for category in SLOSH_CATEGORY_NAMES:
        high_res_filename = build_output_filename(
            dataset["output_prefix"],
            category,
            "z16_20",
            run_tag,
        )
        if not (output_dir / high_res_filename).exists():
            continue

        category_info = {
            "bounds": category_bounds.get(category),
            "cogs": {},
        }
        for config in SLOSH_ZOOM_CONFIGS:
            suffix = config["suffix"]
            filename = build_output_filename(
                dataset["output_prefix"],
                category,
                suffix,
                run_tag,
            )
            if (output_dir / filename).exists():
                category_info["cogs"][suffix] = filename
        manifest["categories"][category] = category_info

    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Wrote manifest %s", manifest_path)
    except OSError as exc:
        logger.warning("Failed to write manifest %s: %s", manifest_path, exc)
    return manifest


def write_global_manifest(manifests: List[Dict[str, object]], run_tag: str) -> None:
    if not manifests:
        return

    index = {
        manifest.get("key"): manifest for manifest in manifests if manifest.get("key")
    }
    manifest_path = PROCESSED_ROOT / f"slosh_datasets_{run_tag}.json"
    latest_path = PROCESSED_ROOT / "slosh_datasets_latest.json"
    legacy_path = PROCESSED_ROOT / "slosh_datasets.json"

    serialized = json.dumps(index, indent=2)

    try:
        manifest_path.write_text(serialized)
        latest_path.write_text(serialized)
        legacy_path.write_text(serialized)
        logger.info(
            "Wrote dataset index %s and updated %s / %s",
            manifest_path,
            latest_path,
            legacy_path,
        )
    except OSError as exc:
        logger.warning(
            "Failed to write dataset index files (%s / %s / %s): %s",
            manifest_path,
            latest_path,
            legacy_path,
            exc,
        )


def list_processed_files(dataset_key: Optional[str] = None) -> Dict[str, List[str]]:
    """Return the generated COG files per dataset."""

    if dataset_key:
        dataset = SLOSH_DATASETS_BY_KEY.get(dataset_key)
        if not dataset:
            raise KeyError(f"Unknown dataset key: {dataset_key}")
        datasets = [dataset]
    else:
        datasets = SLOSH_DATASETS

    results: Dict[str, List[str]] = {}
    for dataset in datasets:
        directory = PROCESSED_ROOT / dataset["processed_subdir"]
        if not directory.exists():
            continue
        files = sorted(directory.glob("*.tif"))
        results[dataset["key"]] = [f.name for f in files]
    return results


def inspect_file(dataset_key: str, filename: str) -> str:
    """Run ``gdalinfo`` on a processed file for debugging."""

    dataset = SLOSH_DATASETS_BY_KEY.get(dataset_key)
    if not dataset:
        raise KeyError(f"Unknown dataset key: {dataset_key}")

    file_path = PROCESSED_ROOT / dataset["processed_subdir"] / filename
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    cmd = ["gdalinfo", "-stats", "-hist", str(file_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error inspecting file: {result.stderr}")
    return result.stdout


@app.local_entrypoint()
def main(*args: str) -> None:
    """Allow ``modal run`` to process all or selected datasets locally."""

    dataset_keys: List[str] = []
    run_tag: Optional[str] = None

    for arg in args:
        if arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        else:
            dataset_keys.append(arg)

    keys_arg: Optional[List[str]] = dataset_keys if dataset_keys else None

    process_slosh_datasets.remote(keys_arg, run_tag=run_tag)
