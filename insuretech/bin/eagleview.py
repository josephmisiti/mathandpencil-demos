import os
import base64
import requests
import json
from urllib.parse import quote

def get_eagleview_token():
    """Get EagleView OAuth token using client credentials"""

    client_id = os.environ.get('EAGLEVIEW_CLIENT_ID')
    client_secret = os.environ.get('EAGLEVIEW_CLIENT_SECRET')

    if not client_id or not client_secret:
        raise ValueError("EAGLEVIEW_CLIENT_ID and EAGLEVIEW_CLIENT_SECRET environment variables are required")

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

    print(f"Requesting token from {url}...")

    response = requests.post(url, headers=headers, data=data, timeout=10)
    response.raise_for_status()

    token_data = response.json()

    print(f"✓ Token received successfully")
    print(f"  Token Type: {token_data.get('token_type')}")
    print(f"  Expires In: {token_data.get('expires_in')} seconds")
    print(f"  Access Token: {token_data.get('access_token')[:50]}...")

    return token_data

def discover_images(access_token, lat, lng):
    """Discover available images for a location"""

    url = "https://sandbox.apis.eagleview.com/imagery/v3/discovery/rank/location"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

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

    print(f"\nDiscovering images for location ({lat}, {lng})...")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code != 200:
        print(f"Error response: {response.text}")

    response.raise_for_status()

    data = response.json()
    print(f"✓ Found {len(data.get('captures', []))} captures")

    return data

def fetch_image_tile(access_token, image_urn, z, x, y, output_path):
    """Fetch a specific image tile"""

    encoded_urn = quote(image_urn, safe='')
    url = f"https://sandbox.apis.eagleview.com/imagery/v3/images/{encoded_urn}/tiles/{z}/{x}/{y}"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    params = {
        "format": "IMAGE_FORMAT_PNG"
    }

    print(f"\nFetching tile for URN: {image_urn}, z={z}, x={x}, y={y}...")

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        print(f"Error response: {response.text}")

    response.raise_for_status()

    with open(output_path, 'wb') as f:
        f.write(response.content)

    print(f"✓ Tile saved to {output_path}")
    return output_path

if __name__ == "__main__":
    try:
        lat = 41.250214
        lng = -95.991634

        # http://localhost:5173/?lat=1.250214&lng=-95.991634&zoom=22

        token_data = get_eagleview_token()
        access_token = token_data['access_token']

        discovery_data = discover_images(access_token, lat, lng)

        print("\n" + "="*50)
        print("Discovery Results:")
        print(json.dumps(discovery_data, indent=2))
        print("="*50)

        if discovery_data.get('captures'):
            first_capture = discovery_data['captures'][0]

            print("\n" + "="*50)
            print("Downloading Images")
            print("="*50)

            orthos = first_capture.get('orthos', {})
            if orthos and orthos.get('images'):
                ortho_image = orthos['images'][0]
                image_urn = ortho_image.get('urn')
                tilebox = ortho_image.get('resources', {}).get('tilebox', {})

                if image_urn and tilebox:
                    z = tilebox.get('z', 22)
                    x = tilebox.get('left', 0)
                    y = tilebox.get('top', 0)

                    print(f"\n📸 Ortho Image:")
                    fetch_image_tile(access_token, image_urn, z, x, y, f"ortho_z{z}_x{x}_y{y}.png")

            obliques = first_capture.get('obliques', {})
            for direction in ['north', 'east', 'south', 'west']:
                direction_data = obliques.get(direction, {})
                if direction_data and direction_data.get('images'):
                    oblique_image = direction_data['images'][0]
                    image_urn = oblique_image.get('urn')
                    tilebox = oblique_image.get('resources', {}).get('tilebox', {})

                    if image_urn and tilebox:
                        z = tilebox.get('z', 18)
                        x = tilebox.get('left', 0)
                        y = tilebox.get('top', 0)

                        print(f"\n📸 Oblique {direction.capitalize()} Image:")
                        fetch_image_tile(access_token, image_urn, z, x, y, f"oblique_{direction}_z{z}_x{x}_y{y}.png")

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)
