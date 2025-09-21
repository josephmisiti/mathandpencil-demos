import os
import logging
import tempfile
import shutil
import json
from datetime import datetime, UTC
from typing import Iterable, List, Dict, Set, Tuple
from collections import defaultdict

import modal


STORAGE_ROOT = "/cache"
TILES_SUBDIR = "tiles"
DEFAULT_OUTPUT_NAME = "NFHL_combined.pmtiles"


storage = modal.Volume.from_name("fema-flood-zone-storage")


def _make_image() -> modal.Image:
    """Return a Modal image with the pmtiles Python package installed."""
    return modal.Image.debian_slim().pip_install("pmtiles==3.4.0")


app = modal.App(
    "fema-pmtiles-combiner",
    image=_make_image(),
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _resolve_inputs(tile_names: Iterable[str]) -> List[str]:
    """Return absolute paths for requested tiles (must exist in the volume)."""
    available_dir = os.path.join(STORAGE_ROOT, TILES_SUBDIR)
    resolved = []
    for name in tile_names:
        candidate = os.path.join(available_dir, name)
        if not os.path.exists(candidate):
            raise FileNotFoundError(f"Missing PMTiles file in volume: {candidate}")
        resolved.append(candidate)
    if not resolved:
        raise ValueError("No PMTiles inputs were provided")
    return resolved


def _group_files_by_fips_and_zoom(filenames: List[str]) -> Dict[str, Dict[str, str]]:
    """Group files by FIPS code and zoom range."""
    grouped = defaultdict(dict)
    
    for filename in filenames:
        # Parse filename: NFHL_<FIPS>_<DATE>[_<ZOOM_RANGE>].pmtiles
        parts = filename.replace('.pmtiles', '').split('_')
        if len(parts) >= 3:
            fips = parts[1]
            if len(parts) == 3:
                # No zoom range specified, assume full range
                zoom_range = "full"
            else:
                zoom_range = parts[3]
            
            grouped[fips][zoom_range] = filename
    
    return grouped


def _get_zoom_priority(zoom_range: str) -> int:
    """Return priority for zoom ranges (lower = higher priority)."""
    if zoom_range == "full":
        return 0
    elif "z18" in zoom_range:
        return 3
    elif "z10_16" in zoom_range:
        return 2
    elif "z0_10" in zoom_range:
        return 1
    else:
        return 4


def _merge_pmtiles_smart(inputs: List[str], output_path: str) -> None:
    """Merge PMTiles archives with smart handling of zoom levels and duplicates."""
    from pmtiles.reader import Reader, MmapSource, traverse
    from pmtiles.reader import zxy_to_tileid, tileid_to_zxy
    from pmtiles.writer import Writer

    if not inputs:
        raise ValueError("No PMTiles files provided for merging")

    logger.info(f"Starting merge of {len(inputs)} files")
    
    # Group files by FIPS and prioritize by zoom range
    filenames = [os.path.basename(f) for f in inputs]
    grouped = _group_files_by_fips_and_zoom(filenames)
    
    # Create processing order: prioritize files with better zoom coverage
    processing_order = []
    for fips, zoom_files in grouped.items():
        # Sort by zoom priority (full range first, then z0_10, z10_16, z18)
        sorted_zooms = sorted(zoom_files.items(), key=lambda x: _get_zoom_priority(x[0]))
        for zoom_range, filename in sorted_zooms:
            full_path = next(f for f in inputs if os.path.basename(f) == filename)
            processing_order.append((fips, zoom_range, full_path))

    logger.info(f"Processing order: {[(fips, zoom) for fips, zoom, _ in processing_order]}")

    metadata_union = None
    vector_layers_map = {}
    bounds = {
        "min_lon_e7": None,
        "min_lat_e7": None,
        "max_lon_e7": None,
        "max_lat_e7": None,
    }

    # Get template from first file
    with open(processing_order[0][2], "rb") as first_file:
        first_reader = Reader(MmapSource(first_file))
        header_template = first_reader.header().copy()
        metadata_union = first_reader.metadata() or {}
        
        for layer in metadata_union.get("vector_layers", []):
            layer_id = layer.get("id", layer.get("name", f"layer-{len(vector_layers_map)}"))
            vector_layers_map[layer_id] = layer
        
        for key in bounds:
            bounds[key] = header_template.get(key)

    # Track which tiles we've seen and their zoom levels
    tile_coverage: Dict[Tuple[int, int, int], str] = {}  # (z, x, y) -> source_file
    tiles_written = 0

    with open(output_path, "wb") as out_file:
        writer = Writer(out_file)

        for fips, zoom_range, src_path in processing_order:
            logger.info(f"Processing {os.path.basename(src_path)} (FIPS: {fips}, Zoom: {zoom_range})")
            
            tiles_from_this_file = 0
            skipped_from_this_file = 0
            
            with open(src_path, "rb") as fh:
                reader = Reader(MmapSource(fh))
                header = reader.header()
                metadata = reader.metadata() or {}

                # Update metadata union
                for layer in metadata.get("vector_layers", []):
                    layer_id = layer.get("id", layer.get("name", f"layer-{len(vector_layers_map)}"))
                    if layer_id not in vector_layers_map:
                        vector_layers_map[layer_id] = layer

                # Update bounds
                for key in bounds:
                    value = header.get(key)
                    if value is None:
                        continue
                    if bounds[key] is None:
                        bounds[key] = value
                    elif "min" in key:
                        bounds[key] = min(bounds[key], value)
                    else:
                        bounds[key] = max(bounds[key], value)

                # Process tiles with smart deduplication
                for (z, x, y), data in traverse(
                    reader.get_bytes,
                    header,
                    header["root_offset"],
                    header["root_length"],
                ):
                    tile_coord = (z, x, y)
                    
                    # Check if we already have this tile
                    if tile_coord in tile_coverage:
                        # Skip if we already have this exact tile
                        # In the future, we could implement more sophisticated merging logic here
                        skipped_from_this_file += 1
                        continue
                    
                    tile_coverage[tile_coord] = os.path.basename(src_path)
                    tile_id = zxy_to_tileid(z, x, y)
                    writer.write_tile(tile_id, data)
                    tiles_from_this_file += 1
                    tiles_written += 1

            logger.info(f"  Added {tiles_from_this_file} tiles, skipped {skipped_from_this_file} duplicates")

        logger.info(f"Total tiles written: {tiles_written}")

        # Finalize header + metadata
        header_template.update({
            "min_lon_e7": bounds["min_lon_e7"],
            "min_lat_e7": bounds["min_lat_e7"],
            "max_lon_e7": bounds["max_lon_e7"],
            "max_lat_e7": bounds["max_lat_e7"],
        })

        # Ensure required header fields
        header_template.setdefault("tile_type", header_template.get("tile_type", 1))
        header_template.setdefault("tile_compression", header_template.get("tile_compression", 2))
        header_template.setdefault("internal_compression", header_template.get("internal_compression", 2))

        metadata_union["vector_layers"] = list(vector_layers_map.values())
        
        # Add some metadata about the merge
        metadata_union.setdefault("name", "FEMA National Flood Hazard Layers (Combined)")
        metadata_union.setdefault("description", "Combined NFHL data from multiple FIPS codes and zoom levels")
        
        writer.finalize(header_template, metadata_union)

    logger.info(f"Merge complete. Final coverage: {len(tile_coverage)} unique tiles")


@app.function(
    timeout=60 * 60 * 4,  # Increased timeout for large merges
    memory=16384,         # Increased memory
    cpu=8,               # More CPU cores
    volumes={STORAGE_ROOT: storage},
)
def combine_pmtiles(
    tile_filenames: List[str] = None,
    output_filename: str = DEFAULT_OUTPUT_NAME,
    dataset_name: str = "FEMA National Flood Hazard Layers",
):
    """Merge several PMTiles archives into a single PMTiles file.

    Args:
        tile_filenames: Specific filenames to merge. If None, merges all .pmtiles files.
        output_filename: Name for the combined PMTiles file.
        dataset_name: Used as the `name` metadata.
    """
    tiles_dir = os.path.join(STORAGE_ROOT, TILES_SUBDIR)
    os.makedirs(tiles_dir, exist_ok=True)

    if tile_filenames is None:
        # Get all pmtiles files, sorted for consistent processing
        tile_filenames = sorted(
            f for f in os.listdir(tiles_dir) 
            if f.lower().endswith(".pmtiles") and f != output_filename
        )

    if not tile_filenames:
        raise ValueError("No PMTiles files found to combine")

    source_tiles = _resolve_inputs(tile_filenames)
    logger.info(f"Merging {len(source_tiles)} PMTiles files into {output_filename}")
    logger.info(f"Input files: {tile_filenames}")

    with tempfile.TemporaryDirectory() as temp_dir:
        combined_pmtiles = os.path.join(temp_dir, "combined.pmtiles")
        _merge_pmtiles_smart(source_tiles, combined_pmtiles)

        target_path = os.path.join(tiles_dir, output_filename)
        logger.info(f"Moving combined archive to {target_path}")
        shutil.move(combined_pmtiles, target_path)

    storage.commit()

    if os.path.exists(target_path):
        size_mb = os.path.getsize(target_path) / (1024 * 1024)
        logger.info(f"Combined PMTiles created ({size_mb:.1f} MB)")
    else:
        raise RuntimeError("Combined PMTiles file was not written to storage")

    metadata = {
        "output": target_path,
        "output_filename": output_filename,
        "source_files": tile_filenames,
        "generated_at": datetime.now(UTC).isoformat(),
        "size_mb": round(size_mb, 1),
    }
    
    logger.info(f"Combination complete: {metadata}")
    return metadata


@app.local_entrypoint()
def main(
    output_filename: str = DEFAULT_OUTPUT_NAME,
    include_files: str = None,  # Comma-separated list of files to include
):
    """Enable local invocation for testing with `modal run`."""
    
    tile_filenames = None
    if include_files:
        tile_filenames = [f.strip() for f in include_files.split(",")]
    
    result = combine_pmtiles.remote(
        tile_filenames=tile_filenames,
        output_filename=output_filename
    )
    print(json.dumps(result, indent=2))