import modal
import os
import base64
import time
import json
from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = modal.App("eagleview-token-api")

api_secret = modal.Secret.from_name("acord-api-secret")
eagleview_secret = modal.Secret.from_name("eagleview-api-secret")

image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "pydantic",
    "requests"
)

@app.function(
    image=image,
    secrets=[eagleview_secret],
    timeout=30
)
def get_eagleview_token() -> dict:
    """Get EagleView OAuth token using client credentials"""
    import requests

    print("[EAGLEVIEW] Starting token request...")

    client_id = os.environ.get('EAGLEVIEW_CLIENT_ID')
    client_secret = os.environ.get('EAGLEVIEW_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("[EAGLEVIEW] ERROR: Missing client credentials")
        return {"error": "EagleView credentials not configured"}

    try:
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        url = "https://apicenter.eagleview.com/oauth2/v1/token"
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "client_credentials"
        }

        print(f"[EAGLEVIEW] Requesting token from {url}")

        response = requests.post(url, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        print(f"[EAGLEVIEW] Token received successfully, expires in {token_data.get('expires_in')} seconds")

        return token_data

    except requests.exceptions.RequestException as e:
        print(f"[EAGLEVIEW] Token request failed: {str(e)}")
        return {"error": f"Token request failed: {str(e)}"}
    except Exception as e:
        print(f"[EAGLEVIEW] Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@app.function(
    image=image,
    secrets=[eagleview_secret],
    timeout=30
)
def fetch_eagleview_tile(urn: str, z: int, x: int, y: int) -> dict:
    """Fetch a tile image from EagleView"""
    import requests
    from urllib.parse import quote

    print(f"[EAGLEVIEW] Fetching tile for URN: {urn}, z={z}, x={x}, y={y}")

    token_result = get_eagleview_token.local()
    if "error" in token_result:
        print(f"[EAGLEVIEW] Token error: {token_result['error']}")
        return {"error": token_result["error"]}

    access_token = token_result.get("access_token")
    if not access_token:
        print("[EAGLEVIEW] No access token in response")
        return {"error": "Failed to get access token"}

    try:
        encoded_urn = quote(urn, safe='')
        url = f"https://sandbox.apis.eagleview.com/imagery/v3/images/{encoded_urn}/tiles/{z}/{x}/{y}"

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        params = {
            "format": "IMAGE_FORMAT_PNG"
        }

        print(f"[EAGLEVIEW] Calling tile API at {url}")

        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            print(f"[EAGLEVIEW] Tile API error: {response.text}")
            return {"error": f"Tile request failed with status {response.status_code}"}

        response.raise_for_status()

        print(f"[EAGLEVIEW] Tile fetched successfully, size: {len(response.content)} bytes")

        content_b64 = base64.b64encode(response.content).decode('utf-8')

        return {
            "content": content_b64,
            "content_type": response.headers.get("Content-Type", "image/png")
        }

    except requests.exceptions.RequestException as e:
        print(f"[EAGLEVIEW] Tile request failed: {str(e)}")
        return {"error": f"Tile request failed: {str(e)}"}
    except Exception as e:
        print(f"[EAGLEVIEW] Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

@app.function(
    image=image,
    secrets=[eagleview_secret],
    timeout=30
)
def discover_eagleview_images(lat: float, lng: float) -> dict:
    """Discover EagleView images for a location"""
    import requests

    print(f"[EAGLEVIEW] Starting discovery for location ({lat}, {lng})...")

    token_result = get_eagleview_token.local()
    if "error" in token_result:
        print(f"[EAGLEVIEW] Token error: {token_result['error']}")
        return {"error": token_result["error"]}

    access_token = token_result.get("access_token")
    if not access_token:
        print("[EAGLEVIEW] No access token in response")
        return {"error": "Failed to get access token"}

    buffer = 0.0001
    min_lng = lng - buffer
    max_lng = lng + buffer
    min_lat = lat - buffer
    max_lat = lat + buffer

    geojson_obj = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat]
            ]]
        },
        "properties": None
    }

    payload = {
        "polygon": {
            "geojson": {
                "value": json.dumps(geojson_obj),
                "epsg": "EPSG:4326"
            }
        },
        "view": {
            "obliques": {
                "cardinals": {
                    "north": True,
                    "east": True,
                    "south": True,
                    "west": True
                }
            },
            "orthos": {},
            "max_images_per_view": 1
        },
        "response_props": {
            "first_published_time": True,
            "composite": True,
            "shot_time": True,
            "calculated_gsd": True,
            "zoom_range": True,
            "ground_footprint": True,
            "look_at": True,
            "image_resources": {
                "tilebox": True,
                "estimated_requested_location": True
            }
        }
    }

    try:
        url = "https://sandbox.apis.eagleview.com/imagery/v3/discovery/rank/location"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        print(f"[EAGLEVIEW] Calling discovery API at {url}")

        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            print(f"[EAGLEVIEW] Discovery API error: {response.text}")

        response.raise_for_status()

        discovery_data = response.json()
        print(f"[EAGLEVIEW] Discovery successful, found {len(discovery_data.get('captures', []))} captures")

        return discovery_data

    except requests.exceptions.RequestException as e:
        print(f"[EAGLEVIEW] Discovery request failed: {str(e)}")
        return {"error": f"Discovery request failed: {str(e)}"}
    except Exception as e:
        print(f"[EAGLEVIEW] Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

class DiscoveryRequest(BaseModel):
    lat: float
    lng: float

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the Bearer token"""
    expected_token = os.environ.get("API_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Server configuration error")

    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return credentials.credentials

web_app = FastAPI(title="EagleView Token API", version="1.0.0")

web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"]
)

@web_app.get("/api/v1/eagleview/token")
async def get_token(token: str = Depends(verify_token)):
    """Get EagleView OAuth token"""
    try:
        print("[API] Received token request")

        result = get_eagleview_token.remote()

        print(f"[API] Token result: {result}")

        if "error" in result:
            print(f"[API] Returning error result")
            return JSONResponse(content=result, status_code=500)

        print("[API] Returning success result")
        return JSONResponse(content=result)

    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        print(f"[API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Token request failed: {str(e)}")

@web_app.post("/api/v1/eagleview/discovery")
async def discovery(request: DiscoveryRequest, token: str = Depends(verify_token)):
    """Discover EagleView images for a location (proxy to avoid CORS)"""
    try:
        print(f"[API] Received discovery request for ({request.lat}, {request.lng})")

        result = discover_eagleview_images.remote(request.lat, request.lng)

        print(f"[API] Discovery result: {len(str(result))} chars")

        if "error" in result:
            print(f"[API] Returning error result")
            return JSONResponse(content=result, status_code=500)

        print("[API] Returning success result")
        return JSONResponse(content=result)

    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        print(f"[API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Discovery request failed: {str(e)}")

@web_app.get("/api/v1/eagleview/tiles/{urn:path}/{z}/{x}/{y}")
async def tile_proxy(urn: str, z: int, x: int, y: int, token: str = Depends(verify_token)):
    """Fetch EagleView tile image (proxy to avoid CORS)"""
    import requests
    from urllib.parse import quote

    try:
        print(f"[API] Received tile request for URN: {urn}, z={z}, x={x}, y={y}")

        token_result = get_eagleview_token.remote()
        if "error" in token_result:
            return JSONResponse(content=token_result, status_code=500)

        access_token = token_result.get("access_token")
        if not access_token:
            return JSONResponse(content={"error": "Failed to get access token"}, status_code=500)

        encoded_urn = quote(urn, safe='')
        url = f"https://sandbox.apis.eagleview.com/imagery/v3/images/{encoded_urn}/tiles/{z}/{x}/{y}"

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        params = {
            "format": "IMAGE_FORMAT_PNG"
        }

        print(f"[API] Proxying tile request to {url}")

        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 404:
            print(f"[API] Tile not found (404)")
            raise HTTPException(status_code=404, detail="Tile not found")

        response.raise_for_status()

        print(f"[API] Returning tile image, size: {len(response.content)} bytes")

        return Response(
            content=response.content,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400"
            }
        )

    except HTTPException:
        raise
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500
        print(f"[API] Tile request failed with status {status_code}: {str(e)}")
        raise HTTPException(status_code=status_code, detail=f"Tile request failed: {str(e)}")
    except Exception as e:
        print(f"[API] EXCEPTION: {str(e)}")
        import traceback
        print(f"[API] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Tile request failed: {str(e)}")

@web_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "eagleview-token-api", "timestamp": time.time()}

@app.function(image=image, secrets=[api_secret])
@modal.asgi_app()
def fastapi_app():
    return web_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8002)
