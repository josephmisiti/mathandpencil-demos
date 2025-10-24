import modal
import os
import logging
import json

GEOJSON_DIR = "/vol/geojson"

storage = modal.Volume.from_name("noaa-shoreline")

db_image = (
    modal.Image.debian_slim()
    .pip_install("psycopg2-binary")
)

app = modal.App(
    "noaa-coastline-seeder",
    image=db_image,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.function(
    secrets=[modal.Secret.from_name("supabase-db")],
    volumes={"/vol": storage},
)
def test_connection():
    import psycopg2

    try:
        logger.info("Attempting to connect to Supabase...")

        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"]
        )

        logger.info("Successfully connected to Supabase!")

        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        logger.info(f"PostgreSQL version: {version[0]}")

        cursor.execute("SELECT COUNT(*) FROM public.noaa_coastline;")
        count = cursor.fetchone()[0]
        logger.info(f"Current rows in noaa_coastline table: {count}")

        cursor.close()
        conn.close()

        return {"status": "success", "row_count": count}

    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return {"status": "failed", "error": str(e)}


@app.function(
    secrets=[modal.Secret.from_name("supabase-db")],
    volumes={"/vol": storage},
    timeout=3600,
    memory=4096,
)
def seed_coastline_file(geojson_filename: str):
    import psycopg2
    import psycopg2.extras

    geojson_path = os.path.join(GEOJSON_DIR, geojson_filename)

    if not os.path.exists(geojson_path):
        logger.error(f"File not found: {geojson_path}")
        return {"status": "failed", "error": "File not found"}

    try:
        logger.info(f"Loading {geojson_filename}...")

        # Check if this file has already been loaded
        logger.info("Connecting to database...")
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"]
        )

        # Set connection to read-only for this check (read-only is fine here)
        conn.set_session(readonly=True, autocommit=True)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM public.noaa_coastline WHERE source = %s", (geojson_filename,))
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            logger.info(f"SKIP: {geojson_filename} already loaded ({existing_count} points)")
            cursor.close()
            conn.close()
            return {
                "status": "skipped",
                "file": geojson_filename,
                "message": f"Already loaded ({existing_count} points)"
            }

        cursor.close()
        conn.close()

        with open(geojson_path, 'r') as f:
            data = json.load(f)

        logger.info(f"Found {len(data['features'])} features")

        points = []
        for feature in data['features']:
            geometry = feature['geometry']
            if geometry['type'] == 'LineString':
                for coord in geometry['coordinates']:
                    lng, lat = coord[0], coord[1]
                    points.append((lat, lng, geojson_filename))

        logger.info(f"Extracted {len(points)} total points")

        if not points:
            return {"status": "skipped", "message": "No points to insert"}

        logger.info("Connecting to database...")
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"]
        )

        # Set connection to read-write mode (needed for transaction pooler)
        conn.set_session(autocommit=False, readonly=False)

        cursor = conn.cursor()

        logger.info(f"Batch inserting {len(points)} points...")
        batch_size = 10000
        inserted = 0

        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            psycopg2.extras.execute_values(
                cursor,
                "INSERT INTO public.noaa_coastline (lat, lng, source) VALUES %s",
                batch,
                page_size=1000
            )
            inserted += len(batch)
            if i % 50000 == 0:
                logger.info(f"Inserted {inserted}/{len(points)} points...")

        conn.commit()
        logger.info(f"Successfully inserted {inserted} points")

        cursor.close()
        conn.close()

        return {
            "status": "success",
            "file": geojson_filename,
            "points_inserted": inserted
        }

    except Exception as e:
        logger.error(f"Error seeding {geojson_filename}: {e}")
        return {"status": "failed", "error": str(e)}


@app.function(volumes={"/vol": storage})
def list_geojson_files():
    """List all GeoJSON files in the volume"""
    if not os.path.exists(GEOJSON_DIR):
        return []

    files = [f for f in os.listdir(GEOJSON_DIR) if f.endswith('.geojson')]
    return sorted(files)


@app.local_entrypoint()
def main(filename: str = None):
    logger.info(f"--- NOAA Coastline Seeder ---")

    if filename:
        # Process single file
        logger.info(f"Processing single file: {filename}")
        result = seed_coastline_file.remote(filename)
        logger.info(f"Result: {result}")

        if result["status"] == "success":
            logger.info(f"Successfully inserted {result['points_inserted']} points")
        elif result["status"] == "skipped":
            logger.info(f"Skipped: {result.get('message', 'Already loaded')}")
        else:
            logger.error(f"Failed: {result.get('error', 'Unknown error')}")
    else:
        # Process all files
        logger.info("Listing all GeoJSON files...")
        files = list_geojson_files.remote()

        if not files:
            logger.error("No GeoJSON files found")
            return

        logger.info(f"Found {len(files)} files to process")

        results = []
        for i, file in enumerate(files, 1):
            logger.info(f"[{i}/{len(files)}] Processing {file}...")
            result = seed_coastline_file.remote(file)
            results.append(result)

            if result["status"] == "success":
                logger.info(f"  ✓ Inserted {result['points_inserted']} points")
            elif result["status"] == "skipped":
                logger.info(f"  ⊘ {result.get('message', 'Skipped')}")
            else:
                logger.error(f"  ✗ {result.get('error', 'Failed')}")

        # Summary
        success_count = sum(1 for r in results if r['status'] == 'success')
        skipped_count = sum(1 for r in results if r['status'] == 'skipped')
        failed_count = sum(1 for r in results if r['status'] == 'failed')

        total_points = sum(r.get('points_inserted', 0) for r in results if r['status'] == 'success')

        logger.info("=" * 60)
        logger.info("SUMMARY")
        logger.info(f"Success: {success_count}, Skipped: {skipped_count}, Failed: {failed_count}")
        logger.info(f"Total points inserted: {total_points:,}")
        logger.info("=" * 60)
