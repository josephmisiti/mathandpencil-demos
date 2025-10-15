import modal
import os
import time
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = modal.App("distance-to-coast-api")

api_secret = modal.Secret.from_name("acord-api-secret")
db_secret = modal.Secret.from_name("supabase-db")

image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "psycopg2-binary",
    "psycopg2-pool",
)

@app.function(
    image=image,
    secrets=[db_secret],
    timeout=30,
    concurrency_limit=100,
    keep_warm=1  # Keep one container warm for faster responses
)
def find_nearest_coastline(lat: float, lng: float, radius_miles: float = 5.0):
    """Find nearest coastline points within radius and return them sorted for display"""
    import psycopg2
    import math

    METERS_PER_MILE = 1609.34
    radius_meters = radius_miles * METERS_PER_MILE

    try:
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.environ["DB_PORT"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=3,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5
        )

        cursor = conn.cursor()

        # Single optimized query - use CTE for efficiency
        if radius_meters > 0:
            query = """
                WITH nearest AS (
                    SELECT
                        id,
                        lat,
                        lng,
                        ST_Distance(
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                            ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
                        ) AS distance_meters
                    FROM public.noaa_coastline
                    ORDER BY ST_SetSRID(ST_MakePoint(lng, lat), 4326) <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                    LIMIT 1
                ),
                radius_points AS (
                    SELECT
                        id,
                        lat,
                        lng,
                        ST_Distance(
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                            ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
                        ) AS distance_meters
                    FROM public.noaa_coastline
                    WHERE ST_DWithin(
                        ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                        %s
                    )
                    ORDER BY ST_SetSRID(ST_MakePoint(lng, lat), 4326) <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                    LIMIT 1000
                )
                SELECT * FROM nearest
                UNION ALL
                SELECT * FROM radius_points;
            """
            cursor.execute(query, (
                lng, lat, lng, lat,  # nearest CTE
                lng, lat, lng, lat, radius_meters, lng, lat  # radius_points CTE
            ))
        else:
            # Just get nearest point
            query = """
                SELECT
                    id,
                    lat,
                    lng,
                    ST_Distance(
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
                    ) AS distance_meters
                FROM public.noaa_coastline
                ORDER BY ST_SetSRID(ST_MakePoint(lng, lat), 4326) <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                LIMIT 1;
            """
            cursor.execute(query, (lng, lat, lng, lat))

        results = cursor.fetchall()

        if not results:
            cursor.close()
            conn.close()
            return {
                "status": "error",
                "message": "No coastline data found in database"
            }

        # First result is always the nearest
        nearest_id, nearest_lat, nearest_lng, nearest_distance = results[0]

        cursor.close()
        conn.close()

        # Always include the nearest point info
        nearest_point_info = {
            "id": nearest_id,
            "lat": nearest_lat,
            "lng": nearest_lng,
            "distance_meters": round(nearest_distance, 2),
            "distance_miles": round(nearest_distance / METERS_PER_MILE, 2)
        }

        # Convert radius results to list of dicts (only lat/lng), skip first (it's the nearest)
        coastline_points = []
        if len(results) > 1:
            for row in results[1:]:
                point_id, point_lat, point_lng, distance_meters = row
                coastline_points.append({
                    "lat": point_lat,
                    "lng": point_lng
                })

        return {
            "status": "success",
            "query_lat": lat,
            "query_lng": lng,
            "radius_miles": radius_miles,
            "distance_to_coast_miles": nearest_point_info["distance_miles"],
            "nearest_point": nearest_point_info,
            "points_found": len(coastline_points),
            "coastline_points": coastline_points
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# Authentication
security = HTTPBearer(auto_error=False)

def verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None, description="Bearer token (alternative to header)")
):
    """Verify the Bearer token from header or query parameter"""
    expected_token = os.environ.get("API_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Server configuration error")

    # Check header first, then query param
    provided_token = None
    if credentials:
        provided_token = credentials.credentials
    elif token:
        provided_token = token

    if not provided_token or provided_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return provided_token


# FastAPI app
web_app = FastAPI(title="Distance to Coast API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://demos.mathandpencil.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@web_app.get("/api/v1/distance_to_coast")
async def distance_to_coast(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: Optional[float] = Query(0, description="Search radius in miles"),
    auth_token: str = Depends(verify_token)
):
    """Find nearest coastline points within radius"""
    try:
        if not (-90 <= lat <= 90):
            raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")

        if not (-180 <= lng <= 180):
            raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")

        if radius < 0 or radius > 100:
            raise HTTPException(status_code=400, detail="Radius must be between 0 and 100 miles")

        result = find_nearest_coastline.remote(lat, lng, radius)

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@web_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "distance-to-coast-api", "timestamp": time.time()}


@app.function(image=image, secrets=[api_secret, db_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8002)
