#!/usr/bin/env python3
"""Process CEMS-EFAS flood hazard rasters into zoom-specific COGs."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import modal

DATASETS: List[Dict[str, str]] = [
    {
        "key": "rp10",
        "description": "Return period 10 years",
        "raw_filename": "Europe_RP10_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP10",
    },
    {
        "key": "rp20",
        "description": "Return period 20 years",
        "raw_filename": "Europe_RP20_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP20",
    },
    {
        "key": "rp30",
        "description": "Return period 30 years",
        "raw_filename": "Europe_RP30_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP30",
    },
    {
        "key": "rp40",
        "description": "Return period 40 years",
        "raw_filename": "Europe_RP40_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP40",
    },
    {
        "key": "rp50",
        "description": "Return period 50 years",
        "raw_filename": "Europe_RP50_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP50",
    },
    {
        "key": "rp75",
        "description": "Return period 75 years",
        "raw_filename": "Europe_RP75_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP75",
    },
    {
        "key": "rp100",
        "description": "Return period 100 years",
        "raw_filename": "Europe_RP100_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP100",
    },
    {
        "key": "rp200",
        "description": "Return period 200 years",
        "raw_filename": "Europe_RP200_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP200",
    },
    {
        "key": "rp500",
        "description": "Return period 500 years",
        "raw_filename": "Europe_RP500_filled_depth.tif",
        "output_prefix": "CEMS_EFAS_RP500",
    },
    {
        "key": "water_bodies",
        "description": "Permanent water bodies",
        "raw_filename": "Europe_permanent_water_bodies.tif",
        "output_prefix": "CEMS_EFAS_WATER",
    },
    {
        "key": "spurious",
        "description": "Spurious depth mask",
        "raw_filename": "Europe_spurious_depth_areas.tif",
        "output_prefix": "CEMS_EFAS_SPURIOUS",
    },
]

DATASETS_BY_KEY: Dict[str, Dict[str, str]] = {dataset["key"]: dataset for dataset in DATASETS}

ZOOM_CONFIGS: List[Dict[str, Optional[float]]] = [
    {"suffix": "z0_8", "description": "Low zoom (0-8)", "resolution": 0.005},
    {"suffix": "z8_12", "description": "Medium zoom (8-12)", "resolution": 0.001},
    {"suffix": "z12_18", "description": "High zoom (12-18)", "resolution": 0.00025},
]

RAW_ROOT = Path("/data/raw")
PROCESSED_ROOT = Path("/data/processed")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = modal.App("cems-efas-processor")
volume = modal.Volume.from_name("cems-efas")

gdal_image = modal.Image.debian_slim(python_version="3.11").apt_install(
    "gdal-bin",
    "python3-gdal",
    "unzip",
    "wget",
).pip_install("rasterio", "numpy")


def select_datasets(keys: Optional[Iterable[str]]) -> List[Dict[str, str]]:
    if not keys:
        return DATASETS

    selected: List[Dict[str, str]] = []
    missing: List[str] = []
    for key in keys:
        dataset = DATASETS_BY_KEY.get(key)
        if dataset:
            selected.append(dataset)
        else:
            missing.append(key)

    if missing:
        raise KeyError(
            "Unknown CEMS-EFAS dataset key(s): " + ", ".join(sorted(set(missing)))
        )

    return selected


def build_output_filename(prefix: str, suffix: str, run_tag: str) -> str:
    sanitized_tag = run_tag.replace(" ", "_")
    return f"{prefix}_{suffix}_{sanitized_tag}.cog.tif"


def extract_bounds(path: Path) -> Optional[List[float]]:
    result = subprocess.run(["gdalinfo", "-json", str(path)], capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("gdalinfo failed for %s: %s", path, result.stderr.strip())
        return None

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse gdalinfo output for %s: %s", path, exc)
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

    min_x = min(pt[0] for pt in valid)
    max_x = max(pt[0] for pt in valid)
    min_y = min(pt[1] for pt in valid)
    max_y = max(pt[1] for pt in valid)
    return [min_x, min_y, max_x, max_y]


def create_cog(input_file: Path, output_file: Path, resolution: Optional[float]) -> None:
    cmd: List[str] = [
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
        "OVERVIEW_RESAMPLING=AVERAGE",
        "-co",
        "NUM_THREADS=ALL_CPUS",
    ]

    if resolution:
        cmd.extend(["-tr", str(resolution), str(resolution), "-r", "average"])

    cmd.extend([str(input_file), str(output_file)])
    run_command(cmd, f"gdal_translate {input_file.name}")


def run_command(cmd: Sequence[str], label: str) -> None:
    logger.info("Running command: %s", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("PROJ_NETWORK", "YES")
    env.setdefault("OSR_USE_ESTIMATED_COORD_OPS", "YES")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        logger.error("%s failed: %s", label, result.stderr.strip())
        raise RuntimeError(f"{label} failed: {result.stderr.strip()}")


def process_dataset(dataset: Dict[str, str], run_tag: str) -> Optional[Dict[str, object]]:
    raw_path = RAW_ROOT / dataset["raw_filename"]
    if not raw_path.exists():
        logger.warning("Skipping %s; raw file missing: %s", dataset["description"], raw_path)
        return None

    output_dir = PROCESSED_ROOT / dataset["key"]
    output_dir.mkdir(parents=True, exist_ok=True)

    produced: List[str] = []
    for config in ZOOM_CONFIGS:
        suffix = config["suffix"]
        output_file = output_dir / build_output_filename(dataset["output_prefix"], suffix, run_tag)

        if output_file.exists():
            logger.info("Skipping existing COG %s", output_file)
            produced.append(str(output_file))
            continue

        logger.info("Creating %s", output_file)
        create_cog(raw_path, output_file, config.get("resolution"))
        produced.append(str(output_file))

    bounds = extract_bounds(raw_path)

    manifest = {
        "key": dataset["key"],
        "description": dataset["description"],
        "raw_filename": dataset["raw_filename"],
        "output_prefix": dataset["output_prefix"],
        "run_tag": run_tag,
        "bounds": bounds,
        "cogs": {
            config["suffix"]: build_output_filename(dataset["output_prefix"], config["suffix"], run_tag)
            for config in ZOOM_CONFIGS
        },
    }

    manifest_path = output_dir / "manifest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
        logger.info("Wrote manifest %s", manifest_path)
    except OSError as exc:
        logger.warning("Failed to write manifest %s: %s", manifest_path, exc)

    logger.info("Completed %s; %d file(s) generated.", dataset["description"], len(produced))
    return manifest


def write_manifest_index(manifests: List[Dict[str, object]], run_tag: str) -> None:
    index = {manifest["key"]: manifest for manifest in manifests}
    manifest_path = PROCESSED_ROOT / f"cems_efas_{run_tag}.json"
    latest_path = PROCESSED_ROOT / "cems_efas_latest.json"

    serialized = json.dumps(index, indent=2)
    try:
        manifest_path.write_text(serialized)
        latest_path.write_text(serialized)
        logger.info("Wrote manifest index %s and updated %s", manifest_path, latest_path)
    except OSError as exc:
        logger.warning(
            "Failed to write manifest index files (%s / %s): %s",
            manifest_path,
            latest_path,
            exc,
        )


def process_all(datasets: List[Dict[str, str]], run_tag: str) -> None:
    manifests: List[Dict[str, object]] = []
    processed_any = False

    for dataset in datasets:
        manifest = process_dataset(dataset, run_tag)
        if manifest:
            processed_any = True
            manifests.append(manifest)

    if processed_any:
        write_manifest_index(manifests, run_tag)
        volume.commit()
        logger.info("Processing complete.")
    else:
        logger.info("No datasets processed.")


def effective_run_tag(run_tag: Optional[str]) -> str:
    return (run_tag or datetime.utcnow().strftime("%Y%m%d")).strip()


@app.function(
    image=gdal_image,
    volumes={"/data": volume},
    timeout=6 * 3600,
    memory=4 * 4096,
)
def process_cems_efas(dataset_keys: Optional[Sequence[str]] = None, run_tag: Optional[str] = None) -> None:
    datasets = select_datasets(dataset_keys)
    tag = effective_run_tag(run_tag)

    logger.info(
        "Processing %d CEMS-EFAS dataset(s) with run tag %s: %s",
        len(datasets),
        tag,
        ", ".join(dataset["description"] for dataset in datasets),
    )

    process_all(datasets, tag)


@app.local_entrypoint()
def main(*args: str) -> None:
    dataset_keys: List[str] = []
    run_tag: Optional[str] = None

    for arg in args:
        if arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        else:
            dataset_keys.append(arg)

    process_cems_efas.remote(dataset_keys or None, run_tag=run_tag)
