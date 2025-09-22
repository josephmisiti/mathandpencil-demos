"""Combine processed SLOSH COGs into PMTiles archives."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import modal

SLOSH_DATASETS: List[Dict[str, str]] = [
    {
        "key": "american_samoa",
        "description": "American Samoa",
        "zip_name": "American_Samoa_SLOSH_MOM_Inundation_v3.zip",
        "output_prefix": "SLOSH_AMERICAN_SAMOA",
        "processed_subdir": "american_samoa",
    },
    {
        "key": "guam",
        "description": "Guam",
        "zip_name": "Guam_SLOSH_MOM_Inundation_v3.zip",
        "output_prefix": "SLOSH_GUAM",
        "processed_subdir": "guam",
    },
    {
        "key": "hispaniola",
        "description": "Hispaniola",
        "zip_name": "Hispaniola_SLOSH_MOM_Inundation.zip",
        "output_prefix": "SLOSH_HISPANIOLA",
        "processed_subdir": "hispaniola",
    },
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
    {
        "key": "usvi",
        "description": "U.S. Virgin Islands",
        "zip_name": "USVI_SLOSH_MOM_Inundation.zip",
        "output_prefix": "SLOSH_USVI",
        "processed_subdir": "usvi",
    },
    {
        "key": "yucatan",
        "description": "Yucatán Peninsula",
        "zip_name": "Yucatan_SLOSH_MOM_Inundation_v3.zip",
        "output_prefix": "SLOSH_YUCATAN",
        "processed_subdir": "yucatan",
    },
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


def select_datasets(keys: Optional[Sequence[str]]) -> List[Dict[str, str]]:
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


STORAGE_ROOT = Path("/cache")
PROCESSED_ROOT = STORAGE_ROOT / "processed"
OUTPUT_ROOT = STORAGE_ROOT / "outputs"


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


volume = modal.Volume.from_name("national-hurricane-center-slosh")

geo_image = (
    modal.Image.debian_slim()
    .apt_install("gdal-bin", "python3-gdal", "curl", "unzip", "wget")
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


def build_output_filename(prefix: str, category: str, suffix: str, run_tag: str) -> str:
    sanitized_tag = run_tag.replace(" ", "_")
    return f"{prefix}_{category}_{suffix}_{sanitized_tag}.cog.tif"


def resolve_latest_cog(
    processed_dir: Path,
    prefix: str,
    category: str,
    run_tag: Optional[str],
) -> Optional[Path]:
    if run_tag:
        tagged = processed_dir / build_output_filename(prefix, category, "z16_20", run_tag)
        if tagged.exists():
            return tagged
        logger.warning(
            "COG with run tag %s not found for %s %s; falling back to latest available.",
            run_tag,
            prefix,
            category,
        )

    pattern = f"{prefix}_{category}_z16_20*.cog.tif"
    candidates = sorted(processed_dir.glob(pattern))
    if not candidates:
        return None

    # Choose the most recent by name (YYYYMMDD suffix) then by modification time.
    return max(candidates, key=lambda path: (path.name, path.stat().st_mtime))


@app.function(
    volumes={str(STORAGE_ROOT): volume},
    timeout=3600,
    memory=4096,
)
def combine_categories(
    dataset_keys: Optional[Sequence[str]] = None,
    run_tag: Optional[str] = None,
) -> None:
    """Convert high-resolution category COGs into PMTiles for one or more datasets."""

    try:
        datasets = select_datasets(dataset_keys)
    except KeyError as exc:
        logger.error("%s", exc)
        raise

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    produced_any = False

    logger.info(
        "Combining %d dataset(s)%s",
        len(datasets),
        f" with run tag {run_tag}" if run_tag else "",
    )

    for dataset in datasets:
        produced_any |= combine_dataset(dataset, run_tag=run_tag)

    if produced_any:
        volume.commit()
        logger.info("Finished writing PMTiles to %s", OUTPUT_ROOT)
    else:
        logger.info("No PMTiles were generated.")


def combine_dataset(dataset: dict, run_tag: Optional[str]) -> bool:
    """Build PMTiles for every available category in ``dataset``."""

    processed_dir = PROCESSED_ROOT / dataset["processed_subdir"]
    if not processed_dir.exists():
        logger.warning(
            "Processed directory missing for %s: %s",
            dataset["description"],
            processed_dir,
        )
        return False

    dataset_output_dir = OUTPUT_ROOT / dataset["key"]
    dataset_output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Combining categories for %s into %s",
        dataset["description"],
        dataset_output_dir,
    )

    produced = False

    for category in SLOSH_CATEGORY_NAMES:
        source = resolve_latest_cog(
            processed_dir,
            dataset["output_prefix"],
            category,
            run_tag,
        )
        if source is None:
            logger.warning(
                "Skipping %s category %s; no COG files found.",
                dataset["description"],
                category,
            )
            continue

        destination = dataset_output_dir / f"{dataset['output_prefix']}_{category}.pmtiles"
        logger.info("Creating %s from %s", destination, source)

        convert_cog_to_pmtiles(source, destination)
        produced = True

    if not produced:
        logger.warning("No categories converted for %s", dataset["description"])

    return produced


def convert_cog_to_pmtiles(source: Path, destination: Path) -> None:
    """Reproject a COG to WebMercator and convert it into PMTiles."""

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        warped = tmp_dir_path / f"{destination.stem}_3857.tif"
        mbtiles = tmp_dir_path / f"{destination.stem}.mbtiles"
        pmtiles = tmp_dir_path / destination.name

        run_command(
            [
                "gdalwarp",
                "-t_srs",
                "EPSG:3857",
                "-r",
                "bilinear",
                "-of",
                "COG",
                "-co",
                "COMPRESS=LZW",
                "-co",
                "PREDICTOR=2",
                str(source),
                str(warped),
            ],
            "gdalwarp",
        )

        run_command(
            [
                "gdal_translate",
                "-of",
                "MBTILES",
                "-co",
                "TILE_FORMAT=PNG",
                str(warped),
                str(mbtiles),
            ],
            "gdal_translate",
        )

        run_command(
            [
                "gdaladdo",
                "-r",
                "average",
                str(mbtiles),
                "2",
                "4",
                "8",
                "16",
                "32",
                "64",
            ],
            "gdaladdo",
        )

        run_command(["pmtiles", "convert", str(mbtiles), str(pmtiles)], "pmtiles convert")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pmtiles, destination)


def run_command(command: Sequence[str], label: str) -> None:
    """Execute a shell command and raise if it fails."""

    logger.info("Running command (%s): %s", label, " ".join(command))
    env = os.environ.copy()
    env.setdefault("PROJ_NETWORK", "YES")
    env.setdefault("OSR_USE_ESTIMATED_COORD_OPS", "YES")
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        logger.error("%s failed: %s", label, result.stderr.strip())
        raise RuntimeError(f"{label} failed: {result.stderr.strip()}")


@app.local_entrypoint()
def main(*args: str) -> None:
    run_tag: Optional[str] = None
    dataset_keys: List[str] = []

    for arg in args:
        if arg.startswith("run_tag="):
            run_tag = arg.split("=", 1)[1]
        else:
            dataset_keys.append(arg)

    keys_arg: Optional[List[str]] = dataset_keys if dataset_keys else None

    combine_categories.remote(keys_arg, run_tag=run_tag)
